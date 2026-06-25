"""Quant-OS Feature-Store API — the Feature-Health Desk backend.

Mounted under ``/api/features`` by :mod:`apps.api.main`. Wraps the ML feature store
(:mod:`quantlab.feature_store`) which persists look-ahead-safe factors to Parquet and
tracks metadata in SQLite. Endpoints feed the Feature-Health dashboard:

* ``/factors``     — the factor registry definitions (the "buffet")
* ``/universe``    — default tickers + which are already built
* ``/status``      — the registry table (status/disk-size/missing-rate per factor)
* ``/correlation`` — the redundancy heatmap (factor correlation matrix)
* ``/timings``     — per-factor compute-ms (the runtime bar chart)
* ``/leakage``     — the no-look-ahead validation badge
* ``/compute``     — (POST) (re)compute + persist a ticker's features

Every endpoint degrades to ``{"ok": false, "error": ...}`` and floats are
NaN/Inf-sanitised — the dashboard convention shared with the other desks.
"""

from __future__ import annotations

import math
import time

from fastapi import APIRouter, Query
from pydantic import BaseModel

from quantlab import feature_store as fs

router = APIRouter(prefix="/api/features", tags=["features"])

_STORE = fs.FeatureStore()
_CACHE: dict[str, tuple[float, object]] = {}
_TTL = 3600.0  # features are daily; cache derived payloads for an hour


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _cached(key: str, ttl: float, build):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    out = build()
    _CACHE[key] = (now, out)
    return out


@router.get("/factors")
def factors() -> dict:
    """The factor registry — name, group and human description for each factor."""
    return {
        "ok": True,
        "groups": list(fs.GROUPS),
        "count": len(fs.REGISTRY),
        "factors": [{"name": f.name, "group": f.group, "description": f.description}
                    for f in fs.REGISTRY],
    }


@router.get("/universe")
def universe() -> dict:
    """Default tickers the dashboard offers, flagged with whether they are built."""
    return {
        "ok": True,
        "tickers": [{"ticker": t, "name": n, "built": _STORE.is_built(t)}
                    for t, n in fs.DEFAULT_UNIVERSE],
    }


@router.get("/status")
def status(ticker: str | None = Query(None)) -> dict:
    """The Feature-Registry table: status / disk size / missing-rate per factor."""
    try:
        rows = _STORE.status(ticker)
        n_total = sum(r["disk_bytes"] for r in rows)
        return _sanitize({
            "ok": True, "ticker": ticker, "count": len(rows),
            "total_disk_bytes": n_total,
            "stale": sum(1 for r in rows if r["status"] == "stale"),
            "rows": rows,
        })
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/correlation")
def correlation(ticker: str = Query("SPY")) -> dict:
    """Factor correlation matrix for the redundancy heatmap."""
    def build():
        try:
            if not _STORE.is_built(ticker):
                return {"ok": False, "error": f"'{ticker}' not built — compute it first"}
            return _sanitize({"ok": True, "ticker": ticker, **_STORE.correlation(ticker)})
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return _cached(f"corr:{ticker}", _TTL, build)


@router.get("/timings")
def timings(ticker: str = Query("SPY")) -> dict:
    """Per-factor compute time (ms) for the runtime bar chart."""
    try:
        rows = _STORE.status(ticker)
        if not rows:
            return {"ok": False, "error": f"'{ticker}' not built — compute it first"}
        bars = sorted(({"factor": r["factor"], "group": r["group"],
                        "compute_ms": r["compute_ms"]} for r in rows),
                      key=lambda r: r["compute_ms"], reverse=True)
        return _sanitize({"ok": True, "ticker": ticker, "bars": bars})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/leakage")
def leakage(ticker: str = Query("SPY")) -> dict:
    """No-look-ahead validation (shift-invariance) for the leakage badge."""
    def build():
        try:
            return _sanitize({"ok": True, "ticker": ticker,
                              **fs.validate_no_lookahead(ticker)})
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return _cached(f"leak:{ticker}", _TTL, build)


class ComputeRequest(BaseModel):
    ticker: str
    start: str = "2010-01-01"
    end: str | None = None
    factors: list[str] | None = None


@router.post("/compute")
def compute(req: ComputeRequest) -> dict:
    """(Re)compute + persist a ticker's features; returns the build summary."""
    ticker = req.ticker.strip()
    if not ticker:
        return {"ok": False, "error": "ticker is required"}
    try:
        summary = _STORE.compute(ticker, start=req.start, end=req.end, factors=req.factors)
        # invalidate derived caches for this ticker
        for k in (f"corr:{ticker}", f"leak:{ticker}"):
            _CACHE.pop(k, None)
        return _sanitize({"ok": True, **summary})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
