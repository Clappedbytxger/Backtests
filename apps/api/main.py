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
