"""Liquidity-sweep detection (spec Teil 1, step 2) as a causal state machine.

A *bullish* sweep: a bar trades with its **Low below** a confirmed swing low (a
wick that grabs the liquidity resting under the level), and within ``K`` bars the
price **closes back above** that level (the level is "reclaimed"). The lowest
point reached during the excursion is ``sweep_low`` (the wick) and becomes the
stop reference. The bearish sweep is the mirror (wick above a swing high, then a
close back below within ``K``).

This module only handles the *sweep + reclaim* part. Assembling it with the
subsequent break-of-structure into a tradeable setup lives in ``signals.py``.

The state machine is intentionally tiny and side-effect free per ``step`` so the
look-ahead test can drive it bar by bar and confirm no repainting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SweepState(Enum):
    IDLE = "idle"          # no active sweep
    SWEPT = "swept"        # wick beyond the level, waiting for a reclaim close
    RECLAIMED = "reclaimed"  # reclaimed within K bars, waiting for BOS


@dataclass
class BullSweep:
    """Tracks a bullish liquidity sweep of a confirmed swing low.

    ``level`` is the swept swing-low price; ``sweep_low`` is the running minimum
    wick during the excursion (frozen once reclaimed); ``bars_since`` counts bars
    since the sweep bar (the sweep bar itself is 0).
    """

    state: SweepState = SweepState.IDLE
    level: float = field(default=float("nan"))
    sweep_low: float = field(default=float("nan"))
    bars_since: int = 0

    def step(self, high: float, low: float, close: float,
             swing_low: float | None, k: int) -> bool:
        """Advance one bar. Returns True on the bar a reclaim completes.

        Args:
            high/low/close: current bar OHLC pieces.
            swing_low: most recent *confirmed* swing-low price, or None.
            k: reclaim window in bars (the sweep bar counts as bar 0, so a
               reclaim is allowed on bars 0..k-1).
        """
        if self.state == SweepState.SWEPT:
            self.bars_since += 1
            self.sweep_low = min(self.sweep_low, low)
            if close > self.level:                     # reclaim close
                self.state = SweepState.RECLAIMED
                return True
            if self.bars_since >= k:                   # window expired -> abort
                self.reset()
            return False

        if self.state == SweepState.IDLE:
            if swing_low is not None and low < swing_low:
                # Arm a sweep of the most recent confirmed swing low.
                self.level = swing_low
                self.sweep_low = low
                self.bars_since = 0
                if close > swing_low:                  # one-bar sweep+reclaim
                    self.state = SweepState.RECLAIMED
                    return True
                self.state = SweepState.SWEPT
            return False

        return False  # RECLAIMED is driven by signals.py, not here

    def reset(self) -> None:
        self.state = SweepState.IDLE
        self.level = float("nan")
        self.sweep_low = float("nan")
        self.bars_since = 0


@dataclass
class BearSweep:
    """Mirror of :class:`BullSweep` for a sweep of a confirmed swing high."""

    state: SweepState = SweepState.IDLE
    level: float = field(default=float("nan"))
    sweep_high: float = field(default=float("nan"))
    bars_since: int = 0

    def step(self, high: float, low: float, close: float,
             swing_high: float | None, k: int) -> bool:
        if self.state == SweepState.SWEPT:
            self.bars_since += 1
            self.sweep_high = max(self.sweep_high, high)
            if close < self.level:
                self.state = SweepState.RECLAIMED
                return True
            if self.bars_since >= k:
                self.reset()
            return False

        if self.state == SweepState.IDLE:
            if swing_high is not None and high > swing_high:
                self.level = swing_high
                self.sweep_high = high
                self.bars_since = 0
                if close < swing_high:
                    self.state = SweepState.RECLAIMED
                    return True
                self.state = SweepState.SWEPT
            return False

        return False

    def reset(self) -> None:
        self.state = SweepState.IDLE
        self.level = float("nan")
        self.sweep_high = float("nan")
        self.bars_since = 0
