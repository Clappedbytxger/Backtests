"""quantlab — a small, reusable framework for quantitative backtesting research.

Public API re-exports the most-used functions so notebooks can simply do
``from quantlab import run_backtest, compute_metrics, ...``.
"""

from . import costs, data, metrics, overlay, plotting, roll, seasonal, significance
from .backtest import run_backtest
from .costs import (
    CostModel,
    IBKR_DEFAULT,
    IBKR_FUTURES,
    IBKR_LIQUID_ETF,
    IBKR_ILLIQUID,
    MES_INTRADAY,
    MNQ_INTRADAY,
)
from .metrics import compute_metrics, trade_stats
from .overlay import build_seasonal_overlay
from .roll import roll_exclusion_test
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
    "overlay",
    "plotting",
    "roll",
    "seasonal",
    "significance",
    "run_backtest",
    "compute_metrics",
    "trade_stats",
    "build_seasonal_overlay",
    "roll_exclusion_test",
    "CostModel",
    "IBKR_DEFAULT",
    "IBKR_FUTURES",
    "IBKR_LIQUID_ETF",
    "IBKR_ILLIQUID",
    "MES_INTRADAY",
    "MNQ_INTRADAY",
    "permutation_test",
    "bootstrap_ci",
    "deflated_sharpe_ratio",
    "t_test_mean_return",
]
