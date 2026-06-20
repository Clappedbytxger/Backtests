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

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

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
