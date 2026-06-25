"""SMC liquidity-sweep + break-of-structure strategy engine (strategy 0069).

Causal, look-ahead-free implementation of the spec in SMC-SWEEP-BOS-SPEC.md:
swing structure (:mod:`structure`), liquidity sweeps (:mod:`sweep`), setup
assembly (:mod:`signals`), exit management (:mod:`exits`) and the event-loop
backtester (:mod:`smc_backtest`).
"""

from .smc_backtest import SmcCosts, run_smc_backtest
from .signals import Setup, SetupDetector
from .exits import ExitFill, Fixed1R, TrailingStop
from .structure import atr, swing_points, true_range

__all__ = [
    "SmcCosts",
    "run_smc_backtest",
    "Setup",
    "SetupDetector",
    "ExitFill",
    "Fixed1R",
    "TrailingStop",
    "atr",
    "swing_points",
    "true_range",
]
