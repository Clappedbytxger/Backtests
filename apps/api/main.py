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
sys.path.insert(0, str(ROOT))          # make `agent` / `live` importable too

import base64  # noqa: E402
import csv  # noqa: E402
import importlib.util  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from uuid import uuid4  # noqa: E402

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

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


# ── Autonomous agent (sandboxed, async) ─────────────────────────────────────
_JOBS: dict[str, dict] = {}
_AGENT_BACKENDS: dict[str, object] = {}
_AGENT_LOCK = threading.Lock()


class AgentRunRequest(BaseModel):
    hypothesis: str
    dry_run: bool = True
    backend: str | None = None  # None -> config backend; "mock" for a no-model smoke
    slug: str | None = None


def _get_agent_backend(name: str | None):
    """Resolve + cache the LLM backend (a real model is loaded once and reused)."""
    from agent.llm import get_backend

    key = name or get_settings().llm_backend
    if key == "mock":
        return get_backend("mock")
    if key not in _AGENT_BACKENDS:
        _AGENT_BACKENDS[key] = get_backend(name)
    return _AGENT_BACKENDS[key]


def _sanitize(obj):
    """Replace non-finite floats (NaN/Inf) with None so the result is valid JSON."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _agent_sandbox_run(job_id: str, hypothesis: str, dry_run: bool,
                       backend_name: str | None, slug: str | None) -> None:
    """Run one agent cycle in an isolated temp repo — never touches the real repo."""
    from agent.loop import run_research_cycle

    settings = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="qos_agent_"))
    try:
        with _AGENT_LOCK:  # the cached model is not thread-safe -> one run at a time
            subprocess.run(["git", "init", "-b", "main", str(tmp)], capture_output=True)
            for k, v in (("user.email", "agent@quant-os.local"), ("user.name", "Quant-OS Agent")):
                subprocess.run(["git", "-C", str(tmp), "config", k, v], capture_output=True)
            (tmp / "strategies").mkdir()
            (tmp / "strategies" / ".gitkeep").write_text("")
            catalog = settings.backtest_dir / "CATALOG.md"
            if catalog.exists():
                shutil.copy(catalog, tmp / "CATALOG.md")  # seed catalog de-dup
            subprocess.run(["git", "-C", str(tmp), "add", "-A"], capture_output=True)
            subprocess.run(["git", "-C", str(tmp), "commit", "-m", "seed"], capture_output=True)

            backend = _get_agent_backend(backend_name)
            res = run_research_cycle(hypothesis, backend=backend, repo_root=tmp,
                                     ideas_dir=settings.ideas_dir, slug=slug, dry_run=dry_run)
        sdir = Path(res["dir"])
        res["run_py"] = (sdir / "run.py").read_text(encoding="utf-8") if (sdir / "run.py").exists() else ""
        report = sdir / "REPORT.md"
        res["report"] = report.read_text(encoding="utf-8") if report.exists() else None

        # Restructure the harness metrics.json into named sections for the UI.
        raw = res.get("metrics") if isinstance(res.get("metrics"), dict) else {}
        if "metrics" in raw:  # harness output shape
            res["summary"] = raw.get("metrics", {})
            res["permutation"] = raw.get("permutation", {})
            res["bootstrap_ci"] = raw.get("bootstrap_ci", {})
            res["deflated_sharpe"] = raw.get("deflated_sharpe", {})
            res["vs_benchmark"] = raw.get("vs_benchmark", {})
            res["instrument"] = raw.get("instrument")

        # Read plots out of the sandbox (base64) before it is deleted.
        res["plots"] = {}
        rdir = sdir / "results"
        if rdir.exists():
            for png in sorted(rdir.glob("*.png")):
                res["plots"][png.stem] = base64.b64encode(png.read_bytes()).decode()

        _JOBS[job_id].update(status="done", result=_sanitize(res), finished=time.time())
    except Exception as e:  # noqa: BLE001
        _JOBS[job_id].update(status="error", error=f"{type(e).__name__}: {e}", finished=time.time())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.post("/agent/run")
def agent_run(req: AgentRunRequest) -> dict:
    """Start a sandboxed agent research cycle (async). Returns a job id to poll.

    Runs in an isolated temporary repo — the user's working copy and branches are
    never modified. ``dry_run`` (default) generates run.py without executing it.
    """
    hypothesis = req.hypothesis.strip()
    if not hypothesis:
        raise HTTPException(status_code=400, detail="hypothesis is required")
    if any(j["status"] == "running" for j in _JOBS.values()):
        raise HTTPException(status_code=409, detail="agent is busy — one run at a time")
    job_id = uuid4().hex[:12]
    _JOBS[job_id] = {"status": "running", "hypothesis": hypothesis,
                     "dry_run": req.dry_run, "started": time.time()}
    threading.Thread(
        target=_agent_sandbox_run,
        args=(job_id, hypothesis, req.dry_run, req.backend, req.slug),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "running"}


@app.get("/agent/job/{job_id}")
def agent_job(job_id: str) -> dict:
    """Poll an agent job's status/result."""
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, **job}
