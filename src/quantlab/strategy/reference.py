"""Reference :class:`IStrategy` implementations wrapping confirmed catalog strategies.

These prove the contract on real, known-good logic (and serve as templates for
promoting research scripts to the production interface). They reuse the existing
``quantlab`` signal builders — no logic is reimplemented.
"""

from __future__ import annotations

import pandas as pd

from ..seasonal import turn_of_month_signal
from .base import IStrategy


class TurnOfMonthStrategy(IStrategy):
    """Turn-of-month long overlay — catalog strategy 0050 (confirmed lead).

    Long on the last ``days_before_end`` + first ``days_after_start`` trading days
    of each month, flat otherwise. Purely calendar-driven, hence look-ahead-safe
    by construction. Macro rationale: month-end pension/fund inflows, salary
    investing and index rebalancing concentrate buying at the turn of the month.
    """

    id = "0050_turn_of_month"
    name = "Turn-of-Month (long overlay)"
    status = "confirmed"

    def __init__(
        self,
        days_before_end: int = 1,
        days_after_start: int = 3,
        instrument: str = "SPY",
    ) -> None:
        self.days_before_end = days_before_end
        self.days_after_start = days_after_start
        self.instruments = (instrument,)

    def generate_signals(self, prices: pd.DataFrame) -> pd.Series:
        return turn_of_month_signal(
            prices.index, self.days_before_end, self.days_after_start
        )
