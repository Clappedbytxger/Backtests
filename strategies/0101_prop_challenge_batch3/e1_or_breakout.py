"""I0067 - 5-min Opening-Range Breakout (Zarattini 2024, claimed Sharpe 2.81).

Faithful reproduction of the rule on a single CTI-tradable instrument (the paper
needs a 7000-stock "stocks-in-play" universe we cannot replicate; the handoff
explicitly asks for the index/gold adaptation). Lesson 0039 already found the
plain OR breakout/fade gross ~0 on ES; here we (a) reproduce that, then (b) add
the paper's conditioning angles (relative-volume gate, gap-day gate, ATR/vol
regime) to see if the edge concentrates anywhere before charging the CFD cost.

Decision-time safe: OR built from the first 5 RTH minutes; the breakout is
detected, then the position opens on the NEXT bar's open. Time-exit at 15:59.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import _common as C
from quantlab.costs import CFD_INDEX, CFD_GOLD

OR_MIN = 5          # opening-range length in minutes
PRICE_REF = 5000.0  # representative index price for the cost preset


def or_breakout_day(day_df: pd.DataFrame, or_minutes: int = OR_MIN,
                    long_short: bool = True, r_target: float | None = None,
                    stop_mult: float = 1.0):
    """Trade the first OR breakout in one RTH session.

    Returns dict with signed return (open->exit, fraction), direction, the
    opening-range width (fraction of price), session volume so far, etc., or None
    if no breakout occurred.
    """
    if len(day_df) < or_minutes + 5:
        return None
    op = day_df["Open"].iloc[0]
    or_window = day_df.iloc[:or_minutes]
    or_hi = or_window["High"].max()
    or_lo = or_window["Low"].min()
    or_width = (or_hi - or_lo) / op
    body = day_df.iloc[or_minutes:]
    if body.empty:
        return None
    # first bar to break the OR
    broke_up = body["High"] > or_hi
    broke_dn = body["Low"] < or_lo
    first_up = body.index[broke_up.values][0] if broke_up.any() else None
    first_dn = body.index[broke_dn.values][0] if broke_dn.any() else None
    if first_up is None and first_dn is None:
        return None
    if first_up is not None and (first_dn is None or first_up <= first_dn):
        direction, level, ts = 1, or_hi, first_up
    else:
        direction, level, ts = -1, or_lo, first_dn
    if direction == -1 and not long_short:
        return None
    # enter on the NEXT bar's open (no signal-bar trade)
    after = body.loc[body.index > ts]
    if after.empty:
        return None
    entry = after["Open"].iloc[0]
    rng = or_hi - or_lo
    # stop = opposite OR side widened by stop_mult; exit at session close otherwise
    if direction == 1:
        stop = level - stop_mult * rng
    else:
        stop = level + stop_mult * rng
    tp = None
    if r_target is not None:
        risk = abs(entry - stop)
        tp = entry + direction * r_target * risk
    exit_px = after["Close"].iloc[-1]  # time-exit default
    rel_vol = float(day_df["Volume"].iloc[:or_minutes].sum())
    for _, bar in after.iterrows():
        if direction == 1:
            if bar["Low"] <= stop:
                exit_px = stop; break
            if tp is not None and bar["High"] >= tp:
                exit_px = tp; break
        else:
            if bar["High"] >= stop:
                exit_px = stop; break
            if tp is not None and bar["Low"] <= tp:
                exit_px = tp; break
    ret = direction * (exit_px - entry) / entry
    return {"ret": ret, "dir": direction, "or_width": or_width,
            "or_vol": rel_vol, "gap": (op - day_df["Open"].iloc[0]) / op}


def run_symbol(symbol: str, cost_model, label: str):
    df = C.rth(C.to_eastern(C.load(symbol)))
    rows = []
    dates = []
    for day, g in C.sessions(df):
        if len(g) < 60:
            continue
        # session-level open gap requires prior close; compute later via shift
        res = or_breakout_day(g, long_short=True)
        if res is None:
            continue
        res["date"] = day
        rows.append(res)
    t = pd.DataFrame(rows).set_index("date")
    if t.empty:
        print(f"  {label}: no trades"); return None
    cost_rt = 2 * cost_model.slippage_bps + 2 * cost_model.regulatory_bps
    print(f"\n=== {label}  ({symbol}, {len(t)} sessions w/ breakout) ===")
    base = C.summarize("plain OR-breakout (time-exit)", t["ret"].values, cost_rt)
    print("  base :", {k: base[k] for k in ["n", "gross_bps", "gross_sharpe", "net_bps", "win"]})

    # conditioning: high relative-volume OR (top tercile), wide-OR, vol regime
    for name, mask in [
        ("hi OR-volume (top tercile)", t["or_vol"] >= t["or_vol"].quantile(2/3)),
        ("wide OR (top tercile width)", t["or_width"] >= t["or_width"].quantile(2/3)),
        ("narrow OR (bottom tercile)", t["or_width"] <= t["or_width"].quantile(1/3)),
    ]:
        s = C.summarize(name, t.loc[mask, "ret"].values, cost_rt)
        print(f"  {name:32s}:", {k: s[k] for k in ["n", "gross_bps", "gross_sharpe", "net_bps", "win"]})

    # R-target variant (1R / 2R) on the plain set
    for rt in (1.0, 2.0):
        rr = [or_breakout_day(g, r_target=rt) for _, g in C.sessions(df) if len(g) >= 60]
        rr = [x["ret"] for x in rr if x is not None]
        s = C.summarize(f"{rt:.0f}R-target", np.array(rr), cost_rt)
        print(f"  {rt:.0f}R-target                      :", {k: s[k] for k in ["n", "gross_bps", "gross_sharpe", "net_bps", "win"]})
    return t


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    run_symbol("ES", CFD_INDEX, "I0067 ES (S&P CFD adaptation)")
    run_symbol("NQ", CFD_INDEX, "I0067 NQ (Nasdaq CFD adaptation)")
    run_symbol("GC", CFD_GOLD, "I0067 GC (XAUUSD adaptation)")
