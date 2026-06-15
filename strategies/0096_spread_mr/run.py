"""Strategy 0096 — Structural RV Mean-Reversion: Brent/WTI (I0060), Inter-Grain
ratios (I0061), and re-test of the 0081 calendar spreads as z-score MR (I0063).

Batch-2 ideas from `D:\\Backtest Ideas` (#s22 Brent/WTI + grain substitution;
#s19 re-test 0081). All three replicate the LIVING 0087 wheat-CHI/KC RV pattern:
a cointegrated anchor + z-score return, NOT directional season (the dead 0081
frame). Discipline (idea requirement): ADF cointegration gate + half-life.

  I0060 Brent/WTI:  level spread BZ - CL ($), transport/quality-arbitrage band.
  I0061 grain ratio: log(ZC/ZW) corn/wheat, log(ZS/ZC) soy/corn substitution band.
  I0063 0081 spreads: front-pair price spread (ZC N/Z, NG H/J, RB N/X) as z-MR
                      instead of directional season; data already cached (~$32).

Engine: rolling z-score (window 60), enter |z|>2 (MR against deviation), exit
z->0, stop |z|>3.5. P&L = position * d(spread), cost per leg modeled. Battery:
ADF on the spread, half-life, permutation vs random entry timing, IS/OOS.

Free data: yfinance (BZ=F/CL=F/ZC=F/ZW=F/ZS=F); cached Databento chains for I0063.

Run: .venv/Scripts/python.exe strategies/0096_spread_mr/run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.tsa.stattools import adfuller  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.data import get_prices  # noqa: E402
from quantlab.futures_chain import outright_closes  # noqa: E402
from quantlab.significance import permutation_test  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)
MONTHS = "FGHJKMNQUVXZ"
MONTH_NUM = {c: i + 1 for i, c in enumerate(MONTHS)}


def ns(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def half_life(spread: pd.Series) -> float:
    s = spread.dropna()
    lag = s.shift(1).dropna()
    s = s.loc[lag.index]
    b = np.polyfit(lag.values, (s - lag).values, 1)[0]
    return float(-np.log(2) / np.log(1 + b)) if -1 < b < 0 else float("nan")


def zscore_mr(spread: pd.Series, win=60, z_in=2.0, z_out=0.0, z_stop=3.5,
              cost_per_change=0.0, scale=1.0) -> dict:
    """MR on a LEVEL spread. Position +1 = long spread (profit when spread rises).
    Enter against deviation: z>z_in -> spread rich -> SHORT (pos=-1); z<-z_in -> LONG.
    P&L = pos * d(spread) / scale (scale ~ spread vol, to normalise to returns)."""
    spread = spread.dropna()
    mu = spread.rolling(win).mean()
    sd = spread.rolling(win).std()
    z = ((spread - mu) / sd).dropna()
    dspread = spread.diff().reindex(z.index).fillna(0.0)
    pos = pd.Series(0.0, index=z.index)
    state = 0
    for i, zz in enumerate(z.values):
        if state == 0:
            if zz > z_in:
                state = -1   # rich -> short spread
            elif zz < -z_in:
                state = 1    # cheap -> long spread
        elif state == 1:
            if zz >= -z_out or zz < -z_stop:
                state = 0
        elif state == -1:
            if zz <= z_out or zz > z_stop:
                state = 0
        pos.iloc[i] = state
    held = pos.shift(1).fillna(0.0)
    pnl = held * dspread / scale
    cost = pos.diff().abs().fillna(pos.abs()) * cost_per_change / scale
    net = pnl - cost
    ar = dspread / scale
    perm = permutation_test(pnl, ar, held, n_perm=4000, metric="sharpe") if held.abs().sum() > 5 else {"p_value": np.nan}
    adf_p = adfuller(spread.dropna().values, maxlag=20, autolag="AIC")[1]
    cut = "2015-01-01"
    n_entries = int(((pos.diff() != 0) & (pos != 0)).sum())
    return {
        "adf_p": float(adf_p), "half_life_d": half_life(spread),
        "n_obs": int(len(z)), "frac_active": float((held != 0).mean()),
        "n_entries": n_entries,
        "gross_sharpe": ns(pnl), "net_sharpe": ns(net), "perm_p": perm["p_value"],
        "is_sharpe": ns(net[net.index < cut]), "oos_sharpe": ns(net[net.index >= cut]),
        "_net": net, "_spread": spread, "_z": z, "_pnl": pnl, "_held": held, "_ar": ar,
    }


def pair_segments(root: str, long_mc: str, short_mc: str) -> list[pd.Series]:
    """ROLL-CLEAN per-year calendar-spread LEVEL segments (price_long - price_short
    for a SINGLE contract year, held only until the long leg's delivery month). Each
    segment is one cointegrated pair; the MR runs WITHIN a segment so no cross-roll
    diff/hold can ever fabricate reversion (mandatory roll-check, lesson 0028/0029/0048).
    Only the last ~9 months before expiry are kept (where the pair is liquid)."""
    closes = outright_closes(root)
    years = sorted({y for (_, y) in closes})
    segs = []
    for y in years:
        lk, sk = (long_mc, y), (short_mc, y)
        if lk in closes and sk in closes:
            sp = (closes[lk] - closes[sk]).dropna()
            exp = pd.Timestamp(year=y, month=MONTH_NUM[long_mc], day=1)
            sp = sp[(sp.index < exp) & (sp.index >= exp - pd.Timedelta(days=300))]
            if len(sp) > 80:
                segs.append(sp.rename(y))
    return segs


def zscore_mr_segments(segs: list[pd.Series], scale: float, **kw) -> dict:
    """Run zscore_mr independently on each roll-clean segment, then pool net/gross/
    held/ar (flat between segments) for one honest permutation + aggregate metrics."""
    nets, pnls, helds, ars, adf_ps, hls = [], [], [], [], [], []
    n_entries = 0
    for sp in segs:
        r = zscore_mr(sp, scale=scale, **kw)
        nets.append(r["_net"]); pnls.append(r["_pnl"]); helds.append(r["_held"]); ars.append(r["_ar"])
        adf_ps.append(r["adf_p"]); hls.append(r["half_life_d"]); n_entries += r["n_entries"]
    net = pd.concat(nets).sort_index()
    pnl = pd.concat(pnls).sort_index()
    held = pd.concat(helds).sort_index()
    ar = pd.concat(ars).sort_index()
    cut = "2015-01-01"
    perm = permutation_test(pnl, ar, held, n_perm=4000, metric="sharpe") if held.abs().sum() > 5 else {"p_value": np.nan}
    return {"adf_p": float(np.median(adf_ps)), "half_life_d": float(np.nanmedian(hls)),
            "n_obs": int(len(net)), "frac_active": float((held != 0).mean()), "n_entries": n_entries,
            "gross_sharpe": ns(pnl), "net_sharpe": ns(net), "perm_p": perm["p_value"],
            "is_sharpe": ns(net[net.index < cut]), "oos_sharpe": ns(net[net.index >= cut]),
            "n_segments": len(segs), "_net": net, "_spread": pd.concat(segs).sort_index(),
            "_z": pd.Series(dtype=float)}


def report_row(name, r, extra=""):
    print(f"{name:26s} ADF p={r['adf_p']:.3f} HL={r['half_life_d']:5.1f}d  "
          f"gSh {r['gross_sharpe']:+.2f} netSh {r['net_sharpe']:+.2f} "
          f"perm p={r['perm_p']:.3f}  IS/OOS {r['is_sharpe']:+.2f}/{r['oos_sharpe']:+.2f} "
          f"act {r['frac_active']:.0%} n={r['n_entries']} {extra}")


def main() -> None:
    out = {"idea_ids": ["I0060", "I0061", "I0063"]}
    results_for_plot = {}

    # ---------- I0060 Brent/WTI ----------
    print("=== I0060 Brent/WTI spread MR ===")
    bz = get_prices("BZ=F", start="2007-01-01")["Close"]
    cl = get_prices("CL=F", start="2007-01-01")["Close"]
    common = bz.index.intersection(cl.index)
    spread = (bz.reindex(common) - cl.reindex(common)).dropna()
    sc = spread.diff().std()  # normalise daily $ change to ~unit vol
    # crude cost: 2 legs * ~1 tick ($0.01-0.02) per RT on the $ spread
    r60 = zscore_mr(spread, cost_per_change=0.04, scale=sc)
    out["I0060_brent_wti"] = {k: v for k, v in r60.items() if not k.startswith("_")}
    results_for_plot["Brent/WTI"] = r60
    report_row("Brent-WTI ($spread)", r60)

    # ---------- I0061 inter-grain ratios ----------
    print("\n=== I0061 inter-grain substitution ratios MR ===")
    grains = {}
    for tk in ("ZC=F", "ZW=F", "ZS=F"):
        grains[tk] = get_prices(tk, start="2005-01-01")["Close"]
    out["I0061"] = {}
    for name, num, den in [("corn/wheat", "ZC=F", "ZW=F"), ("soy/corn", "ZS=F", "ZC=F")]:
        c = grains[num].index.intersection(grains[den].index)
        lr = np.log(grains[num].reindex(c) / grains[den].reindex(c)).dropna()
        sc2 = lr.diff().std()
        r = zscore_mr(lr, cost_per_change=0.002, scale=sc2)  # log-ratio, ~0.1% per leg
        out["I0061"][name] = {k: v for k, v in r.items() if not k.startswith("_")}
        results_for_plot[name] = r
        report_row(f"{name} (log-ratio)", r)

    # ---------- I0063 re-test 0081 spreads as z-MR ----------
    print("\n=== I0063 re-test 0081 calendar spreads as z-score MR ===")
    out["I0063"] = {}
    for name, root, lmc, smc in [("corn Jul/Dec", "ZC", "N", "Z"),
                                 ("natgas Mar/Apr", "NG", "H", "J"),
                                 ("rbob Jul/Nov", "RB", "N", "X")]:
        try:
            segs = pair_segments(root, lmc, smc)
            if len(segs) < 4:
                print(f"{name:26s} too few segments ({len(segs)})"); continue
            scs = pd.concat(segs).diff().std()
            r = zscore_mr_segments(segs, scale=scs, cost_per_change=0.0008)  # roll-clean
            out["I0063"][name] = {k: v for k, v in r.items() if not k.startswith("_")}
            results_for_plot[name] = r
            report_row(f"{name} (0081 spread)", r, extra=f"segs={r['n_segments']}")
        except Exception as e:  # noqa: BLE001
            print(f"{name:26s} error: {e}")

    # ---- plot equity curves ----
    fig, ax = plt.subplots(figsize=(9, 5))
    for nm, r in results_for_plot.items():
        eq = (1 + r["_net"]).cumprod()
        ax.plot(eq.index, eq.values, lw=1, label=f"{nm} (Sh {r['net_sharpe']:+.2f})")
    ax.axhline(1, color="grey", lw=0.6); ax.legend(fontsize=8); ax.grid(alpha=0.3)
    ax.set_title("0096 spread-MR net equity curves"); ax.set_ylabel("growth of 1")
    fig.tight_layout(); fig.savefig(RESULTS / "spread_mr.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    leads = [nm for nm, r in results_for_plot.items()
             if r["net_sharpe"] > 0.4 and r["perm_p"] < 0.05 and r["adf_p"] < 0.10
             and r["oos_sharpe"] > 0]
    print("\nVerdict:", f"lead candidates: {leads}" if leads else "no spread clears ADF+net+perm+OOS — see REPORT.")


if __name__ == "__main__":
    main()
