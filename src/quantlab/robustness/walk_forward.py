"""Walk-forward analysis (WFA) harness.

Rolls (or expands) a train→test window across the sample. On each window it
selects the best parameter set **in-sample** and evaluates it **out-of-sample**,
then stitches the OOS returns. This is the honest path test: parameters are never
chosen on the data they are scored on (the gap CPCV/permutation cannot give you,
because those answer model-skill, not the realised path — see lesson 0059/0060).
"""

from __future__ import annotations

from typing import Callable, Iterable

import numpy as np
import pandas as pd

ANN = np.sqrt(252.0)


def _sharpe(returns) -> float:
    r = pd.Series(returns).dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * ANN) if sd else 0.0


def walk_forward(
    full_index: pd.DatetimeIndex,
    params_list: Iterable,
    run_fn: Callable[[object, pd.DatetimeIndex], pd.Series],
    train: int,
    test: int,
    step: int | None = None,
    expanding: bool = False,
    score_fn: Callable[[pd.Series], float] = _sharpe,
) -> dict:
    """Run a walk-forward analysis.

    Args:
        full_index: the full datetime index to walk over.
        params_list: candidate parameter sets to choose between in-sample.
        run_fn: ``run_fn(params, index_slice) -> returns Series`` over the slice.
        train: in-sample window length (bars).
        test: out-of-sample window length (bars).
        step: stride between windows (defaults to ``test`` — non-overlapping OOS).
        expanding: expanding (anchored) train window instead of rolling.
        score_fn: in-sample selection metric (default annualized Sharpe).

    Returns:
        dict with ``oos_returns`` (stitched), ``chosen`` (per-window params +
        train score), ``oos_sharpe`` and ``n_windows``.
    """
    full_index = pd.DatetimeIndex(full_index)
    n = len(full_index)
    step = step or test
    chosen, oos_parts = [], []

    s = 0
    while s + train + test <= n:
        tr = full_index[(0 if expanding else s):s + train]
        te = full_index[s + train:s + train + test]
        best, best_score = None, -np.inf
        for p in params_list:
            sc = score_fn(run_fn(p, tr))
            if sc > best_score:
                best, best_score = p, sc
        oos_parts.append(pd.Series(np.asarray(run_fn(best, te), dtype=float), index=te))
        chosen.append({"test_start": te[0], "test_end": te[-1], "params": best,
                       "train_score": float(best_score)})
        s += step

    oos = pd.concat(oos_parts) if oos_parts else pd.Series(dtype=float)
    return {
        "oos_returns": oos,
        "chosen": chosen,
        "oos_sharpe": score_fn(oos) if len(oos) else 0.0,
        "n_windows": len(chosen),
    }
