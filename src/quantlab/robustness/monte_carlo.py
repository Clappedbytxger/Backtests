"""Monte-Carlo robustness via the moving-block bootstrap.

Resamples *blocks* of returns (preserving short-run autocorrelation) to build many
synthetic equity paths, then reports the distribution of path metrics — including
**max drawdown**, which is path-dependent and cannot be obtained from the i.i.d.
mean bootstrap in :mod:`quantlab.significance`. Use this to ask "how lucky was the
realized drawdown / Sharpe?" rather than just "is the mean > 0?".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ANN = np.sqrt(252.0)


def block_bootstrap_paths(returns, block: int = 20, n_paths: int = 2000, seed: int = 0) -> np.ndarray:
    """Resample ``n_paths`` synthetic return paths via the circular moving-block bootstrap.

    Returns an ``(n_paths, L)`` array, ``L`` = length of the (dropna'd) input.
    """
    r = np.asarray(pd.Series(returns).dropna(), dtype=float)
    L = len(r)
    if L < 2:
        raise ValueError("need at least 2 returns")
    block = max(1, min(block, L))
    n_blocks = int(np.ceil(L / block))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, L, size=(n_paths, n_blocks))
    idx = (starts[..., None] + np.arange(block)) % L  # circular blocks
    return r[idx.reshape(n_paths, n_blocks * block)[:, :L]]


def _path_metrics(paths: np.ndarray):
    mean = paths.mean(axis=1)
    sd = paths.std(axis=1, ddof=1)
    sharpe = np.where(sd > 0, mean / sd * ANN, 0.0)
    L = paths.shape[1]
    eq = np.cumprod(1.0 + paths, axis=1)
    cagr = eq[:, -1] ** (252.0 / L) - 1.0
    peak = np.maximum.accumulate(eq, axis=1)
    maxdd = ((eq - peak) / peak).min(axis=1)
    return sharpe, cagr, maxdd


def mc_metrics(returns, block: int = 20, n_paths: int = 2000, seed: int = 0, ci: float = 0.95) -> dict:
    """Bootstrap distribution (median + CI) of Sharpe, CAGR and max drawdown.

    Deterministic for a given ``seed``.
    """
    paths = block_bootstrap_paths(returns, block, n_paths, seed)
    sharpe, cagr, maxdd = _path_metrics(paths)
    a = (1.0 - ci) / 2.0

    def summ(x):
        return {
            "median": float(np.median(x)),
            "ci_low": float(np.quantile(x, a)),
            "ci_high": float(np.quantile(x, 1.0 - a)),
        }

    return {
        "n_paths": int(n_paths), "block": int(block), "ci": ci,
        "sharpe": summ(sharpe), "cagr": summ(cagr), "maxdd": summ(maxdd),
    }
