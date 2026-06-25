"""Quant-OS COT API — the Institutional Positioning Desk backend.

Mounted under ``/api/cot`` by :mod:`apps.api.main`. Wraps the COT positioning engine
(:mod:`quantlab.cot`) over the cached CFTC data and aligns the weekly factors with
weekly price candles so the frontend can stack the three classic panels (price /
net positions / COT-index oscillator) on one shared weekly time axis.

Endpoints:
* ``/universe`` — the scannable markets (root, display name, group)
* ``/asset``    — the stacked-chart payload for one market (weekly candles + commercial
                  & managed-money net positions + commercial COT index / z-score)
* ``/scan``     — the Extreme-Positioning table (every market, sorted by |commercial z|)

Heavy work is TTL-cached in-process. Every endpoint degrades to ``{"ok": false,
"error": ...}`` and floats are NaN/Inf-sanitised — the dashboard convention.
"""

from __future__ import annotations

import math
import time

import pandas as pd
from fastapi import APIRouter, Query

from quantlab import cot

router = APIRouter(prefix="/api/cot", tags=["cot"])

_CACHE: dict[str, tuple[float, object]] = {}
_TTL = 6 * 3600.0  # COT is weekly; cache aggressively
_SCAN_TTL = 3 * 3600.0


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _weekly_candles(price_ticker: str, years: int) -> pd.DataFrame:
    """Daily OHLC resampled to weeks ending Tuesday (to align with COT ref_date)."""
    from quantlab.data import get_prices

    start = (pd.Timestamp.today() - pd.DateOffset(years=years + 1)).strftime("%Y-%m-%d")
    try:
        df = get_prices(price_ticker, start=start)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
    if df.empty or not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        return pd.DataFrame()
    wk = df.resample("W-TUE").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    return wk.dropna(subset=["Close"])


@router.get("/universe")
def universe() -> dict:
    """The scannable COT markets grouped by asset class."""
    return {"ok": True, "count": len(cot.UNIVERSE),
            "markets": [{"root": m.root, "name": m.name, "group": m.group,
                         "price_ticker": m.price_ticker} for m in cot.UNIVERSE]}


@router.get("/asset")
def asset(root: str = Query("GC"), window: int = Query(156, ge=26, le=520),
          years: int = Query(5, ge=1, le=17)) -> dict:
    """Stacked-chart payload for one market: candles + net positions + COT oscillator."""
    m = cot.get_market(root)
    if m is None:
        return {"ok": False, "error": f"unknown COT root '{root}'"}
    key = f"asset:{root}:{window}:{years}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        df = cot.compute_cot(root, window=window)
        cutoff = pd.Timestamp.today() - pd.DateOffset(years=years)
        df = df[df.index >= cutoff]
        if df.empty:
            return {"ok": False, "error": f"no COT history for {root}"}
        candles = _weekly_candles(m.price_ticker, years)

        rows = []
        for ts, r in df.iterrows():
            c = candles.loc[ts] if ts in candles.index else None
            rows.append({
                "t": str(ts.date()),
                "open": _r(c["Open"]) if c is not None else None,
                "high": _r(c["High"]) if c is not None else None,
                "low": _r(c["Low"]) if c is not None else None,
                "close": _r(c["Close"]) if c is not None else None,
                "comm_net": int(r["comm_net"]),
                "noncomm_net": int(r["noncomm_net"]),
                "comm_index": _r(r["comm_index"], 1),
                "comm_z": _r(r["comm_z"], 2),
            })
        last = df.iloc[-1]
        latest = {
            "ref_date": str(df.index[-1].date()),
            "comm_net": int(last["comm_net"]), "noncomm_net": int(last["noncomm_net"]),
            "comm_index": _r(last["comm_index"], 1), "comm_z": _r(last["comm_z"], 2),
            "noncomm_index": _r(last["noncomm_index"], 1), "noncomm_z": _r(last["noncomm_z"], 2),
            "open_interest": int(last["open_interest"]),
            "hedging_pressure": _r(last["hedging_pressure"]),
            "signal": cot.classify_signal(float(last["comm_index"]),
                                          float(last["comm_z"]) if pd.notna(last["comm_z"]) else None),
        }
        out = _sanitize({
            "ok": True, "root": root.upper(), "name": m.name, "group": m.group,
            "price_ticker": m.price_ticker, "window": window, "years": years,
            "has_price": not candles.empty, "rows": rows, "latest": latest,
            "zones": {"index_low": cot.INDEX_LOW, "index_high": cot.INDEX_HIGH,
                      "extreme_z": cot.EXTREME_Z},
        })
        _CACHE[key] = (now, out)
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/scan")
def scan(window: int = Query(156, ge=26, le=520)) -> dict:
    """The Extreme-Positioning table: every market, sorted by |commercial z-score|."""
    key = f"scan:{window}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _SCAN_TTL:
        return hit[1]
    try:
        rows = cot.scan_universe(window=window)
        out = _sanitize({"ok": True, "count": len(rows), "window": window, "markets": rows,
                         "zones": {"index_low": cot.INDEX_LOW, "index_high": cot.INDEX_HIGH,
                                   "extreme_z": cot.EXTREME_Z}})
        _CACHE[key] = (now, out)
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _r(x, d: int = 2):
    try:
        v = float(x)
        return None if (math.isnan(v) or math.isinf(v)) else round(v, d)
    except (TypeError, ValueError):
        return None
