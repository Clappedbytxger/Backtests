"""I0073 - Bitcoin intraday trend-continuation + Monday-Asia-open conditioning.

Crypto continues intraday (extremes run, lesson 0013) rather than mean-reverting.
We test trend continuation (N-bar breakout, MA-cross) on BTC 1h with an ATR-
trailing exit, plus the documented Monday-Asia-open conditioning, and a strict
beta-masquerade check (vs long-only BTC). CFD_CRYPTO (20 bps RT) is the hardest
cost wall in the batch (0012-0015).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _common as C
from quantlab.costs import CFD_CRYPTO

COST_RT = 2 * (CFD_CRYPTO.slippage_bps + CFD_CRYPTO.regulatory_bps)


def atr(df, n=24):
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def breakout_trend(df, n=20, atr_mult=3.0, long_only=False, monday_asia=False):
    """N-bar Donchian breakout, ATR-trailing stop. Returns per-bar net position
    pnl series (gross) and trade count."""
    c = df["Close"]
    hi = df["High"].rolling(n).max().shift(1)
    lo = df["Low"].rolling(n).min().shift(1)
    a = atr(df).shift(1)
    pos = np.zeros(len(df))
    trail = np.nan
    state = 0
    idx = df.index
    for i in range(n + 24, len(df)):
        price = c.iloc[i - 1]  # decision on prior close
        if state == 0:
            if price > hi.iloc[i - 1]:
                state = 1; trail = price - atr_mult * a.iloc[i - 1]
            elif (not long_only) and price < lo.iloc[i - 1]:
                state = -1; trail = price + atr_mult * a.iloc[i - 1]
        elif state == 1:
            trail = max(trail, price - atr_mult * a.iloc[i - 1])
            if price < trail:
                state = 0
        elif state == -1:
            trail = min(trail, price + atr_mult * a.iloc[i - 1])
            if price > trail:
                state = 0
        pos[i] = state
    pos = pd.Series(pos, index=idx)
    if monday_asia:
        # only hold during Mon 00-08 UTC continuation window (entries gated)
        keep = (idx.dayofweek == 0) & (idx.hour < 12)
        pos = pos.where(keep, 0.0)
    ret = c.pct_change().fillna(0.0)
    gross = pos.shift(1).fillna(0.0) * ret
    changes = pos.diff().abs().fillna(0.0)
    net = gross - changes * (COST_RT / 1e4)
    return gross, net, changes.sum() / 2


def summarize(name, gross, net, ntr):
    g_ann = C.ann_sharpe_daily(gross.resample("1D").sum())
    n_ann = C.ann_sharpe_daily(net.resample("1D").sum())
    print(f"  {name:34s}: trades~{ntr:6.0f} grossSharpe(d) {g_ann:6.3f} "
          f"netSharpe(d) {n_ann:6.3f} grossTot {gross.sum()*100:8.1f}% netTot {net.sum()*100:8.1f}%")


if __name__ == "__main__":
    df = C.load("BTC_1h")
    print("=== I0073 BTC intraday trend-continuation (1h) ===")
    # beta benchmark: long-only buy & hold
    bh = df["Close"].pct_change().fillna(0.0)
    print(f"  buy&hold BTC                      : annSharpe(d) {C.ann_sharpe_daily(bh.resample('1D').sum()):.3f} "
          f"tot {bh.sum()*100:.0f}%")
    for n in (20, 55, 100):
        for am in (2.0, 3.0):
            g, nn, ntr = breakout_trend(df, n=n, atr_mult=am, long_only=False)
            summarize(f"breakout n={n} atrx{am} L/S", g, nn, ntr)
    # long-only (beta-masquerade check)
    g, nn, ntr = breakout_trend(df, n=55, atr_mult=3.0, long_only=True)
    summarize("breakout n=55 atrx3 LONG-only", g, nn, ntr)
    # Monday-Asia-open conditioning
    g, nn, ntr = breakout_trend(df, n=20, atr_mult=3.0, long_only=False, monday_asia=True)
    summarize("breakout n=20 atrx3 Mon-Asia gate", g, nn, ntr)
