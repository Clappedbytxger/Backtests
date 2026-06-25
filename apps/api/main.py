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
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
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

from .academy import router as academy_router  # noqa: E402
from .altdata import router as altdata_router  # noqa: E402
from .attribution import router as attribution_router  # noqa: E402
from .charts import router as charts_router  # noqa: E402
from .conditional import router as conditional_router  # noqa: E402
from .data import router as data_router  # noqa: E402
from .cot import router as cot_router  # noqa: E402
from .execution import router as execution_router  # noqa: E402
from .factory import router as factory_router  # noqa: E402
from .featurestore import router as featurestore_router  # noqa: E402
from .news import router as news_router  # noqa: E402
from .optimize import router as optimize_router  # noqa: E402
from .pairs import router as pairs_router  # noqa: E402
from .regime import router as regime_router  # noqa: E402
from .risk import router as risk_router  # noqa: E402
from .seasonal import router as seasonal_router  # noqa: E402
from .settings import router as settings_router  # noqa: E402
from .swarm import router as swarm_router  # noqa: E402
from .switchboard import router as switchboard_router  # noqa: E402

app = FastAPI(title="Quant-OS API", version="0.1.0")  # news + charts routers mounted below

# Allow the local Next.js dev server to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(charts_router)  # /api/charts/{instruments,candles,footprint}
app.include_router(news_router)  # /api/news/{items,ingest,verify,feedback,lessons,stats}
app.include_router(academy_router)  # /api/academy/{curriculum,module,lesson,quiz,books,generate}
app.include_router(factory_router)  # /api/factory/{state,pending,report,asset,rejects,stop}
app.include_router(seasonal_router)  # /api/seasonal/{universe,profile,heatmap,patterns,pattern,upcoming,scan}
app.include_router(regime_router)  # /api/regime/{palette,universe,current,timeline,performance,overview}
app.include_router(pairs_router)  # /api/pairs/{universe,scan,pair,heatmap}
app.include_router(risk_router)  # /api/risk/{book,dashboard,correlation}
app.include_router(switchboard_router)  # /api/switchboard/{benchmarks,matrix}
app.include_router(altdata_router)  # /api/altdata/{sources,status,events,series,anomalies,ingest,seed}
app.include_router(cot_router)  # /api/cot/{universe,asset,scan}
app.include_router(featurestore_router)  # /api/features/{factors,universe,status,correlation,timings,leakage,compute}
app.include_router(execution_router)  # /api/execution/{universe,simulate,breakdown,radar,seed}
app.include_router(attribution_router)  # /api/attribution/{book,factors,rolling,brinson}
app.include_router(optimize_router)  # /api/optimize/{config,run,job}
app.include_router(swarm_router)  # /api/swarm/{config,ping,run,job,last}
app.include_router(conditional_router)  # /api/conditional/{router,strategy}
app.include_router(settings_router)  # /api/settings/{status,init,unlock,lock,key,password}
app.include_router(data_router)  # /api/data/{providers,bars}


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
            res["timeframe"] = raw.get("timeframe")
            res["warning"] = raw.get("warning")
            res["signal_error"] = raw.get("signal_error")
            res["params"] = raw.get("params", {})
            res["param_grid"] = raw.get("param_grid", {})

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


def _run_harness_light(signal_code: str, params: dict) -> dict:
    """Re-run the harness in LIGHT mode with given params (no LLM, no git). For sliders."""
    from agent.loop import _build_run_py

    settings = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="qos_eval_"))
    try:
        (tmp / "run.py").write_text(_build_run_py(signal_code), encoding="utf-8")
        env = {**os.environ,
               "PYTHONPATH": str(settings.backtest_dir / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""),
               "QOS_MODE": "light", "QOS_PARAMS": json.dumps(params or {})}
        proc = subprocess.run([sys.executable, "run.py"], cwd=tmp, env=env,
                              capture_output=True, text=True, timeout=300)
        mp = tmp / "results" / "metrics.json"
        if not mp.exists():
            return {"ok": False, "error": (proc.stderr or proc.stdout)[-1500:]}
        raw = json.loads(mp.read_text(encoding="utf-8"))
        out = {"ok": True, "summary": raw.get("metrics", {}), "warning": raw.get("warning"),
               "params": raw.get("params", {}), "vs_benchmark": raw.get("vs_benchmark", {}),
               "instrument": raw.get("instrument"), "plots": {}}
        for png in sorted((tmp / "results").glob("*.png")):
            out["plots"][png.stem] = base64.b64encode(png.read_bytes()).decode()
        return _sanitize(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class AgentEvalRequest(BaseModel):
    job_id: str
    params: dict = {}


@app.post("/agent/evaluate")
def agent_evaluate(req: AgentEvalRequest) -> dict:
    """Re-run a finished run's signal with new parameter values (live slider). No LLM."""
    job = _JOBS.get(req.job_id)
    signal_code = (job or {}).get("result", {}).get("signal_code") if job else None
    if not signal_code:
        raise HTTPException(status_code=404, detail="job not found or has no parameterized signal")
    return _run_harness_light(signal_code, req.params)


def _catalog_row(num: str, slug: str, hypothesis: str, res: dict) -> str:
    s = res.get("summary") or {}
    p = (res.get("permutation") or {}).get("p_value")
    dsr = (res.get("deflated_sharpe") or {}).get("psr_deflated")

    def f(x, suffix="", scale=1.0, d=2):
        return f"{x * scale:.{d}f}{suffix}" if isinstance(x, (int, float)) else "n/a"

    name = slug.replace("-", " ").title()[:28]
    hyp = " ".join(hypothesis.split())[:70].replace("|", "/")
    return (f"| {num} | {name} | agent | {hyp} | testing (agent) | "
            f"{f(s.get('sharpe'))} | {f(s.get('cagr'), '%', 100, 1)} | "
            f"{f(s.get('max_drawdown'), '%', 100, 1)} | {int(s.get('n_trades') or 0)} | "
            f"{f(p, '', 1, 3)} | {f(dsr, '', 1, 2)} | Agent-generated; review before trusting |")


class AgentPromoteRequest(BaseModel):
    job_id: str


@app.post("/agent/promote")
def agent_promote(req: AgentPromoteRequest) -> dict:
    """Promote a finished agent run into the repo + CATALOG.md (on an isolated agent branch)."""
    from agent.guardrails import agent_commit, ensure_agent_branch
    from agent.loop import _build_run_py, next_strategy_number

    job = _JOBS.get(req.job_id)
    res = (job or {}).get("result") if job else None
    if not res or not res.get("signal_code"):
        raise HTTPException(status_code=404, detail="job not found or nothing to promote")
    settings = get_settings()
    repo = settings.backtest_dir
    slug = res.get("slug") or "idea"
    with _AGENT_LOCK:
        branch = ensure_agent_branch(repo, f"promote-{slug}")  # GUARDRAIL: never main
        num = next_strategy_number(repo)
        sdir = repo / "strategies" / f"{num}_agent_{slug}"
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "run.py").write_text(_build_run_py(res["signal_code"]), encoding="utf-8")
        env = {**os.environ,
               "PYTHONPATH": str(repo / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")}
        subprocess.run([sys.executable, "run.py"], cwd=sdir, env=env,
                       capture_output=True, text=True, timeout=600)
        (sdir / "REPORT.md").write_text(
            f"# {num} — {slug} (agent-generated)\n\n**Hypothesis:** {job['hypothesis']}\n\n"
            f"Promoted from the Quant-OS dashboard. Review before trusting.\n", encoding="utf-8")
        row = _catalog_row(num, slug, job["hypothesis"], res)
        catalog = repo / "CATALOG.md"
        if catalog.exists():
            with open(catalog, "a", encoding="utf-8") as fh:
                fh.write("\n" + row)
        sha = agent_commit(repo, f"feat(agent): promote {num} {slug} to catalog",
                           paths=[sdir.relative_to(repo).as_posix(), "CATALOG.md"])
    return {"ok": True, "branch": branch, "num": num,
            "dir": sdir.relative_to(repo).as_posix(), "sha": sha, "catalog_row": row}
