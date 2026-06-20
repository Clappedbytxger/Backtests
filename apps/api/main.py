"""Quant-OS API — FastAPI backend over the strategy registry and data lake.

Phase-1 skeleton: exposes the SQLite registry (built by
``scripts/build_registry.py``) as JSON for the dashboard. The full research-hub
API (equity curves, robustness, live book) follows in Phase 3.

Run:
    .venv/Scripts/uvicorn.exe apps.api.main:app --reload     # from the repo root
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))  # make `quantlab` importable for standalone uvicorn

import csv  # noqa: E402
import importlib.util  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

from quantlab.config import get_settings  # noqa: E402
from quantlab.registry import (  # noqa: E402
    bucket_counts,
    get_strategy,
    list_strategies,
    status_counts,
)

app = FastAPI(title="Quant-OS API", version="0.1.0")

# Allow the local Next.js dev server to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_registry() -> None:
    db = get_settings().registry_db
    if not db.exists():
        raise HTTPException(
            status_code=503,
            detail="registry not built — run: python scripts/build_registry.py",
        )


@app.get("/health")
def health() -> dict:
    db = get_settings().registry_db
    return {"status": "ok", "registry_db": str(db), "registry_exists": db.exists()}


@app.get("/strategies")
def strategies(status: str | None = None) -> list[dict]:
    """All strategies (optionally filtered by raw status), ordered by number."""
    _require_registry()
    return list_strategies(status=status)


@app.get("/strategies/buckets")
def buckets() -> dict:
    """Strategy counts per coarse lifecycle bucket."""
    _require_registry()
    return {"buckets": bucket_counts(), "statuses": status_counts()}


@app.get("/strategies/{num}")
def strategy(num: str) -> dict:
    """One strategy row plus its flattened metrics."""
    _require_registry()
    found = get_strategy(num)
    if found is None:
        raise HTTPException(status_code=404, detail=f"strategy {num} not found")
    return found


def _results_dir(num: str):
    found = get_strategy(num)
    if not found or not found.get("rel_path"):
        return None
    return get_settings().backtest_dir / found["rel_path"] / "results"


@app.get("/strategies/{num}/plots")
def plots(num: str) -> dict:
    """List the PNG plot filenames in a strategy's results folder."""
    d = _results_dir(num)
    if d is None or not d.exists():
        return {"num": num, "plots": []}
    return {"num": num, "plots": sorted(p.name for p in d.glob("*.png"))}


@app.get("/strategies/{num}/plot/{filename}")
def plot(num: str, filename: str):
    """Serve a single PNG plot (path-traversal-safe)."""
    d = _results_dir(num)
    if d is None:
        raise HTTPException(status_code=404, detail=f"strategy {num} not found")
    root = d.resolve()
    target = (d / filename).resolve()
    if (not target.is_relative_to(root)) or target.suffix.lower() != ".png" or not target.exists():
        raise HTTPException(status_code=404, detail="plot not found")
    return FileResponse(target, media_type="image/png")


@app.get("/overview")
def overview() -> dict:
    """Aggregate stats for the dashboard overview (buckets, Sharpe dist, categories, top)."""
    _require_registry()
    rows = list_strategies()
    sharpes = [r["sharpe"] for r in rows if r["sharpe"] is not None]
    categories = Counter((r["category"] or "?") for r in rows)
    ranked = sorted((r for r in rows if r["sharpe"] is not None),
                    key=lambda r: r["sharpe"], reverse=True)[:12]
    return {
        "n_strategies": len(rows),
        "buckets": bucket_counts(),
        "categories": dict(categories.most_common()),
        "sharpes": sharpes,
        "top": [{"num": r["num"], "name": r["name"], "sharpe": r["sharpe"],
                 "bucket": r["bucket"]} for r in ranked],
    }


@app.get("/ideas")
def ideas() -> dict:
    """Research hub: the hypothesis backlog from IDEAS_DIR/HYPOTHESES.csv."""
    path = get_settings().ideas_dir / "HYPOTHESES.csv"
    if not path.exists():
        return {"exists": False, "source": str(path), "count": 0, "ideas": []}
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {"exists": True, "source": str(path), "count": len(rows), "ideas": rows}


# ── Live-book monitor (0108 CTI CORE book) ──────────────────────────────────
_LIVE_CACHE: dict = {"ts": 0.0, "data": None}
_LIVE_TTL = 600.0  # seconds; compute_targets pulls live data, so cache it
_SIGNAL_ENGINE = None


def _signal_engine():
    """Load the frozen 0108 signal engine (importlib; the module sets up its own paths)."""
    global _SIGNAL_ENGINE
    if _SIGNAL_ENGINE is None:
        path = (get_settings().backtest_dir / "strategies"
                / "0108_cti_core_book_live" / "signal_engine.py")
        spec = importlib.util.spec_from_file_location("cti_signal_engine", path)
        _SIGNAL_ENGINE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_SIGNAL_ENGINE)
    return _SIGNAL_ENGINE


@app.get("/live/book")
def live_book(refresh: bool = False) -> dict:
    """Today's target positions of the frozen 0108 CORE book (TTL-cached).

    Calls the 0108 signal engine's ``compute_targets()``; on any data/network
    failure returns ``{"ok": false, "error": ...}`` so the dashboard degrades.
    """
    now = time.time()
    if not refresh and _LIVE_CACHE["data"] is not None and now - _LIVE_CACHE["ts"] < _LIVE_TTL:
        return {**_LIVE_CACHE["data"], "cached": True}
    try:
        positions, ctx = _signal_engine().compute_targets()
        data = {
            "ok": True,
            "asof": ctx.get("asof"),
            "book_sharpe": ctx.get("book_sharpe"),
            "gross_exposure_pct": round(sum(abs(v) for v in positions.values()) * 100, 1),
            "positions": [{"instrument": k, "weight_pct": round(v * 100, 3)}
                          for k, v in sorted(positions.items(), key=lambda kv: -abs(kv[1]))],
            "context": {k: ctx.get(k) for k in
                        ("month_end", "carry_on", "vix", "crypto_gate", "idx_in_pos", "K")},
        }
        _LIVE_CACHE.update(ts=now, data=data)
        return {**data, "cached": False}
    except Exception as e:  # noqa: BLE001 - any data/network/import issue degrades gracefully
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
