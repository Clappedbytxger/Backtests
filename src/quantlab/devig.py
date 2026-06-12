"""De-vigging: bookmaker decimal odds -> fair outcome probabilities.

Three standard methods, all solving "remove the overround" differently:

* ``multiplicative`` — proportional normalisation ``p_i = (1/o_i) / sum(1/o_j)``.
  Simple but keeps the favourite-longshot bias (longshots stay overpriced).
* ``shin`` — Shin (1992/1993): models the overround as protection against
  insider traders; solves the insider fraction ``z`` so probabilities sum to 1.
  Shifts more of the margin onto longshots, empirically better calibrated.
* ``power`` — solves exponent ``k`` in ``p_i = (1/o_i)^k`` with ``sum p_i = 1``.
  Margin > 0 implies ``k > 1``, which also penalises longshots.

All methods are exact identities when the book has zero margin.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

METHODS = ("multiplicative", "shin", "power")


def margin(odds: np.ndarray) -> np.ndarray:
    """Bookmaker overround ``sum(1/o_i) - 1`` (last axis = outcomes)."""
    odds = np.asarray(odds, dtype=float)
    return (1.0 / odds).sum(axis=-1) - 1.0


def _shin_row(pi: np.ndarray) -> np.ndarray:
    """Shin probabilities for one market from implied probs ``pi`` (sum > 1)."""
    b = pi.sum()

    def p_of_z(z: float) -> np.ndarray:
        return (np.sqrt(z * z + 4.0 * (1.0 - z) * pi**2 / b) - z) / (2.0 * (1.0 - z))

    # sum p(0) = sqrt(b) > 1 and sum p(z->1) < 1, so a root exists in (0, 1).
    z = brentq(lambda z: p_of_z(z).sum() - 1.0, 0.0, 1.0 - 1e-9, xtol=1e-12)
    p = p_of_z(z)
    return p / p.sum()


def _power_row(pi: np.ndarray) -> np.ndarray:
    """Power-method probabilities ``pi**k`` with k solved so they sum to 1."""
    # sum(pi**k) is strictly decreasing in k for pi in (0,1).
    k = brentq(lambda k: np.sum(pi**k) - 1.0, 1e-6, 100.0, xtol=1e-12)
    return pi**k


def devig(odds: np.ndarray, method: str = "shin") -> np.ndarray:
    """Convert decimal odds to fair probabilities.

    Args:
        odds: shape ``(n_outcomes,)`` for one market or
            ``(n_markets, n_outcomes)`` for a panel. Invalid rows
            (NaN or odds <= 1) yield NaN probabilities.
        method: one of ``multiplicative | shin | power``.

    Returns:
        Fair probabilities, same shape as ``odds``, each market summing to 1.
    """
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}, expected one of {METHODS}")

    odds = np.asarray(odds, dtype=float)
    single = odds.ndim == 1
    rows = np.atleast_2d(odds)
    out = np.full(rows.shape, np.nan)

    valid = np.isfinite(rows).all(axis=1) & (rows > 1.0).all(axis=1)
    pi_all = 1.0 / rows[valid]

    if method == "multiplicative":
        out[valid] = pi_all / pi_all.sum(axis=1, keepdims=True)
    else:
        solver = _shin_row if method == "shin" else _power_row
        solved = np.empty_like(pi_all)
        for i, pi in enumerate(pi_all):
            if pi.sum() <= 1.0:  # zero/negative margin: normalisation only
                solved[i] = pi / pi.sum()
            else:
                solved[i] = solver(pi)
        out[valid] = solved

    return out[0] if single else out


def fair_odds(odds: np.ndarray, method: str = "shin") -> np.ndarray:
    """Fair decimal odds ``1 / devig(odds)``."""
    return 1.0 / devig(odds, method=method)
