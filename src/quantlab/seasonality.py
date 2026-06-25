"""Seasonality analytics — Seasonax-style pattern detection & validation.

This is the *analytics* layer (averaged seasonal profiles, window scoring,
alpha-decay checks) that powers the Quant-OS Seasonal Calendar. It is distinct
from :mod:`quantlab.seasonal`, which holds the *decision-time signal builders*
used inside backtests. Here we reuse those primitives plus
:mod:`quantlab.metrics` / :mod:`quantlab.significance` — never re-implementing a
metric or a significance test.

Core ideas
----------
* **Seasonal profile** — average the daily return of every calendar day
  ``(month, day)`` across all available years, then cumulate into the classic
  "average year" equity curve.
* **Window pattern** — a contiguous calendar window ``[start_md, end_md]`` traded
  once per year (long or short). It is scored by the *per-year* window returns:
  mean, median, win rate, and a one-sample t-test (n = number of years), plus an
  annualised Sharpe over the pooled in-window daily returns.
* **Alpha decay** — re-score the same window over the most recent ``recent_years``
  and compare. A pattern that loses significance (recent p-value > 0.05) is
  flagged ``"weak"``; one that also flips its sign or win rate is ``"decayed"``.

All windows are pre-specified calendar windows, so there is no look-ahead: the
return of a window in year *y* uses only prices inside that window. The
``scan_windows`` search *does* test many windows, so its ranked output is a set
of *candidates* to validate (decay + out-of-sample), not confirmed edges — the
caller is told how many windows were scanned so multiple-testing is visible.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd

from .metrics import sharpe_ratio

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _md_label(md: tuple[int, int]) -> str:
    """``(10, 1)`` -> ``"01 Oct"``."""
    m, d = md
    return f"{d:02d} {_MONTHS[m - 1]}"


def window_label(start_md: tuple[int, int], end_md: tuple[int, int]) -> str:
    """Human window label, e.g. ``"01 Oct – 15 Nov"``."""
    return f"{_md_label(start_md)} – {_md_label(end_md)}"


def _wraps(start_md: tuple[int, int], end_md: tuple[int, int]) -> bool:
    """True when the window crosses the year boundary (e.g. Dec -> Jan)."""
    return tuple(end_md) <= tuple(start_md)


# ----------------------------------------------------------------- profile
def seasonal_profile(prices: pd.Series, lookback_years: int | None = None) -> pd.DataFrame:
    """Average daily-return profile across the calendar year.

    For every calendar day ``(month, day)`` average the simple daily return over
    all available years, then cumulate into the "average year" curve. The index
    is an ordered list of ``(month, day)`` buckets (Jan 1 .. Dec 31, leap-day
    included when present).

    Args:
        prices: daily adjusted close, datetime-indexed.
        lookback_years: if given, only use the last N calendar years.

    Returns columns: ``month, day, doy, label, mean_return, hit_rate, n_years,
    cum_return`` (cum_return in %, starting at 0).
    """
    px = prices.dropna()
    if lookback_years is not None:
        cutoff = px.index.max() - pd.DateOffset(years=lookback_years)
        px = px[px.index >= cutoff]
    ret = px.pct_change().dropna()
    if ret.empty:
        return pd.DataFrame(
            columns=["month", "day", "doy", "label", "mean_return",
                     "hit_rate", "n_years", "cum_return"]
        )

    df = pd.DataFrame({"ret": ret.values}, index=ret.index)
    df["month"] = ret.index.month
    df["day"] = ret.index.day

    grp = df.groupby(["month", "day"])["ret"]
    prof = pd.DataFrame({
        "mean_return": grp.mean(),
        "hit_rate": grp.apply(lambda s: float((s > 0).mean())),
        "n_years": grp.count(),
    }).reset_index()
    prof = prof.sort_values(["month", "day"]).reset_index(drop=True)
    prof["doy"] = np.arange(1, len(prof) + 1)
    prof["label"] = [f"{d:02d} {_MONTHS[m - 1]}" for m, d in zip(prof["month"], prof["day"])]
    # Cumulative "average year" curve in percent, anchored at 0.
    prof["cum_return"] = ((1.0 + prof["mean_return"]).cumprod() - 1.0) * 100.0
    return prof


def monthly_heatmap(prices: pd.Series) -> dict:
    """Month-by-year return matrix (in %) for the outlier-spotting heatmap.

    Returns ``{"years": [...], "months": ["Jan"..], "matrix": [[..]],
    "monthly_avg": [..], "yearly_total": [..]}`` where ``matrix[i][j]`` is the
    return of month ``j`` in year ``years[i]`` (percent, ``None`` if missing).
    """
    px = prices.dropna()
    monthly = px.resample("ME").last().pct_change().dropna() * 100.0
    if monthly.empty:
        return {"years": [], "months": _MONTHS, "matrix": [],
                "monthly_avg": [None] * 12, "yearly_total": []}

    frame = pd.DataFrame({"ret": monthly.values}, index=monthly.index)
    frame["year"] = monthly.index.year
    frame["month"] = monthly.index.month
    pivot = frame.pivot_table(index="year", columns="month", values="ret")
    pivot = pivot.reindex(columns=range(1, 13))

    years = [int(y) for y in pivot.index]
    matrix = [[None if pd.isna(v) else round(float(v), 2) for v in row]
              for row in pivot.values]
    monthly_avg = [None if pd.isna(v) else round(float(v), 2)
                   for v in pivot.mean(axis=0).values]
    # Yearly total (compounded across that year's observed months), in %.
    yearly_total = []
    for _, row in pivot.iterrows():
        vals = row.dropna() / 100.0
        yearly_total.append(round(float(((1 + vals).prod() - 1) * 100.0), 2)
                            if len(vals) else None)
    return {"years": years, "months": _MONTHS, "matrix": matrix,
            "monthly_avg": monthly_avg, "yearly_total": yearly_total}


# ----------------------------------------------------------------- windows
def _window_year_returns(
    prices: pd.Series,
    start_md: tuple[int, int],
    end_md: tuple[int, int],
    direction: str = "long",
) -> tuple[pd.Series, pd.Series]:
    """Per-year window return + pooled in-window daily returns.

    Returns ``(yearly, daily)`` where ``yearly`` is one return per year (indexed
    by entry year) for buying at the first trading day in the window and selling
    at the last, and ``daily`` is the concatenation of the daily returns inside
    every window (for an annualised Sharpe). ``direction == "short"`` flips signs.
    """
    px = prices.dropna()
    if px.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    # Work on numpy: searchsorted on int64 timestamps is O(log n) per window edge,
    # vs an O(n) boolean mask — this is the hot path of scan_windows.
    idx = px.index
    ts = idx.values.astype("datetime64[ns]")
    vals = px.values.astype(float)
    dret = np.empty_like(vals)
    dret[0] = np.nan
    dret[1:] = vals[1:] / vals[:-1] - 1.0

    wraps = _wraps(start_md, end_md)
    sign = -1.0 if direction == "short" else 1.0

    yearly: dict[int, float] = {}
    daily_parts: list[np.ndarray] = []
    for y in range(int(idx.year.min()), int(idx.year.max()) + 1):
        try:
            start_ts = np.datetime64(pd.Timestamp(y, *start_md))
            end_ts = np.datetime64(pd.Timestamp(y + 1 if wraps else y, *end_md))
        except ValueError:
            continue  # e.g. Feb 29 in a non-leap year — skip safely
        lo = int(np.searchsorted(ts, start_ts, side="left"))
        hi = int(np.searchsorted(ts, end_ts, side="right"))
        if hi - lo < 2:
            continue
        yearly[y] = float(vals[hi - 1] / vals[lo] - 1.0) * sign
        daily_parts.append(dret[lo + 1:hi] * sign)  # skip entry bar

    yearly_s = pd.Series(yearly, name="window_return").sort_index()
    daily_s = (pd.Series(np.concatenate(daily_parts)) if daily_parts
               else pd.Series(dtype=float))
    return yearly_s, daily_s


@dataclass
class SeasonalPattern:
    """One seasonal window pattern with its validation statistics.

    Returns are fractional (0.05 = +5%); win_rate and p_value in [0, 1].
    ``status`` is the alpha-decay verdict: ``"active"`` (still significant
    recently), ``"weak"`` (recent p > 0.05), ``"decayed"`` (recent sign/edge
    gone). Fields are JSON-serialisable via :meth:`to_dict`.
    """
    ticker: str
    name: str
    asset_class: str
    direction: str
    start_md: tuple[int, int]
    end_md: tuple[int, int]
    window_label: str
    calendar_days: int
    n_years: int
    mean_return: float
    median_return: float
    win_rate: float
    std: float
    sharpe: float
    t_stat: float
    p_value: float
    # alpha-decay (recent sub-sample); None when too few recent years
    recent_years: int | None = None
    recent_mean: float | None = None
    recent_win_rate: float | None = None
    recent_p_value: float | None = None
    status: str = "active"
    # forward timing (filled by upcoming filter, relative to a reference date)
    days_until_start: int | None = None
    next_start: str | None = None
    next_end: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start_md"] = list(self.start_md)
        d["end_md"] = list(self.end_md)
        return d


def _decay_status(
    full_p: float, recent_mean: float | None,
    full_mean: float, recent_p: float | None,
) -> str:
    """Classify alpha decay from full vs recent significance."""
    if recent_p is None or recent_mean is None:
        return "active" if full_p < 0.05 else "weak"
    sign_flip = (recent_mean * full_mean) < 0
    if sign_flip or recent_mean <= 0:
        return "decayed"
    if recent_p > 0.05:
        return "weak"
    return "active"


def evaluate_window(
    prices: pd.Series,
    start_md: tuple[int, int],
    end_md: tuple[int, int],
    *,
    ticker: str = "",
    name: str = "",
    asset_class: str = "",
    direction: str = "long",
    recent_years: int = 5,
) -> SeasonalPattern | None:
    """Score one calendar window into a validated :class:`SeasonalPattern`.

    Uses per-year window returns for the t-test / win rate (n = years) and the
    pooled in-window daily returns for an annualised Sharpe. Also re-scores the
    most recent ``recent_years`` for the alpha-decay verdict. Returns ``None``
    when there are too few years (< 5) to say anything.
    """
    yearly, daily = _window_year_returns(prices, start_md, end_md, direction)
    if len(yearly) < 5:
        return None

    from scipy import stats  # local import keeps module import cheap
    t_stat, p_value = stats.ttest_1samp(yearly.values, 0.0)
    sharpe = sharpe_ratio(daily) if len(daily) > 2 else float("nan")

    # Recent sub-sample for decay.
    recent = yearly[yearly.index >= (int(yearly.index.max()) - recent_years + 1)]
    r_mean = r_wr = r_p = None
    if len(recent) >= 3:
        r_mean = float(recent.mean())
        r_wr = float((recent > 0).mean())
        _, r_p = stats.ttest_1samp(recent.values, 0.0)
        r_p = float(r_p)

    full_mean = float(yearly.mean())
    cal_days = (pd.Timestamp(2001 if _wraps(start_md, end_md) else 2000, *end_md)
                - pd.Timestamp(2000, *start_md)).days

    return SeasonalPattern(
        ticker=ticker, name=name or ticker, asset_class=asset_class,
        direction=direction, start_md=tuple(start_md), end_md=tuple(end_md),
        window_label=window_label(start_md, end_md), calendar_days=int(cal_days),
        n_years=int(len(yearly)), mean_return=full_mean,
        median_return=float(yearly.median()), win_rate=float((yearly > 0).mean()),
        std=float(yearly.std(ddof=1)), sharpe=float(sharpe),
        t_stat=float(t_stat), p_value=float(p_value),
        recent_years=recent_years, recent_mean=r_mean,
        recent_win_rate=r_wr, recent_p_value=r_p,
        status=_decay_status(float(p_value), r_mean, full_mean, r_p),
    )


def scan_windows(
    prices: pd.Series,
    *,
    ticker: str = "",
    name: str = "",
    asset_class: str = "",
    min_len: int = 10,
    max_len: int = 60,
    step_len: int = 10,
    step_start: int = 5,
    both_directions: bool = True,
    min_win_rate: float = 0.0,
    max_p_value: float = 1.0,
    top: int = 20,
) -> tuple[list[SeasonalPattern], int]:
    """Brute-force search for the strongest seasonal windows of an asset.

    Slides calendar windows of length ``min_len..max_len`` calendar days (in
    ``step_len`` steps), anchored every ``step_start`` days through the year, and
    scores each with :func:`evaluate_window`. Long (and, if ``both_directions``,
    short) variants are tried. Returns ``(patterns, n_scanned)`` — the ranked
    survivors plus how many windows were scanned (for multiple-testing honesty).

    Ranking favours significant, high-hit-rate, high-Sharpe windows.
    """
    patterns: list[SeasonalPattern] = []
    n_scanned = 0
    directions = ["long", "short"] if both_directions else ["long"]
    lengths = range(min_len, max_len + 1, step_len)
    # Anchor start dates by day-of-year on a reference (leap) year for full coverage.
    ref = 2000
    for doy in range(1, 366, step_start):
        start_ts = pd.Timestamp(ref, 1, 1) + pd.Timedelta(days=doy - 1)
        start_md = (start_ts.month, start_ts.day)
        for length in lengths:
            end_ts = start_ts + pd.Timedelta(days=length)
            end_md = (end_ts.month, end_ts.day)
            for direction in directions:
                n_scanned += 1
                pat = evaluate_window(
                    prices, start_md, end_md, ticker=ticker, name=name,
                    asset_class=asset_class, direction=direction,
                )
                if pat is None:
                    continue
                if pat.win_rate < min_win_rate or pat.p_value > max_p_value:
                    continue
                patterns.append(pat)

    patterns = _dedupe_overlapping(patterns)
    patterns.sort(key=_rank_key, reverse=True)
    return patterns[:top], n_scanned


def _rank_key(p: SeasonalPattern) -> float:
    """Composite score: reward Sharpe + win-rate edge, penalise weak/decayed."""
    sharpe = 0.0 if np.isnan(p.sharpe) else p.sharpe
    base = sharpe + 4.0 * (p.win_rate - 0.5) + 30.0 * abs(p.mean_return)
    if p.status == "weak":
        base *= 0.6
    elif p.status == "decayed":
        base *= 0.3
    return base


def _overlap(a: SeasonalPattern, b: SeasonalPattern) -> bool:
    """Two windows overlap if their day-of-year spans intersect (same direction)."""
    if a.direction != b.direction:
        return False
    def span(p):
        s = pd.Timestamp(2000, *p.start_md).dayofyear
        e = s + p.calendar_days
        return s, e
    s1, e1 = span(a)
    s2, e2 = span(b)
    return not (e1 < s2 or e2 < s1)


def _dedupe_overlapping(patterns: list[SeasonalPattern]) -> list[SeasonalPattern]:
    """Greedy non-overlap: keep the best-ranked window, drop ones overlapping it."""
    kept: list[SeasonalPattern] = []
    for p in sorted(patterns, key=_rank_key, reverse=True):
        if not any(_overlap(p, k) for k in kept):
            kept.append(p)
    return kept


# ----------------------------------------------------------------- upcoming
def _next_occurrence(start_md: tuple[int, int], ref: date) -> date:
    """Next calendar date on/after ``ref`` matching ``(month, day)``."""
    year = ref.year
    for y in (year, year + 1):
        try:
            cand = date(y, *start_md)
        except ValueError:  # Feb 29 -> roll to Mar 1 of that year
            cand = date(y, 3, 1)
        if cand >= ref:
            return cand
    return date(year + 1, *start_md)


def annotate_upcoming(
    patterns: list[SeasonalPattern], ref: date, horizon_days: int = 14,
) -> list[SeasonalPattern]:
    """Fill forward-timing fields and keep only windows starting within horizon.

    A pattern "starts soon" if its window start is within ``horizon_days``
    calendar days of ``ref`` (windows already in progress are excluded — use
    ``days_until_start >= 0``). Sorted by soonest start.
    """
    out: list[SeasonalPattern] = []
    for p in patterns:
        nxt = _next_occurrence(p.start_md, ref)
        delta = (nxt - ref).days
        if 0 <= delta <= horizon_days:
            p.days_until_start = delta
            p.next_start = nxt.isoformat()
            end_year = nxt.year + 1 if _wraps(p.start_md, p.end_md) else nxt.year
            try:
                p.next_end = date(end_year, *p.end_md).isoformat()
            except ValueError:
                p.next_end = date(end_year, 3, 1).isoformat()
            out.append(p)
    out.sort(key=lambda q: (q.days_until_start, -_rank_key(q)))
    return out


# ----------------------------------------------------------------- intraday
# Intraday seasonality: time-of-day, day-of-week and a weekday x hour grid over
# the cached 1-minute lake (ES/NQ/GC/6B + ~50 Nasdaq names + BTC). These are
# *gross* analytics — the repo's own work (strategies 0038-0041) shows a single
# liquid market's intraday DIRECTION is not tradable net of cost, so these views
# are for structure/context, not a standalone edge. Returns are in basis points.
_WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def intraday_hour_profile(hourly_returns: pd.Series) -> list[dict]:
    """Average return per exchange-local clock hour, with a cumulative day curve.

    ``hourly_returns`` is the per-bar return (close/open - 1) of hourly bars,
    indexed by a tz-aware local timestamp. Returns one row per hour with mean
    (bps), hit rate, count, t-test p-value and the cumulative "average day"
    curve (bps, summed across hours).
    """
    from scipy import stats
    r = hourly_returns.dropna()
    if r.empty:
        return []
    df = pd.DataFrame({"ret": r.values})
    df["hour"] = r.index.hour
    rows = []
    for h, g in df.groupby("hour"):
        s = g["ret"]
        t, p = stats.ttest_1samp(s, 0.0) if len(s) > 2 else (float("nan"), float("nan"))
        rows.append({"hour": int(h), "mean_bps": round(float(s.mean()) * 1e4, 3),
                     "hit_rate": round(float((s > 0).mean()), 4), "n": int(len(s)),
                     "p_value": round(float(p), 4)})
    rows.sort(key=lambda x: x["hour"])
    cum = 0.0
    for row in rows:
        cum += row["mean_bps"]
        row["cum_bps"] = round(cum, 3)
    return rows


def intraday_weekday_profile(daily_returns: pd.Series) -> list[dict]:
    """Average session return per weekday (the day-of-week effect).

    ``daily_returns`` is the per-day session return (close/open - 1), indexed by
    a tz-aware local date. Returns one row per observed weekday (Mon..Sun) with
    mean (bps), hit rate, count and a t-test p-value.
    """
    from scipy import stats
    r = daily_returns.dropna()
    if r.empty:
        return []
    df = pd.DataFrame({"ret": r.values})
    df["wd"] = r.index.weekday
    rows = []
    for wd, g in df.groupby("wd"):
        s = g["ret"]
        t, p = stats.ttest_1samp(s, 0.0) if len(s) > 2 else (float("nan"), float("nan"))
        rows.append({"weekday": int(wd), "name": _WEEKDAYS[int(wd)],
                     "mean_bps": round(float(s.mean()) * 1e4, 3),
                     "hit_rate": round(float((s > 0).mean()), 4), "n": int(len(s)),
                     "p_value": round(float(p), 4)})
    rows.sort(key=lambda x: x["weekday"])
    return rows


def intraday_weekday_hour_heatmap(hourly_returns: pd.Series) -> dict:
    """Weekday x hour mean-return grid (bps) for the intraday heatmap.

    Returns ``{"weekdays": [names], "hours": [...], "matrix": [[bps|None]]}``
    where ``matrix[i][j]`` is the mean return of hour ``hours[j]`` on weekday
    ``weekdays[i]``.
    """
    r = hourly_returns.dropna()
    if r.empty:
        return {"weekdays": [], "hours": [], "matrix": []}
    df = pd.DataFrame({"ret": r.values})
    df["wd"] = r.index.weekday
    df["hour"] = r.index.hour
    pivot = df.pivot_table(index="wd", columns="hour", values="ret", aggfunc="mean") * 1e4
    hours = [int(h) for h in pivot.columns]
    wds = [int(w) for w in pivot.index]
    matrix = [[None if pd.isna(v) else round(float(v), 2) for v in row] for row in pivot.values]
    return {"weekdays": [_WEEKDAYS[w] for w in wds], "hours": hours, "matrix": matrix}


# ----------------------------------------------------------------- universe
# Curated, macro-justifiable starting universe across asset classes. Each entry
# is a free yfinance symbol so the dashboard works out of the box; arbitrary
# tickers are also accepted by the API. ``note`` is the supply/demand rationale.
SEASONAL_UNIVERSE: list[dict] = [
    # --- Commodities / futures ------------------------------------------------
    {"ticker": "GC=F", "name": "Gold", "asset_class": "commodity",
     "note": "Pre-CNY & Indian wedding/festival physical demand; year-end safe-haven."},
    {"ticker": "SI=F", "name": "Silver", "asset_class": "commodity",
     "note": "Industrial + jewellery demand; tracks gold seasonality with higher beta."},
    {"ticker": "HG=F", "name": "Copper", "asset_class": "commodity",
     "note": "China restocking & construction season (spring); industrial demand cycle."},
    {"ticker": "PL=F", "name": "Platinum", "asset_class": "commodity",
     "note": "Turn-of-year autocatalyst restocking (strategy 0019/0021)."},
    {"ticker": "PA=F", "name": "Palladium", "asset_class": "commodity",
     "note": "Autocatalyst demand; tight supply, platinum cross-seasonality."},
    {"ticker": "CL=F", "name": "WTI Crude Oil", "asset_class": "commodity",
     "note": "Driving-season build into summer; refinery maintenance shoulders."},
    {"ticker": "RB=F", "name": "Gasoline", "asset_class": "commodity",
     "note": "Pre-driving-season spec build (Feb-May); summer demand peak."},
    {"ticker": "HO=F", "name": "Heating Oil", "asset_class": "commodity",
     "note": "Winter distillate demand; autumn build."},
    {"ticker": "NG=F", "name": "Natural Gas", "asset_class": "commodity",
     "note": "Heating demand autumn->winter; injection-season summer softness."},
    {"ticker": "ZC=F", "name": "Corn", "asset_class": "commodity",
     "note": "Planting/old-crop spring strength; harvest-pressure autumn lows."},
    {"ticker": "ZW=F", "name": "Wheat", "asset_class": "commodity",
     "note": "Northern-hemisphere weather/harvest cycle."},
    {"ticker": "ZS=F", "name": "Soybeans", "asset_class": "commodity",
     "note": "US growing-season weather premium; South-American harvest."},
    {"ticker": "KC=F", "name": "Coffee", "asset_class": "commodity",
     "note": "Brazilian frost-risk window (Jun-Aug) supply scares."},
    {"ticker": "SB=F", "name": "Sugar", "asset_class": "commodity",
     "note": "Brazil/India harvest & crush cycle; ethanol parity."},
    {"ticker": "CT=F", "name": "Cotton", "asset_class": "commodity",
     "note": "US planting/harvest cycle; year-end demand."},
    {"ticker": "LE=F", "name": "Live Cattle", "asset_class": "commodity",
     "note": "Grilling-season demand (spring) & placement cycle."},
    # --- Indices / ETFs -------------------------------------------------------
    {"ticker": "SPY", "name": "S&P 500", "asset_class": "index",
     "note": "Sell-in-May / Halloween; Santa-rally & turn-of-month flow."},
    {"ticker": "QQQ", "name": "Nasdaq 100", "asset_class": "index",
     "note": "Same calendar flow as SPY with higher beta."},
    {"ticker": "DIA", "name": "Dow Jones 30", "asset_class": "index",
     "note": "Blue-chip calendar flow; turn-of-month & year-end."},
    {"ticker": "IWM", "name": "Russell 2000", "asset_class": "index",
     "note": "January small-cap effect; year-end tax-loss bounce."},
    {"ticker": "EEM", "name": "Emerging Markets", "asset_class": "index",
     "note": "Risk-appetite & USD seasonality."},
    {"ticker": "^GDAXI", "name": "DAX 40", "asset_class": "index",
     "note": "European equity calendar; summer lull, year-end strength."},
    {"ticker": "XLE", "name": "Energy Sector", "asset_class": "index",
     "note": "Tracks crude driving-season; cyclical risk appetite."},
    {"ticker": "XLF", "name": "Financials Sector", "asset_class": "index",
     "note": "Rate cycle & earnings-season flow."},
    {"ticker": "XLK", "name": "Technology Sector", "asset_class": "index",
     "note": "Product/earnings cycle; risk-on calendar."},
    {"ticker": "SMH", "name": "Semiconductors", "asset_class": "index",
     "note": "Chip demand cycle; high-beta tech seasonality."},
    {"ticker": "XLV", "name": "Health Care Sector", "asset_class": "index",
     "note": "Defensive; year-end rotation & policy calendar."},
    {"ticker": "XLU", "name": "Utilities Sector", "asset_class": "index",
     "note": "Defensive bond-proxy; summer demand & rate seasonality."},
    {"ticker": "GDX", "name": "Gold Miners", "asset_class": "index",
     "note": "Levered gold seasonality (pre-CNY, year-end)."},
    {"ticker": "TLT", "name": "20Y+ Treasuries", "asset_class": "index",
     "note": "Month-end duration demand (strategy 0050/0075); flight-to-quality."},
    # --- Single stocks --------------------------------------------------------
    {"ticker": "AAPL", "name": "Apple", "asset_class": "equity",
     "note": "Product-cycle (Sep launch) & holiday-quarter demand."},
    {"ticker": "MSFT", "name": "Microsoft", "asset_class": "equity",
     "note": "Enterprise budget flush (Q4/Q2) & mega-cap calendar."},
    {"ticker": "GOOGL", "name": "Alphabet", "asset_class": "equity",
     "note": "Ad-spend cycle; Q4 holiday advertising."},
    {"ticker": "AMZN", "name": "Amazon", "asset_class": "equity",
     "note": "Q4 holiday retail; Prime-Day summer bump."},
    {"ticker": "META", "name": "Meta Platforms", "asset_class": "equity",
     "note": "Ad-spend seasonality; Q4 holiday advertising peak."},
    {"ticker": "NVDA", "name": "Nvidia", "asset_class": "equity",
     "note": "Earnings-cycle & product-launch momentum."},
    {"ticker": "AMD", "name": "AMD", "asset_class": "equity",
     "note": "Chip-cycle high-beta; product-launch calendar."},
    {"ticker": "TSLA", "name": "Tesla", "asset_class": "equity",
     "note": "Quarter-end delivery push; high-beta risk sentiment."},
    {"ticker": "AVGO", "name": "Broadcom", "asset_class": "equity",
     "note": "Semi demand cycle; dividend & earnings calendar."},
    {"ticker": "NFLX", "name": "Netflix", "asset_class": "equity",
     "note": "Content-slate & subscriber-season (Q1/Q4)."},
    {"ticker": "JPM", "name": "JPMorgan", "asset_class": "equity",
     "note": "Earnings-season bellwether; rate cycle."},
    {"ticker": "V", "name": "Visa", "asset_class": "equity",
     "note": "Holiday-quarter payment volumes; consumer spend cycle."},
    {"ticker": "XOM", "name": "Exxon Mobil", "asset_class": "equity",
     "note": "Tracks crude driving-season seasonality."},
    {"ticker": "CVX", "name": "Chevron", "asset_class": "equity",
     "note": "Energy seasonality; dividend calendar."},
    {"ticker": "LLY", "name": "Eli Lilly", "asset_class": "equity",
     "note": "Defensive pharma; product-cycle momentum."},
    {"ticker": "UNH", "name": "UnitedHealth", "asset_class": "equity",
     "note": "Enrollment-season (Q4) & medical-cost calendar."},
    {"ticker": "COST", "name": "Costco", "asset_class": "equity",
     "note": "Holiday & membership-renewal seasonality."},
    {"ticker": "WMT", "name": "Walmart", "asset_class": "equity",
     "note": "Defensive retail; Q4 holiday demand."},
    {"ticker": "HD", "name": "Home Depot", "asset_class": "equity",
     "note": "Spring home-improvement season; housing cycle."},
    {"ticker": "NKE", "name": "Nike", "asset_class": "equity",
     "note": "Back-to-school & holiday demand; product drops."},
    {"ticker": "DIS", "name": "Disney", "asset_class": "equity",
     "note": "Park-attendance season; content/holiday calendar."},
    {"ticker": "CAT", "name": "Caterpillar", "asset_class": "equity",
     "note": "Construction-season cyclical; global capex cycle."},
    {"ticker": "BA", "name": "Boeing", "asset_class": "equity",
     "note": "Delivery & order cycle; travel-demand sentiment."},
    {"ticker": "KO", "name": "Coca-Cola", "asset_class": "equity",
     "note": "Defensive staple; summer beverage demand."},
    # --- Crypto ---------------------------------------------------------------
    {"ticker": "BTC-USD", "name": "Bitcoin", "asset_class": "crypto",
     "note": "Q4 strength / 'Uptober'; post-halving annual cycle."},
    {"ticker": "ETH-USD", "name": "Ethereum", "asset_class": "crypto",
     "note": "Risk-on crypto beta; tracks BTC calendar with dispersion."},
    {"ticker": "SOL-USD", "name": "Solana", "asset_class": "crypto",
     "note": "High-beta alt; risk-on crypto seasonality."},
    {"ticker": "BNB-USD", "name": "BNB", "asset_class": "crypto",
     "note": "Exchange-token; crypto risk cycle."},
    {"ticker": "XRP-USD", "name": "XRP", "asset_class": "crypto",
     "note": "Event/news-driven; broad crypto calendar."},
]

_UNIVERSE_BY_TICKER = {u["ticker"]: u for u in SEASONAL_UNIVERSE}


def universe_meta(ticker: str) -> dict:
    """Look up curated metadata for a ticker (empty-ish dict if unknown)."""
    return _UNIVERSE_BY_TICKER.get(
        ticker, {"ticker": ticker, "name": ticker, "asset_class": "other", "note": ""}
    )
