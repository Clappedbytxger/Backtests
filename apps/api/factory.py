"""Quant-OS Alpha Factory API — monitor the autonomous research worker.

Mounted under ``/api/factory`` by :mod:`apps.api.main`. Read-only over the worker's
on-disk artefacts (``reports/alpha_factory/state.json`` + ``rejected.jsonl`` and the
Markdown reports in ``reports/pending_review/``), plus a safe Stop control that drops
the worker's ``STOP`` file. The worker itself runs standalone (``python -m
agent.alpha_factory``) — this never spawns or holds the LLM in the web process.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from quantlab.config import get_settings

router = APIRouter(prefix="/api/factory", tags=["factory"])

_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")  # path-traversal guard for report/asset names


def _dirs():
    s = get_settings()
    af = s.reports_dir / "alpha_factory"
    pending = s.reports_dir / "pending_review"
    return af, pending


@router.get("/state")
def state() -> dict:
    """Worker counters + a freshness-derived 'running' flag."""
    af, _ = _dirs()
    sf = af / "state.json"
    if not sf.exists():
        return {"ok": True, "exists": False, "running": False,
                "state": None, "stop_pending": (af / "STOP").exists()}
    try:
        data = json.loads(sf.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "exists": True, "error": "state.json unreadable"}
    age = None
    try:
        updated = datetime.fromisoformat(str(data.get("updated")).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - updated).total_seconds()
    except (ValueError, TypeError):
        pass
    return {"ok": True, "exists": True,
            "running": age is not None and age < 180,  # fresh tick ⇒ alive
            "age_s": age, "stop_pending": (af / "STOP").exists(), "state": data}


@router.get("/pending")
def pending() -> dict:
    """List the reports awaiting human review (newest first)."""
    _, pdir = _dirs()
    if not pdir.exists():
        return {"ok": True, "count": 0, "reports": []}
    items = []
    for md in pdir.glob("*.md"):
        try:
            head = md.read_text(encoding="utf-8")[:400]
        except OSError:
            continue
        title = next((ln[3:].strip() for ln in head.splitlines() if ln.startswith("## ")), md.stem)
        items.append({"name": md.name, "title": title,
                      "mtime": datetime.fromtimestamp(md.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")})
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return {"ok": True, "count": len(items), "reports": items}


@router.get("/report")
def report(name: str = Query(..., description="report filename, e.g. AF-0123_my-idea.md")) -> dict:
    """One pending report's Markdown + the list of its plot asset filenames."""
    _, pdir = _dirs()
    if not _NAME_RE.match(name) or not name.endswith(".md"):
        raise HTTPException(status_code=400, detail="bad report name")
    path = pdir / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="report not found")
    assets_dir = pdir / "assets" / name[:-3]
    plots = sorted(p.name for p in assets_dir.glob("*.png")) if assets_dir.exists() else []
    return {"ok": True, "name": name, "markdown": path.read_text(encoding="utf-8"), "plots": plots}


@router.get("/asset")
def asset(report: str = Query(...), file: str = Query(...)):
    """Serve a report's plot PNG (path-traversal-safe)."""
    _, pdir = _dirs()
    if not (_NAME_RE.match(report) and _NAME_RE.match(file)) or not file.endswith(".png"):
        raise HTTPException(status_code=400, detail="bad asset path")
    base = (pdir / "assets" / (report[:-3] if report.endswith(".md") else report)).resolve()
    target = (base / file).resolve()
    if not target.is_relative_to(base) or not target.exists():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(target, media_type="image/png")


@router.get("/rejects")
def rejects(limit: int = Query(60, ge=1, le=500)) -> dict:
    """The most recent rejected hypotheses (for de-dup transparency)."""
    af, _ = _dirs()
    rl = af / "rejected.jsonl"
    if not rl.exists():
        return {"ok": True, "count": 0, "items": []}
    lines = rl.read_text(encoding="utf-8").splitlines()
    items = []
    for ln in lines[-limit:]:
        try:
            items.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    items.reverse()
    return {"ok": True, "count": len(lines), "items": items}


@router.post("/stop")
def stop() -> dict:
    """Ask the worker to stop after its current iteration (drops the STOP file)."""
    af, _ = _dirs()
    af.mkdir(parents=True, exist_ok=True)
    (af / "STOP").write_text("stop requested via dashboard\n", encoding="utf-8")
    return {"ok": True, "stop_pending": True}
