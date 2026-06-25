"""Strategy 0085 — Equity calendar/flow screen (I0012 OPEX, I0029 Pre-Holiday, I0013 Pension).

Three flow/calendar equity ideas from the handoff, tested with the drift-trap
permutation (the class where the confirmed leads live: 0050/0075/0078).

  I0012 OPEX-week drift  : long SPY during the monthly options-expiry week
                           (Mon-Fri containing the 3rd Friday); dealer +gamma support.
  I0029 Pre-Holiday      : long SPY only on the trading day before US market holidays.
  I0013 Pension rebalance: at month-end, if equities outperformed bonds that month,
                           the 60/40 rebalance sells equities/buys bonds -> long
                           IEF / short SPY into month-end (conditional spread).

Data: SPY, ^GSPC, IEF (yfinance, free). Holidays inferred from trading-calendar gaps.

Run:
    .venv/Scripts/python.exe strategies/0085_equity_flow/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.costs import MES_INTRADAY, IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics, trade_stats  # noqa: E402
from quantlab.significance import bootstrap_ci, permutation_test, t_test_mean_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)


def net_sharpe(r): r = r.dropna(); return float(r.mean()/r.std()*ANN) if r.std() else float("nan")


def opex_week_mask(index: pd.DatetimeIndex) -> pd.Series:
    """True on Mon-Fri of the week containing the 3rd Friday of each month."""
    idx = pd.DatetimeIndex(index)
    out = pd.Series(False, index=idx)
    for (y, m), grp in idx.to_series().groupby([idx.year, idx.month]):
        fridays = [d for d in grp.index if d.weekday() == 4]
        if len(fridays) < 3:
            continue
        third = fridays[2]
        wk_start = third - pd.Timedelta(days=4)
        out[(idx >= wk_start) & (idx <= third)] = True
    return out


def pre_holiday_mask(index: pd.DatetimeIndex) -> pd.Series:
    """True on the trading day before a market holiday (gap exceeds normal weekend)."""
    idx = pd.DatetimeIndex(index)
    nxt = idx[1:]
    gap = (nxt - idx[:-1]).days
    wd = idx[:-1].weekday
    # normal gap: 1 (Mon-Thu) or 3 (Fri). Larger -> holiday between.
    holiday = ((wd < 4) & (gap > 1)) | ((wd == 4) & (gap > 3))
    mask = pd.Series(False, index=idx)
    mask.iloc[:-1] = holiday
    return mask


def main() -> None:
    out: dict = {}
    spy = get_prices("SPY", start="1993-01-01")
    gspc = get_prices("^GSPC", start="1960-01-01")
    ief = get_prices("IEF", start="2002-01-01")

    # ---- I0012 OPEX week ----
    m = opex_week_mask(spy.index)
    sig = m.astype(float)
    bt = run_backtest(spy, sig, cost_model=MES_INTRADAY)
    ar = spy["Close"].pct_change().fillna(0.0)
    perm = permutation_test(bt["gross_returns"], ar, bt["position"], n_perm=5000)
    held = bt["position"] > 0
    opex_mean = ar[held.values].mean() * 1e4
    rest_mean = ar[~held.values].mean() * 1e4
    out["I0012_opex"] = {"opex_day_bps": float(opex_mean), "rest_day_bps": float(rest_mean),
                         "perm_p": perm["p_value"], "net_sharpe": net_sharpe(bt["returns"]),
                         "frac_days": float(m.mean())}
    print(f"I0012 OPEX-week: opex-day {opex_mean:+.2f}bps vs rest {rest_mean:+.2f}bps, perm p={perm['p_value']:.3f}")

    # ---- I0029 Pre-Holiday (SPY + long-history ^GSPC) ----
    out["I0029_preholiday"] = {}
    for tk, p in [("SPY", spy), ("^GSPC", gspc)]:
        ph = pre_holiday_mask(p.index)
        arr = p["Close"].pct_change().fillna(0.0)
        ph_ret = arr[ph.values]
        rest = arr[~ph.values]
        tt = t_test_mean_return(pd.Series(ph_ret.values))
        boot = bootstrap_ci(pd.Series(ph_ret.values), "mean", 5000)
        out["I0029_preholiday"][tk] = {"prehol_bps": float(ph_ret.mean()*1e4), "rest_bps": float(rest.mean()*1e4),
                                       "n": int(ph.sum()), "t_p": tt["p_value"],
                                       "boot_ci_bps": [boot["ci_low"]*1e4, boot["ci_high"]*1e4]}
        print(f"I0029 Pre-Holiday {tk}: {ph_ret.mean()*1e4:+.2f}bps vs rest {rest.mean()*1e4:+.2f}bps "
              f"(n={int(ph.sum())}, t-p={tt['p_value']:.4f}, CI [{boot['ci_low']*1e4:+.2f},{boot['ci_high']*1e4:+.2f}])")

    # ---- I0013 Pension rebalance (conditional bond-minus-equity into month-end) ----
    common = spy.index.intersection(ief.index)
    s_ret = spy["Close"].pct_change().reindex(common).fillna(0.0)
    i_ret = ief["Close"].pct_change().reindex(common).fillna(0.0)
    # month-to-date equity-minus-bond spread, evaluated at each day
    feats = pd.DataFrame(index=common)
    feats["tdom_from_end"] = pd.Series(common, index=common).groupby(common.to_period("M")).cumcount(ascending=False)
    last3 = feats["tdom_from_end"] < 3
    # prior-month equity vs bond outperformance (decision-time at month start)
    m_s = (1 + s_ret).resample("ME").prod() - 1
    m_i = (1 + i_ret).resample("ME").prod() - 1
    spread_m = (m_s - m_i).shift(1)  # prior month's equity-minus-bond
    spread_by = spread_m.copy(); spread_by.index = spread_by.index.to_period("M")
    cur = pd.Series(common.to_period("M"), index=common).map(spread_by)
    # if equities outperformed last month (cur>0) -> rebalance sells equity/buys bond -> long IEF short SPY in last 3 days
    pos_dir = np.where((last3.values) & (cur.values > 0), 1.0, 0.0)  # 1 = long (IEF - SPY)
    bond_minus_eq = i_ret - s_ret
    strat = pd.Series(pos_dir, index=common).shift(1).fillna(0.0) * bond_minus_eq
    # permutation vs random same-count days
    perm13 = permutation_test(strat, bond_minus_eq, pd.Series(pos_dir, index=common).shift(1).fillna(0.0), n_perm=5000)
    act = strat[pd.Series(pos_dir, index=common).shift(1).fillna(0.0) > 0]
    boot13 = bootstrap_ci(act[act != 0], "mean", 5000)
    out["I0013_pension"] = {"active_day_bps": float(act.mean()*1e4), "perm_p": perm13["p_value"],
                            "boot_ci_bps": [boot13["ci_low"]*1e4, boot13["ci_high"]*1e4], "n_active": int((pos_dir>0).sum())}
    print(f"I0013 Pension (long IEF-short SPY last 3d after strong equity month): "
          f"{act.mean()*1e4:+.2f}bps/day, perm p={perm13['p_value']:.3f}, CI [{boot13['ci_low']*1e4:+.2f},{boot13['ci_high']*1e4:+.2f}]")

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
