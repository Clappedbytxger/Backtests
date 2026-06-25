"""Quant-OS Swarm Command Center API — hybrid local/cloud multi-agent desk.

Mounted under ``/api/swarm`` by :mod:`apps.api.main`. This router is the *wiring*:
it connects three concrete worker drones to their real (cached) data sources, runs
them in parallel, aggregates their lean JSON, and hands it to the cloud commander.
The transport + verdict logic lives in :mod:`quantlab.swarm` (network-free, tested).

Drones (local Ollama narration over real signals):
* ``regime``   — SPY market regime (ADX / ATR / volatility) via :mod:`apps.api.regime`
* ``seasonal`` — upcoming seasonal windows via :mod:`apps.api.seasonal`
* ``cot``      — institutional COT extremes via :mod:`quantlab.cot`

Commander (cloud Gemini, model fallback + backoff): one aggregated prompt → the
final ACTIVE/PAUSED routing + allocation weights + ungeschönte Begründung.

Endpoints:
* ``GET  /config`` — drone specs + the (non-secret) LLM config (no network)
* ``GET  /ping``   — live reachability of Ollama + presence of a Gemini key
* ``POST /run``    — start a swarm cycle (async job); returns a ``job_id``
* ``GET  /job/{id}`` / ``GET /last`` — poll the live job / the most recent one

Every endpoint degrades to ``{"ok": false, "error": ...}`` and the whole pipeline
runs deterministically when Ollama/Gemini are absent — the dashboard convention.
"""

from __future__ import annotations

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from quantlab import conditional as cb
from quantlab import cot
from quantlab import regime as rg
from quantlab import swarm as sw
from quantlab.config import get_settings
from quantlab.fundamental_data import read_api_key

from .cot import scan as _cot_scan
from .regime import _classify
from .seasonal import upcoming as _seasonal_upcoming
from .switchboard import _load_book

router = APIRouter(prefix="/api/swarm", tags=["swarm"])

try:  # process RAM gauge for the drone tiles (truthful = API-process RSS)
    import psutil  # type: ignore

    _PROC = psutil.Process()
except Exception:  # noqa: BLE001 - psutil optional
    _PROC = None


def _rss_mb() -> float | None:
    if _PROC is None:
        return None
    try:
        return round(_PROC.memory_info().rss / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001
        return None


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


# ── drone data sources (real, cached) ───────────────────────────────────────
def _signal_regime() -> tuple[dict, str, str]:
    """SPY regime signal → (signal, fallback_headline, fallback_stance)."""
    _, cls = _classify("SPY", 8)
    snap = rg.current_regime(cls)
    m = snap.get("metrics") or {}
    direction = snap.get("direction") or "neutral"
    stance = {"bull": "risk_on", "bear": "risk_off"}.get(direction, "neutral")
    adx, atr = m.get("adx"), m.get("atr_pct")
    signal = {
        "ticker": "SPY", "regime": snap.get("regime"), "label": snap.get("label"),
        "direction": direction, "direction_label": snap.get("direction_label"),
        "adx": adx, "atr_pct": atr, "hist_vol": m.get("hist_vol"),
        "vol_rank": m.get("vol_rank"), "vol_state": snap.get("vol_state"),
        "trend_state": snap.get("trend_state"), "asof": snap.get("asof"),
    }
    adx_s = f"ADX {adx:.0f}" if isinstance(adx, (int, float)) else "ADX n/a"
    atr_s = f"ATR {atr * 100:.1f}%" if isinstance(atr, (int, float)) else ""
    fb = f"SPY: {snap.get('label')} ({adx_s} {atr_s}) → {stance.replace('_', '-').upper()}"
    return signal, fb.strip(), stance


def _signal_seasonal() -> tuple[dict, str, str]:
    """Upcoming seasonal windows (next 21d) → signal, fallback headline/stance."""
    up = _seasonal_upcoming(horizon=21, top=8, asof=None)
    pats = up.get("patterns", []) if up.get("ok") else []
    longs = sum(1 for p in pats if p.get("direction") == "long")
    shorts = len(pats) - longs
    bias = "long" if longs >= shorts else "short"
    top = [{"ticker": p.get("ticker"), "name": p.get("name"),
            "window": p.get("window_label"), "direction": p.get("direction"),
            "mean": p.get("mean_return"), "days_until": p.get("days_until_start")}
           for p in pats[:5]]
    signal = {"exists": up.get("exists", False), "n_upcoming": len(pats),
              "strongest_bias": bias if pats else "none", "top": top}
    if not up.get("exists", False):
        return signal, "Kein Saison-Snapshot — POST /api/seasonal/scan zum Aufbau.", "neutral"
    if not pats:
        return signal, "Keine Saison-Muster im 21-Tage-Fenster.", "neutral"
    stance = "risk_on" if bias == "long" else "risk_off"
    nxt = top[0]
    fb = (f"{len(pats)} Saison-Setups voraus; nächstes {nxt['ticker']} "
          f"({nxt['direction']}, in {nxt['days_until']}T).")
    return signal, fb, stance


def _signal_cot() -> tuple[dict, str, str]:
    """COT institutional extremes (|commercial z| extreme) → signal, fallback."""
    sc = _cot_scan(window=156)
    markets = sc.get("markets", []) if sc.get("ok") else []
    extremes = [r for r in markets if (r.get("signal") or {}).get("severity") == "extreme"]
    bull = sum(1 for r in extremes if (r.get("signal") or {}).get("bias") == "bullish")
    bear = sum(1 for r in extremes if (r.get("signal") or {}).get("bias") == "bearish")
    net = "bullish" if bull > bear else ("bearish" if bear > bull else "mixed")
    view = [{"root": r.get("root"), "name": r.get("name"), "comm_z": r.get("comm_z"),
             "bias": (r.get("signal") or {}).get("bias"),
             "status": (r.get("signal") or {}).get("status")} for r in extremes[:5]]
    signal = {"n_markets": len(markets), "n_extremes": len(extremes),
              "net_bias": net, "extremes": view}
    stance = {"bullish": "risk_on", "bearish": "risk_off"}.get(net, "neutral")
    if not extremes:
        return signal, f"COT ruhig — keine Extreme in {len(markets)} Märkten.", "neutral"
    top = view[0]
    fb = (f"{len(extremes)} COT-Extreme; stärkstes {top['root']} "
          f"(z {top['comm_z']}, {top['bias']}).")
    return signal, fb, stance


_SPECS: list[sw.DroneSpec] = [
    sw.DroneSpec("regime", "Regime Scout", "Marktregime: ADX, ATR, Volatilität (SPY)",
                 "#38bdf8", _signal_regime),
    sw.DroneSpec("seasonal", "Seasonality Hunter", "Anstehende Saison-Muster (21-Tage-Fenster)",
                 "#f59e0b", _signal_seasonal),
    sw.DroneSpec("cot", "COT Sentinel", "Institutionelle COT-Positionierungs-Extreme",
                 "#a78bfa", _signal_cot),
]


def _routable_strategies(limit: int = 10) -> list[dict]:
    """Top non-rejected strategies (by Sharpe) — the fallback when the book is empty."""
    try:
        from quantlab.registry import list_strategies

        rows = list_strategies()
    except Exception:  # noqa: BLE001 - registry not built yet
        return []
    cand = [r for r in rows if r.get("sharpe") is not None
            and (r.get("bucket") or "") not in ("rejected", "blocked")]
    cand.sort(key=lambda r: r.get("sharpe") or 0.0, reverse=True)
    return [{"num": r.get("num"), "name": r.get("name"),
             "category": r.get("category"), "sharpe": r.get("sharpe")}
            for r in cand[:limit]]


def _regime_routing(benchmark: str = "SPY", years: int = 8) -> tuple[list[dict], dict | None, dict | None]:
    """Conditional-backtest router → (regime-annotated strategies, regime_context, switch).

    Slices every alive sleeve's returns by the benchmark regime, returns the commander's
    regime-grounded strategy view + the live regime/switch context. Falls back to the
    plain top-Sharpe list (no regime fields → category heuristic) if the book fails.
    """
    try:
        panel, meta = _load_book()
        if panel.empty:
            return _routable_strategies(), None, None
        _, classified = _classify(benchmark, years)
        board = cb.build_router(panel, meta, classified)
        switch = board.get("switch") or {}
        cur = switch.get("current_regime")
        view = cb.commander_strategy_view(board["rows"], cur)
        ctx = {"benchmark": benchmark, "current_regime": cur,
               "current_label": switch.get("current_label"),
               "previous_regime": switch.get("previous_regime"),
               "previous_label": switch.get("previous_label"),
               "just_switched": switch.get("just_switched"),
               "bars_in_regime": switch.get("bars_in_regime"),
               "active": board["summary"]["active"], "paused": board["summary"]["paused"]}
        switch_block = {**switch, "delta": board.get("switch_delta"),
                        "summary": board["summary"], "benchmark": benchmark}
        return view, ctx, switch_block
    except Exception:  # noqa: BLE001 - one bad book must not kill the cycle
        return _routable_strategies(), None, None


# ── async job machinery ─────────────────────────────────────────────────────
_JOBS: dict[str, dict] = {}
_LAST_JOB_ID: dict[str, str] = {}
_RUN_LOCK = threading.Lock()


def _build_clients() -> tuple[sw.OllamaClient | None, sw.GeminiClient | None, dict]:
    """Resolve the Ollama/Gemini clients + a small status dict (no heavy network)."""
    s = get_settings()
    ollama = sw.OllamaClient(s.ollama_base_url, s.ollama_model, s.ollama_timeout_s)
    reachable, models = ollama.available()
    if not reachable:
        ollama = None  # don't pay 3× timeouts; drones fall back deterministically
    gemini = None
    has_key = False
    try:
        key = read_api_key("gemini")
        has_key = bool(key)
        gemini = sw.GeminiClient(key, [s.gemini_model, s.gemini_fallback_model],
                                 s.gemini_timeout_s)
    except RuntimeError:
        pass
    status = {
        "ollama": {"base_url": s.ollama_base_url, "model": s.ollama_model,
                   "reachable": reachable, "models": models},
        "gemini": {"model": s.gemini_model, "fallback_model": s.gemini_fallback_model,
                   "has_key": has_key},
    }
    return ollama, gemini, status


def _run_drone(idx: int, job: dict, ollama: sw.OllamaClient | None) -> dict:
    """Execute one drone, mutating its tile in ``job['drones']`` as it goes."""
    spec = _SPECS[idx]
    tile = job["drones"][idx]
    tile.update(status="computing", started=time.time())
    t0 = time.perf_counter()
    try:
        signal, fb_headline, fb_stance = spec.fn()
        headline, stance, model = sw.drone_narrate(
            spec.key, signal, fb_headline, fb_stance, ollama)
        signal["stance"] = stance
        tile.update(status="done", ok=True, signal=_sanitize(signal),
                    headline=headline, model=model, stance=stance,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000),
                    rss_mb=_rss_mb(), error=None)
    except Exception as e:  # noqa: BLE001 - one bad drone must not kill the swarm
        tile.update(status="error", ok=False,
                    elapsed_ms=round((time.perf_counter() - t0) * 1000),
                    rss_mb=_rss_mb(), error=f"{type(e).__name__}: {e}")
    return tile


def _run_swarm(job_id: str) -> None:
    """The full cycle: parallel drones → aggregate → commander verdict."""
    job = _JOBS[job_id]
    try:
        with _RUN_LOCK:  # Ollama is effectively single-threaded; serialise cycles
            ollama, gemini, status = _build_clients()
            job["config"] = status
            job["status"] = "drones"
            # run the three drones in parallel; each updates its own tile live
            with ThreadPoolExecutor(max_workers=len(_SPECS)) as pool:
                list(pool.map(lambda i: _run_drone(i, job, ollama), range(len(_SPECS))))

            job["status"] = "commander"
            strategies, regime_ctx, switch = _regime_routing()
            job["strategies"] = _sanitize(strategies)
            job["regime_switch"] = _sanitize(switch)
            verdict = sw.run_commander(job["drones"], strategies, gemini, regime_ctx)
            job.update(verdict=_sanitize(verdict), status="done", finished=time.time())
    except Exception as e:  # noqa: BLE001
        job.update(status="error", error=f"{type(e).__name__}: {e}", finished=time.time())


def _new_job() -> dict:
    return {
        "status": "running", "started": time.time(), "finished": None,
        "drones": [{"drone": s.key, "label": s.label, "task": s.task, "accent": s.accent,
                    "status": "idle", "ok": None, "signal": None, "headline": None,
                    "model": None, "stance": None, "elapsed_ms": None, "rss_mb": None,
                    "error": None} for s in _SPECS],
        "strategies": [], "regime_switch": None, "verdict": None,
        "config": None, "error": None,
    }


# ── endpoints ────────────────────────────────────────────────────────────────
@router.get("/config")
def config() -> dict:
    """Drone roster + the non-secret LLM config (no network calls)."""
    s = get_settings()
    return {
        "ok": True,
        "drones": [{"key": d.key, "label": d.label, "task": d.task, "accent": d.accent}
                   for d in _SPECS],
        "ollama": {"base_url": s.ollama_base_url, "model": s.ollama_model},
        "gemini": {"model": s.gemini_model, "fallback_model": s.gemini_fallback_model},
    }


@router.get("/ping")
def ping() -> dict:
    """Live reachability of the local Ollama server + whether a Gemini key exists."""
    s = get_settings()
    ollama = sw.OllamaClient(s.ollama_base_url, s.ollama_model, s.ollama_timeout_s)
    reachable, models = ollama.available()
    has_key = False
    try:
        has_key = bool(read_api_key("gemini"))
    except RuntimeError:
        pass
    return {
        "ok": True,
        "ollama": {"base_url": s.ollama_base_url, "model": s.ollama_model,
                   "reachable": reachable, "models": models,
                   "model_present": s.ollama_model in models or any(
                       m.split(":")[0] == s.ollama_model for m in models)},
        "gemini": {"model": s.gemini_model, "fallback_model": s.gemini_fallback_model,
                   "has_key": has_key},
    }


class SwarmRunRequest(BaseModel):
    pass  # no params yet; benchmark/horizon overrides can be added later


@router.post("/run")
def run(_req: SwarmRunRequest | None = None) -> dict:
    """Start one swarm cycle (async). Returns a ``job_id`` to poll via ``/job``."""
    if any(j["status"] in ("running", "drones", "commander") for j in _JOBS.values()):
        raise HTTPException(status_code=409, detail="swarm is busy — one cycle at a time")
    job_id = uuid4().hex[:12]
    _JOBS[job_id] = _new_job()
    _LAST_JOB_ID["id"] = job_id
    # prune old jobs (keep last 8)
    for old in list(_JOBS)[:-8]:
        _JOBS.pop(old, None)
    threading.Thread(target=_run_swarm, args=(job_id,), daemon=True).start()
    return {"ok": True, "job_id": job_id, "status": "running"}


@router.get("/job/{job_id}")
def job(job_id: str) -> dict:
    """Poll a swarm job's live state (drone tiles update as they finish)."""
    j = _JOBS.get(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"ok": True, "job_id": job_id, **j}


@router.get("/last")
def last() -> dict:
    """The most recent swarm job (for the dashboard's initial render), or null."""
    jid = _LAST_JOB_ID.get("id")
    if not jid or jid not in _JOBS:
        return {"ok": True, "job_id": None, "job": None}
    return {"ok": True, "job_id": jid, "job": _JOBS[jid]}
