"""Robustness lab: Monte-Carlo, walk-forward and reality-check tools.

Consolidates the new path-aware tools with the existing single-stream battery in
:mod:`quantlab.significance` (permutation, bootstrap CI, Deflated Sharpe) and the
CPCV/PBO machinery in :mod:`quantlab.cpcv`, so a strategy's full robustness review
is one import.
"""

from ..significance import (
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)
from .monte_carlo import block_bootstrap_paths, mc_metrics
from .reality_check import whites_reality_check
from .walk_forward import walk_forward

__all__ = [
    # new (path-aware)
    "mc_metrics", "block_bootstrap_paths", "walk_forward", "whites_reality_check",
    # re-exported single-stream battery
    "permutation_test", "bootstrap_ci", "deflated_sharpe_ratio", "t_test_mean_return",
]
