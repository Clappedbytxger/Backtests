"""White's Reality Check for data-snooping across many candidate strategies.

When you pick the *best* of N strategies, its performance is upward-biased by the
search. White's Reality Check (Econometrica, 2000) tests H0: the best strategy
does not beat the benchmark, accounting for the full set of N. It bootstraps the
joint distribution of the N strategies' excess returns (moving-block, to preserve
autocorrelation) and compares the observed max statistic to its bootstrap null.

Complements :func:`quantlab.significance.deflated_sharpe_ratio` (which deflates a
single Sharpe for the number of trials) by working directly on the N return
streams and their cross-correlation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _moving_block_rows(T: int, block: int, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    n_blocks = int(np.ceil(T / block))
    starts = rng.integers(0, T, size=(n_boot, n_blocks))
    idx = (starts[..., None] + np.arange(block)) % T
    return idx.reshape(n_boot, n_blocks * block)[:, :T]


def whites_reality_check(returns_matrix, block: int = 10, n_boot: int = 2000, seed: int = 0) -> dict:
    """White's Reality Check across N strategies.

    Args:
        returns_matrix: ``T x N`` array/DataFrame of each strategy's **excess**
            returns over the benchmark (use raw returns if the benchmark is cash/0).
        block: moving-block length (preserves serial dependence).
        n_boot: bootstrap resamples.
        seed: RNG seed (deterministic).

    Returns:
        dict with ``p_value`` (data-snooping-adjusted), ``best_strategy`` (column
        index), ``best_mean``, the observed statistic ``V`` and ``n_strategies``.
    """
    f = np.asarray(returns_matrix, dtype=float)
    if f.ndim != 2:
        raise ValueError("returns_matrix must be 2-D (T x N)")
    T, N = f.shape
    fbar = f.mean(axis=0)
    V_per = np.sqrt(T) * fbar
    V = float(V_per.max())
    best = int(np.argmax(fbar))

    rng = np.random.default_rng(seed)
    rows = _moving_block_rows(T, max(1, min(block, T)), n_boot, rng)
    v_star = np.empty(n_boot)
    for b in range(n_boot):
        fb = f[rows[b]]                       # T x N resample
        v_star[b] = (np.sqrt(T) * (fb.mean(axis=0) - fbar)).max()

    return {
        "p_value": float(np.mean(v_star >= V)),
        "best_strategy": best,
        "best_mean": float(fbar[best]),
        "V": V,
        "n_strategies": int(N),
    }
