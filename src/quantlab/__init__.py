"""quantlab — a small, reusable framework for quantitative backtesting research.

Public API re-exports the most-used functions so notebooks can simply do
``from quantlab import run_backtest, compute_metrics, ...``.
"""

from . import (
    commodity_features, costs, cot_data, cpcv, cross_sectional, crypto_features,
    crypto_xsection, data, features, fundamental_data, futures_curve, ic,
    metrics, ml_portfolio, overlay, plotting, roll, seasonal, significance,
)
from .backtest import run_backtest
from .cross_sectional import (
    cross_sectional_permutation_test,
    momentum_signal,
    run_cross_sectional,
)
from .costs import (
    CostModel,
    IBKR_DEFAULT,
    IBKR_FUTURES,
    IBKR_LIQUID_ETF,
    IBKR_ILLIQUID,
    IBKR_METALS_LIQUID,
    IBKR_METALS_PGM,
    IBKR_SOFTS,
    IBKR_SOFTS_THIN,
    MES_INTRADAY,
    MNQ_INTRADAY,
)
from .features import pit_join, weather_anomaly, wasde_surprise, crop_condition_delta
from .fundamental_data import (
    REGION_COORDS,
    WASDE_COMMODITY,
    read_api_key,
    get_weather_daily,
    get_nass_crop_condition,
    get_wasde_psd,
    get_eia_series,
    get_fred_vintage,
    as_of,
    build_pit_series,
)
from .ic import score_feature, print_scorecard, ic_decay, ic_permutation_test
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
    # modules
    "commodity_features", "cot_data", "cpcv", "crypto_features",
    "crypto_xsection", "data", "metrics", "costs",
    "cross_sectional", "features", "fundamental_data", "futures_curve", "ic",
    "ml_portfolio", "overlay", "plotting", "roll", "seasonal", "significance",
    # backtest engine
    "run_backtest",
    # cross-sectional engine
    "run_cross_sectional", "momentum_signal", "cross_sectional_permutation_test",
    # metrics
    "compute_metrics", "trade_stats",
    # costs
    "CostModel",
    "IBKR_DEFAULT", "IBKR_FUTURES", "IBKR_LIQUID_ETF", "IBKR_ILLIQUID",
    "IBKR_METALS_LIQUID", "IBKR_METALS_PGM", "IBKR_SOFTS", "IBKR_SOFTS_THIN",
    "MES_INTRADAY", "MNQ_INTRADAY",
    # fundamental data loaders
    "REGION_COORDS", "WASDE_COMMODITY", "read_api_key",
    "get_weather_daily", "get_nass_crop_condition", "get_wasde_psd",
    "get_eia_series", "get_fred_vintage", "as_of", "build_pit_series",
    # features
    "pit_join", "weather_anomaly", "wasde_surprise", "crop_condition_delta",
    # IC / signal quality
    "score_feature", "print_scorecard", "ic_decay", "ic_permutation_test",
    # seasonal / overlay
    "build_seasonal_overlay", "roll_exclusion_test",
    # significance
    "permutation_test", "bootstrap_ci", "deflated_sharpe_ratio", "t_test_mean_return",
]
