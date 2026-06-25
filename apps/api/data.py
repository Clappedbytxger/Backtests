"""Quant-OS Data API — the unified market-data layer (Phase 3.2).

Mounted under ``/api/data`` by :mod:`apps.api.main`. Exposes the pluggable provider
interface (:mod:`quantlab.datasource`): list provider availability and fetch a small
bar preview from any provider — used by the Settings page to validate that a freshly
entered Alpaca key actually pulls live data.

Degrades to ``{"ok": false, "error": ...}`` and NaN/Inf-sanitises — the dashboard
convention.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Query

from quantlab import datasource as ds

router = APIRouter(prefix="/api/data", tags=["data"])


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


@router.get("/providers")
def providers() -> dict:
    """Available data providers + whether each is wired up (keys present)."""
    return {"ok": True, "providers": ds.provider_status(),
            "timeframes": list(ds._TF.keys())}


@router.get("/bars")
def bars(
    symbol: str = Query("SPY"),
    provider: str = Query("yfinance"),
    timeframe: str = Query("1Day"),
    start: str | None = Query(None),
    limit: int = Query(120, ge=1, le=1000),
) -> dict:
    """A small OHLCV preview from one provider — the Settings 'test connection' call."""
    try:
        df = ds.get_bars(symbol, start=start, timeframe=timeframe, provider=provider, limit=limit)
        tail = df.tail(limit)
        rows = [{"t": str(ix.date() if hasattr(ix, "date") else ix),
                 "open": float(r.Open), "high": float(r.High), "low": float(r.Low),
                 "close": float(r.Close), "volume": float(r.Volume)}
                for ix, r in tail.iterrows()]
        return _sanitize({
            "ok": True, "symbol": symbol.upper(), "provider": provider,
            "timeframe": timeframe, "count": len(rows),
            "start": rows[0]["t"] if rows else None,
            "end": rows[-1]["t"] if rows else None, "bars": rows,
        })
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
