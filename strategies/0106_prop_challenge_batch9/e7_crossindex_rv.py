"""I0098 - Cross-index RV-MR, market-neutral (NAS100/US500 + GER40/EU50).
Adds equity exposure with ~0 net beta (long A / short B vol-matched) -> diversifies
WITHOUT consuming the book's 30% equity-beta budget. ADF/half-life gate (I0089)
against the growth-trend trap (NAS/SPX 2020-23 was a multi-year trend, not MR).
"""
import numpy as np
from _common import (ann_sharpe, backtest_spread_mr, bootstrap_mean_ci, cagr_mdd,
                     load_close, perm_test_sign, save_stream, scale_to_vol, sharpe_per_trade)

PAIRS = {"NAS100/US500": ("^NDX", "^GSPC"), "GER40/EU50": ("^GDAXI", "^STOXX50E")}
SPREAD = 2 * (3.0 / 1e4)   # two index legs
SWAP = 2.0 / 1e4


def run(verbose=True):
    streams = {}; alltr = []
    for name, (a, b) in PAIRS.items():
        legA = load_close(a); legB = load_close(b)
        daily, trades = backtest_spread_mr(
            legA, legB, z_win=60, adf_win=250, adf_p=0.10, hl_lo=10, hl_hi=120,
            z_entry=2.0, z_exit=0.5, z_stop=3.5, time_stop=30,
            spread_rt=SPREAD, swap=SWAP)
        streams[name] = daily; alltr += list(trades)
        if verbose:
            s = ann_sharpe(daily); c, m = cagr_mdd(daily)
            print(f"I0098 {name:14s}: trades={len(trades):3d} "
                  f"meanR={np.mean(trades)*100 if len(trades) else 0:+.2f}% "
                  f"Sharpe={s:+.2f} CAGR={c:+.2%} MaxDD={m:.1%}")
    import pandas as pd
    book = pd.concat(streams, axis=1).fillna(0.0).mean(axis=1)
    book = book[book != 0]
    alltr = np.array(alltr, float)
    if verbose and len(alltr) > 3:
        n = len(book)
        print(f"I0098 BOOK: Sharpe={ann_sharpe(book):+.2f} perm_p={perm_test_sign(alltr):.3f} "
              f"bootCI%={tuple(round(x*100,2) for x in bootstrap_mean_ci(alltr))} "
              f"IS/OOS {ann_sharpe(book.iloc[:n//2]):+.2f}/{ann_sharpe(book.iloc[n//2:]):+.2f}")
    return book


if __name__ == "__main__":
    b = run()
    if len(b) > 30 and b.std():
        save_stream("i0098_crossindex_rv", scale_to_vol(b))
