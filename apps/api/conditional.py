"""Quant-OS Conditional Backtesting API — the Bridge to Strategies (the Router).

Mounted under ``/api/conditional`` by :mod:`apps.api.main`. Wires the Conditional
Backtesting Engine (:mod:`quantlab.conditional`) to the live data: the cached returns
book (:mod:`apps.api.switchboard`) and the benchmark regime timeline
(:mod:`apps.api.regime`).

Endpoints:
* ``/router``         — per-strategy regime matrix + ACTIVE/PAUSED + the live-switch
                        event (current vs previous regime) + the ACTIVE/PAUSED flip plan.
* ``/strategy/{num}`` — one sleeve's **Regime Performance Matrix**: its regime-tagged
                        trades, per-regime trade stats, daily-returns cells and the
                        ``allowed_market_regimes`` set the Alpha Factory validates against.

Reuses the Switchboard's TTL-cached book + the Radar's cached classification, degrades
to ``{"ok": false, "error": ...}``, and NaN/Inf-sanitises — the dashboard convention.
"""

from __future__ import annotations

import math
import time

import pandas as pd
from fastapi import APIRouter, Query

from quantlab import conditional as cb
from quantlab import switchboard as sb
from quantlab.config import get_settings

from .regime import _classify, _meta
from .switchboard import _BENCHMARK_TICKERS, _load_book

router = APIRouter(prefix="/api/conditional", tags=["conditional"])

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 120.0


def _sanitize(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _thresholds(min_sharpe: float, min_pf: float, min_trades: int) -> sb.RoutingThresholds:
    return sb.RoutingThresholds(min_sharpe=min_sharpe, min_profit_factor=min_pf,
                                min_trades=min_trades)


@router.get("/router")
def conditional_router(
    benchmark: str = Query("SPY"),
    years: int = Query(8, ge=2, le=30),
    min_sharpe: float = Query(0.8),
    min_profit_factor: float = Query(1.2),
    min_trades: int = Query(10, ge=1),
) -> dict:
    """The live Router: regime matrix + ACTIVE/PAUSED routing + the auto-switch event.

    The ``benchmark`` regime timeline is the global market regime every sleeve is
    sliced by. The response adds, over the plain Switchboard, the latest regime
    transition (``switch``) and exactly which sleeves flip ACTIVE↔PAUSED on it
    (``switch_delta``) — the trigger the Swarm command center consumes.
    """
    key = f"{benchmark}:{years}:{min_sharpe}:{min_profit_factor}:{min_trades}"
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    try:
        if benchmark not in _BENCHMARK_TICKERS:
            return {"ok": False, "error": f"unknown benchmark '{benchmark}'"}
        panel, meta = _load_book()
        if panel.empty:
            return {"ok": False, "error": "no strategies with a parseable trade log"}
        _, classified = _classify(benchmark, years)
        th = _thresholds(min_sharpe, min_profit_factor, min_trades)
        board = cb.build_router(panel, meta, classified, th)
        out = _sanitize({"ok": True, "benchmark": benchmark,
                         "benchmark_meta": _meta(benchmark), "years": years, **board})
        _CACHE[key] = (now, out)
        return out
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _load_trades(num: str) -> pd.DataFrame | None:
    """Read a strategy's ``results/trades.csv`` via the registry (path-safe)."""
    try:
        from quantlab.registry import get_strategy

        found = get_strategy(num)
    except Exception:  # noqa: BLE001
        return None
    if not found or not found.get("rel_path"):
        return None
    path = get_settings().backtest_dir / found["rel_path"] / "results" / "trades.csv"
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return None


@router.get("/strategy/{num}")
def strategy_matrix(
    num: str,
    benchmark: str = Query("SPY"),
    years: int = Query(8, ge=2, le=30),
    min_sharpe: float = Query(0.8),
    min_profit_factor: float = Query(1.2),
    min_trades: int = Query(10, ge=1),
) -> dict:
    """One sleeve's Regime Performance Matrix — for the Alpha Factory regime check.

    Returns its daily-returns regime cells + ``allowed_market_regimes`` (the regimes it
    is cleared to trade) plus the **trade-level** read: each historical trade tagged
    with the regime active at entry, aggregated per regime. The Factory pre-registers a
    strategy's regime claim; this endpoint checks it against realised performance.
    """
    try:
        if benchmark not in _BENCHMARK_TICKERS:
            return {"ok": False, "error": f"unknown benchmark '{benchmark}'"}
        _, classified = _classify(benchmark, years)
        th = _thresholds(min_sharpe, min_profit_factor, min_trades)

        # daily-returns matrix (from the cached book), if this sleeve is in the book
        panel, meta = _load_book()
        label = next((m["label"] for m in meta if str(m.get("num")) == str(num)), None)
        matrix = None
        name = None
        if label is not None and label in panel.columns:
            col = panel[label].dropna()
            name = next((m.get("name") for m in meta if m["label"] == label), label)
            if not col.empty:
                matrix = cb.conditional_matrix(col, classified, th)

        # trade-level regime tagging
        trades = _load_trades(num)
        trade_stats = None
        n_trades = 0
        tagged_sample: list[dict] = []
        if trades is not None and not trades.empty:
            tagged = cb.tag_trades(trades, classified)
            trade_stats = cb.regime_trade_stats(tagged)
            n_trades = int(len(tagged))
            keep = [c for c in ("entry_date", "exit_date", "direction",
                                "net_return", "gross_return", "pnl",
                                "entry_regime", "entry_regime_label") if c in tagged.columns]
            tagged_sample = tagged[keep].tail(40).to_dict("records") if keep else []

        if matrix is None and trade_stats is None:
            return {"ok": False, "error": f"no returns or trade log for strategy {num}"}

        return _sanitize({
            "ok": True, "num": num, "name": name, "benchmark": benchmark,
            "matrix": matrix, "allowed_market_regimes":
                (matrix or {}).get("allowed_market_regimes", []),
            "best_regime": (matrix or {}).get("best_regime"),
            "n_trades": n_trades, "trade_stats": trade_stats,
            "tagged_trades": tagged_sample,
            "regimes": [{"code": c, "label": sb.rg.REGIME_LABELS[c]} for c in sb.rg.REGIMES],
        })
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
