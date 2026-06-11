"""Regression tests for significance tools — focus on the DSR fix.

Guards against the two degeneracies the old Deflated Sharpe had:
  * n_trials=1 forced DSR=1.0 (z(0)=-inf benchmark) for every forward test;
  * a hard-coded trial variance of 1.0 (wrong scale for per-period Sharpes)
    crushed every screened effect to DSR~0.
The metric must instead vary monotonically with the observed Sharpe.
"""

import numpy as np
import pandas as pd

from quantlab.significance import deflated_sharpe_ratio


def _series(per_period_sharpe: float, n: int = 500, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, 1.0, n)
    r = (r - r.mean()) / r.std()
    return pd.Series(r + per_period_sharpe)  # mean=sp, std~1 => per-period Sharpe ~sp


def test_single_trial_is_not_mechanically_one():
    """n_trials=1 must give a graded PSR-vs-zero, not a constant 1.0."""
    weak = deflated_sharpe_ratio(0.02, n_obs=500, n_trials=1, returns=_series(0.02))
    strong = deflated_sharpe_ratio(0.10, n_obs=500, n_trials=1, returns=_series(0.10))
    assert weak["expected_max_sharpe_under_null"] == 0.0
    assert weak["psr_deflated"] < strong["psr_deflated"]
    assert strong["psr_deflated"] < 1.0


def test_screen_benchmark_is_on_per_period_scale():
    """With many trials the null benchmark must stay near per-period Sharpe size,
    not blow up to ~2.6 as the old V=1.0 default did."""
    d = deflated_sharpe_ratio(0.08, n_obs=500, n_trials=121, returns=_series(0.08))
    assert 0.0 < d["expected_max_sharpe_under_null"] < 0.5


def test_screen_is_graded_not_binary():
    """A weak screened effect should be penalized; a strong one should clear."""
    weak = deflated_sharpe_ratio(0.03, n_obs=500, n_trials=121, returns=_series(0.03))
    strong = deflated_sharpe_ratio(0.13, n_obs=500, n_trials=121, returns=_series(0.13))
    assert weak["psr_deflated"] < 0.5 < strong["psr_deflated"]


def test_more_trials_lower_dsr():
    """Holding the observed Sharpe fixed, more trials = harder bar = lower DSR."""
    r = _series(0.09)
    few = deflated_sharpe_ratio(0.09, n_obs=500, n_trials=10, returns=r)
    many = deflated_sharpe_ratio(0.09, n_obs=500, n_trials=500, returns=r)
    assert many["psr_deflated"] < few["psr_deflated"]


def test_empirical_trial_variance_is_used():
    """Passing the real trial-Sharpe dispersion overrides the analytic fallback."""
    trials = np.random.default_rng(1).normal(0.0, 0.05, 121)
    d = deflated_sharpe_ratio(
        0.12, n_obs=500, n_trials=121, returns=_series(0.12), trial_sharpes=trials
    )
    assert abs(d["sharpe_variance_used"] - np.var(trials, ddof=1)) < 1e-9
