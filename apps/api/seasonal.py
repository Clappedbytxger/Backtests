"""Quant-OS seasonality API — Seasonax-style seasonal patterns & calendar.

Mounted under ``/api/seasonal`` by :mod:`apps.api.main`. Wraps
:mod:`quantlab.seasonality` (the analytics layer) over the cached yfinance daily
data. Endpoints:

* ``/universe``   — curated cross-asset universe (commodities, indices, stocks, crypto)
* ``/profile``    — averaged "seasonal year" cumulative curve + monthly bucket bars
* ``/heatmap``    — month-by-year return matrix (outlier spotting)
* ``/patterns``   — scan + validate the strongest windows for one ticker
* ``/pattern``    — score one explicit window, with its average in-window path
* ``/upcoming``   — top patterns starting in the next N days (reads the scan snapshot)
* ``/scan``       — POST: (re)build the universe snapshot used by ``/upcoming``

Heavy work (price downloads, window scans) is TTL-cached in-process; the
universe-wide ``/upcoming`` reads a JSON snapshot written by the weekly scan job
(``scripts/seasonal_scan.py``) so the request path stays fast. Every endpoint
degrades to ``{"ok": false, "error": ...}`` — the dashboard convention.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
from datetime import date, datetime

import pandas as pd
from fastapi import APIRouter, Query

from quantlab import footprint as fp
from quantlab import seasonality as sz
from quantlab.config import get_settings
from quantlab.data import get_prices
from quantlab.seasonal import bucket_return_analysis

router = APIRouter(prefix="/api/seasonal", tags=["seasonal"])

# --- in-process caches (downloads + scans are expensive) --------------------
_PRICE_CACHE: dict[str, tuple[float, pd.Series]] = {}
_PRICE_TTL = 6 * 3600.0
_SCAN_CACHE: dict[str, tuple[float, dict]] = {}
_SCAN_TTL = 6 * 3600.0
_INTRADAY_CACHE: dict[str, tuple[float, dict]] = {}
_INTRADAY_TTL = 6 * 3600.0

# Background snapshot-scan state (the universe scan can take minutes).
_SCAN_STATE: dict = {"running": False, "started_at": None, "built_at": None,
                     "error": None, "count": 0, "n_assets": 0}
_SCAN_LOCK = threading.Lock()


def _snapshot_path():
    return get_settings().data_dir / "seasonal" / "patterns.json"


def _load_prices(ticker: str, start: str = "2000-01-01") -> pd.Series:
    """Cached daily adjusted close for a ticker (6h TTL)."""
    now = time.time()
    hit = _PRICE_CACHE.get(ticker)
    if hit and now - hit[0] < _PRICE_TTL:
        return hit[1]
    df = get_prices(ticker, start=start)
    close = df["Close"].dropna()
    close.name = ticker
    _PRICE_CACHE[ticker] = (now, close)
    return close


def _years_span(px: pd.Series) -> dict:
    return {"start": px.index.min().date().isoformat(),
            "end": px.index.max().date().isoformat(),
            "n_years": int(px.index.year.nunique())}


# --------------------------------------------------------------- endpoints
@router.get("/universe")
def universe() -> dict:
    """Curated cross-asset seasonal universe with macro rationale per symbol."""
    return {"ok": True, "count": len(sz.SEASONAL_UNIVERSE),
            "universe": sz.SEASONAL_UNIVERSE}


@router.get("/profile")
def profile(ticker: str, years: int | None = Query(None, ge=3, le=60)) -> dict:
    """Averaged seasonal-year curve + monthly bucket bars for one ticker.

    ``years`` optionally restricts to the most recent N calendar years (e.g. to
    inspect alpha decay visually). The curve is the cumulative average daily
    return across the standardised year; monthly bars come from the shared
    :func:`bucket_return_analysis`.
    """
    try:
        meta = sz.universe_meta(ticker)
        px = _load_prices(ticker)
        prof = sz.seasonal_profile(px, lookback_years=years)
        curve = [{"doy": int(r.doy), "label": r.label,
                  "cum_return": round(float(r.cum_return), 3),
                  "mean_return": round(float(r.mean_return) * 100, 4),
                  "hit_rate": round(float(r.hit_rate), 3)}
                 for r in prof.itertuples()]
        # Monthly average-return bars (reuse the canonical bucket analysis).
        ret = px.pct_change().dropna()
        if years is not None:
            ret = ret[ret.index >= px.index.max() - pd.DateOffset(years=years)]
        buckets = bucket_return_analysis(ret, by="month")
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        monthly = [{"month": months[int(m) - 1],
                    "mean_return": round(float(row.mean_return) * 100 * 21, 3),
                    "hit_rate": round(float(row.hit_rate), 3),
                    "p_value": round(float(row.p_value), 4)}
                   for m, row in buckets.iterrows()]
        return {"ok": True, "ticker": ticker, "meta": meta,
                "span": _years_span(px), "curve": curve, "monthly": monthly}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/heatmap")
def heatmap(ticker: str) -> dict:
    """Month-by-year return matrix (percent) for the outlier heatmap."""
    try:
        px = _load_prices(ticker)
        hm = sz.monthly_heatmap(px)
        return {"ok": True, "ticker": ticker, "meta": sz.universe_meta(ticker), **hm}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/patterns")
def patterns(
    ticker: str,
    top: int = Query(12, ge=1, le=40),
    both_directions: bool = True,
    min_win_rate: float = Query(0.0, ge=0.0, le=1.0),
    max_p_value: float = Query(1.0, ge=0.0, le=1.0),
) -> dict:
    """Scan + validate the strongest seasonal windows for one ticker (cached)."""
    try:
        key = f"{ticker}|{top}|{both_directions}|{min_win_rate}|{max_p_value}"
        now = time.time()
        hit = _SCAN_CACHE.get(key)
        if hit and now - hit[0] < _SCAN_TTL:
            return hit[1]
        meta = sz.universe_meta(ticker)
        px = _load_prices(ticker)
        pats, n_scanned = sz.scan_windows(
            px, ticker=ticker, name=meta["name"], asset_class=meta["asset_class"],
            both_directions=both_directions, min_win_rate=min_win_rate,
            max_p_value=max_p_value, top=top)
        out = {"ok": True, "ticker": ticker, "meta": meta, "span": _years_span(px),
               "n_scanned": n_scanned, "count": len(pats),
               "patterns": [p.to_dict() for p in pats]}
        _SCAN_CACHE[key] = (now, out)
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/pattern")
def pattern(
    ticker: str,
    start: str = Query(..., description="window start as MM-DD"),
    end: str = Query(..., description="window end as MM-DD"),
    direction: str = "long",
) -> dict:
    """Score one explicit calendar window + its average in-window price path."""
    try:
        sm = tuple(int(x) for x in start.split("-"))  # (month, day)
        em = tuple(int(x) for x in end.split("-"))
        meta = sz.universe_meta(ticker)
        px = _load_prices(ticker)
        pat = sz.evaluate_window(px, sm, em, ticker=ticker, name=meta["name"],
                                 asset_class=meta["asset_class"], direction=direction)
        if pat is None:
            return {"ok": False, "error": "too few years for this window"}
        # Average normalised path through the window (entry = 100) for the chart.
        path = _avg_window_path(px, sm, em, direction)
        return {"ok": True, "ticker": ticker, "meta": meta,
                "pattern": pat.to_dict(), "path": path}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _avg_window_path(px: pd.Series, sm, em, direction: str) -> list[dict]:
    """Average rebased (entry=100) path across years, by trading-day offset."""
    sign = -1.0 if direction == "short" else 1.0
    wraps = tuple(em) <= tuple(sm)
    paths: list[list[float]] = []
    idx = px.index
    for y in range(int(idx.year.min()), int(idx.year.max()) + 1):
        try:
            s = pd.Timestamp(y, *sm)
            e = pd.Timestamp(y + 1 if wraps else y, *em)
        except ValueError:
            continue
        seg = px[(idx >= s) & (idx <= e)]
        if len(seg) < 2:
            continue
        rebased = (seg.values / seg.values[0] - 1.0) * sign * 100.0 + 100.0
        paths.append(list(rebased))
    if not paths:
        return []
    n = min(len(p) for p in paths)
    arr = pd.DataFrame([p[:n] for p in paths])
    return [{"t": int(i), "value": round(float(arr[i].mean()), 3)} for i in range(n)]


@router.get("/upcoming")
def upcoming(
    horizon: int = Query(21, ge=1, le=120),
    top: int = Query(20, ge=1, le=100),
    asof: str | None = None,
) -> dict:
    """Top seasonal patterns starting within ``horizon`` days (from snapshot).

    Reads the universe snapshot written by ``scripts/seasonal_scan.py``. If the
    snapshot is missing the response says so (call ``POST /scan`` to build it).
    """
    try:
        ref = date.fromisoformat(asof) if asof else date.today()
        snap = _read_snapshot()
        if snap is None:
            return {"ok": True, "exists": False, "asof": ref.isoformat(),
                    "count": 0, "patterns": [],
                    "hint": "no snapshot yet — POST /api/seasonal/scan to build it"}
        pats = [_pattern_from_dict(d) for d in snap.get("patterns", [])]
        soon = sz.annotate_upcoming(pats, ref, horizon_days=horizon)
        return {"ok": True, "exists": True, "asof": ref.isoformat(),
                "built_at": snap.get("built_at"), "horizon_days": horizon,
                "count": len(soon), "patterns": [p.to_dict() for p in soon[:top]]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.post("/scan")
def scan(top_per_asset: int = Query(6, ge=1, le=20)) -> dict:
    """Kick off a universe snapshot rebuild in the background, return immediately.

    The scan of ~60 symbols can take a few minutes (downloads + window search),
    so it runs in a daemon thread. Poll ``GET /scan/status`` for progress; the
    weekly cron uses ``scripts/seasonal_scan.py`` (the same builder, synchronous).
    """
    with _SCAN_LOCK:
        if _SCAN_STATE["running"]:
            return {"ok": True, "running": True, "already": True}
        _SCAN_STATE.update(running=True, error=None,
                           started_at=datetime.now().isoformat(timespec="seconds"))

    def _work():
        try:
            snap = build_snapshot(top_per_asset=top_per_asset)
            _SCAN_STATE.update(built_at=snap["built_at"], count=len(snap["patterns"]),
                               n_assets=snap["n_assets"])
        except Exception as e:  # noqa: BLE001
            _SCAN_STATE["error"] = f"{type(e).__name__}: {e}"
        finally:
            _SCAN_STATE["running"] = False

    threading.Thread(target=_work, daemon=True).start()
    return {"ok": True, "running": True, "started": True}


@router.get("/scan/status")
def scan_status() -> dict:
    """Background-scan progress + whether a snapshot exists on disk."""
    return {"ok": True, "exists": _snapshot_path().exists(), **_SCAN_STATE}


# --------------------------------------------------------------- intraday
_RTH_START, _RTH_END = dt.time(9, 30), dt.time(16, 0)


def _load_intraday(ticker: str, years: int, rth: bool) -> dict:
    """Hourly + daily-session return profiles from the 1-minute lake (cached).

    Loads the last ``years`` of bars for ``ticker`` from the DuckDB lake, converts
    to the exchange-local tz, optionally filters to the regular session, then
    resamples to hourly (close/open per bar) and to a daily session return.
    Crypto is treated as 24h UTC (``rth`` ignored).
    """
    from .charts import _lake, _resolve  # reuse the chart terminal's discovery

    key = f"{ticker}|{years}|{rth}"
    now = time.time()
    hit = _INTRADAY_CACHE.get(key)
    if hit and now - hit[0] < _INTRADAY_TTL:
        return hit[1]

    meta = _resolve(ticker)
    lake = _lake()
    lo, hi = fp.dataset_bounds(lake, meta["dataset"])
    start = max(lo, hi - pd.Timedelta(days=365 * years))
    bars = fp.load_bars(lake, meta["dataset"], start, hi)
    if bars.empty:
        raise ValueError(f"no intraday bars for {ticker}")

    is_crypto = meta["asset_class"] == "crypto"
    tz = "UTC" if is_crypto else "US/Eastern"
    use_rth = rth and not is_crypto
    b = bars.tz_convert(tz)
    if use_rth:
        t = b.index.time
        b = b[(t >= _RTH_START) & (t < _RTH_END)]

    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    hourly = b.resample("1h").agg(agg).dropna()
    hourly = hourly[hourly["Open"] > 0]
    hr = (hourly["Close"] / hourly["Open"] - 1.0).rename("ret")

    daily = b.resample("1D").agg(agg).dropna()
    daily = daily[daily["Open"] > 0]
    dr = (daily["Close"] / daily["Open"] - 1.0).rename("ret")

    out = {
        "ticker": ticker,
        "meta": {"ticker": meta["ticker"], "name": sz.universe_meta(ticker)["name"],
                 "asset_class": meta["asset_class"], "native_tf": meta["native_tf"],
                 "note": sz.universe_meta(ticker)["note"]},
        "tz": tz, "rth": use_rth,
        "span": {"start": b.index.min().date().isoformat(),
                 "end": b.index.max().date().isoformat(),
                 "n_days": int(daily.shape[0])},
        "hours": sz.intraday_hour_profile(hr),
        "weekdays": sz.intraday_weekday_profile(dr),
        "heatmap": sz.intraday_weekday_hour_heatmap(hr),
    }
    _INTRADAY_CACHE[key] = (now, out)
    return out


@router.get("/intraday/instruments")
def intraday_instruments() -> dict:
    """List instruments with intraday data in the lake (ES/NQ/GC + stocks + BTC)."""
    try:
        from .charts import _instruments
        insts, _ = _instruments()
        out = [{"ticker": i["ticker"], "asset_class": i["asset_class"],
                "native_tf": i["native_tf"], "start": i["start"], "end": i["end"],
                "name": sz.universe_meta(i["ticker"])["name"]}
               for i in insts]
        return {"ok": True, "count": len(out), "instruments": out}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/intraday")
def intraday(
    ticker: str,
    years: int = Query(6, ge=1, le=20),
    rth: bool = True,
) -> dict:
    """Time-of-day, day-of-week and weekday-x-hour seasonal profiles (gross, bps).

    Honesty note: these are *gross* intraday structure views. The repo's own work
    (strategies 0038-0041) shows a single liquid market's intraday DIRECTION is
    not tradable net of cost — read these for structure/context, not as an edge.
    """
    try:
        return {"ok": True, **_load_intraday(ticker, years, rth)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------- snapshot
def _read_snapshot() -> dict | None:
    p = _snapshot_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _pattern_from_dict(d: dict) -> sz.SeasonalPattern:
    """Rehydrate a SeasonalPattern from its JSON dict (tuples were stored as lists)."""
    d = dict(d)
    d["start_md"] = tuple(d["start_md"])
    d["end_md"] = tuple(d["end_md"])
    # Drop forward-timing fields recomputed per request.
    for k in ("days_until_start", "next_start", "next_end"):
        d.pop(k, None)
    return sz.SeasonalPattern(**d)


def build_snapshot(top_per_asset: int = 6) -> dict:
    """Scan + validate every universe symbol; write & return the snapshot dict."""
    all_pats: list[dict] = []
    n_assets = 0
    for u in sz.SEASONAL_UNIVERSE:
        try:
            px = _load_prices(u["ticker"])
        except Exception:  # noqa: BLE001 - a dead symbol shouldn't kill the scan
            continue
        pats, _ = sz.scan_windows(
            px, ticker=u["ticker"], name=u["name"], asset_class=u["asset_class"],
            top=top_per_asset)
        all_pats.extend(p.to_dict() for p in pats)
        n_assets += 1
    snap = {"built_at": datetime.now().isoformat(timespec="seconds"),
            "n_assets": n_assets, "patterns": all_pats}
    path = _snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return snap
