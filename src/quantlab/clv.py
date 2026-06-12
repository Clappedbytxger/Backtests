"""Closing Line Value: the per-bet skill metric of value betting.

CLV of a bet = ``bet_odds * fair_close_prob - 1`` — how much better the taken
odds were than the de-vigged (Pinnacle) closing line. The closing line is the
best public predictor of outcome probabilities, so a positive median CLV over
many bets evidences skill long before realised P&L escapes its variance.
This is the betting equivalent of the repo's permutation tests: per-bet,
immediate, high-N.
"""

from __future__ import annotations

import numpy as np


def clv(bet_odds: np.ndarray, fair_close_prob: np.ndarray) -> np.ndarray:
    """CLV per bet vs the de-vigged closing line (0.02 = 2% better than close)."""
    return np.asarray(bet_odds, float) * np.asarray(fair_close_prob, float) - 1.0


def clv_summary(
    clv_values: np.ndarray,
    n_boot: int = 10_000,
    seed: int = 0,
) -> dict:
    """Median/mean CLV with a bootstrap CI on the median.

    Returns ``n``, ``median``, ``mean``, ``frac_positive`` and the 95%
    bootstrap CI of the median (``median_ci_low/high``). The proof bar is a
    CI that excludes 0.
    """
    x = np.asarray(clv_values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return {"n": 0}

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    boot_medians = np.median(x[idx], axis=1)

    return {
        "n": int(len(x)),
        "median": float(np.median(x)),
        "mean": float(np.mean(x)),
        "frac_positive": float((x > 0).mean()),
        "median_ci_low": float(np.percentile(boot_medians, 2.5)),
        "median_ci_high": float(np.percentile(boot_medians, 97.5)),
    }
