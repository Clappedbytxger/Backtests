"""I0091 - Overnight-gap reversal on index CFD (overreaction fade).

ChatGPT S8 + DeepSeek S9 (#s40), independently convergent. Distinct from I0079
(overnight-drift HARVEST): here a strong prior-day move is FADED intraday next day
(market-maker inventory rebalancing). No overnight hold -> swap-arm.

Rules:
  Long  if DayRet(t) < -1.5% AND RSI(2,Daily)[t] < 10
  Short if DayRet(t) > +1.5% AND RSI(2,Daily)[t] > 90
  Entry t+1 open ; exit t+1 close (time) OR 1.0*ATR(10) target ; stop 1.5*ATR(10).
  Asymmetric RRR<1 (high hit-rate MR carries the EV) -- honest: only works if
  win-rate is really >65%. No Friday-signal trade. Daily OHLC -> intrabar fills
  approximated from t+1 High/Low (stop assumed first if both hit = conservative).

Cost: index spread 3 bps RT, NO overnight swap (open->close). Cost wall is the
RRR<1 enemy: every trade pays 3 bps against a small ATR target.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _common import (
    SPREAD_RT, ann_sharpe, atr, bootstrap_mean_ci, load_ohlc,
    perm_test_trades, save_stream, sharpe_per_trade, wilder_rsi,
)

INDEX = {"US500": "^GSPC", "US30": "^DJI", "NAS100": "^NDX"}
SPREAD = SPREAD_RT["index"] / 1e4
MOVE = 0.015
ATR_N, TP_K, SL_K = 10, 1.0, 1.5


def run_index(ticker: str, verbose=True):
    o = load_ohlc(ticker, start="1995-01-01")
    op, hi, lo, cl = o["Open"], o["High"], o["Low"], o["Close"]
    dayret = cl.pct_change()
    rsi = wilder_rsi(cl, 2)
    a = atr(o, ATR_N)

    long_sig = (dayret < -MOVE) & (rsi < 10)
    short_sig = (dayret > MOVE) & (rsi > 90)
    fri = pd.Series(o.index.weekday == 4, index=o.index)

    trades = []
    daily = pd.Series(0.0, index=o.index)
    idx = o.index
    for i in range(ATR_N + 2, len(idx) - 1):
        t, t1 = idx[i], idx[i + 1]
        if fri.iloc[i]:
            continue
        d = 0
        if bool(long_sig.iloc[i]):
            d = 1
        elif bool(short_sig.iloc[i]):
            d = -1
        if d == 0:
            continue
        entry = op.loc[t1]
        atr_v = a.iloc[i]
        if not np.isfinite(entry) or not np.isfinite(atr_v) or atr_v <= 0:
            continue
        h, l, c = hi.loc[t1], lo.loc[t1], cl.loc[t1]
        if d == 1:
            tp, sl = entry + TP_K * atr_v, entry - SL_K * atr_v
            if l <= sl:            # conservative: stop first if both hit
                px = sl
            elif h >= tp:
                px = tp
            else:
                px = c
        else:
            tp, sl = entry - TP_K * atr_v, entry + SL_K * atr_v
            if h >= sl:
                px = sl
            elif l <= tp:
                px = tp
            else:
                px = c
        ret = d * (px / entry - 1) - SPREAD
        trades.append(ret)
        daily.loc[t1] += ret

    trades = np.array(trades, float)
    daily = daily[daily != 0]
    if verbose and len(trades) > 5:
        print(f"{ticker:6s} n={len(trades):4d} win={np.mean(trades>0):.1%} "
              f"meanR={trades.mean()*1e4:+6.1f}bps perTrSharpe={sharpe_per_trade(trades):+.3f} "
              f"perm_p={perm_test_trades(trades):.3f} "
              f"bootCI={tuple(round(x*1e4,1) for x in bootstrap_mean_ci(trades))}bps "
              f"ann.Sharpe={ann_sharpe(daily):+.2f}")
    return daily, trades


if __name__ == "__main__":
    print("=== I0091 Overnight-gap reversal (cost-on, no event-skip) ===")
    all_daily = {}
    for name, tk in INDEX.items():
        d, t = run_index(tk)
        all_daily[name] = d
    # combined book (sum of per-index daily nets, sharing capital equally)
    book = pd.concat(all_daily, axis=1).fillna(0.0).mean(axis=1)
    book = book[book != 0]
    print(f"\nCombined book ann.Sharpe={ann_sharpe(book):+.2f}  trades/yr~"
          f"{sum(len(run_index(tk, verbose=False)[1]) for tk in INDEX.values())/ ((book.index.max()-book.index.min()).days/365):.0f}")
    save_stream("i0091_gap_reversal", book)
