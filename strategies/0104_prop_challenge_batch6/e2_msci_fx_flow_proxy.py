"""I0087 - Index-rebalance FX flow (MSCI effective day). STAGE-2 PROXY only.

#s37: passive funds adjust to new MSCI weights at the close before the effective
day -> a mandate-driven, calendar-exact FX hedge flow into the currency whose
region gained weight. Distinct calendar trigger from the I0075 month-end FX flow.

Stage-1 (faithful) needs the ANNOUNCED weight changes per currency -> DATA-BLOCKER
(MSCI weight data not freely PIT-available). This script tests only the Stage-2
PROXY: relative regional EQUITY performance over the review window as a direction
proxy (outperforming region -> its currency is bought). Per RESEARCH-PROCESS.md
repro-treue: a Stage-2 reject is NOT an edge-reject of the flow hypothesis.

Effective day = last business day of Feb/May/Aug/Nov (quarterly review). Long the
currencies of top-ranked-equity regions, short bottom, dollar-neutral; hold the
effective-day window (close[eff-1] -> close[eff+H]). Cost = FX spread per leg.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _common import (
    SPREAD_RT, ann_sharpe, bootstrap_mean_ci, load_close,
)

# region ETF -> currency long-vs-USD daily return
REGION = {"JPY": "EWJ", "GBP": "EWU", "EUR": "EWG", "AUD": "EWA", "CHF": "EWL"}
FX = {  # how to express "long CCY vs USD" from a yfinance pair
    "JPY": ("USDJPY=X", -1), "GBP": ("GBPUSD=X", +1), "EUR": ("EURUSD=X", +1),
    "AUD": ("AUDUSD=X", +1), "CHF": ("USDCHF=X", -1),
}
SPREAD = SPREAD_RT["fx"] / 1e4
REVIEW_MONTHS = (2, 5, 8, 11)


def ccy_return_panel(start="2003-01-01") -> pd.DataFrame:
    out = {}
    for c, (pair, sign) in FX.items():
        s = load_close(pair, start=start).pct_change() * sign
        out[c] = s
    return pd.DataFrame(out).dropna(how="all")


def equity_panel(start="2003-01-01") -> pd.DataFrame:
    return pd.DataFrame({c: load_close(etf, start=start) for c, etf in REGION.items()}).dropna(how="all")


def effective_days(index: pd.DatetimeIndex) -> list:
    """Last business day of each review month present in the index."""
    days = []
    for (y, m), grp in pd.Series(index, index=index).groupby([index.year, index.month]):
        if m in REVIEW_MONTHS:
            days.append(grp.index.max())
    return sorted(days)


def run(hold=1, lookback=63, monthly=False, verbose=True):
    eq = equity_panel()
    fx = ccy_return_panel().reindex(eq.index).fillna(0.0)
    eq_ret_window = eq / eq.shift(lookback) - 1.0
    idx = eq.index

    if monthly:
        # monthly variant: last business day of every month
        ser = pd.Series(idx, index=idx)
        effs = sorted(g.index.max() for _, g in ser.groupby([idx.year, idx.month]))
    else:
        effs = effective_days(idx)

    per_event = []
    for d in effs:
        pos = idx.get_indexer([d])[0]
        if pos < lookback or pos + hold >= len(idx):
            continue
        perf = eq_ret_window.iloc[pos]  # decision uses data up to eff day close
        perf = perf.dropna()
        if len(perf) < 4:
            continue
        ranked = perf.sort_values()
        longs, shorts = ranked.index[-2:], ranked.index[:2]
        w = pd.Series(0.0, index=FX.keys())
        for c in longs:
            w[c] = 0.5
        for c in shorts:
            w[c] = -0.5
        # hold close[eff] -> close[eff+hold]
        win = fx.iloc[pos + 1 : pos + 1 + hold]
        ret = (win * w).sum(axis=1).sum() - SPREAD * w.abs().sum()
        per_event.append(ret)

    x = np.array(per_event, float)
    if verbose and len(x) > 3:
        from _common import perm_test_rotation  # noqa
        rng = np.random.default_rng(0)
        # random-sign permutation on the same |event moves|
        real = x.mean()
        p = (sum((rng.choice([-1.0, 1.0], len(x)) * np.abs(x)).mean() >= real
                 for _ in range(5000)) + 1) / 5001
        lo, hi = bootstrap_mean_ci(x)
        tag = "monthly" if monthly else "quarterly"
        print(f"[{tag:9s} hold={hold} lb={lookback}] n={len(x):3d} "
              f"meanR={x.mean()*1e4:+6.1f}bps win={np.mean(x>0):.1%} "
              f"sumR={x.sum()*100:+.1f}% perm_p={p:.3f} "
              f"bootCI={tuple(round(v*1e4,1) for v in (lo,hi))}bps")
    return x


if __name__ == "__main__":
    print("=== I0087 MSCI FX-flow -- STAGE-2 PROXY (regional-equity-perf direction) ===")
    print("Stage-1 (announced weight changes) = DATA-BLOCKER; proxy is a weaker, different edge.\n")
    for hold in (1, 2, 3):
        run(hold=hold, lookback=63, monthly=False)
    print()
    for hold in (1, 2):
        run(hold=hold, lookback=21, monthly=True)
