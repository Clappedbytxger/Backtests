"""Causal market-structure primitives for the SMC sweep+BOS strategy.

Two building blocks, deliberately kept *label-only* (no streaming state) so the
causal lag is added explicitly by the caller and can be verified by the
look-ahead test:

* :func:`swing_points` labels each bar as an ``N``-bar fractal swing high/low.
  A pivot at bar ``i`` references bars ``i-N .. i+N``, so it is only *knowable*
  at bar ``i+N``. The label itself is non-causal by construction; the backtest
  loop consults ``is_swing_high[t-N]`` at bar ``t`` to respect causality (spec
  Teil 5: a swing only flows into sweep/BOS logic from ``Bildung + N``).
* :func:`atr` is a causal Average True Range used for the stop buffer.

Keeping these as pure array functions (rather than a stateful detector) makes the
causality guarantee a property of the *loop*, not hidden inside the detector —
which is exactly what ``tests/test_causality.py`` pins down.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(df: pd.DataFrame) -> pd.Series:
    """Wilder True Range = max(H-L, |H-prevC|, |L-prevC|), per bar.

    The first bar has no previous close, so its TR is just ``High - Low``.
    Causal: bar ``t`` uses only bars ``t`` and ``t-1``.
    """
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    tr.iloc[0] = high.iloc[0] - low.iloc[0]
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Causal ATR as the simple rolling mean of True Range over ``period`` bars.

    ``atr[t]`` uses TR of bars ``t-period+1 .. t`` (all <= t), so it is known at
    the close of bar ``t`` — exactly when an entry decision is taken. Uses
    ``min_periods=1`` so early bars still get a (shorter-window) value rather
    than NaN.
    """
    return true_range(df).rolling(period, min_periods=1).mean()


def swing_points(
    high: pd.Series, low: pd.Series, back: int, forward: int | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """Label ``(back, forward)``-candle swing highs and lows.

    Bar ``i`` is a swing high if ``High[i]`` is strictly greater than the highs
    of the ``back`` candles before it AND the ``forward`` candles after it; a
    swing low is the mirror on lows. This is the **asymmetric** pivot the
    reference strategy uses ("six candles back, two forward" etc.) — the chart
    weights more history (``back``) but confirms quickly (``forward`` candles).
    ``forward=None`` falls back to a symmetric ``back``-bar fractal.

    Returns two boolean arrays aligned to the bar index. **These labels peek
    ``forward`` bars into the future by construction** — the caller MUST add the
    ``forward``-bar confirmation lag (only trust ``is_swing_*[t-forward]`` at
    bar ``t``).

    Vectorized via rolling window maxima/minima; edge bars get NaN neighbour
    extremes, so the strict comparison yields ``False`` (never a pivot).
    """
    if forward is None:
        forward = back
    h = high.to_numpy(dtype=float)
    lo = low.to_numpy(dtype=float)
    hs = pd.Series(h)
    ls = pd.Series(lo)
    # left side: extremes of the `back` bars strictly before i
    left_hi = hs.rolling(back).max().shift(1).to_numpy()
    left_lo = ls.rolling(back).min().shift(1).to_numpy()
    # right side: extremes of the `forward` bars strictly after i (rolling on reverse)
    right_hi = hs[::-1].rolling(forward).max().shift(1)[::-1].to_numpy()
    right_lo = ls[::-1].rolling(forward).min().shift(1)[::-1].to_numpy()
    is_high = (h > left_hi) & (h > right_hi)   # NaN comparisons -> False at edges
    is_low = (lo < left_lo) & (lo < right_lo)
    return is_high, is_low
