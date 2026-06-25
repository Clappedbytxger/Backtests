"""quantlab — a small, reusable framework for quantitative backtesting research.

Public API re-exports the most-used functions so notebooks can simply do
``from quantlab import run_backtest, compute_metrics, ...``.
"""

from . import (
    attribution, commodity_features, costs, cot_data, cpcv, cross_sectional,
    crypto_features, crypto_xsection, data, edgar_data, execution, feature_store,
    features, fundamental_data, futures_curve, ic, metrics, ml_portfolio, overlay,
    pairs, plotting, regime, roll, seasonal, significance,
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
from .feature_store import (
    FeatureStore,
    REGISTRY as FEATURE_REGISTRY,
    compute_features,
    validate_no_lookahead,
)
from .attribution import (
    brinson_fachler,
    classify_quadrant,
    factor_regression,
    rolling_factor,
)
from .execution import (
    SlippageLedger,
    SlippageModel,
    adaptive_cost_components,
    corwin_schultz_spread,
    implementation_shortfall,
    liquidity_gauge,
    run_adaptive_backtest,
    square_root_impact,
)
from .ic import score_feature, print_scorecard, ic_decay, ic_permutation_test
from .metrics import compute_metrics, trade_stats
from .overlay import build_seasonal_overlay
from .pairs import (
    PairStats,
    backtest_pair,
    correlation_prefilter,
    engle_granger,
    half_life,
    scan_pairs,
    signal_from_z,
    signal_series,
    zscore,
)
from .regime import (
    REGIME_COLORS,
    REGIME_LABELS,
    REGIMES,
    RegimeConfig,
    classify,
    current_regime,
    regime_distribution,
    regime_performance,
    segments,
)
from .roll import roll_exclusion_test
from .significance import (
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

__all__ = [
    # modules
    "attribution", "commodity_features", "cot_data", "cpcv", "crypto_features",
    "crypto_xsection", "data", "edgar_data", "execution", "feature_store",
    "metrics", "costs", "cross_sectional", "features", "fundamental_data",
    "futures_curve", "ic", "ml_portfolio", "overlay", "pairs", "plotting",
    "regime", "roll", "seasonal", "significance",
    # performance attribution
    "factor_regression", "rolling_factor", "brinson_fachler", "classify_quadrant",
    # feature store
    "FeatureStore", "FEATURE_REGISTRY", "compute_features", "validate_no_lookahead",
    # execution / slippage
    "SlippageModel", "SlippageLedger", "run_adaptive_backtest",
    "adaptive_cost_components", "corwin_schultz_spread", "square_root_impact",
    "implementation_shortfall", "liquidity_gauge",
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
    # market-regime engine
    "classify", "current_regime", "segments", "regime_distribution",
    "regime_performance", "RegimeConfig", "REGIMES", "REGIME_LABELS", "REGIME_COLORS",
    # cointegration / pairs trading
    "scan_pairs", "engle_granger", "correlation_prefilter", "half_life", "zscore",
    "signal_from_z", "signal_series", "backtest_pair", "PairStats",
    # significance
    "permutation_test", "bootstrap_ci", "deflated_sharpe_ratio", "t_test_mean_return",
]
