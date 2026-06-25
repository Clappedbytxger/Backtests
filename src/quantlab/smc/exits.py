"""Exit management (spec Teil 1, Exit-Logik) — bar-by-bar, look-ahead-free.

Two regimes, fixed per asset before the run:

* :class:`TrailingStop` — the default for every asset except GBPUSD. Step the
  stop up in 1R increments: on reaching ``entry + nR`` the stop moves to
  ``entry + (n-1)R`` (so +1R -> break-even, +2R -> +1R, ...). No take-profit;
  the trade ends only when the trailed stop is hit.
* :class:`Fixed1R` — GBPUSD only. Take-profit at ``entry + 1R`` (full exit),
  stop fixed at the initial level.

**Intrabar convention (conservative, look-ahead-free).** Within one bar we first
test whether the *current* stop (set from prior bars) was hit; only if not do we
let the bar's extreme ratchet the stop for *future* bars. If a bar would both
reach the next R-level and breach the current stop, the stop is treated as hit
first. Gaps through the stop fill at the bar open (you cannot do better than the
gap), never at the stop price.

Each ``update`` returns ``None`` while the position stays open, or an
``ExitFill`` (price + reason) on the bar the position closes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExitFill:
    price: float       # realized exit price (gross, before slippage/commission)
    reason: str        # "stop", "trail", "target"
    r_locked: int      # R-levels locked at exit (diagnostic)


class TrailingStop:
    """1R-step trailing stop for one open position.

    Args:
        direction: +1 long, -1 short.
        entry: entry price.
        r: risk per trade in price units (``entry - stop`` for a long, > 0).
    """

    def __init__(self, direction: int, entry: float, r: float,
                 lock_on_close: bool = False):
        self.dir = direction
        self.entry = entry
        self.r = r
        self.locked = 0                       # number of R-levels locked in
        self.stop = entry - direction * r     # initial stop = entry - 1R (signed)
        # lock_on_close: ratchet the stop only when a bar CLOSES beyond the next
        # R-level (vs. when its wick merely touches it). Touching on the wick
        # ratchets the trailed stop up fast and a normal pullback then exits the
        # trade — capping winners on strongly trending assets. Locking on close
        # keeps the stop further from price and lets trends run.
        self.lock_on_close = lock_on_close

    def _stop_for_locked(self, locked: int) -> float:
        # locked=0 -> initial stop (entry-1R); locked=1 -> break-even; locked=2 -> entry+1R ...
        return self.entry + self.dir * (locked - 1) * self.r

    def update(self, high: float, low: float, open_: float,
               close: float | None = None) -> ExitFill | None:
        # 1) Stop check FIRST, against the stop set from prior bars (conservative).
        if self.dir == 1:
            if low <= self.stop:
                fill = min(open_, self.stop)          # gap fills worse than stop
                return ExitFill(fill, "trail" if self.locked > 0 else "stop", self.locked)
        else:
            if high >= self.stop:
                fill = max(open_, self.stop)
                return ExitFill(fill, "trail" if self.locked > 0 else "stop", self.locked)

        # 2) Not stopped out: ratchet using this bar's favourable extreme (wick)
        #    or its close. The new, higher stop only governs FUTURE bars.
        if self.lock_on_close and close is not None:
            favourable = close
        else:
            favourable = high if self.dir == 1 else low
        reached = self.dir * (favourable - self.entry) / self.r  # R-multiple reached
        n = int(reached)                                 # floor of R-multiple, >=0
        if n >= 1 and n > self.locked:
            self.locked = n
            self.stop = self._stop_for_locked(self.locked)
        return None


class Fixed1R:
    """Fixed take-profit at +1R with a fixed initial stop (GBPUSD)."""

    def __init__(self, direction: int, entry: float, r: float):
        self.dir = direction
        self.entry = entry
        self.r = r
        self.stop = entry - direction * r
        self.target = entry + direction * r

    def update(self, high: float, low: float, open_: float,
               close: float | None = None) -> ExitFill | None:
        # Stop checked before target (conservative on the ambiguous same-bar case).
        if self.dir == 1:
            if low <= self.stop:
                return ExitFill(min(open_, self.stop), "stop", 0)
            if high >= self.target:
                return ExitFill(self.target, "target", 1)   # limit fill, no gap credit
        else:
            if high >= self.stop:
                return ExitFill(max(open_, self.stop), "stop", 0)
            if low <= self.target:
                return ExitFill(self.target, "target", 1)
        return None
