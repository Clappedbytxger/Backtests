"""Adapter that runs an :class:`IStrategy` through the vectorized engine.

The runner is intentionally thin: it builds the strategy's target weights and
hands them to the existing, look-ahead-safe :func:`quantlab.backtest.run_backtest`
— the engine is never reimplemented. The same ``IStrategy`` object also drives
the live path, so a backtested strategy and its live deployment cannot diverge in
signal logic.
"""

from __future__ import annotations

import pandas as pd

from ..backtest import run_backtest
from ..costs import CostModel
from .base import IStrategy


def backtest_strategy(
    strategy: IStrategy,
    prices: pd.DataFrame,
    cost_model: CostModel | None = None,
    **kwargs,
) -> dict:
    """Backtest an :class:`IStrategy` on a single instrument's OHLC frame.

    Args:
        strategy: the strategy object (same one used live).
        prices: OHLCV DataFrame with a ``Close`` column, datetime-indexed.
        cost_model: transaction-cost model (defaults to IBKR tiered in the engine).
        **kwargs: forwarded to :func:`run_backtest` (e.g. ``representative_price``).

    Returns:
        The :func:`run_backtest` result dict (returns, equity, trades, ...).
    """
    signal = strategy.target_weights(prices)
    return run_backtest(prices, signal, cost_model=cost_model, **kwargs)
