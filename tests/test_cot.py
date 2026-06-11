"""COT loader guards: release timing and the no-Friday-leak rule."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantlab.cot_data import (  # noqa: E402
    COT_CODES,
    RELEASE_LAG_DAYS,
    _cache_path,
    cot_daily_panel,
    get_cot,
)


def _synthetic_cot() -> dict[str, pd.DataFrame]:
    # Two Tuesdays; releases land on the following Fridays.
    ref = pd.DatetimeIndex(["2024-01-02", "2024-01-09"], name="ref_date")
    df = pd.DataFrame(
        {
            "open_interest": [100.0, 100.0],
            "comm_long": [20.0, 30.0],
            "comm_short": [60.0, 40.0],
            "noncomm_long": [50.0, 40.0],
            "noncomm_short": [10.0, 30.0],
        },
        index=ref,
    )
    df["hedging_pressure"] = (df["comm_short"] - df["comm_long"]) / df["open_interest"]
    df["release_date"] = df.index + pd.Timedelta(days=RELEASE_LAG_DAYS)
    return {"XX": df}


def test_release_is_friday():
    cot = _synthetic_cot()["XX"]
    assert (cot["release_date"].dt.dayofweek == 4).all()  # Tuesday + 3d = Friday


def test_daily_panel_no_friday_leak():
    """The Friday-released value must first be usable on the NEXT trading day."""
    cot = _synthetic_cot()
    days = pd.bdate_range("2024-01-02", "2024-01-16")
    panel = cot_daily_panel(cot, days)

    rel = pd.Timestamp("2024-01-05")  # Friday release of the 2024-01-02 report
    next_day = pd.Timestamp("2024-01-08")  # Monday
    assert pd.isna(panel.loc[rel, "XX"]), "release-day close must not see the release"
    assert panel.loc[next_day, "XX"] == pytest.approx(0.4)

    rel2_next = pd.Timestamp("2024-01-15")  # Monday after the 2024-01-12 release
    assert panel.loc[rel2_next, "XX"] == pytest.approx(0.1)
    # Between the two effective dates the older value forward-fills.
    assert panel.loc[pd.Timestamp("2024-01-12"), "XX"] == pytest.approx(0.4)


def test_hedging_pressure_sign():
    """Net-short commercials => positive hedging pressure (long premium)."""
    cot = _synthetic_cot()["XX"]
    assert cot["hedging_pressure"].iloc[0] == pytest.approx(0.4)
    assert cot["hedging_pressure"].iloc[1] == pytest.approx(0.1)


@pytest.mark.skipif(
    not _cache_path("CL").exists(), reason="COT cache not pulled on this machine"
)
def test_cached_cot_sane():
    df = get_cot("CL")
    assert len(df) > 500
    assert df["hedging_pressure"].abs().max() < 1.0
    assert (df["release_date"] - df.index).dt.days.eq(RELEASE_LAG_DAYS).all()
    # Weekly cadence: median gap 7 days.
    assert df.index.to_series().diff().dt.days.median() == 7
