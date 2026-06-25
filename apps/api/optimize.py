"""Quant-OS GA Optimizer API — evolutionary parameter search (Evolution Monitor).

Mounted under ``/api/optimize`` by :mod:`apps.api.main`. Runs the genetic algorithm
in :mod:`quantlab.optimize` as a background job and streams per-generation telemetry
so the dashboard can animate convergence in real time, then exposes the final IS/OOS
result matrix and the fitness surface for the 3-D plateau-vs-spike view.

Design mirrors the agent/seasonal job pattern: a threaded worker writes into a
shared job dict under a lock; the UI polls ``GET /job/{id}`` for live history and the
final result. The GA itself is pure NumPy/pandas and never holds an LLM.
"""

from __future__ import annotations

import math
import threading
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from quantlab.costs import (
    CFD_CRYPTO,
    IBKR_DEFAULT,
    IBKR_FUTURES,
    IBKR_LIQUID_ETF,
    MES_INTRADAY,
)
from quantlab.data import get_prices
from quantlab.optimize import (
    FITNESS_FUNCTIONS,
    GAConfig,
    GenerationStats,
    ParamSpace,
    ParamSpec,
    fitness_surface,
    ma_crossover_strategy,
    run_ga,
)

router = APIRouter(prefix="/api/optimize", tags=["optimize"])

# ── instrument shortlist (cheap, deep daily history; reuses the data cache) ──
INSTRUMENTS = [
    {"ticker": "SPY", "name": "S&P 500 ETF", "asset_class": "equity", "cost": "etf"},
    {"ticker": "QQQ", "name": "Nasdaq-100 ETF", "asset_class": "equity", "cost": "etf"},
    {"ticker": "GLD", "name": "Gold ETF", "asset_class": "commodity", "cost": "etf"},
    {"ticker": "TLT", "name": "20Y Treasury ETF", "asset_class": "bond", "cost": "etf"},
    {"ticker": "BTC-USD", "name": "Bitcoin", "asset_class": "crypto", "cost": "crypto"},
    {"ticker": "ES=F", "name": "S&P 500 Future", "asset_class": "future", "cost": "future"},
]
_TICKERS = {i["ticker"] for i in INSTRUMENTS}

_COST_MODELS = {
    "etf": IBKR_LIQUID_ETF,
    "future": IBKR_FUTURES,
    "mes": MES_INTRADAY,
    "crypto": CFD_CRYPTO,
    "default": IBKR_DEFAULT,
}

# Built-in strategy: the demo MA crossover. Genes are the tunable parameters with
# sensible default bounds; the UI can narrow them per run.
STRATEGIES = {
    "ma_crossover": {
        "label": "Moving-Average Crossover (long-only)",
        "fn": ma_crossover_strategy,
        "params": [
            {"name": "sma_fast", "low": 5, "high": 60, "integer": True, "step": None,
             "label": "SMA Fast"},
            {"name": "sma_slow", "low": 80, "high": 250, "integer": True, "step": None,
             "label": "SMA Slow"},
            {"name": "stop_loss_pct", "low": 0.0, "high": 0.25, "integer": False,
             "step": 0.01, "label": "Trailing Stop %"},
        ],
        "surface_axes": ["sma_fast", "sma_slow"],
    },
}

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_RUN_LOCK = threading.Lock()  # one GA at a time (CPU-bound, keeps the box responsive)


def _finite(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and math.isfinite(x) else None


@router.get("/config")
def config() -> dict:
    """Static config for the UI: instruments, strategies + their genes, fitness fns."""
    return {
        "ok": True,
        "instruments": INSTRUMENTS,
        "strategies": [
            {"key": k, "label": v["label"], "params": v["params"],
             "surface_axes": v["surface_axes"]}
            for k, v in STRATEGIES.items()
        ],
        "fitness_functions": [
            {"key": "sharpe_dd", "label": "Sharpe × (1 − |MaxDD|)  (default)"},
            {"key": "sharpe", "label": "Sharpe Ratio"},
            {"key": "calmar", "label": "Calmar (CAGR / |MaxDD|)"},
        ],
        "defaults": {
            "population_size": 40, "generations": 30, "selection": "tournament",
            "crossover_prob": 0.9, "base_mutation_rate": 0.3,
            "min_mutation_rate": 0.05, "elitism": 2, "oos_fraction": 0.3,
            "haircut_reject_pct": 50.0, "seed": 42,
        },
    }


class OptimizeRequest(BaseModel):
    ticker: str = "SPY"
    strategy: str = "ma_crossover"
    fitness_metric: str = "sharpe_dd"
    start: str = "2010-01-01"
    end: str | None = None
    cost_model: str | None = None  # None -> infer from instrument
    # GA hyper-parameters
    population_size: int = 40
    generations: int = 30
    selection: str = "tournament"
    crossover_prob: float = 0.9
    base_mutation_rate: float = 0.3
    min_mutation_rate: float = 0.05
    elitism: int = 2
    seed: int = 42
    # IS/OOS protocol
    oos_fraction: float = 0.3
    haircut_reject_pct: float = 50.0
    top_n: int = 5
    # Optional per-gene bound overrides: {gene: {low, high}}
    bounds: dict[str, dict[str, float]] = {}


def _build_space(strategy_key: str, bounds: dict[str, dict[str, float]]) -> ParamSpace:
    """Build the ParamSpace from a strategy's gene defs, applying any bound overrides."""
    specs = []
    for p in STRATEGIES[strategy_key]["params"]:
        ov = bounds.get(p["name"], {})
        specs.append(ParamSpec(
            name=p["name"],
            low=float(ov.get("low", p["low"])),
            high=float(ov.get("high", p["high"])),
            integer=bool(p["integer"]),
            step=p["step"],
        ))
    return ParamSpace(specs)


def _worker(job_id: str, req: OptimizeRequest) -> None:
    """Background GA run; streams generation telemetry into the shared job dict."""
    try:
        with _RUN_LOCK:
            prices = get_prices(req.ticker, start=req.start, end=req.end)
            if len(prices) < 200:
                raise ValueError(f"too few bars ({len(prices)}) for {req.ticker}")

            space = _build_space(req.strategy, req.bounds)
            strat = STRATEGIES[req.strategy]["fn"]
            inst = next((i for i in INSTRUMENTS if i["ticker"] == req.ticker), None)
            cost_key = req.cost_model or (inst["cost"] if inst else "default")
            cost_model = _COST_MODELS.get(cost_key, IBKR_DEFAULT)

            cfg = GAConfig(
                population_size=req.population_size, generations=req.generations,
                selection=req.selection, crossover_prob=req.crossover_prob,
                base_mutation_rate=req.base_mutation_rate,
                min_mutation_rate=req.min_mutation_rate, elitism=req.elitism,
                seed=req.seed,
            )

            def on_gen(stats: GenerationStats) -> None:
                with _JOBS_LOCK:
                    j = _JOBS[job_id]
                    j["history"].append(stats.to_dict())
                    j["current_generation"] = stats.generation
                    j["progress"] = (stats.generation + 1) / cfg.generations

            res = run_ga(
                prices, space, strategy=strat, config=cfg,
                fitness_metric=req.fitness_metric, oos_fraction=req.oos_fraction,
                haircut_reject_pct=req.haircut_reject_pct, cost_model=cost_model,
                top_n=req.top_n, on_generation=on_gen,
            )

            # Fitness surface over the strategy's two headline genes (held at best).
            axes = STRATEGIES[req.strategy]["surface_axes"]
            surface = None
            if res.best is not None and len(axes) >= 2:
                surface = fitness_surface(
                    prices, space, res.best["params"], (axes[0], axes[1]),
                    strategy=strat, fitness_metric=req.fitness_metric,
                    grid=24, oos_fraction=req.oos_fraction, cost_model=cost_model,
                )

        result = res.to_dict()
        result["surface"] = surface
        result["ticker"] = req.ticker
        result["strategy"] = req.strategy
        result["cost_model"] = cost_key
        result["span"] = {"start": str(prices.index.min().date()),
                          "end": str(prices.index.max().date()), "bars": len(prices)}
        with _JOBS_LOCK:
            _JOBS[job_id].update(status="done", result=result, finished=time.time(),
                                 progress=1.0)
    except Exception as e:  # noqa: BLE001
        with _JOBS_LOCK:
            _JOBS[job_id].update(status="error", error=f"{type(e).__name__}: {e}",
                                 finished=time.time())


@router.post("/run")
def run(req: OptimizeRequest) -> dict:
    """Start a background GA optimization. Returns a job id to poll."""
    if req.ticker not in _TICKERS:
        raise HTTPException(status_code=400, detail=f"unknown ticker '{req.ticker}'")
    if req.strategy not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"unknown strategy '{req.strategy}'")
    if req.fitness_metric not in FITNESS_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"unknown fitness '{req.fitness_metric}'")
    if req.elitism >= req.population_size:
        raise HTTPException(status_code=400, detail="elitism must be < population_size")
    with _JOBS_LOCK:
        if any(j["status"] == "running" for j in _JOBS.values()):
            raise HTTPException(status_code=409, detail="an optimization is already running")
        job_id = uuid4().hex[:12]
        _JOBS[job_id] = {
            "status": "running", "ticker": req.ticker, "strategy": req.strategy,
            "fitness_metric": req.fitness_metric, "generations": req.generations,
            "current_generation": -1, "progress": 0.0, "history": [],
            "started": time.time(),
        }
    threading.Thread(target=_worker, args=(job_id, req), daemon=True).start()
    return {"ok": True, "job_id": job_id, "status": "running"}


@router.get("/job/{job_id}")
def job(job_id: str) -> dict:
    """Poll a GA job: live generation history while running, full result when done."""
    with _JOBS_LOCK:
        j = _JOBS.get(job_id)
        if j is None:
            raise HTTPException(status_code=404, detail="job not found")
        # Shallow copy so the response is consistent even if the worker writes mid-read.
        return {"ok": True, "job_id": job_id, **{k: v for k, v in j.items()}}
