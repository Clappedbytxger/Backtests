"""Quant-OS Alternative Data API — the Alternative Insights Desk backend.

Mounted under ``/api/altdata`` by :mod:`apps.api.main`. Read-only over the structured
alt-data store (:mod:`quantlab.altdata.store`) plus two write controls: ``/ingest`` runs
the scrapers in a background thread (one at a time), ``/seed`` fabricates an offline demo
dataset. Heavy scraping never blocks the request thread.

Endpoints:
* ``/sources``   — the watchlist (tickers ↔ repos/CIKs)
* ``/status``    — store counters + ingest job state
* ``/events``    — the Alt-Data event ticker (newest first)
* ``/series``    — price overlaid with the asset's alt-data score (sentiment/commits)
* ``/anomalies`` — the Anomalie-Radar bubble points
* ``/ingest``    — POST: kick off a background scrape (optional ticker filter)
* ``/seed``      — POST: load the offline demo dataset

Every GET degrades to ``{"ok": false, "error": ...}`` — the dashboard convention.
"""

from __future__ import annotations

import math
import threading
import time

from fastapi import APIRouter, Query
from pydantic import BaseModel

from quantlab.altdata import store
from quantlab.altdata.sources import WATCHLIST

router = APIRouter(prefix="/api/altdata", tags=["altdata"])

# single background ingest job (scraping is rate-limited; one run at a time)
_JOB: dict = {"status": "idle", "started": None, "finished": None, "summary": None, "error": None}
_LOCK = threading.Lock()


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


@router.get("/sources")
def sources() -> dict:
    """The curated watchlist — which tickers map to which repos / SEC CIKs."""
    return {"ok": True, "count": len(WATCHLIST),
            "sources": [{"ticker": s.ticker, "name": s.name, "asset_class": s.asset_class,
                         "repo": s.repo, "cik": s.cik} for s in WATCHLIST]}


@router.get("/status")
def status() -> dict:
    """Store counters plus the background-ingest job state."""
    try:
        return _sanitize({"ok": True, "store": store.status(), "job": _JOB})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/events")
def events(limit: int = Query(50, ge=1, le=300)) -> dict:
    """The Alt-Data event ticker (SEC filings + GitHub spikes), newest first."""
    try:
        return _sanitize({"ok": True, "events": store.events(limit)})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/series")
def series(ticker: str = Query(...), years: int = Query(3, ge=1, le=15)) -> dict:
    """Price overlaid with the asset's alt-data score (sentiment or commit rate) + z."""
    try:
        return _sanitize(store.series(ticker, years=years))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/anomalies")
def anomalies() -> dict:
    """The Anomalie-Radar: one bubble per asset (alt-data z vs recent price move)."""
    try:
        return _sanitize({"ok": True, "points": store.anomalies()})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


class IngestRequest(BaseModel):
    tickers: list[str] | None = None
    days: int = 90


def _run_ingest(tickers: list[str] | None, days: int) -> None:
    with _LOCK:
        _JOB.update(status="running", started=time.time(), finished=None, error=None, summary=None)
        try:
            _JOB["summary"] = store.ingest_all(tickers, days=days)
            _JOB["status"] = "done"
        except Exception as e:  # noqa: BLE001
            _JOB.update(status="error", error=f"{type(e).__name__}: {e}")
        finally:
            _JOB["finished"] = time.time()


@router.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    """Kick off a background scrape of the watchlist (or a ticker subset). Non-blocking."""
    if _JOB["status"] == "running":
        return {"ok": False, "error": "ingest already running", "job": _sanitize(_JOB)}
    threading.Thread(target=_run_ingest, args=(req.tickers, req.days), daemon=True).start()
    return {"ok": True, "status": "running"}


@router.post("/seed")
def seed() -> dict:
    """Load the offline demo dataset (so the desk renders without network access)."""
    try:
        return _sanitize({"ok": True, **store.seed()})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
