"""I0093 - Gold/Silver ratio RV-MR with ADF/half-life gate + multi-year extreme.
Re-test of I0082 (rejected: 60d ratio TRENDS). New angle: rolling stationarity gate
(lesson I0089) + 1y z-band + only trade multi-year extremes. Market-neutral XAU/XAG.
"""
from _common import (ann_sharpe, backtest_spread_mr, bootstrap_mean_ci, cagr_mdd,
                     load_close, perm_test_sign, save_stream, scale_to_vol, sharpe_per_trade)

GOLD = load_close("GC=F"); SILVER = load_close("SI=F")
SPREAD = (4.0 + 6.0) / 1e4   # gold + silver RT spread on the spread position
SWAP = 2.0 / 1e4


def run(verbose=True):
    daily, trades = backtest_spread_mr(
        GOLD, SILVER, z_win=250, adf_win=500, adf_p=0.10, hl_lo=20, hl_hi=250,
        z_entry=2.0, z_exit=0.5, z_stop=3.5, time_stop=60,
        spread_rt=SPREAD, swap=SWAP, extreme_dec=1250)  # ~5y daily extreme
    if verbose:
        s = ann_sharpe(daily); c, m = cagr_mdd(daily); n = len(daily)
        print(f"I0093 Gold/Silber-RV (gated): trades={len(trades)} "
              f"perTrade meanR={trades.mean()*100:+.2f}% spt={sharpe_per_trade(trades):+.3f} "
              f"| daily Sharpe={s:+.2f} CAGR={c:+.2%} MaxDD={m:.1%}")
        if len(trades) > 3:
            print(f"   perm_p={perm_test_sign(trades):.3f} bootCI%={tuple(round(x*100,2) for x in bootstrap_mean_ci(trades))} "
                  f"| IS/OOS Sharpe {ann_sharpe(daily.iloc[:n//2]):+.2f}/{ann_sharpe(daily.iloc[n//2:]):+.2f}")
    return daily, trades


if __name__ == "__main__":
    d, t = run()
    save_stream("i0093_goldsilver_rv", scale_to_vol(d))
