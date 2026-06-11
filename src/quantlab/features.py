"""PIT-correct feature generators for fundamental commodity signals.

All functions return DataFrames indexed by ``ref_date`` with a ``release_date``
column.  The caller MUST join to price data on ``release_date``, not on
``ref_date``, to avoid look-ahead.

The look-ahead guard in ``tests/test_pit.py`` verifies this contract.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Weather anomaly
# ---------------------------------------------------------------------------

def weather_anomaly(
    weather_df: pd.DataFrame,
    variable: str,
    agg: str = "sum",
    window_years: int = 20,
    min_years: int = 5,
) -> pd.DataFrame:
    """Monthly climatological anomaly (z-score) for a weather variable.

    Aggregates the daily weather data to monthly totals/means, then computes
    a z-score against a **rolling, past-only** climatology of the same
    calendar month.  This is PIT-correct: the climatology for month M of year
    Y uses only observations from month M in years prior to Y.

    Args:
        weather_df: output of ``fundamental_data.get_weather_daily()``.
            Indexed by ``ref_date`` with columns ``release_date`` and one or
            more weather variables.
        variable: column name in ``weather_df``, e.g. ``"precipitation_sum"``.
        agg: ``"sum"`` for precipitation totals, ``"mean"`` for temperatures.
        window_years: maximum number of past years used for climatology.
            Expands until ``window_years`` is reached, then stays fixed.
        min_years: minimum years of history required before emitting anomalies.

    Returns:
        DataFrame indexed by ``ref_date`` (month start) with columns:
        ``release_date`` (first day of following month — all daily data for
        the month is known by then),
        ``{variable}_monthly`` (raw monthly aggregate),
        ``{variable}_anomaly`` (z-score vs. rolling climatology).

    PIT notes:
    - The climatology window is lagged by 1 year (shift(1) over the monthly
      same-calendar-month series), so no current-year data enters the norm.
    - ``release_date`` is the month-end + 1 day.  For a signal used at daily
      frequency, forward-fill from the release date into subsequent trading days.
    """
    series = weather_df[variable].dropna()

    # Aggregate to monthly (month-start index)
    monthly = series.resample("MS").agg(agg)

    results: list[pd.DataFrame] = []
    for month in range(1, 13):
        mask = monthly.index.month == month
        m = monthly[mask].sort_index()
        if len(m) < min_years + 1:
            continue

        # Rolling window capped at window_years, shifted to exclude current obs
        roll_mean = (
            m.expanding(min_periods=min_years)
            .mean()
            .shift(1)
        )
        roll_std = (
            m.expanding(min_periods=min_years)
            .std()
            .shift(1)
        )
        # Once we have window_years worth of data, cap the window
        fixed_mean = m.rolling(window_years, min_periods=min_years).mean().shift(1)
        fixed_std  = m.rolling(window_years, min_periods=min_years).std().shift(1)

        has_enough = fixed_mean.notna()
        roll_mean[has_enough] = fixed_mean[has_enough]
        roll_std[has_enough]  = fixed_std[has_enough]

        z = (m - roll_mean) / roll_std.replace(0.0, np.nan)

        results.append(pd.DataFrame({
            f"{variable}_monthly": m,
            f"{variable}_anomaly": z,
        }))

    if not results:
        raise ValueError(
            f"Not enough data to compute weather_anomaly for variable={variable!r}. "
            f"Need at least {min_years + 1} years."
        )

    df_out = pd.concat(results).sort_index()
    # release_date = first day of the next month (all data in the month is then known)
    df_out["release_date"] = df_out.index + pd.offsets.MonthBegin(1)
    return df_out.dropna(subset=[f"{variable}_anomaly"])


# ---------------------------------------------------------------------------
# WASDE surprise
# ---------------------------------------------------------------------------

def wasde_surprise(
    psd_df: pd.DataFrame,
    value_col: str = "value",
    attribute: str | None = None,
) -> pd.DataFrame:
    """Month-over-month revision in a WASDE estimate (naïve surprise proxy).

    ``surprise = current_month_value − prior_month_value``

    This is the naïve proxy for analyst-consensus surprise.  Document in every
    REPORT.md that uses this feature: the assumption is that the prior month's
    WASDE estimate equals the market's expectation for the current month.

    Args:
        psd_df: output of ``fundamental_data.get_wasde_psd()``.
            May contain multiple attributes; filter with ``attribute`` or
            pre-filter before calling.
        value_col: name of the value column (default ``"value"``).
        attribute: if provided, filter ``psd_df`` to this attribute first.

    Returns:
        DataFrame indexed by ``ref_date`` (month start) with columns:
        ``release_date``, ``attribute`` (if present), ``value`` (current),
        ``surprise`` (current − prior), ``surprise_pct`` (relative surprise).

    PIT notes:
    - ``release_date`` is inherited from ``psd_df``.
    - The prior-month observation is available before the current WASDE, so
      the surprise is PIT-correct at the WASDE release date.
    - The naïve proxy can diverge from true analyst consensus during periods of
      rapid trend changes.  Flag any large-surprise trades in REPORT.md.
    """
    df = psd_df.copy()
    if attribute:
        df = df[df["attribute"] == attribute]

    if df.empty:
        raise ValueError(
            f"wasde_surprise: no rows after filtering for attribute={attribute!r}."
        )

    # Sort and compute month-over-month diff within each attribute
    df = df.sort_index()

    def _diff_group(g: pd.DataFrame) -> pd.DataFrame:
        g = g.copy()
        g["surprise"] = g[value_col].diff()
        g["surprise_pct"] = g["surprise"] / g[value_col].shift(1).replace(0, np.nan)
        return g

    if "attribute" in df.columns:
        df = df.groupby("attribute", group_keys=False).apply(_diff_group)
    else:
        df["surprise"] = df[value_col].diff()
        df["surprise_pct"] = df["surprise"] / df[value_col].shift(1).replace(0, np.nan)

    return df.dropna(subset=["surprise"])


# ---------------------------------------------------------------------------
# NASS Crop Condition delta
# ---------------------------------------------------------------------------

def crop_condition_delta(
    nass_df: pd.DataFrame,
    col: str = "pct_good_excellent",
) -> pd.DataFrame:
    """Week-over-week change in crop condition (good + excellent %).

    The delta between successive NASS weekly readings is PIT-correct because
    both observations are from already-released reports.

    Args:
        nass_df: output of ``fundamental_data.get_nass_crop_condition()``.
        col: condition column to diff.  Default ``"pct_good_excellent"``.

    Returns:
        DataFrame indexed by ``ref_date`` (week ending Sunday) with columns:
        ``release_date``, ``{col}`` (level), ``{col}_delta`` (WoW change),
        ``{col}_4w_change`` (4-week cumulative change for trend context).

    PIT notes:
    - ``release_date = ref_date + 1 day`` (inherited from ``nass_df``).
    - The 4-week cumulative change compares to 4 weeks prior, both already
      public by the current release date.
    """
    df = nass_df[[col, "release_date"]].copy().sort_index().dropna(subset=[col])
    df[f"{col}_delta"]     = df[col].diff(1)
    df[f"{col}_4w_change"] = df[col].diff(4)
    return df.dropna(subset=[f"{col}_delta"])


# ---------------------------------------------------------------------------
# Export YoY growth
# ---------------------------------------------------------------------------

def export_yoy(
    df: pd.DataFrame,
    value_col: str,
    periods: int = 12,
) -> pd.DataFrame:
    """Year-over-year growth rate, computed on the release-date timeline.

    Args:
        df: DataFrame indexed by ``ref_date`` with a ``release_date`` column.
            Typically monthly export data from USDA or a similar source.
        value_col: the column containing export volumes or values.
        periods: number of periods to lag for the YoY comparison.
            Default 12 for monthly data.

    Returns:
        DataFrame with same index, ``release_date``, ``{value_col}_yoy``
        (fractional YoY growth rate), and ``{value_col}_yoy_z`` (z-score of
        the YoY rate over an expanding window, for signal normalization).

    PIT notes:
    - Comparison is between current and ``periods``-prior observation, both
      already known at the current ``release_date``.
    - For series with large seasonal patterns, use ``periods=12`` (monthly)
      or ``periods=52`` (weekly) to remove seasonality from the growth rate.
    """
    d = df[[value_col, "release_date"]].copy().sort_index().dropna(subset=[value_col])
    prior = d[value_col].shift(periods)
    d[f"{value_col}_yoy"] = (d[value_col] - prior) / prior.abs().replace(0, np.nan)

    yoy = d[f"{value_col}_yoy"]
    expanding_mean = yoy.expanding(min_periods=12).mean()
    expanding_std  = yoy.expanding(min_periods=12).std()
    d[f"{value_col}_yoy_z"] = (yoy - expanding_mean) / expanding_std.replace(0, np.nan)

    return d.dropna(subset=[f"{value_col}_yoy"])


# ---------------------------------------------------------------------------
# Inventory change
# ---------------------------------------------------------------------------

def inventory_change(
    df: pd.DataFrame,
    value_col: str,
    periods: int = 1,
) -> pd.DataFrame:
    """Absolute and relative period-over-period inventory change.

    Args:
        df: DataFrame indexed by ``ref_date`` with ``release_date`` column.
        value_col: inventory level column.
        periods: number of periods for the diff (1 = WoW for weekly data).

    Returns:
        DataFrame with ``release_date``, ``{value_col}_delta`` (absolute),
        ``{value_col}_pct_change`` (relative), ``{value_col}_z`` (z-score of
        percent change over expanding window).

    PIT notes:
    - Both the current and prior observation are released before the current
      date → PIT-correct.
    - A large inventory draw (delta < 0) is typically bullish for price.
    """
    d = df[[value_col, "release_date"]].copy().sort_index().dropna(subset=[value_col])
    d[f"{value_col}_delta"] = d[value_col].diff(periods)
    pct = d[value_col].pct_change(periods)
    d[f"{value_col}_pct_change"] = pct

    exp_mean = pct.expanding(min_periods=12).mean()
    exp_std  = pct.expanding(min_periods=12).std()
    d[f"{value_col}_z"] = (pct - exp_mean) / exp_std.replace(0, np.nan)

    return d.dropna(subset=[f"{value_col}_delta"])


# ---------------------------------------------------------------------------
# Ethanol premium (sugar-specific)
# ---------------------------------------------------------------------------

def ethanol_premium(
    ethanol_price: pd.Series,
    sugar_price: pd.Series,
    window: int = 52,
) -> pd.DataFrame:
    """Rolling z-score of the ethanol-to-sugar price ratio.

    When ethanol is expensive relative to sugar, Brazilian mills divert cane
    into ethanol production, reducing sugar supply.  The z-score of the ratio
    captures when this incentive is unusually strong (or weak).

    Args:
        ethanol_price: weekly or daily ethanol price series (e.g. from EIA).
            Indexed by date.
        sugar_price: daily sugar front-month close (SB=F from yfinance).
            Indexed by date.
        window: rolling window for z-score normalization (default 52 weeks).

    Returns:
        DataFrame indexed by date with columns ``ratio``, ``ratio_z``, and
        ``release_date`` (= index, since both inputs are market prices).

    PIT notes:
    - Both inputs are market prices, available in real time → no release lag.
    - ``release_date = index`` (daily market data).
    - The rolling z-score uses only past data (shift(1) on the rolling stats).
    """
    # Align on the finer-grained index
    common = ethanol_price.index.intersection(sugar_price.index)
    eth = ethanol_price.reindex(common)
    sug = sugar_price.reindex(common)

    ratio = eth / sug.replace(0, np.nan)
    roll_mean = ratio.rolling(window, min_periods=12).mean().shift(1)
    roll_std  = ratio.rolling(window, min_periods=12).std().shift(1)
    ratio_z   = (ratio - roll_mean) / roll_std.replace(0, np.nan)

    df_out = pd.DataFrame({
        "ratio":        ratio,
        "ratio_z":      ratio_z,
        "release_date": common,
    }, index=common)
    df_out.index.name = "ref_date"
    return df_out.dropna(subset=["ratio_z"])


# ---------------------------------------------------------------------------
# PIT join helper
# ---------------------------------------------------------------------------

def pit_join(
    feature_df: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    feature_col: str,
) -> pd.Series:
    """Align a fundamental feature to a daily price index, PIT-correct.

    For each day t in ``price_index``, takes the most recent observation
    where ``release_date <= t`` and forward-fills until the next release.

    This is the correct way to feed monthly/weekly fundamental features
    into a daily backtest without look-ahead.

    Args:
        feature_df: DataFrame indexed by ``ref_date`` with columns
            ``release_date`` and ``feature_col``.
        price_index: daily DatetimeIndex of the asset price series.
        feature_col: column to align.

    Returns:
        pd.Series indexed like ``price_index``.  NaN before the first release.
    """
    release_indexed = (
        feature_df[["release_date", feature_col]]
        .reset_index()
        .set_index("release_date")[feature_col]
        .sort_index()
    )
    # Reindex to daily price calendar, then forward-fill (carry forward last known)
    daily = release_indexed.reindex(price_index, method="ffill")
    # Mask dates before the first release
    if not release_indexed.empty:
        daily[daily.index < release_indexed.index.min()] = np.nan
    return daily
