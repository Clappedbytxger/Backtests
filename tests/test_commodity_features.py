"""Feature-pipeline guards: rank transform, target alignment, design matrix."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantlab.commodity_features import (  # noqa: E402
    TARGET_HORIZONS,
    assemble_design_matrix,
    rank_transform,
)

RNG = np.random.default_rng(3)
DATES = pd.bdate_range("2018-01-01", "2021-12-31")
COLS = list("ABCDEFGHIJ")


def test_rank_transform_range_and_nan():
    panel = pd.DataFrame(RNG.normal(size=(50, 10)), columns=COLS)
    panel.iloc[0, 0] = np.nan
    r = rank_transform(panel)
    assert r.iloc[0].isna().sum() == 1
    valid = r.stack()
    assert valid.min() > -0.5 and valid.max() < 0.5
    # Per-date mean of a full row is exactly 0 (symmetric ranks).
    assert abs(r.iloc[1].mean()) < 1e-12
    # Monotone: higher raw value => higher rank.
    row = panel.iloc[2]
    assert (r.iloc[2][row.idxmax()] == r.iloc[2].max())


def test_forward_target_alignment():
    """fwd_h at date t must equal price[t+h]/price[t] - 1 — decided at close t."""
    price = pd.DataFrame(
        {"A": np.linspace(100, 200, len(DATES))}, index=DATES
    )
    h = 5
    fwd = price.pct_change(h).shift(-h)
    t = DATES[100]
    expected = price["A"].iloc[105] / price["A"].iloc[100] - 1
    assert fwd.loc[t, "A"] == pytest.approx(expected)
    # The last h rows have no future => NaN, never filled.
    assert fwd["A"].iloc[-h:].isna().all()


def _synthetic_panels() -> dict:
    n, m = len(DATES), len(COLS)
    front = pd.DataFrame(
        100 * np.exp(np.cumsum(RNG.normal(0, 0.01, size=(n, m)), axis=0)),
        index=DATES, columns=COLS,
    )
    rets = front.pct_change()
    feats = {
        "carry": pd.DataFrame(RNG.normal(size=(n, m)), index=DATES, columns=COLS),
        "mom_252": front.pct_change(252),
        "vol_20": rets.rolling(20).std() * np.sqrt(252),
    }
    targets_raw = {h: front.pct_change(h).shift(-h) for h in TARGET_HORIZONS}
    targets_rank = {h: rank_transform(t) for h, t in targets_raw.items()}
    return {
        "features": feats,
        "targets_raw": targets_raw,
        "targets_rank": targets_rank,
        "returns": rets,
        "vol20": feats["vol_20"],
        "days": DATES,
    }


def test_design_matrix_shape_and_core_dropna():
    panels = _synthetic_panels()
    df = assemble_design_matrix(panels, horizon=21, sample_freq="W")
    assert list(df.index.names) == ["date", "root"]
    for col in ("carry", "mom_252", "y", "fwd_ret"):
        assert col in df.columns
    assert df["y"].notna().all()
    assert df["mom_252"].notna().all()
    # Rank-transformed features live in (-0.5, 0.5).
    assert df["carry"].abs().max() < 0.5


def test_design_matrix_y_is_rank_of_fwd():
    """Within a date, the rank target must order exactly like the raw forward
    return — and never use information beyond t+h."""
    panels = _synthetic_panels()
    df = assemble_design_matrix(panels, horizon=21, sample_freq="W")
    some_date = df.index.get_level_values("date")[len(df) // 2]
    sub = df.xs(some_date, level="date")
    assert (
        sub.sort_values("fwd_ret")["y"].is_monotonic_increasing
    ), "rank target does not match forward-return ordering"
