"""Strategy 0083 — FX Carry (G10) with vol/crash filter.

Idea I0020 from the `D:\\Backtest Ideas` handoff (#s11; Quantpedia FX-Carry,
Menkhoff/Sarno). Long high-rate / short low-rate currencies earns the forward-
premium risk premium; crash risk (negative skew) is damped by an FX-vol filter.
A different asset class than the dead commodity carry (0048).

Exact rule (#s11 deepread): 10-ish currencies, long top-3 / short bottom-3 by
policy/short rate, monthly rebalance, USD funding. Total carry return = spot
return (in USD terms) + interest accrual (rate/12).

Currencies (vs USD): EUR JPY GBP AUD CAD CHF NZD SEK NOK. Rates = FRED OECD 3-month
interbank (monthly, 2003-2026). FX spot = yfinance (built as XXX/USD return).

Tests: dollar-neutral L/S Sharpe, permutation (shuffle rate ranks monthly),
bootstrap monthly-return CI, IS/OOS, and a global-FX-vol risk-off filter.

Run:
    .venv/Scripts/python.exe strategies/0083_fx_carry/run.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.data import get_prices  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(12)  # monthly returns
rng = np.random.default_rng(20)

# currency -> (yfinance symbol, invert?) ; invert=True means symbol is USD/XXX
FX = {"EUR": ("EURUSD=X", False), "GBP": ("GBPUSD=X", False), "AUD": ("AUDUSD=X", False),
      "NZD": ("NZDUSD=X", False), "JPY": ("USDJPY=X", True), "CHF": ("USDCHF=X", True),
      "CAD": ("USDCAD=X", True), "SEK": ("USDSEK=X", True), "NOK": ("USDNOK=X", True)}
RATE_ID = {"EUR": "IR3TIB01EZM156N", "JPY": "IR3TIB01JPM156N", "GBP": "IR3TIB01GBM156N",
           "AUD": "IR3TIB01AUM156N", "CAD": "IR3TIB01CAM156N", "CHF": "IR3TIB01CHM156N",
           "NZD": "IR3TIB01NZM156N", "SEK": "IR3TIB01SEM156N", "NOK": "IR3TIB01NOM156N"}


def fred(series_id: str) -> pd.Series:
    cache = RESULTS / f"rate_{series_id}.json"
    if cache.exists():
        d = json.loads(cache.read_text())
    else:
        key = (ROOT / ".fred.key").read_text().strip()
        url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}"
               f"&api_key={key}&file_type=json&observation_start=2003-01-01")
        d = json.load(urllib.request.urlopen(url, timeout=30))
        cache.write_text(json.dumps(d))
    obs = d["observations"]
    s = pd.Series({pd.Timestamp(o["date"]): float(o["value"]) for o in obs if o["value"] != "."})
    return s.sort_index()


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def main() -> None:
    out: dict = {"idea_id": "I0020"}

    # monthly XXX/USD spot levels -> monthly returns
    spot = {}
    for cc, (sym, inv) in FX.items():
        px = get_prices(sym, start="2003-01-01")["Close"]
        m = px.resample("ME").last()
        if inv:
            m = 1.0 / m
        spot[cc] = m
    spot = pd.DataFrame(spot)
    fx_ret = spot.pct_change()

    rates = pd.DataFrame({cc: fred(RATE_ID[cc]) for cc in FX}).reindex(spot.index, method="ffill")
    print(f"FX carry panel: {fx_ret.shape[1]} currencies, {fx_ret.index.min().date()}..{fx_ret.index.max().date()}")

    # total carry return per currency next month = spot_ret + accrued rate/12 (decision-time rate)
    carry_ret = fx_ret + rates.shift(1) / 100.0 / 12.0

    # monthly: rank by decision-time rate, long top-3 / short bottom-3
    def ls_returns(rank_src: pd.DataFrame, k: int = 3) -> pd.Series:
        out_r = {}
        for dt in fx_ret.index[1:]:
            r = rank_src.shift(1).loc[dt].dropna()
            avail = r.index.intersection(carry_ret.loc[dt].dropna().index)
            r = r[avail]
            if len(r) < 2 * k:
                continue
            longs = r.nlargest(k).index
            shorts = r.nsmallest(k).index
            out_r[dt] = carry_ret.loc[dt, longs].mean() - carry_ret.loc[dt, shorts].mean()
        return pd.Series(out_r)

    ls = ls_returns(rates)
    # cost: ~2 legs turnover/month, FX ETF/spot ~2 bps/side -> ~ a few bps/month; small
    ls_net = ls - 0.0008  # ~8 bps/month round-trip drag (conservative)
    m_sharpe = net_sharpe(ls_net)
    cagr = (1 + ls_net).prod() ** (12 / len(ls_net)) - 1
    maxdd = ((1 + ls_net).cumprod() / (1 + ls_net).cumprod().cummax() - 1).min()
    skew = float(ls_net.skew())

    # permutation: shuffle the rate ranking across currencies each month
    obs = m_sharpe
    null = np.empty(800)
    for i in range(len(null)):
        # shuffle the rate values across currencies within each month (kills rank info)
        arr = rates.values.copy()
        for j in range(arr.shape[0]):
            arr[j] = rng.permutation(arr[j])
        shuf = pd.DataFrame(arr, index=rates.index, columns=rates.columns)
        null[i] = net_sharpe(ls_returns(shuf) - 0.0008)
    p_perm = float((null >= obs).mean())

    boot = np.array([rng.choice(ls_net.dropna().values, len(ls_net.dropna())).mean() for _ in range(5000)])
    ci = (float(np.percentile(boot, 2.5) * 100), float(np.percentile(boot, 97.5) * 100))

    print(f"\n=== FX carry L/S (long top-3 / short bottom-3 by 3m rate) ===")
    print(f"  Sharpe {m_sharpe:+.2f}, CAGR {cagr*100:+.1f}%, MaxDD {maxdd*100:.0f}%, skew {skew:+.2f}")
    print(f"  permutation p={p_perm:.3f}, monthly-return 95% CI [{ci[0]:+.3f}%, {ci[1]:+.3f}%]")
    out["ls_carry"] = {"sharpe": m_sharpe, "cagr_pct": float(cagr*100), "maxdd_pct": float(maxdd*100),
                       "skew": skew, "perm_p": p_perm, "monthly_ci_pct": list(ci), "n_months": int(len(ls_net))}

    # vol filter: risk-off when global FX vol (rolling std of basket) is high -> flat
    gvol = ls.rolling(6).std()
    on = (gvol <= gvol.median()).shift(1).fillna(True)
    ls_vf = (ls_net * on).dropna()
    out["vol_filtered"] = {"sharpe": net_sharpe(ls_vf), "maxdd_pct": float(((1+ls_vf).cumprod()/(1+ls_vf).cumprod().cummax()-1).min()*100)}
    print(f"  vol-filtered: Sharpe {net_sharpe(ls_vf):+.2f}, MaxDD {out['vol_filtered']['maxdd_pct']:.0f}%")

    # IS/OOS
    out["is_oos"] = {nm: net_sharpe(ls_net[msk]) for nm, msk in
                     [("IS 2004-2014", ls_net.index < "2015-01-01"), ("OOS 2015-2026", ls_net.index >= "2015-01-01")]}
    print(f"  IS/OOS: IS {out['is_oos']['IS 2004-2014']:+.2f} / OOS {out['is_oos']['OOS 2015-2026']:+.2f}")

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    ax[0].plot((1 + ls_net).cumprod(), label="carry L/S (net)")
    ax[0].plot((1 + ls_vf).cumprod(), label="vol-filtered", alpha=0.8)
    ax[0].set_yscale("log"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3, which="both")
    ax[0].set_title("G10 FX carry L/S equity")
    ax[1].hist(ls_net.dropna()*100, bins=30, color="slateblue", edgecolor="k")
    ax[1].axvline(0, color="k", lw=0.8); ax[1].set_xlabel("monthly return %")
    ax[1].set_title(f"Return dist (skew {skew:+.2f} = crash risk?)"); ax[1].grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(RESULTS / "fx_carry.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    passes = (p_perm < 0.05 and ci[0] > 0 and m_sharpe > 0 and out["is_oos"]["OOS 2015-2026"] > 0)
    print("\nVerdict:", "LEAD/testing — carry premium survives." if passes
          else "see REPORT — carry premium weak/insignificant.")


if __name__ == "__main__":
    main()
