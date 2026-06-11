"""Combinatorial Purged Cross-Validation (CPCV) and PBO — the ML validation core.

Why not plain walk-forward: a single chronological path is one draw; the
backtest-overfitting literature (Bailey/Lopez de Prado et al.) shows CPCV's
*distribution* of OOS results plus the Probability of Backtest Overfitting
(PBO) discriminates luck from skill far better.

Two leak channels CPCV must close on panel data with forward-return labels:

1. **Purging.** A training sample at date ``t`` with an ``h``-day forward
   label spans ``[t, t+h]``. If that span touches a test block, the trainer
   has literally seen test-period returns. We drop train dates within ``h``
   days *before* each test block, and within ``h`` days *after* it (test
   labels extending into the train region leak the other way).
2. **Embargo.** Serial correlation outlives the label window; an extra
   ``embargo_frac`` of the timeline after each test block is dropped too.

PBO follows the CSCV procedure: partition the per-config OOS return matrix
into ``n_blocks`` time blocks, take every half/half combination, rank configs
in-sample, and ask how the IS-best config ranks out-of-sample. PBO = fraction
of combinations where the IS winner lands in the OOS bottom half. PBO ~0.5 on
noise, near 0 for real, stable skill.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd


def make_cpcv_splits(
    dates: pd.DatetimeIndex,
    n_groups: int = 8,
    n_test_groups: int = 2,
    purge_days: int = 63,
    embargo_frac: float = 0.01,
) -> list[dict]:
    """Build the C(n_groups, n_test_groups) purged train/test splits.

    Args:
        dates: sorted unique trading dates of the panel.
        n_groups: contiguous, equal-sized date blocks.
        n_test_groups: blocks held out per split (2 is the de Prado default).
        purge_days: the *label horizon* in calendar days — train dates whose
            forward-label window can overlap a test block are dropped.
        embargo_frac: extra fraction of the timeline embargoed after each
            test block.

    Returns:
        list of ``{"train": DatetimeIndex, "test": DatetimeIndex,
        "test_groups": tuple[int, ...]}``.
    """
    dates = pd.DatetimeIndex(dates).sort_values().unique()
    groups = np.array_split(np.arange(len(dates)), n_groups)
    bounds = [(dates[g[0]], dates[g[-1]]) for g in groups]
    embargo = pd.Timedelta(days=int(np.ceil(embargo_frac * (dates[-1] - dates[0]).days)))
    purge = pd.Timedelta(days=purge_days)

    splits = []
    for test_idx in combinations(range(n_groups), n_test_groups):
        test_mask = np.zeros(len(dates), dtype=bool)
        for gi in test_idx:
            test_mask[groups[gi]] = True

        train_mask = ~test_mask
        for gi in test_idx:
            start, end = bounds[gi]
            # Pre-block purge: train labels reaching into the test block.
            train_mask &= ~((dates >= start - purge) & (dates < start))
            # Post-block purge + embargo: test labels reaching into train,
            # plus serial-correlation buffer.
            train_mask &= ~((dates > end) & (dates <= end + purge + embargo))

        splits.append(
            {
                "train": dates[train_mask],
                "test": dates[test_mask],
                "test_groups": test_idx,
            }
        )
    return splits


def stitch_oos_predictions(
    splits: list[dict], preds_per_split: list[pd.DataFrame]
) -> pd.DataFrame:
    """Average per-date OOS predictions across the splits that held the date out.

    Every date is in exactly ``C(n_groups-1, n_test_groups-1)`` test sets; the
    mean over those models is a single fully-OOS prediction panel usable for
    one stitched backtest path.
    """
    num = None
    den = None
    for split, preds in zip(splits, preds_per_split):
        p = preds.reindex(split["test"])
        if num is None:
            num = p.fillna(0.0).copy()
            den = p.notna().astype(float)
            continue
        num = num.add(p.fillna(0.0), fill_value=0.0)
        den = den.add(p.notna().astype(float), fill_value=0.0)
    return num.where(den > 0).div(den.replace(0, np.nan))


def pbo_cscv(returns_matrix: pd.DataFrame, n_blocks: int = 16) -> dict:
    """Probability of Backtest Overfitting via CSCV (Bailey et al. 2015).

    Args:
        returns_matrix: per-period returns, columns = strategy configs/trials,
            rows = time. Should be the *OOS-stitched* returns of every config.
        n_blocks: even number of contiguous time blocks for the half/half
            combinations (16 -> C(16,8) = 12870 combinations).

    Returns:
        dict with ``pbo``, the logit distribution and the per-combination
        OOS relative rank of the IS winner.
    """
    m = returns_matrix.dropna(how="all").fillna(0.0)
    n_cfg = m.shape[1]
    if n_cfg < 2:
        raise ValueError("PBO needs >=2 configs.")
    blocks = np.array_split(np.arange(len(m)), n_blocks)

    # Precompute per-block count/sum/sum-of-squares so each of the C(n, n/2)
    # combinations is an O(n_blocks * n_cfg) reduction, not a full re-scan.
    vals = m.values
    n_b = np.array([len(b) for b in blocks], dtype=float)
    s_b = np.stack([vals[b].sum(axis=0) for b in blocks])
    q_b = np.stack([(vals[b] ** 2).sum(axis=0) for b in blocks])

    def combo_sharpe(idx: tuple[int, ...]) -> np.ndarray:
        n = n_b[list(idx)].sum()
        s = s_b[list(idx)].sum(axis=0)
        q = q_b[list(idx)].sum(axis=0)
        mu = s / n
        var = (q - n * mu**2) / (n - 1)
        sd = np.sqrt(np.maximum(var, 0.0))
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(sd > 0, mu / sd, 0.0)

    logits = []
    omegas = []
    all_groups = set(range(n_blocks))
    for is_idx in combinations(range(n_blocks), n_blocks // 2):
        oos_idx = tuple(sorted(all_groups - set(is_idx)))
        sr_is = combo_sharpe(is_idx)
        sr_oos = combo_sharpe(oos_idx)
        best = int(np.argmax(sr_is))
        # Relative OOS rank of the IS winner in (0, 1); 0.5 = median.
        omega = (np.sum(sr_oos <= sr_oos[best])) / (n_cfg + 1.0)
        omega = min(max(omega, 1e-9), 1 - 1e-9)
        omegas.append(omega)
        logits.append(np.log(omega / (1 - omega)))

    logits_arr = np.asarray(logits)
    return {
        "pbo": float(np.mean(logits_arr <= 0.0)),
        "logit_mean": float(logits_arr.mean()),
        "n_combinations": len(logits),
        "omega_mean": float(np.mean(omegas)),
    }
