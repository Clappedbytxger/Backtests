"""I0097 - Pre-holiday + turn-of-year overnight harvest (selective nights; indices + gold).
Long index over the night before US market holidays (+ year-end gold). Low-freq -> dodges
the 0051 turnover wall. Honest enemies: post-1990 decay (0085) + the 5bps/night swap+spread.
"""
import numpy as np, pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from _common import (ann_sharpe, bootstrap_mean_ci, cagr_mdd, load_close,
                     perm_test_sign, save_stream)

IDX = {"US500": "^GSPC", "US30": "^DJI", "NAS100": "^NDX"}
SPREAD = 3.0 / 1e4; SWAP = 2.0 / 1e4


def run(verbose=True):
    cal = USFederalHolidayCalendar()
    streams = {}; alltr = []
    for name, tk in IDX.items():
        px = load_close(tk, start="1995-01-01")
        hol = cal.holidays(start=px.index.min(), end=px.index.max())
        # pre-holiday trading day = last session strictly before a holiday date
        rets = px.pct_change()
        is_prehol = pd.Series(False, index=px.index)
        for h in hol:
            prior = px.index[px.index < h]
            if len(prior):
                is_prehol.loc[prior[-1]] = True
        # overnight long held INTO the pre-holiday close: enter close[t-1], exit close[t]
        sig = is_prehol  # the day whose return we capture
        r = rets[sig] - SPREAD - SWAP   # 1-night cost
        streams[name] = r
        alltr += list(r.values)
        if verbose:
            print(f"I0097 {name:6s}: nights={len(r)} meanR={r.mean()*1e4:+.1f}bps "
                  f"win={(r>0).mean():.1%} sumR={r.sum()*100:+.1f}%")
    book = pd.concat(streams, axis=1).fillna(0.0).mean(axis=1); book = book[book != 0]
    x = np.array([v for v in alltr if not np.isnan(v)])
    if verbose:
        # decay split
        bk = book.copy(); bk.index = pd.to_datetime(bk.index)
        pre10 = bk[bk.index < "2010-01-01"]; post10 = bk[bk.index >= "2010-01-01"]
        print(f"I0097 BOOK: meanR={x.mean()*1e4:+.1f}bps perm_p={perm_test_sign(x):.3f} "
              f"bootCI={tuple(round(v*1e4,1) for v in bootstrap_mean_ci(x))}bps")
        print(f"   decay: pre-2010 meanR={pre10.mean()*1e4:+.1f}bps  post-2010 {post10.mean()*1e4:+.1f}bps")
    return book


if __name__ == "__main__":
    b = run()
    save_stream("i0097_preholiday", b)
