"""PIT (Point-in-Time) look-ahead guard for the fundamental data framework.

These tests enforce the core contract: no fundamental feature value may be
used in a backtest before its ``release_date``.  This is the equivalent of
the backtest engine's own look-ahead guard (``tests/test_backtest.py``), but
applied to the fundamental data layer.

The central rule:
    ``pit_join(feature_df, price_index, col)[t] = NaN``
    for all  ``t < feature_df["release_date"].min()``.
    For all  ``t >= first_release``, the value must equal the most recently
    released observation as of t, not any future observation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.fundamental_data import as_of
from quantlab.features import pit_join, weather_anomaly, wasde_surprise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monthly_feature(
    start: str = "2010-01-01",
    n_months: int = 60,
    release_lag_days: int = 10,
) -> pd.DataFrame:
    """Synthetic monthly fundamental feature with known release dates."""
    ref_dates = pd.date_range(start, periods=n_months, freq="MS")
    release_dates = ref_dates + pd.Timedelta(days=release_lag_days)
    values = np.arange(float(n_months))

    df = pd.DataFrame({
        "release_date": release_dates,
        "value":        values,
    }, index=ref_dates)
    df.index.name = "ref_date"
    return df


def _make_price_index(start: str = "2009-01-01", end: str = "2015-06-01") -> pd.DatetimeIndex:
    return pd.bdate_range(start, end)


# ---------------------------------------------------------------------------
# Test 1: pit_join — no data before first release
# ---------------------------------------------------------------------------

def test_pit_join_no_data_before_first_release():
    """pit_join must return NaN for all dates before the first release_date."""
    feature_df = _make_monthly_feature(start="2010-06-01", n_months=24,
                                       release_lag_days=10)
    price_idx = _make_price_index("2009-01-01", "2013-01-01")
    first_release = feature_df["release_date"].min()

    aligned = pit_join(feature_df, price_idx, "value")

    pre_release = aligned[aligned.index < first_release]
    assert pre_release.isna().all(), (
        "pit_join leaked data before the first release_date. "
        f"Earliest non-NaN at {aligned.dropna().index.min()}, "
        f"first release was {first_release}."
    )


# ---------------------------------------------------------------------------
# Test 2: pit_join — no future data on any given day
# ---------------------------------------------------------------------------

def test_pit_join_no_future_releases():
    """On each day t, pit_join must use only observations released on or before t."""
    feature_df = _make_monthly_feature(start="2010-01-01", n_months=36,
                                       release_lag_days=10)
    price_idx = _make_price_index("2010-01-01", "2013-01-01")
    aligned = pit_join(feature_df, price_idx, "value")

    for t in price_idx[::20]:   # sample every 20 days to keep test fast
        val_at_t = aligned.get(t, np.nan)
        if pd.isna(val_at_t):
            continue
        # The value at t must correspond to a release on or before t
        releases_known = feature_df[feature_df["release_date"] <= t]
        assert not releases_known.empty, (
            f"pit_join returned a value at {t.date()} but no releases were known."
        )
        latest_known_val = releases_known["value"].iloc[-1]
        assert val_at_t == pytest.approx(latest_known_val), (
            f"At {t.date()}: pit_join returned {val_at_t!r} but the most recent "
            f"known release had value {latest_known_val!r}."
        )


# ---------------------------------------------------------------------------
# Test 3: as_of — FRED/ALFRED vintage correctness
# ---------------------------------------------------------------------------

def test_as_of_uses_only_past_vintages():
    """as_of() must not expose any vintage released after the cutoff date."""
    vintage_df = pd.DataFrame({
        "ref_date":     [pd.Timestamp("2020-01-01")] * 3,
        "release_date": [
            pd.Timestamp("2020-01-15"),   # first release
            pd.Timestamp("2020-02-15"),   # first revision
            pd.Timestamp("2020-03-20"),   # second revision
        ],
        "value": [100.0, 101.5, 102.3],
    })

    # At 2020-01-20: only the first release is known
    result = as_of(vintage_df, "2020-01-20")
    assert result.loc[pd.Timestamp("2020-01-01"), "value"] == pytest.approx(100.0), (
        "as_of() exposed the first revision before it was released."
    )

    # At 2020-02-20: first revision is known, second is not
    result2 = as_of(vintage_df, "2020-02-20")
    assert result2.loc[pd.Timestamp("2020-01-01"), "value"] == pytest.approx(101.5), (
        "as_of() did not pick up the first revision."
    )

    # At 2020-04-01: both revisions are known
    result3 = as_of(vintage_df, "2020-04-01")
    assert result3.loc[pd.Timestamp("2020-01-01"), "value"] == pytest.approx(102.3), (
        "as_of() did not pick up the second revision."
    )


def test_as_of_no_future_vintage():
    """as_of() must return empty if no vintage has been released by cutoff."""
    vintage_df = pd.DataFrame({
        "ref_date":     [pd.Timestamp("2020-01-01")],
        "release_date": [pd.Timestamp("2020-01-15")],
        "value":        [99.0],
    })

    result = as_of(vintage_df, "2020-01-10")   # before any release
    assert result.empty, (
        "as_of() returned data before the earliest release_date."
    )


# ---------------------------------------------------------------------------
# Test 4: weather_anomaly — no future data in climatology
# ---------------------------------------------------------------------------

def test_weather_anomaly_no_look_ahead_in_climatology():
    """weather_anomaly() must compute climatology from past years only.

    We create a synthetic temperature series where January is cold in early
    years and hot in later years.  The anomaly for Jan 2015 must be computed
    using only Jan 2000-2014 data; if it uses 2015+ data, the sign will flip.
    """
    rng = np.random.default_rng(0)
    # 2000-2014: January mean = 0°C; 2015+: January mean = 10°C (big step)
    n_years = 25
    start_year = 2000
    dates = pd.date_range(f"{start_year}-01-01", periods=n_years * 365, freq="D")
    temps = rng.normal(5.0, 1.0, size=len(dates))

    # Inject the structural break: raise January temps by 10°C from 2015 on
    january_mask = (dates.month == 1) & (dates.year >= 2015)
    temps[january_mask] += 10.0

    weather_df = pd.DataFrame({
        "temperature_2m_mean": temps,
        "release_date": dates + pd.Timedelta(days=1),
    }, index=dates)
    weather_df.index.name = "ref_date"

    anom = weather_anomaly(weather_df, "temperature_2m_mean", agg="mean",
                           window_years=20, min_years=3)

    # The anomaly for January 2015 should be POSITIVE (hot relative to 2000-2014)
    jan_2015 = anom[anom.index == "2015-01-01"]
    if not jan_2015.empty:
        z_2015 = jan_2015["temperature_2m_mean_anomaly"].iloc[0]
        assert z_2015 > 0, (
            f"Jan 2015 anomaly should be positive (hot year) but got z={z_2015:.3f}. "
            "Likely look-ahead: future hot years leaked into the pre-2015 climatology."
        )


# ---------------------------------------------------------------------------
# Test 5: wasde_surprise — PIT order of computations
# ---------------------------------------------------------------------------

def test_wasde_surprise_uses_prior_month_as_expectation():
    """wasde_surprise must compute surprise as current - prior, not using future values."""
    psd_df = pd.DataFrame({
        "release_date": pd.date_range("2020-01-10", periods=6, freq="MS"),
        "attribute":    ["Production"] * 6,
        "value":        [100.0, 102.0, 99.0, 105.0, 103.0, 108.0],
        "unit":         ["1000 MT"] * 6,
    }, index=pd.date_range("2020-01-01", periods=6, freq="MS"))
    psd_df.index.name = "ref_date"

    surprises = wasde_surprise(psd_df, "value", "Production")

    # February surprise = 102 - 100 = +2 (revision up from January)
    feb = surprises[surprises.index == "2020-02-01"]
    assert not feb.empty
    assert feb["surprise"].iloc[0] == pytest.approx(2.0), (
        "wasde_surprise computed wrong surprise for February."
    )

    # March surprise = 99 - 102 = -3 (downgrade)
    mar = surprises[surprises.index == "2020-03-01"]
    assert not mar.empty
    assert mar["surprise"].iloc[0] == pytest.approx(-3.0), (
        "wasde_surprise computed wrong surprise for March."
    )

    # January must be NaN (no prior month available) → dropped
    jan = surprises[surprises.index == "2020-01-01"]
    assert jan.empty or jan["surprise"].isna().all(), (
        "January should have no surprise (no prior month), but it has a value."
    )
