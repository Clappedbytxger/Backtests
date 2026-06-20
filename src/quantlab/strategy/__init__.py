"""Quant-OS strategy contract: ``IStrategy`` + backtest runner + parity check.

The same ``IStrategy`` object runs in the backtest engine and live, giving
research-to-production parity. See :mod:`quantlab.strategy.base`.
"""

from .base import IStrategy
from .parity import validate_parity
from .reference import TurnOfMonthStrategy
from .runner import backtest_strategy

__all__ = ["IStrategy", "backtest_strategy", "validate_parity", "TurnOfMonthStrategy"]
