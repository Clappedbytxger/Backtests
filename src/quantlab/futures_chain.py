"""Single-contract futures chains -> roll-clean calendar & inter-commodity spreads.

Databento GLBX parent-symbology daily bars (cached as
``data/cache/futures_chain_{ROOT}.parquet``) contain every listed outright
contract (e.g. ``ZCN5`` = July-2015 corn) plus exchange spreads. This module
parses the OUTRIGHT contracts and builds **dollar-neutral spread RETURN series**
(long-leg %return minus short-leg %return), which are:

  * roll-clean: each year's contract pair is held only inside the season window;
    the year-to-year roll happens OUTSIDE the window, so no stitch artifact enters
    the traded return (the whole point of trading the spread, lesson 0028/0029).
  * beta-neutral within the commodity (a calendar spread) or across the complex
    (an inter-commodity spread like the crush/crack).

Month codes: F G H J K M N Q U V X Z = Jan..Dec. The single-digit contract year
is disambiguated by the contract's LAST observed trade date (a contract trades
until ~its delivery month, so its expiry year == max(ts_event).year).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

_CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
MONTHS = "FGHJKMNQUVXZ"
MONTH_NUM = {c: i + 1 for i, c in enumerate(MONTHS)}


def load_chain(root: str) -> pd.DataFrame:
    """Load the cached parent-symbology daily chain for a root (tz-naive index)."""
    df = pd.read_parquet(_CACHE / f"futures_chain_{root}.parquet")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def outright_closes(root: str) -> dict[tuple[str, int], pd.Series]:
    """Return {(month_code, year): close-series} for every outright contract.

    Year is resolved from each contract's last observed date (= delivery year).
    """
    df = load_chain(root)
    pat = re.compile(rf"^{re.escape(root)}([{MONTHS}])(\d)$")
    out: dict[tuple[str, int], pd.Series] = {}
    # Group by instrument_id: single-digit year codes (e.g. ZCN0) collide across
    # decades (2010 vs 2020) under the SAME symbol string, but each listed contract
    # instance has a distinct instrument_id. Year = the instance's last trade year.
    for iid, g in df.groupby("instrument_id"):
        sym = str(g["contract"].iloc[0])
        m = pat.match(sym)
        if not m:
            continue
        mc = m.group(1)
        last_year = g.index.max().year
        close = g["close"].sort_index()
        close = close[~close.index.duplicated(keep="last")]
        out[(mc, last_year)] = close
    return out


def calendar_spread_return(root: str, long_mc: str, short_mc: str,
                           same_year: bool = True, short_year_offset: int = 0) -> pd.Series:
    """Continuous dollar-neutral calendar-spread return: long_mc leg minus short_mc leg.

    For each delivery year Y the pair is (long_mc{Y}, short_mc{Y+short_year_offset}).
    On each date we use the pair whose LONG leg has not yet expired (nearest), so the
    series rolls to the next year's pair after each long-leg expiry. The return is
    ``ret(long) - ret(short)`` (equal-notional spread).
    """
    closes = outright_closes(root)
    long_by_year = {y: s for (mc, y), s in closes.items() if mc == long_mc}
    short_by_year = {y: s for (mc, y), s in closes.items() if mc == short_mc}
    pieces = []
    for y, ls in sorted(long_by_year.items()):
        sy = y + short_year_offset
        ss = short_by_year.get(sy)
        if ss is None:
            continue
        long_exp = pd.Timestamp(y, MONTH_NUM[long_mc], 1)
        # active window: from prior long-leg expiry up to this long leg's expiry month-end
        start = pd.Timestamp(y - 1, MONTH_NUM[long_mc], 28)
        idx = ls.index.intersection(ss.index)
        idx = idx[(idx > start) & (idx <= long_exp + pd.offsets.MonthEnd(0))]
        if len(idx) < 20:
            continue
        lr = ls.reindex(idx).pct_change()
        sr = ss.reindex(idx).pct_change()
        pieces.append((lr - sr).rename(None))
    if not pieces:
        return pd.Series(dtype=float)
    out = pd.concat(pieces).sort_index()
    out = out[~out.index.duplicated(keep="first")]
    return out.fillna(0.0)


def matched_month_spread_return(legs: list[tuple[str, float]], month_code: str,
                                start_md, end_md) -> pd.Series:
    """Roll-CLEAN inter-commodity spread: matched same-delivery-month contracts,
    held only inside the pre-delivery season window each year.

    For each delivery year Y, all legs use the contract ``{root}{month_code}{Y}``
    (same delivery month -> no per-leg roll), restricted to the window
    [start_md, end_md] that precedes the delivery (the window is shorter than the
    contract life, so one matched set covers it -> no roll inside the trade).
    Return = sum_i weight_i * ret_i. The year-to-year roll happens between windows.
    """
    closes_by_root = {root: outright_closes(root) for root, _ in legs}
    wrap = start_md > end_md
    years = sorted({y for c in closes_by_root.values() for (mc, y) in c if mc == month_code})
    pieces = []
    for y in years:
        leg_series = []
        ok = True
        for root, w in legs:
            s = closes_by_root[root].get((month_code, y))
            if s is None:
                ok = False
                break
            leg_series.append((s, w))
        if not ok:
            continue
        # window that PRECEDES delivery month_code of year y
        end_year = y
        start_year = y - 1 if wrap else y
        start = pd.Timestamp(start_year, start_md[0], start_md[1])
        end = pd.Timestamp(end_year, end_md[0], end_md[1])
        idx = leg_series[0][0].index
        for s, _ in leg_series[1:]:
            idx = idx.intersection(s.index)
        idx = idx[(idx >= start) & (idx <= end)]
        if len(idx) < 15:
            continue
        sr = sum(w * s.reindex(idx).pct_change() for s, w in leg_series)
        pieces.append(sr)
    if not pieces:
        return pd.Series(dtype=float)
    out = pd.concat(pieces).sort_index()
    return out[~out.index.duplicated(keep="first")].fillna(0.0)


def intercommodity_front_return(legs: list[tuple[str, float]], months: str = "HKNUZ") -> pd.Series:
    """Dollar-neutral inter-commodity spread return using matched nearest contracts.

    legs: list of (root, weight) — positive weight = long, negative = short. For each
    root we build a continuous 'front' close from the nearest not-yet-expired contract
    restricted to the given delivery ``months`` (so all legs use the same delivery
    cycle), then spread return = sum_i weight_i * ret_i. Weights should net ~0 in
    notional terms (e.g. crush 1*ZM + 1*ZL - 1*ZS, crack 2*RB + 1*HO - 3*CL scaled).
    """
    leg_rets = []
    for root, w in legs:
        closes = outright_closes(root)
        # build a continuous nearest-contract close among allowed months
        series_by_year = {(mc, y): s for (mc, y), s in closes.items() if mc in months}
        # for each date, pick the contract with the nearest future expiry
        all_dates = sorted(set().union(*[s.index for s in series_by_year.values()]))
        front = pd.Series(index=pd.DatetimeIndex(all_dates), dtype=float)
        # precompute expiry timestamp per contract
        exp = {k: pd.Timestamp(k[1], MONTH_NUM[k[0]], 28) for k in series_by_year}
        for d in front.index:
            cands = [(exp[k], k) for k in series_by_year if d <= exp[k] and d in series_by_year[k].index]
            if not cands:
                continue
            _, k = min(cands)
            front[d] = series_by_year[k][d]
        leg_rets.append(w * front.pct_change())
    df = pd.concat(leg_rets, axis=1).dropna(how="all")
    return df.sum(axis=1).fillna(0.0)
