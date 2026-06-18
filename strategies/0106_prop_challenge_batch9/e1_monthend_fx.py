"""I0092 - Month-end FX flow, close-proxy + quarter-end 2x (refine I0075).
Mandate-driven real-money hedge rebalancing: foreign equities up over the month ->
hedgers buy USD at month-end. Signal = MSCI-ex-US (EFA) vs S&P monthly relative perf.
Fix-window (Dukascopy M15) is data-deferred; this tests the daily-close proxy + Q-end 2x.
"""
import numpy as np, pandas as pd
from _common import (ann_sharpe, bootstrap_mean_ci, cagr_mdd, load_close,
                     perm_test_sign, save_stream, scale_to_vol, sharpe_per_trade)

# long-ccy-vs-USD daily return per pair
FX = {"EUR": ("EURUSD=X", +1), "JPY": ("USDJPY=X", -1), "AUD": ("AUDUSD=X", +1), "CHF": ("USDCHF=X", -1)}
SPREAD = 1.6 / 1e4
EFA = load_close("EFA"); SPX = load_close("^GSPC")


def run(verbose=True):
    rets = {c: load_close(p).pct_change() * sgn for c, (p, sgn) in FX.items()}
    fx = pd.DataFrame(rets).dropna(how="all")
    spx_m = SPX.resample("ME").last().pct_change()
    efa_m = EFA.resample("ME").last().pct_change()
    sig = (efa_m - spx_m).dropna()   # foreign-minus-US monthly rel perf (decision: prior-month)
    idx = fx.index
    lbd = pd.Series(idx, index=idx).groupby([idx.year, idx.month]).max()  # last business day per month
    lbd_set = set(lbd.values)
    per_event = []; daily = pd.Series(0.0, index=idx)
    for d in lbd:
        nxt = idx[idx > d]
        if len(nxt) == 0:
            continue
        d1 = nxt[0]
        m = (d.year, d.month)
        # signal = the JUST-COMPLETED month's foreign-vs-US (known at LBD close) — I0075 mechanic
        cur = [k for k in sig.index if (k.year, k.month) == m]
        if not cur:
            continue
        s = sig.loc[cur[-1]]
        # I0075-validated direction (perm 0,0006): US equities strong (s<0) -> hedgers BUY USD ->
        # SHORT foreign ccy basket. direction = sign(foreign-US): s<0 -> short foreign.
        direction = np.sign(s)
        is_qend = d.month in (3, 6, 9, 12)
        size = (2.0 if is_qend else 1.0)
        r = direction * fx.loc[d1].mean() * size - SPREAD * size  # hold close[lbd]->close[d1]
        per_event.append(r); daily.loc[d1] = r
    x = np.array(per_event, float); daily = daily[daily != 0]
    if verbose:
        n = len(daily)
        print(f"I0092 Monatsend-FX (close-proxy +Q2x): events={len(x)} "
              f"meanR={x.mean()*1e4:+.1f}bps win={np.mean(x>0):.1%} sumR={x.sum()*100:+.1f}%")
        print(f"   perm_p={perm_test_sign(x):.3f} bootCI={tuple(round(v*1e4,1) for v in bootstrap_mean_ci(x))}bps "
              f"daily Sharpe={ann_sharpe(daily):+.2f} IS/OOS {ann_sharpe(daily.iloc[:n//2]):+.2f}/{ann_sharpe(daily.iloc[n//2:]):+.2f}")
    return daily, x


if __name__ == "__main__":
    d, x = run()
    save_stream("i0092_monthend_fx", scale_to_vol(d))
