"""CPCV guards: purge/embargo correctness and PBO calibration."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantlab.cpcv import make_cpcv_splits, pbo_cscv, stitch_oos_predictions  # noqa: E402

DATES = pd.bdate_range("2012-01-02", "2024-12-31")


def test_splits_cover_and_disjoint():
    splits = make_cpcv_splits(DATES, n_groups=8, n_test_groups=2, purge_days=21)
    assert len(splits) == 28  # C(8,2)
    for sp in splits:
        assert len(np.intersect1d(sp["train"], sp["test"])) == 0
    # Every date appears in exactly C(7,1)=7 test sets.
    counts = pd.Series(0, index=DATES)
    for sp in splits:
        counts[sp["test"]] += 1
    assert (counts == 7).all()


def test_purge_and_embargo_gap():
    purge_days = 63
    splits = make_cpcv_splits(
        DATES, n_groups=8, n_test_groups=2, purge_days=purge_days, embargo_frac=0.01
    )
    embargo_days = int(np.ceil(0.01 * (DATES[-1] - DATES[0]).days))
    for sp in splits:
        test = pd.DatetimeIndex(sp["test"])
        train = pd.DatetimeIndex(sp["train"])
        # Contiguous test blocks.
        blocks = []
        block_start = test[0]
        prev = test[0]
        for d in test[1:]:
            if (d - prev).days > 30:  # gap => new block
                blocks.append((block_start, prev))
                block_start = d
            prev = d
        blocks.append((block_start, prev))
        for start, end in blocks:
            before = train[(train < start) & (train >= start - pd.Timedelta(days=purge_days))]
            assert len(before) == 0, "pre-test purge violated"
            after = train[
                (train > end)
                & (train <= end + pd.Timedelta(days=purge_days + embargo_days))
            ]
            assert len(after) == 0, "post-test purge/embargo violated"


def test_stitch_every_date_covered():
    splits = make_cpcv_splits(DATES, n_groups=8, n_test_groups=2, purge_days=21)
    preds = [
        pd.DataFrame(1.0, index=sp["test"], columns=["A", "B"]) for sp in splits
    ]
    stitched = stitch_oos_predictions(splits, preds)
    assert stitched.notna().all().all()
    assert (stitched == 1.0).all().all()
    assert len(stitched) == len(DATES)


def test_pbo_near_half_on_noise():
    # Per-dataset PBO on noise is high-variance (the combinations share the
    # same columns), but its mean across independent datasets must be ~0.5.
    pbos = []
    for seed in range(8):
        rng = np.random.default_rng(seed)
        noise = pd.DataFrame(rng.normal(0, 0.01, size=(2000, 20)))
        pbos.append(pbo_cscv(noise, n_blocks=10)["pbo"])
    assert 0.35 < np.mean(pbos) < 0.65


def test_pbo_low_on_real_skill():
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 0.01, size=(2000, 20))
    noise[:, 0] += 0.002  # one config with genuine, stable edge
    res = pbo_cscv(pd.DataFrame(noise), n_blocks=10)
    assert res["pbo"] < 0.15
