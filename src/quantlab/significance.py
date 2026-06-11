"""Statistical significance tests — separating real edge from luck.

Because we test many strategies, a good-looking backtest can easily be noise.
These tools quantify how likely the result is under the null hypothesis of
"no edge", and correct for multiple testing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .metrics import sharpe_ratio


def t_test_mean_return(returns: pd.Series) -> dict:
    """One-sample t-test that mean per-period return != 0.

    Returns the t-statistic and two-sided p-value. A small p-value means the
    average return is unlikely to be zero by chance (but says nothing about
    economic significance after costs).
    """
    r = returns.dropna()
    t_stat, p_value = stats.ttest_1samp(r, 0.0)
    return {"t_stat": float(t_stat), "p_value": float(p_value), "n": int(r.shape[0])}


def permutation_test(
    strategy_returns: pd.Series,
    asset_returns: pd.Series,
    position: pd.Series,
    n_perm: int = 2000,
    metric: str = "sharpe",
    seed: int | None = 42,
) -> dict:
    """Monte-Carlo permutation test against random timing.

    Keeps the realized *position sizes* but randomly shuffles **when** they are
    applied, destroying any genuine timing skill while preserving the marginal
    distribution of positions and asset returns. The p-value is the fraction of
    random reshuffles whose metric is >= the real strategy's metric.

    Args:
        strategy_returns: realized net (or gross) strategy returns.
        asset_returns: the underlying asset's per-period returns.
        position: the held position series (already shifted) used by the strategy.
        n_perm: number of random permutations.
        metric: ``"sharpe"`` or ``"mean"``.
        seed: RNG seed for reproducibility.

    Returns:
        dict with the observed metric, the permutation p-value and the random
        distribution's mean/std for context.
    """
    rng = np.random.default_rng(seed)
    asset = asset_returns.reindex(position.index).fillna(0.0).values
    pos = position.values

    def score(series: np.ndarray) -> float:
        s = pd.Series(series)
        if metric == "sharpe":
            return sharpe_ratio(s)
        return float(s.mean())

    observed = score(strategy_returns.values)

    null_scores = np.empty(n_perm)
    for i in range(n_perm):
        shuffled = rng.permutation(pos)
        null_scores[i] = score(shuffled * asset)

    p_value = float((np.sum(null_scores >= observed) + 1) / (n_perm + 1))
    return {
        "observed": float(observed),
        "p_value": p_value,
        "null_mean": float(np.mean(null_scores)),
        "null_std": float(np.std(null_scores)),
        "n_perm": n_perm,
        "metric": metric,
    }


def bootstrap_ci(
    returns: pd.Series,
    statistic: str = "sharpe",
    n_boot: int = 2000,
    alpha: float = 0.05,
    seed: int | None = 42,
) -> dict:
    """Bootstrap confidence interval for Sharpe or CAGR.

    Resamples returns with replacement to estimate sampling uncertainty.
    A CI that comfortably excludes 0 is reassuring.
    """
    rng = np.random.default_rng(seed)
    r = returns.dropna().values
    n = len(r)
    stats_arr = np.empty(n_boot)
    for i in range(n_boot):
        sample = pd.Series(rng.choice(r, size=n, replace=True))
        if statistic == "sharpe":
            stats_arr[i] = sharpe_ratio(sample)
        else:  # mean per-period return
            stats_arr[i] = sample.mean()
    lo = float(np.percentile(stats_arr, 100 * alpha / 2))
    hi = float(np.percentile(stats_arr, 100 * (1 - alpha / 2)))
    return {
        "statistic": statistic,
        "point": float(np.mean(stats_arr)),
        "ci_low": lo,
        "ci_high": hi,
        "alpha": alpha,
    }


def deflated_sharpe_ratio(
    observed_sharpe: float,
    n_obs: int,
    n_trials: int,
    returns: pd.Series | None = None,
    sharpe_variance_across_trials: float | None = None,
    trial_sharpes: "np.ndarray | pd.Series | list | None" = None,
) -> dict:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).

    Corrects an observed Sharpe for:
      * the number of strategy variants tried (``n_trials``), because the best
        of many random strategies looks good by chance;
      * non-normal returns (skew/kurtosis) when ``returns`` is provided.

    Returns the probability that the true Sharpe exceeds the selection-adjusted
    benchmark (``psr_deflated``). Near 1 = robust edge; near 0.5 or below =
    consistent with selection luck.

    **Scale contract.** ``observed_sharpe``, ``n_obs`` and the trial-Sharpe
    variance must all be on the *same* time base — pass the raw **per-period**
    (non-annualized) Sharpe, ``n_obs = len(returns)``, and per-period trial
    Sharpes. Mixing an annualized observed Sharpe with a per-period ``n_obs``
    double-counts the √(periods/yr) factor.

    Benchmark (``SR*`` = expected max Sharpe under the null):
      * ``n_trials <= 1`` (single pre-committed test): ``SR* = 0`` — the DSR
        reduces to the plain Probabilistic Sharpe Ratio against zero. (The old
        code evaluated ``z(1 - 1/1) = z(0) = -inf`` here, forcing DSR = 1.0 for
        *every* forward test regardless of edge.)
      * ``n_trials > 1``: ``SR* = sqrt(V) * E[max of n_trials std-normals]``,
        where ``V`` is the variance of the per-period trial Sharpes. ``V`` is
        taken from ``trial_sharpes`` if given (preferred — the real screen
        dispersion), else ``sharpe_variance_across_trials``, else an analytic
        null fallback ``1/(n_obs-1)`` (the sampling variance of a per-period
        Sharpe estimator under SR≈0). The old hard-coded ``V = 1.0`` was on the
        wrong scale for per-period Sharpes (~0.05), inflating ``SR*`` to ~2.6
        and crushing every screened effect to DSR ≈ 0.
    """
    euler_mascheroni = 0.5772156649
    z = stats.norm.ppf

    if n_trials <= 1:
        # Single pre-committed test => no selection to deflate; PSR vs zero.
        expected_max_sharpe = 0.0
        var = float("nan")
    else:
        if trial_sharpes is not None:
            arr = np.asarray(trial_sharpes, dtype=float)
            arr = arr[np.isfinite(arr)]
            var = float(np.var(arr, ddof=1)) if arr.size > 1 else 1.0 / max(n_obs - 1, 1)
        elif sharpe_variance_across_trials is not None:
            var = float(sharpe_variance_across_trials)
        else:
            # Analytic null: Var(SR_hat) ≈ 1/(n_obs-1) for a per-period Sharpe.
            var = 1.0 / max(n_obs - 1, 1)
        max_z = (1 - euler_mascheroni) * z(1 - 1.0 / n_trials) + euler_mascheroni * z(
            1 - 1.0 / (n_trials * np.e)
        )
        expected_max_sharpe = np.sqrt(var) * max_z

    skew = 0.0
    kurt = 3.0  # non-excess kurtosis of a normal; correct PSR default
    if returns is not None:
        r = returns.dropna()
        skew = float(stats.skew(r))
        kurt = float(stats.kurtosis(r, fisher=False))  # non-excess kurtosis

    # Probabilistic Sharpe Ratio of observed vs the benchmark (expected max).
    numerator = (observed_sharpe - expected_max_sharpe) * np.sqrt(max(n_obs - 1, 1))
    denominator = np.sqrt(
        1 - skew * observed_sharpe + (kurt - 1) / 4.0 * observed_sharpe**2
    )
    dsr = float(stats.norm.cdf(numerator / denominator)) if denominator > 0 else float("nan")

    return {
        "observed_sharpe": float(observed_sharpe),
        "expected_max_sharpe_under_null": float(expected_max_sharpe),
        "sharpe_variance_used": float(var),
        "n_trials": int(n_trials),
        "psr_deflated": dsr,
    }
