"""I0069 - Index intraday mean-reversion (VWAP fade) and
I0070 - Gap-fill fade at the open.

Both are the "MR is robust on index, not crypto" angle (0013). MR is the highest-
frequency class -> most cost-sensitive. We measure the gross reversion edge first,
then charge CFD_INDEX.

I0069 VWAP fade: when Close > VWAP + k*sigma_intraday -> short toward VWAP (and
mirror for long), hard stop at a further ATR step, exit on VWAP touch or close.

I0070 gap fade: at the RTH open, if |open/prev_rth_close - 1| > thr, fade toward
prev close (target = prev close), hard stop beyond the open extreme, time-exit.
The RTH-filtered first bar IS the real cash open (lesson 0038 satisfied).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _common as C
from quantlab.costs import CFD_INDEX

COST_RT = 2 * (CFD_INDEX.slippage_bps + CFD_INDEX.regulatory_bps)


def vwap_fade(symbol: str, k: float = 2.0, label: str = ""):
    df = C.rth(C.to_eastern(C.load(symbol)))
    rets = []
    for day, g in C.sessions(df):
        if len(g) < 60:
            continue
        c = g["Close"].values
        tp = (g["High"].values + g["Low"].values + c) / 3.0
        vol = g["Volume"].values.astype(float)
        cum_v = np.cumsum(vol); cum_pv = np.cumsum(tp * vol)
        vwap = np.where(cum_v > 0, cum_pv / np.maximum(cum_v, 1), c)
        # rolling intraday dispersion of close-vs-vwap
        dev = c - vwap
        sig = pd.Series(dev).expanding(min_periods=15).std().values
        pos = 0; entry = 0.0; target = 0.0; stop = 0.0
        nb = len(g)
        for i in range(15, nb - 1):
            if np.isnan(sig[i]) or sig[i] == 0:
                continue
            if pos == 0:
                if dev[i] > k * sig[i]:
                    pos = -1; entry = g["Open"].values[i+1]; target = vwap[i]; stop = c[i] + k * sig[i]
                elif dev[i] < -k * sig[i]:
                    pos = 1; entry = g["Open"].values[i+1]; target = vwap[i]; stop = c[i] - k * sig[i]
            else:
                hi = g["High"].values[i]; lo = g["Low"].values[i]
                exit_px = None
                if pos == 1:
                    if lo <= stop: exit_px = stop
                    elif hi >= target: exit_px = target
                else:
                    if hi >= stop: exit_px = stop
                    elif lo <= target: exit_px = target
                if exit_px is not None:
                    rets.append(pos * (exit_px - entry) / entry); pos = 0
        if pos != 0:
            rets.append(pos * (c[-1] - entry) / entry)
    s = C.summarize(f"VWAP-fade k={k} {label}", np.array(rets), COST_RT)
    print(f"  VWAP-fade k={k:<3} {label:6s}: n={s['n']:5d} gross={s['gross_bps']:7.3f}bps "
          f"gS={s['gross_sharpe']:.4f} net={s['net_bps']:7.3f}bps win={s['win']:.3f}")
    return s


def gap_fade(symbol: str, thr: float, label: str = ""):
    df = C.rth(C.to_eastern(C.load(symbol)))
    sess = list(C.sessions(df))
    prev_close = None
    rets = []
    for day, g in sess:
        if len(g) < 60:
            prev_close = g["Close"].iloc[-1]; continue
        if prev_close is None:
            prev_close = g["Close"].iloc[-1]; continue
        op = g["Open"].iloc[0]
        gap = op / prev_close - 1
        if abs(gap) >= thr:
            direction = -np.sign(gap)  # fade: up-gap -> short
            target = prev_close
            body = g.iloc[1:]
            entry = body["Open"].iloc[0]
            # stop beyond the open extreme (1x gap distance past open)
            stop = op + np.sign(gap) * abs(op - prev_close) * 1.0
            exit_px = body["Close"].iloc[-1]
            for _, bar in body.iterrows():
                if direction == 1:
                    if bar["Low"] <= stop: exit_px = stop; break
                    if bar["High"] >= target: exit_px = target; break
                else:
                    if bar["High"] >= stop: exit_px = stop; break
                    if bar["Low"] <= target: exit_px = target; break
            rets.append(direction * (exit_px - entry) / entry)
        prev_close = g["Close"].iloc[-1]
    s = C.summarize(f"gap-fade thr={thr} {label}", np.array(rets), COST_RT)
    print(f"  gap-fade thr={thr:<5} {label:6s}: n={s['n']:5d} gross={s['gross_bps']:7.3f}bps "
          f"gS={s['gross_sharpe']:.4f} net={s['net_bps']:7.3f}bps win={s['win']:.3f}")
    return s


if __name__ == "__main__":
    print("=== I0069 VWAP mean-reversion fade ===")
    for sym in ("ES", "NQ"):
        for k in (1.5, 2.0, 2.5):
            vwap_fade(sym, k, sym)
    print("\n=== I0070 gap-fill fade ===")
    for sym in ("ES", "NQ"):
        for thr in (0.001, 0.003, 0.005):
            gap_fade(sym, thr, sym)
