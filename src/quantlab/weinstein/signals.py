"""Stage-2 breakout entry detection (Weinstein Stage Analysis, daily adaptation).

A *signal* on bar ``t`` is decided using only data up to and including the close
of bar ``t`` (the breakout bar). The portfolio engine fills the entry at the
**open of bar ``t+1``**, so no same-bar / future information ever leaks into a
trade (the project's no-look-ahead convention).

The five user-specified entry conditions, all measured on the breakout bar ``t``
over a trailing **base window** ``[t-base_window, t-1]`` (the prior consolidation,
which excludes the breakout bar itself):

1. **MA breakout from below.** ``Close[t]`` is above the 30-day MA while the
   close was at/below the MA somewhere in the last ``ma_cross_lookback`` bars
   (a genuine upward pierce, not a stock already trending well above the MA).
2. **Stage-1 trading range.** Over the base window the 30-day MA is roughly flat
   (``|slope| <= max_ma_slope``) and the range height
   ``(resistance-support)/support <= max_base_range`` — i.e. a real base, not a
   runaway uptrend.
3. **Resistance tested >= ``min_touches`` then broken.** ``resistance`` is the
   base-window high; the breakout bar closes above it for the first time, and the
   ceiling was approached in ``>= min_touches`` distinct clusters beforehand.
4. **Volume expansion.** ``Volume[t]`` exceeds ``vol_mult x`` the average volume
   of the previous ``vol_window`` bars.
5. **Relative strength turns positive.** Mansfield RS vs the benchmark crosses
   from negative to positive (it was ``< 0`` within the last ``rs_cross_lookback``
   bars and is ``> 0`` now).

The cheap conditions (1,2,4,5 and the resistance break) are vectorized; the only
per-bar work is counting resistance touches, done **only on bars that already
pass everything else** (breakouts are rare), so the whole scan stays fast.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..smc.structure import atr as atr_series


@dataclass
class EntryParams:
    """Tunable Stage-2 entry parameters (see module docstring)."""

    ma_period: int = 30
    base_window: int = 40
    min_touches: int = 3
    touch_band: float = 0.03          # resistance "zone" = top 3% below the high
    vol_window: int = 20
    vol_mult: float = 1.5             # breakout volume > 1.5x trailing average
    rs_period: int = 30               # Mansfield RS lookback (daily)
    ma_cross_lookback: int = 10       # close must have been <= MA within this many bars
    rs_cross_lookback: int = 20       # RS must have been < 0 within this many bars
    max_base_range: float = 0.45      # base height cap (resistance/support - 1)
    max_ma_slope: float = 0.15        # |MA drift over the base| cap = "flat" Stage-1
    atr_period: int = 14
    stop_mode: str = "support"        # "support" | "atr" | "breakout"
    stop_buffer: float = 0.02         # support stop sits this far below the base low
    stop_atr_mult: float = 2.0        # ATR stop = entry - 2*ATR (stop_mode="atr")


def moving_average(close: pd.Series, period: int = 30) -> pd.Series:
    """Simple moving average of the close (causal; ``ma[t]`` uses bars <= t)."""
    return close.rolling(period, min_periods=period).mean()


def mansfield_rs(
    stock_close: pd.Series, bench_close: pd.Series, period: int = 30
) -> pd.Series:
    """Zero-centered Mansfield relative strength vs a benchmark.

    ``RS = stock/benchmark``; the Mansfield RS is ``(RS / SMA(RS, period) - 1)``
    in percent, oscillating around zero. A cross from negative to positive means
    the stock just started **out-performing** the benchmark — Weinstein's RS
    requirement. Causal: only uses past/current prices.
    """
    bench = bench_close.reindex(stock_close.index).ffill()
    rs = stock_close / bench
    rs_ma = rs.rolling(period, min_periods=period).mean()
    return (rs / rs_ma - 1.0) * 100.0


def _count_touch_clusters(high_win: np.ndarray, resistance: float, band: float) -> int:
    """Number of distinct approaches to the resistance zone in a base window.

    A "touch" is a contiguous run of bars whose High enters the zone
    ``[resistance*(1-band), resistance]``. Counting runs (rising edges) means a
    flat top hugging resistance counts once, while three separate pokes at the
    ceiling count three times — exactly the "tested N times" notion.
    """
    if resistance <= 0:
        return 0
    in_zone = high_win >= resistance * (1.0 - band)
    runs = 0
    prev = False
    for v in in_zone:
        if v and not prev:
            runs += 1
        prev = bool(v)
    return runs


def detect_stage2_entries(
    df: pd.DataFrame, bench_close: pd.Series, params: EntryParams | None = None
) -> pd.DataFrame:
    """Detect Stage-2 breakout entries on one stock's OHLCV frame.

    Returns a DataFrame aligned to ``df.index`` with columns:
        ``signal``      – bool, True on a breakout bar ``t`` (decide at close t)
        ``ma``          – 30-day MA
        ``mrs``         – Mansfield relative strength
        ``resistance``  – base-window high (the broken ceiling)
        ``support``     – base-window low
        ``atr``         – causal ATR (for ATR stops / chandelier exits)
        ``stop``        – initial protective stop level for a signal bar
        ``n_touches``   – resistance touch clusters (only filled on candidates)

    The caller (portfolio engine) fills the entry at the **next** bar's open.
    """
    p = params or EntryParams()
    out = pd.DataFrame(index=df.index)

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    vol = df["Volume"].astype(float)

    ma = moving_average(close, p.ma_period)
    mrs = mansfield_rs(close, bench_close, p.rs_period)
    atr = atr_series(df, p.atr_period)

    # Base window stats from the PRIOR window (shift(1) excludes the breakout bar).
    resistance = high.rolling(p.base_window, min_periods=p.base_window).max().shift(1)
    support = low.rolling(p.base_window, min_periods=p.base_window).min().shift(1)

    # (1) MA breakout from below.
    above_ma = close > ma
    below_recent = (
        (close <= ma).astype(int).rolling(p.ma_cross_lookback, min_periods=1).sum().shift(1) > 0
    )
    ma_breakout = above_ma & below_recent

    # (2) Stage-1 base: flat MA + bounded range height.
    ma_slope = (ma.shift(1) - ma.shift(p.base_window)) / ma.shift(p.base_window)
    flat_ma = ma_slope.abs() <= p.max_ma_slope
    range_height = (resistance - support) / support
    tight_base = range_height <= p.max_base_range

    # (3) Resistance broken (first close above the base high).
    res_break = (close > resistance) & (close.shift(1) <= resistance)

    # (4) Volume expansion vs the previous vol_window bars.
    vol_avg = vol.rolling(p.vol_window, min_periods=p.vol_window).mean().shift(1)
    vol_ok = vol > p.vol_mult * vol_avg

    # (5) RS crosses from negative to positive.
    rs_was_neg = (
        (mrs < 0).astype(int).rolling(p.rs_cross_lookback, min_periods=1).sum().shift(1) > 0
    )
    rs_ok = (mrs > 0) & rs_was_neg

    candidate = (
        ma_breakout & flat_ma & tight_base & res_break & vol_ok & rs_ok
    ).fillna(False)

    # Touch count only on the (rare) candidate bars.
    high_arr = high.to_numpy()
    res_arr = resistance.to_numpy()
    n_touches = np.zeros(len(df), dtype=int)
    signal = np.zeros(len(df), dtype=bool)
    cand_idx = np.flatnonzero(candidate.to_numpy())
    for i in cand_idx:
        lo = i - p.base_window
        if lo < 0:
            continue
        win = high_arr[lo:i]                      # base window, excludes bar i
        nt = _count_touch_clusters(win, res_arr[i], p.touch_band)
        n_touches[i] = nt
        if nt >= p.min_touches:
            signal[i] = True

    # Initial protective stop for each bar (used when a signal fires there).
    if p.stop_mode == "atr":
        stop = close - p.stop_atr_mult * atr
    elif p.stop_mode == "breakout":
        stop = resistance * (1.0 - p.stop_buffer)  # just under the broken ceiling
    else:  # "support" (Weinstein default: below the base)
        stop = support * (1.0 - p.stop_buffer)

    out["signal"] = signal
    out["ma"] = ma
    out["mrs"] = mrs
    out["resistance"] = resistance
    out["support"] = support
    out["atr"] = atr
    out["stop"] = stop
    out["n_touches"] = n_touches
    return out
