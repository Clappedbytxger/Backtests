"""Volume-footprint & candle aggregation from cached OHLCV bars.

This powers the ``/api/charts`` terminal (candles + volume profile + footprint).

HONESTY NOTE (read before trusting the delta)
---------------------------------------------
The data lake holds **only OHLCV bars** — there is no tick/trade data and no
bid/ask split anywhere on disk. Two consequences, both surfaced to the UI:

* **Volume-by-price (the profile + POC) is a genuine reconstruction.** Each
  native bar's volume is spread across the price bins its ``[Low, High]`` range
  spans (the standard uniform-over-range OHLC approximation of intrabar volume).

* **The bid/ask DELTA is an APPROXIMATION via the tick rule.** An up bar
  (``Close > Open``) has its volume treated as ask/buy-aggressor, a down bar as
  bid/sell-aggressor, a doji split 50/50. This is *not* real order flow. Every
  footprint payload carries ``approx=True`` and ``delta_method="tick-rule"`` so
  the front-end can label it clearly. Real bid/ask requires Databento's
  ``trades`` schema (``aggressor_side``) — see :func:`fetch_trades_footprint`,
  which is wired but deliberately never called automatically (it spends credit).

All public math functions take a plain OHLCV ``DataFrame`` (UTC ``DatetimeIndex``,
columns ``Open/High/Low/Close/Volume``) so they are unit-testable without the lake.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

# Timeframe vocabulary shared with the API/front-end.
TF_TO_OFFSET = {"1m": "1min", "5m": "5min", "15m": "15min",
                "1h": "1h", "4h": "4h", "1D": "1D"}
TF_MINUTES = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1D": 1440}
TIMEFRAMES = list(TF_TO_OFFSET)

_NY = "America/New_York"  # RTH / trading-day reference for US futures & equities

# Instrument tick sizes (price grid quantum). choose_bin_size() snaps to these so
# footprint rows align to a real exchange grid. Fallbacks cover the rest.
_TICK = {
    "ES": 0.25, "NQ": 0.25, "MES": 0.25, "MNQ": 0.25,
    "GC": 0.1, "SI": 0.005, "HG": 0.0005, "PL": 0.1, "PA": 0.1,
    "6A": 0.0001, "6B": 0.0001, "6C": 0.00005, "6E": 0.00005, "6J": 0.0000005,
    "ZC": 0.25, "ZW": 0.25, "ZS": 0.25, "CL": 0.01, "NG": 0.001,
}


# --------------------------------------------------------------------- helpers
def _ensure_utc(df: pd.DataFrame) -> pd.DataFrame:
    """Return ``df`` with a tz-aware UTC DatetimeIndex (no-op if already UTC)."""
    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx, utc=True)
    elif idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    out = df.copy()
    out.index = idx
    return out


def filter_rth(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only US regular-trading-hours bars (09:30–16:00 America/New_York).

    Meaningful for ES/NQ/equities; for 24h markets (crypto/FX) callers pass
    ``rth=False`` and this is never invoked.
    """
    if df.empty:
        return df
    et = df.index.tz_convert(_NY)
    tod = et.hour * 60 + et.minute
    mask = (tod >= 9 * 60 + 30) & (tod < 16 * 60) & (et.weekday < 5)
    return df[mask]


def split_adjust(bars: pd.DataFrame, splits) -> pd.DataFrame:
    """Split-adjust RAW OHLCV bars, TradingView-style (prices ÷ factor, volume × factor).

    ``splits`` is a Series/dict of ``{ex_date -> ratio}`` (e.g. ``4.0`` for a 4:1).
    Every bar on a calendar day *strictly before* an ex-date is divided by that
    ratio (and its volume multiplied), so the most recent data is unchanged and the
    dollar-volume per bar is preserved. Dividends are intentionally NOT adjusted —
    the absolute price levels stay real, which is what a volume footprint needs.
    Only meaningful for equities; futures/crypto callers pass no splits.
    """
    if bars is None or bars.empty or splits is None or len(splits) == 0:
        return bars
    df = _ensure_utc(bars)
    et = df.index.tz_convert(_NY)
    bar_key = (et.year * 10000 + et.month * 100 + et.day).to_numpy()  # ET calendar date
    factor = np.ones(len(df), dtype="float64")
    items = splits.items() if hasattr(splits, "items") else dict(splits).items()
    for d, ratio in items:
        try:
            r = float(ratio)
        except (TypeError, ValueError):
            continue
        if r <= 0 or r == 1.0:
            continue
        ed = pd.Timestamp(d)
        ex_key = ed.year * 10000 + ed.month * 100 + ed.day
        factor[bar_key < ex_key] *= r
    if np.allclose(factor, 1.0):
        return df
    out = df.copy()
    for c in ("Open", "High", "Low", "Close"):
        out[c] = out[c].to_numpy() / factor
    out["Volume"] = out["Volume"].to_numpy() * factor
    return out


def _decimals(step: float) -> int:
    """Sensible rounding precision for a given price step."""
    if step >= 1:
        return 2
    return min(8, max(2, -int(math.floor(math.log10(step))) + 1))


def instrument_tick(ticker: str | None, asset_class: str | None = None,
                    price: float | None = None) -> float:
    """Best-guess exchange tick size for a ticker / asset class."""
    root = (ticker or "").upper().split("_")[0].split(".")[0]
    if root in _TICK:
        return _TICK[root]
    if asset_class == "equities":
        return 0.01
    if price and price > 0:  # generic: ~1/1000th of price magnitude
        return 10 ** (math.floor(math.log10(price)) - 3)
    return 0.01


def choose_bin_size(low: float, high: float, tick: float, target_rows: int = 80) -> float:
    """A constant price-bin size for the window, snapped up to a multiple of ``tick``.

    One bin size for the whole request keeps footprint rows aligned horizontally
    across clusters. ``target_rows`` is the rough number of price levels desired
    across the visible high–low range.
    """
    rng = max(high - low, tick)
    raw = rng / max(target_rows, 1)
    if raw <= tick:
        return tick
    return math.ceil(raw / tick) * tick


def _agg_ohlcv(frame: pd.DataFrame) -> dict:
    return {
        "open": float(frame["Open"].iloc[0]),
        "high": float(frame["High"].max()),
        "low": float(frame["Low"].min()),
        "close": float(frame["Close"].iloc[-1]),
        "volume": float(frame["Volume"].sum()),
    }


def _cluster_keys(df: pd.DataFrame, timeframe: str):
    """Bucket key per row, matching aggregate_candles() bucket boundaries."""
    if timeframe == "1D":
        return df.index.tz_convert(_NY).normalize()  # ET trading day
    return df.index.floor(TF_TO_OFFSET[timeframe])    # UTC-anchored intraday bucket


def _bucket_time(key: pd.Timestamp, timeframe: str):
    """Serialise a bucket key to a lightweight-charts time value."""
    if timeframe == "1D":
        d = key.date()
        return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"  # BusinessDay string
    return int(key.tz_convert("UTC").timestamp())          # UTCTimestamp (seconds)


# ----------------------------------------------------------------- candles API
def aggregate_candles(bars: pd.DataFrame, timeframe: str, rth: bool = False) -> list[dict]:
    """Aggregate native OHLCV bars into ``timeframe`` candles for lightweight-charts.

    Returns a list of ``{time, open, high, low, close, volume}`` dicts ordered by
    time. ``time`` is unix seconds (intraday) or a ``"YYYY-MM-DD"`` string (1D).
    """
    if timeframe not in TF_TO_OFFSET:
        raise ValueError(f"unknown timeframe {timeframe!r}")
    df = _ensure_utc(bars)
    if rth:
        df = filter_rth(df)
    if df.empty:
        return []

    # Vectorised aggregation (a per-group Python loop is ~10x slower on 1m windows).
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    if timeframe == "1D":
        g = df.groupby(df.index.tz_convert(_NY).normalize()).agg(agg).dropna(subset=["Open"])
        times = [f"{k.year:04d}-{k.month:02d}-{k.day:02d}" for k in g.index]
    else:
        g = (df.resample(TF_TO_OFFSET[timeframe], label="left", closed="left")
               .agg(agg).dropna(subset=["Open"]))
        # resolution-independent epoch seconds (DuckDB hands back microsecond stamps)
        times = (g.index.tz_convert("UTC").tz_localize(None)
                 .to_numpy().astype("datetime64[s]").astype("int64").tolist())
    o, h, lo_, c, v = (g["Open"].tolist(), g["High"].tolist(), g["Low"].tolist(),
                       g["Close"].tolist(), g["Volume"].tolist())
    return [{"time": t, "open": oo, "high": hh, "low": ll, "close": cc, "volume": vv}
            for t, oo, hh, ll, cc, vv in zip(times, o, h, lo_, c, v)]


# --------------------------------------------------------------- footprint API
def _value_area(levels: list[dict], total: float, pct: float = 0.70):
    """Value-area high/low: smallest price band around the POC holding ``pct`` of volume."""
    if not levels:
        return None, None
    poc_i = max(range(len(levels)), key=lambda i: levels[i]["total"])
    target = total * pct
    acc = levels[poc_i]["total"]
    lo_i = hi_i = poc_i
    n = len(levels)
    while acc < target and (lo_i > 0 or hi_i < n - 1):
        below = levels[lo_i - 1]["total"] if lo_i > 0 else -1.0
        above = levels[hi_i + 1]["total"] if hi_i < n - 1 else -1.0
        if above >= below:
            hi_i += 1
            acc += levels[hi_i]["total"]
        else:
            lo_i -= 1
            acc += levels[lo_i]["total"]
    return levels[hi_i]["price"], levels[lo_i]["price"]


def build_footprint(bars: pd.DataFrame, timeframe: str, bin_size: float | None = None,
                    rth: bool = False, ticker: str | None = None,
                    asset_class: str | None = None, target_rows: int = 80) -> list[dict]:
    """Reconstruct a per-cluster volume footprint from native OHLCV bars.

    For each ``timeframe`` cluster, distributes every native bar's volume across
    the price bins spanning its ``[Low, High]`` (uniform-over-range) and splits it
    into approximate bid/ask via the tick rule (see module docstring). Returns a
    list of cluster dicts with ``levels`` sorted high→low price, plus ``poc_price``
    and value-area bounds. Every cluster carries ``approx=True``.
    """
    if timeframe not in TF_TO_OFFSET:
        raise ValueError(f"unknown timeframe {timeframe!r}")
    df = _ensure_utc(bars)
    if rth:
        df = filter_rth(df)
    if df.empty:
        return []

    lo = float(df["Low"].min())
    hi = float(df["High"].max())
    tick = instrument_tick(ticker, asset_class, price=(lo + hi) / 2)
    if not bin_size or bin_size <= 0:
        bin_size = choose_bin_size(lo, hi, tick, target_rows)
    origin = math.floor(lo / bin_size) * bin_size
    dec = _decimals(bin_size)

    keys = _cluster_keys(df, timeframe)
    clusters: list[dict] = []
    for key, g in df.groupby(keys):
        bins: dict[int, list[float]] = {}  # bin index -> [bid_vol, ask_vol]
        o = g["Open"].to_numpy(float)
        h = g["High"].to_numpy(float)
        lw = g["Low"].to_numpy(float)
        cl = g["Close"].to_numpy(float)
        vol = g["Volume"].to_numpy(float)
        for bo, bh, bl, bc, bv in zip(o, h, lw, cl, vol):
            if bv <= 0:
                continue
            i0 = int(math.floor((bl - origin) / bin_size))
            i1 = int(math.floor((bh - origin) / bin_size))
            if i1 < i0:
                i1 = i0
            share = bv / (i1 - i0 + 1)
            sign = 1 if bc > bo else (-1 if bc < bo else 0)
            for i in range(i0, i1 + 1):
                cell = bins.setdefault(i, [0.0, 0.0])
                if sign > 0:
                    cell[1] += share
                elif sign < 0:
                    cell[0] += share
                else:  # doji: split so bid+ask == total is preserved exactly
                    cell[0] += share / 2
                    cell[1] += share / 2

        levels = []
        for i in sorted(bins, reverse=True):  # high price -> low price
            bid, ask = bins[i]
            price = round(origin + i * bin_size + bin_size / 2, dec)
            levels.append({"price": float(price), "bid_volume": float(round(bid, 2)),
                           "ask_volume": float(round(ask, 2)), "delta": float(round(ask - bid, 2)),
                           "total": float(round(bid + ask, 2))})

        agg = _agg_ohlcv(g)
        total_vol = agg["volume"]
        poc_price = max(levels, key=lambda l: l["total"])["price"] if levels else None
        va_high, va_low = _value_area(levels, total_vol)
        clusters.append({
            "time": _bucket_time(key, timeframe),
            **agg,
            "total_volume": round(total_vol, 2),
            "poc_price": poc_price,
            "value_area_high": va_high,
            "value_area_low": va_low,
            "bin_size": bin_size,
            "approx": True,
            "delta_method": "tick-rule",
            "levels": levels,
        })
    clusters.sort(key=lambda r: (r["time"] if isinstance(r["time"], str) else f"{r['time']:020d}"))
    return clusters


# --------------------------------------------------------- lake loaders (DuckDB)
def _pq(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def _utc(ts) -> "pd.Timestamp":
    t = pd.Timestamp(ts)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def dataset_bounds(lake, dataset: str, time_col: str | None = None):
    """(min_ts, max_ts) of a dataset as tz-aware UTC Timestamps (row-group stats; instant)."""
    tcol = time_col or lake.time_column(dataset)
    q = f'SELECT min("{tcol}") lo, max("{tcol}") hi FROM read_parquet({_pq(lake.path(dataset))})'
    r = lake.sql(q)
    return _utc(r["lo"].iloc[0]), _utc(r["hi"].iloc[0])


def load_bars(lake, dataset: str, start=None, end=None,
              time_col: str | None = None) -> pd.DataFrame:
    """Read an OHLCV window from a Parquet dataset via DuckDB (predicate pushdown).

    Only the rows in ``[start, end]`` are scanned, so slicing the 5.5M-row ES file
    for a chart window stays well under the 200ms target.
    """
    tcol = time_col or lake.time_column(dataset)
    where, params = [], []
    if start is not None:
        where.append(f'"{tcol}" >= ?')
        params.append(_utc(start).to_pydatetime())
    if end is not None:
        where.append(f'"{tcol}" <= ?')
        params.append(_utc(end).to_pydatetime())
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    q = (f'SELECT "{tcol}", "Open", "High", "Low", "Close", "Volume" '
         f'FROM read_parquet({_pq(lake.path(dataset))}){clause} ORDER BY "{tcol}"')
    df = lake.sql(q, params)
    if df.empty:
        return df
    df[tcol] = pd.to_datetime(df[tcol], utc=True)
    df = df.set_index(tcol)
    df.index.name = "Date"
    return df[["Open", "High", "Low", "Close", "Volume"]]


# ------------------------------------------------- real bid/ask (opt-in, no auto)
def footprint_levels(lake, dataset: str, timeframe: str, start, end, **kw) -> list[dict]:
    """Footprint for a window: REAL bid/ask if a trades cache exists, else approx.

    Source abstraction so the front-end stays the same when real trade data lands.
    Today only the approximation path is wired (no trades on disk). The per-day
    cache convention is ``data/cache/footprint/{ticker}/{YYYY-MM-DD}.parquet``;
    populate it via :func:`fetch_trades_footprint` (opt-in, costs credit).
    """
    bars = load_bars(lake, dataset, start, end)
    return build_footprint(bars, timeframe, **kw)


def fetch_trades_footprint(symbol: str, start: str, end: str, max_usd: float = 5.0):
    """OPT-IN: build a REAL bid/ask footprint cache from Databento ``trades``.

    Deliberately NOT called by any endpoint — it spends metered Databento credit.
    Lessons learned (CLAUDE.md): a bulk ``to_df()`` over tens of millions of trade
    rows OOMs *after* the metered transfer (~$30 burned once). So this MUST stream
    **per day** and write each day's Parquet immediately, and MUST gate on
    :func:`quantlab.futures_intraday.estimate_cost` first.

    Implementation intentionally left as a guarded stub until the user opts in.
    """
    raise NotImplementedError(
        "Real-trades footprint is opt-in and costs Databento credit. Implement "
        "per-day streaming (schema='trades', aggressor side -> bid/ask) with an "
        "estimate_cost() gate before enabling. The chart uses the tick-rule "
        "approximation until then."
    )
