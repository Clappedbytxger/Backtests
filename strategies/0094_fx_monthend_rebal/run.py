"""Strategy 0094 — Month-End FX-Rebalancing Flow (WMR 4pm fix).

Batch-2 idea I0058 from `D:\\Backtest Ideas` (source #s20: Melvin & Prins 2015,
"Equity hedging and exchange rates at the London 4pm fix", J. Financial Markets;
BIS). High-priority: same month-end forced-flow mechanism as the 0075 winner, but
in the (living, 0083-confirmed) FX universe — an own, diversifying trigger.

Mechanism: real-money hedgers (pensions/AMs with currency-hedge mandates) holding
foreign equities must adjust their USD hedges at month-end. If foreign equities
OUTPERFORM US during the month, their foreign-currency exposure grew -> they SELL
foreign currency / BUY USD at the month-end WMR 4pm fix to keep the hedge ratio.
=> predictable USD flow, direction derivable from the month's equity relative move.

Pre-registered rule (the idea's own framing, direction empirically tested):
  signal_month = (foreign equity month-return) - (US equity month-return)
  If foreign OUTPERFORMED (signal>0) -> hedgers buy USD/sell foreign ccy
    -> the FX future (foreign/USD, e.g. 6E) FALLS at month-end -> SHORT it.
  i.e. position on the FX future = -sign(signal) = sign(US - foreign).

Hold window: enter ~penultimate trading day close, exit first trading day of next
month (captures the last-day fix flow + rollover). Mark signal on the last 2
trading days (tdom_from_end in {0,1}); engine shifts +1 -> holds last day + first
day next month, exactly the documented 1-2 day window.

Permutation: against RANDOM month-end-sized day blocks (drift-trap baseline, 0050
lesson). We also report the IC of the equity signal vs the realized FX month-end
return, and a sub-period split (effect strength pre/post 2015).

Free data: yfinance (6E=F/6B=F/6J=F/6A=F/6C=F + SPY/EFA/^STOXX50E/^FTSE/^N225).

Run: .venv/Scripts/python.exe strategies/0094_fx_monthend_rebal/run.py
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.costs import IBKR_FUTURES  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.seasonal import add_calendar_features  # noqa: E402
from quantlab.significance import bootstrap_ci, permutation_test, t_test_mean_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)

# FX future -> currency-specific foreign equity index (Melvin-Prins is aggregate;
# we use the broad EAFE proxy EFA as primary signal, currency-specific as variant)
PAIRS = {
    "6E=F": "^STOXX50E",  # EUR  -> Euro Stoxx 50
    "6B=F": "^FTSE",      # GBP  -> FTSE 100
    "6J=F": "^N225",      # JPY  -> Nikkei 225
    "6A=F": "^AXJO",      # AUD  -> ASX 200
    "6C=F": "^GSPTSE",    # CAD  -> TSX
}


def ns(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def month_to_date_rel(fx_idx: pd.DatetimeIndex, us: pd.Series, foreign: pd.Series) -> pd.Series:
    """At each date, foreign-minus-US return since the first trading day of the month.
    PIT-safe: uses only closes up to and including that date."""
    us = us.reindex(fx_idx).ffill()
    fo = foreign.reindex(fx_idx).ffill()
    mk = fx_idx.to_period("M")
    out = pd.Series(index=fx_idx, dtype=float)
    for _, locs in pd.Series(range(len(fx_idx)), index=mk).groupby(level=0):
        sl = locs.values
        u0, f0 = us.iloc[sl[0]], fo.iloc[sl[0]]
        out.iloc[sl] = (fo.iloc[sl] / f0 - 1).values - (us.iloc[sl] / u0 - 1).values
    return out


def monthend_signal(index: pd.DatetimeIndex, direction: pd.Series) -> pd.Series:
    """Position on last 2 trading days = direction (decided at that day's close)."""
    feats = add_calendar_features(index)
    mask = feats["tdom_from_end"].isin([0, 1]).values
    s = np.where(mask, np.sign(direction.reindex(index).fillna(0.0).values), 0.0)
    return pd.Series(s, index=index, name="fx_monthend")


def event_returns(fx_ret: np.ndarray, feats: pd.DataFrame, direction: np.ndarray):
    """Per-month realized signed return over [last day, first day next month]."""
    # last day = tdom_from_end==0; its NEXT-day return belongs to next month's first day.
    rel = []
    tfe = feats["tdom_from_end"].values
    n = len(fx_ret)
    for i in range(1, n - 1):
        if tfe[i] == 1:  # penultimate: decision day; held last day -> earn ret[i+1]
            # window = ret[i+1] (last day) + ret[i+2] if exists (first day next month)
            w = fx_ret[i + 1]
            if i + 2 < n:
                w = (1 + fx_ret[i + 1]) * (1 + fx_ret[i + 2]) - 1
            rel.append((np.sign(direction[i]) * w))
    return np.array(rel)


def main() -> None:
    out = {"idea_id": "I0058"}
    spy = get_prices("SPY", start="1999-01-01")["Close"]
    efa = get_prices("EFA", start="2001-08-01")["Close"]  # MSCI EAFE aggregate foreign

    summary = {}
    for fx_tk, eq_tk in PAIRS.items():
        try:
            fx = get_prices(fx_tk, start="2001-01-01")
        except Exception as e:  # noqa: BLE001
            print(f"{fx_tk}: skip ({e})"); continue
        fx_ret = fx["Close"].pct_change().fillna(0.0)
        feats = add_calendar_features(fx.index)

        recs = {}
        # signal variants: aggregate EAFE, and currency-specific index
        sig_sources = {"EAFE": efa}
        try:
            sig_sources["ccy"] = get_prices(eq_tk, start="2001-01-01")["Close"]
        except Exception:  # noqa: BLE001
            pass

        for sname, foreign in sig_sources.items():
            rel = month_to_date_rel(fx.index, spy, foreign)
            # I0058 pre-registered direction (mode="hedge"): foreign outperformed ->
            # buy USD -> short FX future = -sign(rel). mode="mom" = the opposite
            # (foreign equity strength -> foreign ccy up) for honest characterisation.
            mode = "hedge"  # the idea's claim is what we judge
            base = -np.sign(rel)
            direction = base.copy()  # position on FX future (hedge direction)
            # tradable backtest
            sig = monthend_signal(fx.index, pd.Series(direction, index=fx.index))
            bt = run_backtest(fx, sig, cost_model=IBKR_FUTURES)
            gross, net = bt["gross_returns"], bt["returns"]
            perm = permutation_test(gross, fx_ret, bt["position"], n_perm=4000, metric="sharpe")
            # per-event signed return + IC of signal vs realized fx month-end move
            ev = event_returns(fx_ret.values, feats, np.nan_to_num(direction.values))
            ev = ev[np.isfinite(ev)]
            tt = t_test_mean_return(pd.Series(ev))
            boot = bootstrap_ci(pd.Series(ev), statistic="mean", n_boot=4000)
            # reverse (momentum) direction characterisation
            sig_r = monthend_signal(fx.index, pd.Series(-direction, index=fx.index))
            bt_r = run_backtest(fx, sig_r, cost_model=IBKR_FUTURES)
            net_r = bt_r["returns"]
            perm_r = permutation_test(bt_r["gross_returns"], fx_ret, bt_r["position"], n_perm=4000, metric="sharpe")
            # sub-period
            cut = "2015-01-01"
            recs[sname] = {
                "reverse_net_sharpe": ns(net_r), "reverse_perm_p": perm_r["p_value"],
                "reverse_net_cagr_pct": float(compute_metrics(net_r)["cagr"] * 100),
                "n_events": int(len(ev)),
                "event_mean_bps": float(np.mean(ev) * 1e4),
                "event_t": tt["t_stat"], "event_p": tt["p_value"],
                "boot_ci_bps": [boot["ci_low"] * 1e4, boot["ci_high"] * 1e4],
                "net_sharpe": ns(net), "gross_sharpe": ns(gross),
                "net_cagr_pct": float(compute_metrics(net)["cagr"] * 100),
                "perm_p": perm["p_value"], "frac_active": float((bt["position"] != 0).mean()),
                "sharpe_pre2015": ns(net[net.index < cut]),
                "sharpe_post2015": ns(net[net.index >= cut]),
            }
        out[fx_tk] = recs
        summary[fx_tk] = recs
        for sname, r in recs.items():
            print(f"{fx_tk} [{sname:4s}] ev {r['event_mean_bps']:+.2f}bps "
                  f"(t={r['event_t']:+.2f},p={r['event_p']:.3f}) "
                  f"HEDGE net Sh {r['net_sharpe']:+.2f} perm p={r['perm_p']:.3f} | "
                  f"REVERSE net Sh {r['reverse_net_sharpe']:+.2f} perm p={r['reverse_perm_p']:.3f} "
                  f"boot[{r['boot_ci_bps'][0]:+.1f},{r['boot_ci_bps'][1]:+.1f}]")
        print()

    # ---- G3 basket (EUR/GBP/JPY) with EAFE signal: equal-weight combined return ----
    basket_rets = []
    for fx_tk in ["6E=F", "6B=F", "6J=F"]:
        if fx_tk in out and "EAFE" in out[fx_tk]:
            try:
                fx = get_prices(fx_tk, start="2001-01-01")
                rel = month_to_date_rel(fx.index, spy, efa)
                sig = monthend_signal(fx.index, pd.Series(-np.sign(rel), index=fx.index))
                bt = run_backtest(fx, sig, cost_model=IBKR_FUTURES)
                basket_rets.append(bt["returns"].rename(fx_tk))
            except Exception:  # noqa: BLE001
                pass
    if basket_rets:
        bk = pd.concat(basket_rets, axis=1).fillna(0.0).mean(axis=1)
        out["G3_basket_EAFE"] = {"net_sharpe": ns(bk),
                                 "net_cagr_pct": float(compute_metrics(bk)["cagr"] * 100),
                                 "sharpe_pre2015": ns(bk[bk.index < "2015-01-01"]),
                                 "sharpe_post2015": ns(bk[bk.index >= "2015-01-01"])}
        print(f"G3 basket (EAFE signal): net Sharpe {ns(bk):+.2f}, "
              f"pre/post15 {out['G3_basket_EAFE']['sharpe_pre2015']:+.2f}/"
              f"{out['G3_basket_EAFE']['sharpe_post2015']:+.2f}")

    # ---- plot ----
    fig, ax = plt.subplots(figsize=(8, 4.6))
    labs, vals, ps = [], [], []
    for fx_tk in PAIRS:
        if fx_tk in out and "EAFE" in out[fx_tk]:
            labs.append(fx_tk.replace("=F", ""))
            vals.append(out[fx_tk]["EAFE"]["event_mean_bps"])
            ps.append(out[fx_tk]["EAFE"]["event_p"])
    colors = ["seagreen" if p < 0.05 else "grey" for p in ps]
    ax.bar(labs, vals, color=colors)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_ylabel("signed month-end return (bps)")
    ax.set_title("I0058 Month-End FX-Rebalancing (EAFE signal)\ngreen = event p<0.05")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(RESULTS / "fx_monthend.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    # verdict: any pair with event p<0.05 + boot CI excl 0 + perm p<0.05 + no full OOS collapse
    leads = [fx for fx in PAIRS if fx in out and "EAFE" in out[fx]
             and out[fx]["EAFE"]["event_p"] < 0.05
             and out[fx]["EAFE"]["boot_ci_bps"][0] > 0
             and out[fx]["EAFE"]["perm_p"] < 0.05]
    print("\nVerdict:", f"lead candidates: {leads}" if leads else "no pair clears the battery — see REPORT.")


if __name__ == "__main__":
    main()
