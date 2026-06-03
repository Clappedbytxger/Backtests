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


def sell_in_may_signal(index: pd.DatetimeIndex) -> pd.Series:
    """Long Nov-Apr, flat May-Oct ("Halloween indicator").

    Macro rationale: historically weaker summer equity returns, often linked to
    seasonal liquidity and risk-appetite cycles.
    """
    feats = add_calendar_features(index)
    in_winter = feats["month"].isin([11, 12, 1, 2, 3, 4])
    return in_winter.astype(float).rename("sell_in_may")
