"""Research-to-production parity check.

Generalizes the ad-hoc ``validate()`` in the frozen 0108 CTI book
(``strategies/0108_cti_core_book_live/signal_engine.py``): given a *reconstructed*
return stream (e.g. produced by the live signal engine or a re-run of the
promoted :class:`IStrategy`) and the *saved* research stream, confirm they are
the same strategy by correlation and annualized-Sharpe agreement. A failing
parity check means the live reconstruction has drifted from what was researched —
the engine is not faithful and must not trade.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ANN = np.sqrt(252)


def _sharpe(returns: pd.Series) -> float:
    r = pd.Series(returns).dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * ANN) if sd else 0.0


def validate_parity(
    reconstructed: pd.Series,
    saved: pd.Series,
    *,
    min_corr: float = 0.99,
    max_sharpe_diff: float = 0.05,
) -> dict:
    """Compare a reconstructed return stream against a saved research stream.

    Args:
        reconstructed: live / re-run net-return stream.
        saved: the stored research net-return stream.
        min_corr: minimum acceptable correlation on the overlapping dates.
        max_sharpe_diff: maximum acceptable absolute Sharpe difference.

    Returns:
        dict with ``passed``, ``corr``, ``sharpe_recon``, ``sharpe_saved``,
        ``sharpe_diff`` and ``overlap`` (number of common dates).
    """
    a = pd.Series(reconstructed).dropna()
    b = pd.Series(saved).dropna()
    common = a.index.intersection(b.index)
    if len(common) < 2:
        return {
            "passed": False, "reason": "insufficient overlap", "overlap": int(len(common)),
            "corr": float("nan"), "sharpe_recon": _sharpe(a), "sharpe_saved": _sharpe(b),
            "sharpe_diff": float("nan"),
        }

    av = a.reindex(common).fillna(0.0).to_numpy()
    bv = b.reindex(common).fillna(0.0).to_numpy()
    if np.std(av) == 0 or np.std(bv) == 0:
        corr = 1.0 if np.allclose(av, bv) else 0.0
    else:
        corr = float(np.corrcoef(av, bv)[0, 1])

    sr_a, sr_b = _sharpe(a.reindex(common)), _sharpe(b.reindex(common))
    sharpe_diff = abs(sr_a - sr_b)
    passed = (corr >= min_corr) and (sharpe_diff <= max_sharpe_diff)
    return {
        "passed": bool(passed), "corr": corr,
        "sharpe_recon": sr_a, "sharpe_saved": sr_b, "sharpe_diff": sharpe_diff,
        "overlap": int(len(common)),
    }
