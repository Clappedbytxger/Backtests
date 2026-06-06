"""Seasonality detection — calendar-based return patterns.

Provides calendar feature engineering and a bucketed return analysis with
significance, plus signal builders for common, macro-justifiable calendar
effects. All signals are *decision-time* signals: they encode the position you
would set knowing only the date; :mod:`quantlab.backtest` applies the look-ahead
shift, so no future information leaks in.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def add_calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Build a DataFrame of calendar attributes for a date index."""
    idx = pd.DatetimeIndex(index)
    df = pd.DataFrame(index=idx)
    df["year"] = idx.year
    df["month"] = idx.month
    df["day"] = idx.day
    df["weekday"] = idx.weekday  # 0 = Monday
    df["week"] = idx.isocalendar().week.astype(int).values
    df["doy"] = idx.dayofyear

    # Trading-day position within each month (1 = first trading day).
    month_key = idx.to_period("M")
    df["tdom"] = df.groupby(month_key).cumcount() + 1
    # Trading days remaining until month end (0 = last trading day of month).
    df["tdom_from_end"] = df.groupby(month_key).cumcount(ascending=False)
    return df


def bucket_return_analysis(
    returns: pd.Series,
    by: str = "month",
) -> pd.DataFrame:
    """Average return per calendar bucket with significance.

    For each bucket (e.g. each month) report mean return, hit rate (share of
    positive periods), count and a one-sample t-test p-value vs 0.

    Args:
        returns: per-period simple returns (datetime-indexed).
        by: one of the calendar feature columns, e.g. ``"month"``, ``"weekday"``,
            ``"tdom"``, ``"tdom_from_end"``.
    """
    feats = add_calendar_features(returns.index)
    df = feats.copy()
    df["ret"] = returns.values

    rows = []
    for key, grp in df.groupby(by):
        r = grp["ret"].dropna()
        if len(r) < 2:
            continue
        t_stat, p_value = stats.ttest_1samp(r, 0.0)
        rows.append(
            {
                by: key,
                "mean_return": r.mean(),
                "hit_rate": (r > 0).mean(),
                "std": r.std(ddof=1),
                "count": len(r),
                "t_stat": t_stat,
                "p_value": p_value,
            }
        )
    return pd.DataFrame(rows).set_index(by).sort_index()


# --- Signal builders for specific, macro-justifiable calendar effects -------
# Each returns a position-weight Series aligned to ``index`` (1 = long, 0 = flat).


def turn_of_month_signal(
    index: pd.DatetimeIndex,
    days_before_end: int = 1,
    days_after_start: int = 3,
) -> pd.Series:
    """Long around the month boundary (last N + first M trading days).

    Macro rationale: month-end pension/fund inflows, salary investing and
    index rebalancing concentrate buying pressure at the turn of the month.
    """
    feats = add_calendar_features(index)
    is_end = feats["tdom_from_end"] < days_before_end
    is_start = feats["tdom"] <= days_after_start
    return (is_end | is_start).astype(float).rename("turn_of_month")


def turn_of_year_signal(
    index: pd.DatetimeIndex,
    start_month: int = 12,
    start_tdom_from_end: int = 5,
    end_month: int = 1,
    end_tdom: int = 4,
) -> pd.Series:
    """Long over the year-end window ("Santa Claus rally" + early January).

    Macro rationale: tax-loss selling exhausts into year-end, window dressing by
    funds, thin holiday liquidity and new-year inflows.
    """
    feats = add_calendar_features(index)
    in_december = (feats["month"] == start_month) & (
        feats["tdom_from_end"] < start_tdom_from_end
    )
    in_january = (feats["month"] == end_month) & (feats["tdom"] <= end_tdom)
    return (in_december | in_january).astype(float).rename("turn_of_year")


def month_window_signal(
    index: pd.DatetimeIndex,
    months: list[int],
    name: str = "month_window",
) -> pd.Series:
    """Long (weight 1.0) during the given calendar months, else flat.

    A generic building block for macro-seasonal windows (e.g. natural-gas
    heating demand Sep-Dec, gasoline pre-driving-season Feb-May). The window is
    a *pre-specified* hypothesis from supply/demand cycles, not chosen from the
    price — so it does not carry in-sample selection bias.
    """
    feats = add_calendar_features(index)
    return feats["month"].isin(months).astype(float).rename(name)


def week_window_signal(
    index: pd.DatetimeIndex,
    weeks: list[int],
    name: str = "week_window",
) -> pd.Series:
    """Long (weight 1.0) during the given ISO calendar weeks, else flat.

    A short-horizon seasonal building block: a contiguous run of one to a few
    ISO weeks (~5-15 trading days) repeated every year. Used to test whether a
    *short* seasonal price kick exists once roll/carry decay is largely avoided
    (relevant when trading futures rather than long-held commodity ETFs). The
    week set may wrap the year boundary (e.g. ``[51, 52, 1]``).
    """
    feats = add_calendar_features(index)
    return feats["week"].isin(weeks).astype(float).rename(name)


def sell_in_may_signal(index: pd.DatetimeIndex) -> pd.Series:
    """Long Nov-Apr, flat May-Oct ("Halloween indicator").

    Macro rationale: historically weaker summer equity returns, often linked to
    seasonal liquidity and risk-appetite cycles.
    """
    feats = add_calendar_features(index)
    in_winter = feats["month"].isin([11, 12, 1, 2, 3, 4])
    return in_winter.astype(float).rename("sell_in_may")


# --- Single-event seasonal windows (one trade per year) ---------------------
# These power the multi-leg seasonal calendar (see :mod:`quantlab.overlay`).
# Both are *decision-time* signals; the backtest/overlay applies the T+1 shift.


def event_signal(
    index: pd.DatetimeIndex,
    iso_week: int,
    hold_days: int = 5,
    name: str = "event",
) -> pd.Series:
    """Long ``hold_days`` trading days from the first day of a given ISO week.

    One trade per calendar year: enter on the first trading day whose ISO week
    equals ``iso_week`` and hold for ``hold_days`` trading days. Used for short
    week-anchored seasonals (e.g. gasoline KW9, feeder-cattle KW21). Extracted
    from strategies 0006/0009/0033/0036 so every calendar leg shares one
    implementation.
    """
    idx = pd.DatetimeIndex(index)
    feats = add_calendar_features(idx)
    weeks = feats["week"].values
    years = idx.year.values
    pos = np.zeros(len(idx))
    for y in np.unique(years):
        locs = np.where((years == y) & (weeks == iso_week))[0]
        if len(locs) == 0:
            continue
        start = locs[0]
        pos[start:min(len(idx), start + hold_days)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def date_window_signal(
    index: pd.DatetimeIndex,
    start_md: tuple[int, int],
    end_md: tuple[int, int],
    name: str = "date",
) -> pd.Series:
    """Long over the calendar window ``[start_md, end_md]`` each year, else flat.

    ``start_md`` / ``end_md`` are ``(month, day)`` tuples. A window whose end is
    calendrically before its start (e.g. ``(12, 18)`` -> ``(1, 10)``) is treated
    as wrapping the year boundary. One trade per year. Used for date-anchored
    seasonals (e.g. platinum turn-of-year, corn WASDE, cotton year-end).
    """
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    same_year = tuple(end_md) > tuple(start_md)
    for y in range(int(idx.year.min()) - 1, int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *start_md)
        end = pd.Timestamp(y if same_year else y + 1, *end_md)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    return pd.Series(pos, index=idx, name=name)


# Chinese New Year (Gregorian dates). A moving feast, so seasonal windows around
# it cannot be expressed as a fixed (month, day) — they need this lookup.
CHINESE_NEW_YEAR = {
    2000: "2000-02-05", 2001: "2001-01-24", 2002: "2002-02-12", 2003: "2003-02-01",
    2004: "2004-01-22", 2005: "2005-02-09", 2006: "2006-01-29", 2007: "2007-02-18",
    2008: "2008-02-07", 2009: "2009-01-26", 2010: "2010-02-14", 2011: "2011-02-03",
    2012: "2012-01-23", 2013: "2013-02-10", 2014: "2014-01-31", 2015: "2015-02-19",
    2016: "2016-02-08", 2017: "2017-01-28", 2018: "2018-02-16", 2019: "2019-02-05",
    2020: "2020-01-25", 2021: "2021-02-12", 2022: "2022-02-01", 2023: "2023-01-22",
    2024: "2024-02-10", 2025: "2025-01-29", 2026: "2026-02-17", 2027: "2027-02-06",
    2028: "2028-01-26", 2029: "2029-02-13", 2030: "2030-02-03",
}


def cny_window_signal(
    index: pd.DatetimeIndex,
    days_before: int = 15,
    days_after: int = 2,
    name: str = "cny_window",
) -> pd.Series:
    """Long in a *calendar-day* window around Chinese New Year, else flat.

    One trade per year: long every trading day in ``[CNY - days_before, CNY +
    days_after]`` calendar days. CNY is a moving feast (late Jan - mid Feb), so
    the window is anchored to :data:`CHINESE_NEW_YEAR` rather than a fixed
    calendar date. Calendar-day offsets match the pre-event-buying framing of the
    original studies (0023/0024). Macro rationale: pre-CNY precious-metal /
    jewellery buying in China. Decision-time signal; the engine applies the T+1
    shift.
    """
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    for date_str in CHINESE_NEW_YEAR.values():
        cny = pd.Timestamp(date_str)
        start = cny - pd.Timedelta(days=days_before)
        end = cny + pd.Timedelta(days=days_after)
        pos[np.asarray((idx >= start) & (idx <= end))] = 1.0
    return pd.Series(pos, index=idx, name=name)


def leg_signal(index: pd.DatetimeIndex, leg: dict) -> pd.Series:
    """Dispatch a calendar-leg dict to the matching window signal.

    A *leg* is a dict describing one seasonal trade. Recognised keys:
      ``kind``     -- ``"week"`` (uses :func:`event_signal`) or ``"date"``
                      (uses :func:`date_window_signal``).
      ``week``     -- ISO week (when ``kind == "week"``).
      ``hold_days``-- holding length for week legs (default 5).
      ``start_md`` / ``end_md`` -- ``(month, day)`` tuples (when ``kind == "date"``).
      ``cny_offset_days`` -- ``[days_before, days_after]`` (when ``kind == "cny"``).
      ``name`` / ``ticker`` -- used as the Series name (``name`` preferred).
    """
    label = leg.get("name", leg.get("ticker", "leg"))
    if leg["kind"] == "week":
        return event_signal(
            index, leg["week"], hold_days=leg.get("hold_days", 5), name=label
        )
    if leg["kind"] == "cny":
        before, after = leg.get("cny_offset_days", [15, 2])
        return cny_window_signal(index, days_before=abs(before), days_after=after, name=label)
    return date_window_signal(index, leg["start_md"], leg["end_md"], name=label)
