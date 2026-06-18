"""I0071 - Session breakout: Asia range -> London/NY open break (FX + Gold).

The Asian session (00:00-07:00 UTC) forms a tight range; the London open injects
liquidity -> a break of the Asia range starts the daily move. Time-exact, like a
seasonal window but daily. Tested on 6B (GBP future, FX proxy) and GC (gold).

Decision-time safe: range from 00-07 UTC; the break is detected after 07:00 UTC
and the position opens on the NEXT bar. Stop = opposite side; R-target or time-exit
at 16:00 UTC.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _common as C
from quantlab.costs import CFD_FX, CFD_GOLD


def session_breakout(symbol: str, cost_model, r_target: float = 2.0,
                     break_buffer: float = 0.0, label: str = ""):
    df = C.load(symbol)  # UTC
    df["date"] = df.index.normalize()
    cost_rt = 2 * (cost_model.slippage_bps + cost_model.regulatory_bps)
    rets = []
    for day, g in df.groupby("date"):
        t = g.index.time
        asia = g[(t >= pd.Timestamp("00:00").time()) & (t < pd.Timestamp("07:00").time())]
        body = g[(t >= pd.Timestamp("07:00").time()) & (t < pd.Timestamp("16:00").time())]
        if len(asia) < 30 or len(body) < 30:
            continue
        hi = asia["High"].max(); lo = asia["Low"].min()
        rng = hi - lo
        if rng <= 0:
            continue
        up_lvl = hi + break_buffer * rng
        dn_lvl = lo - break_buffer * rng
        broke_up = body["High"] > up_lvl
        broke_dn = body["Low"] < dn_lvl
        fu = body.index[broke_up.values][0] if broke_up.any() else None
        fd = body.index[broke_dn.values][0] if broke_dn.any() else None
        if fu is None and fd is None:
            continue
        if fu is not None and (fd is None or fu <= fd):
            direction, ts = 1, fu
        else:
            direction, ts = -1, fd
        after = body.loc[body.index > ts]
        if after.empty:
            continue
        entry = after["Open"].iloc[0]
        stop = (lo if direction == 1 else hi)
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        tp = entry + direction * r_target * risk
        exit_px = after["Close"].iloc[-1]
        for _, bar in after.iterrows():
            if direction == 1:
                if bar["Low"] <= stop: exit_px = stop; break
                if bar["High"] >= tp: exit_px = tp; break
            else:
                if bar["High"] >= stop: exit_px = stop; break
                if bar["Low"] <= tp: exit_px = tp; break
        rets.append(direction * (exit_px - entry) / entry)
    s = C.summarize(f"session-breakout {label}", np.array(rets), cost_rt)
    print(f"  {label:18s} r={r_target} buf={break_buffer}: n={s['n']:5d} "
          f"gross={s['gross_bps']:7.3f}bps gS={s['gross_sharpe']:.4f} "
          f"net={s['net_bps']:7.3f}bps win={s['win']:.3f}")
    return s


if __name__ == "__main__":
    print("=== I0071 session breakout (Asia range -> London) ===")
    for r in (1.0, 2.0):
        for buf in (0.0, 0.1):
            session_breakout("6B", CFD_FX, r_target=r, break_buffer=buf, label="6B (GBP FX)")
    for r in (1.0, 2.0):
        for buf in (0.0, 0.1):
            session_breakout("GC", CFD_GOLD, r_target=r, break_buffer=buf, label="GC (gold)")
