"""Setup assembly (spec Teil 1, steps 1-6 + Teil 4 step 3).

:class:`SetupDetector` streams over bars and emits a :class:`Setup` on the bar a
break-of-structure confirms a reclaimed sweep. It owns the *causal* structure
state:

* most-recent **confirmed** swing high/low, where a pivot at bar ``i`` is only
  admitted at bar ``i+N`` (the confirmation lag from :mod:`structure`);
* a bullish and a bearish :mod:`sweep` state machine running in parallel;
* the wait for a BOS close beyond the most recent confirmed opposite swing.

Bullish flow: sweep a confirmed swing low -> reclaim within ``K`` -> a later bar
**closes above** the most recent confirmed swing high (BOS) -> emit a long setup
(entry = BOS close, stop = ``sweep_low - buffer``). Bearish is the mirror.

A reclaimed setup is invalidated if price closes back beyond the swept wick
before the BOS (structure failed), which bounds how long a pending setup lingers.

The detector is direction-agnostic; the per-asset direction filter (SPX/NDX
long-only) is applied by the backtest, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .sweep import BearSweep, BullSweep, SweepState


@dataclass
class Setup:
    """A confirmed, tradeable setup at its BOS bar."""

    bar_index: int        # index of the BOS bar (entry bar, Variant A close)
    direction: int        # +1 long, -1 short
    entry: float          # entry price = close of the BOS bar
    stop: float           # sweep_low - buffer (long) / sweep_high + buffer (short)
    sweep_extreme: float  # the swept wick (sweep_low / sweep_high)
    swing_ref: float      # the broken swing high/low (BOS reference)
    r: float              # entry - stop (long) / stop - entry (short), > 0


class SetupDetector:
    """Streaming, causal detector. Feed bars in order via :meth:`update`."""

    def __init__(self, n: int, k: int, buffer_mult: float,
                 require_structure: bool = True):
        self.n = n
        self.k = k
        self.buffer_mult = buffer_mult
        # require_structure: BOS must break a swing that genuinely sits BEYOND the
        # reclaim (a real pending structure), with the reference FROZEN at reclaim
        # time. Without it, the "most recent swing" is often already exceeded by
        # price, so a setup fires on nearly every reclaimed sweep (trivial break,
        # over-generation). Frozen-from-past data => still look-ahead-free.
        self.require_structure = require_structure
        self.recent_swing_high: float | None = None
        self.recent_swing_low: float | None = None
        self.bull = BullSweep()
        self.bear = BearSweep()
        self.bull_bos_ref: float | None = None
        self.bear_bos_ref: float | None = None

    def update(
        self,
        i: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        atr: float,
        new_swing_high: float | None,
        new_swing_low: float | None,
    ) -> Setup | None:
        """Advance one bar; return a :class:`Setup` if a BOS confirms here.

        Args:
            i: bar index (into the asset frame).
            open_/high/low/close: current bar OHLC.
            atr: causal ATR at this bar (for the stop buffer).
            new_swing_high/new_swing_low: a swing price that becomes *confirmed*
                on this bar (i.e. the pivot at ``i-n`` was a fractal), else None.
                The caller supplies these so the n-bar lag is explicit.
        """
        # 1) Admit newly *confirmed* swings as the live structure references.
        if new_swing_high is not None:
            self.recent_swing_high = new_swing_high
        if new_swing_low is not None:
            self.recent_swing_low = new_swing_low

        emitted: Setup | None = None

        # 2) Bullish branch: sweep+reclaim of a swing low, then BOS over swing high.
        if self.bull.state == SweepState.RECLAIMED:
            ref = self.bull_bos_ref if self.require_structure else self.recent_swing_high
            if close < self.bull.sweep_low or ref is None:   # structure gone -> dead
                self.bull.reset(); self.bull_bos_ref = None
            elif close > ref:
                stop = self.bull.sweep_low - self.buffer_mult * atr
                r = close - stop
                if r > 0:
                    emitted = Setup(i, +1, close, stop, self.bull.sweep_low, ref, r)
                self.bull.reset(); self.bull_bos_ref = None
        else:
            if self.bull.step(high, low, close, self.recent_swing_low, self.k):
                # reclaim just happened: freeze the BOS reference (pre-sweep high)
                ref = self.recent_swing_high
                if self.require_structure and (ref is None or ref <= close):
                    self.bull.reset()                        # no structure above
                    self.bull_bos_ref = None
                else:
                    self.bull_bos_ref = ref

        # 3) Bearish branch (mirror). Only one setup per bar; bull takes priority
        #    if both fire (rare; per-asset direction filter usually excludes one).
        if self.bear.state == SweepState.RECLAIMED:
            ref = self.bear_bos_ref if self.require_structure else self.recent_swing_low
            if close > self.bear.sweep_high or ref is None:
                self.bear.reset(); self.bear_bos_ref = None
            elif close < ref:
                stop = self.bear.sweep_high + self.buffer_mult * atr
                r = stop - close
                if r > 0 and emitted is None:
                    emitted = Setup(i, -1, close, stop, self.bear.sweep_high, ref, r)
                self.bear.reset(); self.bear_bos_ref = None
        else:
            if self.bear.step(high, low, close, self.recent_swing_high, self.k):
                ref = self.recent_swing_low
                if self.require_structure and (ref is None or ref >= close):
                    self.bear.reset()
                    self.bear_bos_ref = None
                else:
                    self.bear_bos_ref = ref

        return emitted
