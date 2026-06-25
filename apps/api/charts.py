"""Quant-OS charts API — candles + volume-profile/footprint over the Parquet lake.

Mounted under ``/api/charts`` by :mod:`apps.api.main`. Uses the DuckDB
:class:`~quantlab.store.DataLake` for predicate-pushdown window slices and
:mod:`quantlab.footprint` for aggregation. All endpoints degrade gracefully to
``{"ok": false, "error": ...}`` (the dashboard convention).

Footprint honesty: the lake holds only OHLCV bars, so the bid/ask delta is a
tick-rule APPROXIMATION (``approx=true``, ``delta_method="tick-rule"`` in every
payload). Real bid/ask needs Databento ``trades`` — see
:func:`quantlab.footprint.fetch_trades_footprint` (opt-in, not wired here).
"""

from __future__ import annotations

import re
import time

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from quantlab import footprint as fp
from quantlab.data import get_splits
from quantlab.store import DataLake

router = APIRouter(prefix="/api/charts", tags=["charts"])

# ohlcv-1m / ohlcv-15m / ohlcv-1h / ohlcv-1d -> normalised timeframe token.
_TF_RE = re.compile(r"ohlcv-(\d+[mhd])", re.IGNORECASE)
_NORM_TF = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1D"}

_CACHE: dict = {"ts": 0.0, "instruments": None, "by_ticker": None}
_TTL = 300.0  # filesystem scan + per-instrument bounds; cache the discovery


def _lake() -> DataLake:
    return DataLake()  # cheap: an in-memory DuckDB connection over the parquet lake


# Split history is fetched once per ticker and kept warm (keeps the hot path fast).
_SPLITS: dict[str, tuple] = {}
_SPLITS_TTL = 6 * 3600


def _splits_for(ticker: str):
    now = time.time()
    hit = _SPLITS.get(ticker)
    if hit and now - hit[0] < _SPLITS_TTL:
        return hit[1]
    try:
        s = get_splits(ticker)
    except Exception:  # noqa: BLE001 - never let a split lookup break a chart
        s = None
    _SPLITS[ticker] = (now, s)
    return s


def _adjust_equities(bars, meta: dict, adjust: bool):
    """Split-adjust RAW equities bars (TradingView parity). Futures/crypto untouched."""
    if not adjust or meta["asset_class"] != "equities" or bars.empty:
        return bars
    s = _splits_for(meta["ticker"])
    return fp.split_adjust(bars, s) if s is not None and len(s) else bars


def _parse_ts(s):
    """Accept epoch seconds (int/str of digits) or an ISO-8601 string -> Timestamp."""
    if s is None or s == "":
        return None
    txt = str(s).strip()
    try:
        if re.fullmatch(r"-?\d+(\.\d+)?", txt):  # epoch seconds
            return pd.Timestamp(float(txt), unit="s", tz="UTC")
    except (ValueError, OverflowError):
        pass
    return pd.Timestamp(txt)


# --------------------------------------------------------------- discovery
def _discover(lake: DataLake) -> dict:
    """Map ticker -> {ticker, dataset, asset_class, native_tf} from cached filenames.

    Always points at the FINEST-granularity file per instrument; coarser
    timeframes are aggregated up from it. Daily-only root tickers are omitted —
    this terminal targets the intraday (footprint-capable) instruments.
    """
    insts: dict[str, dict] = {}

    futures: dict[str, list] = {}
    for d in lake.list_datasets("futures"):
        name = d.rsplit("/", 1)[-1]
        m = _TF_RE.search(name)
        if not m:
            continue
        tf = _NORM_TF.get(m.group(1).lower())
        if tf is None:
            continue
        rm = re.match(r"(.+?)_[cv]_0_", name)  # ES_c_0_..., 6B_v_0_...
        root = rm.group(1) if rm else name.split("_ohlcv")[0]
        futures.setdefault(root, []).append((tf, d, name))
    for root, items in futures.items():
        items.sort(key=lambda t: fp.TF_MINUTES.get(t[0], 1e9))
        finest = items[0][0]
        cands = [it for it in items if it[0] == finest]
        # prefer the full-history non-RTH file (longer, no "_RTH" suffix)
        cands.sort(key=lambda it: ("RTH" in it[2], -len(it[2])))
        insts[root] = {"ticker": root, "dataset": cands[0][1],
                       "asset_class": "futures", "native_tf": finest}

    for d in lake.list_datasets("equities"):
        name = d.rsplit("/", 1)[-1]
        m = _TF_RE.search(name)
        if not m:
            continue
        tf = _NORM_TF.get(m.group(1).lower())
        tkr = name.split("_ohlcv")[0]
        insts[tkr] = {"ticker": tkr, "dataset": d, "asset_class": "equities",
                      "native_tf": tf}

    crypto: dict[str, list] = {}
    for d in lake.list_datasets("crypto"):
        name = d.rsplit("/", 1)[-1]
        mm = re.match(r"binance_([A-Z0-9]+)_([A-Z0-9]+)_(\w+)\.parquet", name)
        if not mm:
            continue
        tf = _NORM_TF.get(mm.group(3).lower())
        if tf is None:
            continue
        tkr = f"{mm.group(1)}{mm.group(2)}"
        crypto.setdefault(tkr, []).append((tf, d))
    for tkr, items in crypto.items():
        items.sort(key=lambda t: fp.TF_MINUTES.get(t[0], 1e9))
        insts[tkr] = {"ticker": tkr, "dataset": items[0][1],
                      "asset_class": "crypto", "native_tf": items[0][0]}

    return insts


def _instruments(refresh: bool = False):
    now = time.time()
    if (not refresh and _CACHE["instruments"] is not None
            and now - _CACHE["ts"] < _TTL):
        return _CACHE["instruments"], _CACHE["by_ticker"]
    lake = _lake()
    out = []
    for tkr, meta in sorted(_discover(lake).items()):
        nat_min = fp.TF_MINUTES.get(meta["native_tf"], 1)
        avail = [tf for tf in fp.TIMEFRAMES if fp.TF_MINUTES[tf] >= nat_min]
        try:
            lo, hi = fp.dataset_bounds(lake, meta["dataset"])
            lo_s, hi_s = lo.isoformat(), hi.isoformat()
        except Exception:  # noqa: BLE001 - a broken file shouldn't kill discovery
            lo_s = hi_s = None
        out.append({**meta, "available_tfs": avail,
                    "footprint": nat_min <= 5, "start": lo_s, "end": hi_s})
    by_ticker = {i["ticker"]: i for i in out}
    _CACHE.update(ts=now, instruments=out, by_ticker=by_ticker)
    return out, by_ticker


def _resolve(ticker: str) -> dict:
    _, by = _instruments()
    meta = by.get(ticker)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"unknown ticker {ticker!r}")
    return meta


def _bounds(meta: dict, lake: DataLake):
    """(min, max) Timestamps — reuse the cached instrument bounds, else query."""
    if meta.get("start") and meta.get("end"):
        return pd.Timestamp(meta["start"]), pd.Timestamp(meta["end"])
    return fp.dataset_bounds(lake, meta["dataset"])


def _default_window(meta: dict, timeframe: str, limit: int, rth: bool, lo, hi):
    """[start, end] for the latest ``limit`` candles, capped so the native scan stays small."""
    nat_min = fp.TF_MINUTES.get(meta["native_tf"], 1)
    per_day_min = 1440 if meta["asset_class"] == "crypto" else (390 if rth else 1380)
    days_for_limit = fp.TF_MINUTES[timeframe] * limit / per_day_min * 1.7 + 3
    days_cap = 50_000 * nat_min / per_day_min  # bound native bars read to ~50k
    days = max(1.0, min(days_for_limit, days_cap))
    return max(hi - pd.Timedelta(days=days), lo), hi


# --------------------------------------------------------------- endpoints
@router.get("/instruments")
def instruments(refresh: bool = False) -> dict:
    """All chartable instruments with their available timeframes + footprint flag."""
    try:
        out, _ = _instruments(refresh)
        return {"ok": True, "count": len(out), "instruments": out}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/candles")
def candles(
    ticker: str,
    timeframe: str = "15m",
    start: str | None = None,
    end: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
    rth: bool = False,
    adjust: bool = True,
) -> dict:
    """OHLCV candles aggregated to ``timeframe`` for lightweight-charts.

    No ``start``/``end`` -> the latest ``limit`` candles. For pagination, pass
    ``end`` = the oldest loaded candle's time to fetch the window before it.
    ``adjust`` split-adjusts equities (TradingView parity); ignored for futures/crypto.
    """
    try:
        meta = _resolve(ticker)
        if timeframe not in meta["available_tfs"]:
            raise HTTPException(status_code=400,
                                detail=f"timeframe {timeframe!r} not available for {ticker}")
        lake = _lake()
        use_rth = rth and meta["asset_class"] != "crypto"
        lo, hi = _bounds(meta, lake)
        if start is None and end is None:
            start_ts, end_ts = _default_window(meta, timeframe, limit, use_rth, lo, hi)
            trim = True
        else:
            start_ts = _parse_ts(start) or lo
            end_ts = _parse_ts(end) or hi
            trim = False
        bars = fp.load_bars(lake, meta["dataset"], start_ts, end_ts)
        bars = _adjust_equities(bars, meta, adjust)
        out = fp.aggregate_candles(bars, timeframe, rth=use_rth)
        has_more_past = False
        if not bars.empty:
            has_more_past = bool(bars.index.min() > lo.tz_convert("UTC") + pd.Timedelta(minutes=1))
        if trim and len(out) > limit:
            out = out[-limit:]
        return {"ok": True, "ticker": ticker, "timeframe": timeframe, "rth": use_rth,
                "adjusted": bool(adjust and meta["asset_class"] == "equities"),
                "count": len(out), "has_more_past": has_more_past, "candles": out}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/footprint")
def footprint(
    ticker: str,
    start: str,
    end: str,
    timeframe: str = "15m",
    bin_size: float | None = None,
    rth: bool = False,
    adjust: bool = True,
) -> dict:
    """Per-cluster volume footprint (volume-by-price + POC + approx. bid/ask delta).

    ``start``/``end`` bound the visible window (epoch seconds or ISO-8601). The
    delta is a tick-rule approximation — see module docstring. ``adjust``
    split-adjusts equities so the price grid matches the candles.
    """
    try:
        meta = _resolve(ticker)
        if not meta["footprint"]:
            return {"ok": False,
                    "error": f"{ticker}: native {meta['native_tf']} data is too coarse for a footprint"}
        if timeframe not in meta["available_tfs"]:
            raise HTTPException(status_code=400,
                                detail=f"timeframe {timeframe!r} not available for {ticker}")
        lake = _lake()
        bars = fp.load_bars(lake, meta["dataset"], _parse_ts(start), _parse_ts(end))
        bars = _adjust_equities(bars, meta, adjust)
        clusters = fp.build_footprint(
            bars, timeframe, bin_size=bin_size,
            rth=rth and meta["asset_class"] != "crypto",
            ticker=meta["ticker"], asset_class=meta["asset_class"])
        return {"ok": True, "ticker": ticker, "timeframe": timeframe,
                "approx": True, "delta_method": "tick-rule",
                "count": len(clusters), "clusters": clusters}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
