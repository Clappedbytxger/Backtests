"""quantlab — a small, reusable framework for quantitative backtesting research.

Public API re-exports the most-used functions so notebooks can simply do
``from quantlab import run_backtest, compute_metrics, ...``.
"""

from . import costs, data, metrics, plotting, seasonal, significance
from .backtest import run_backtest
from .costs import CostModel, IBKR_DEFAULT, IBKR_LIQUID_ETF, IBKR_ILLIQUID
from .metrics import compute_metrics, trade_stats
from .significance import (
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

__all__ = [
    "data",
    "metrics",
    "costs",
    "plotting",
    "seasonal",
    "significance",
    "run_backtest",
    "compute_metrics",
    "trade_stats",
    "CostModel",
    "IBKR_DEFAULT",
    "IBKR_LIQUID_ETF",
    "IBKR_ILLIQUID",
    "permutation_test",
    "bootstrap_ci",
    "deflated_sharpe_ratio",
    "t_test_mean_return",
]
