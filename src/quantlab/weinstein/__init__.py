"""Stan Weinstein Stage Analysis — Stage-2 breakout on individual stocks.

Reference: Stan Weinstein, *Secrets for Profiting in Bull and Bear Markets*.
This package implements a **daily-chart adaptation** of the canonical Stage-2
breakout (Weinstein uses the 30-*week* MA on weekly charts; here the user asked
for the 30-*day* MA on the daily chart):

* :mod:`signals` — look-ahead-safe Stage-2 entry detection: a stock breaks above
  its 30-day MA out of a Stage-1 trading range whose resistance was tested at
  least ``min_touches`` times, on expanding volume, with Mansfield relative
  strength crossing from negative to positive.
* :mod:`portfolio` — a shared-equity, multi-position event-loop backtester with
  several exit regimes (MA stop, 1R trailing, chandelier, partial+trail) and
  optional pyramiding.
"""

from .signals import (
    detect_stage2_entries,
    mansfield_rs,
    moving_average,
    EntryParams,
)
from .portfolio import (
    PortfolioConfig,
    build_orders,
    build_random_orders,
    prepare_data,
    run_portfolio,
)

__all__ = [
    "detect_stage2_entries",
    "mansfield_rs",
    "moving_average",
    "EntryParams",
    "PortfolioConfig",
    "build_orders",
    "build_random_orders",
    "prepare_data",
    "run_portfolio",
]
