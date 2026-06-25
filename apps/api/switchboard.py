"""Quant-OS Switchboard API — dynamic strategy routing by market regime.

Mounted under ``/api/switchboard`` by :mod:`apps.api.main`. The bridge between the
Market-Weather-Radar (:mod:`apps.api.regime`) and the strategy book
(:mod:`quantlab.risk_book`): it classifies a benchmark's regime history, slices every
alive sleeve's daily returns by that *global* market regime, and runs the rule-based
router (:mod:`quantlab.switchboard`) that marks each sleeve ACTIVE / PAUSED for the
regime of the latest closed bar.

Endpoints:
* ``/benchmarks`` — selectable benchmarks that define "the market regime"
* ``/matrix``     — the full switchboard payload: per-strategy × per-regime performance
                    matrix (Sharpe / Profit Factor / Win Rate / MaxDD), the live current
                    regime (with the last-switch marker), and the ACTIVE/PAUSED routing

Every endpoint degrades to ``{"ok": false, "error": ...}`` and all floats are
NaN/Inf-sanitised — the dashboard convention.
"""

from __future__ import annotations

import math
import time

import pandas as pd
from fastapi import APIRouter, Query

from quantlab import regime as rg
from quantlab import risk_book, switchboard as sb

# reuse the radar router's TTL-cached classify (handles VIX blending + caching)
from .regime import UNIVERSE as REGIME_UNIVERSE, _classify, _meta

router = APIRouter(prefix="/api/switchboard", tags=["switchboard"])

# Benchmarks that can define "the market regime" the whole book is routed by. Equity
# benchmarks blend ^VIX (see the radar); BTC is offered for crypto-leaning books.
_BENCHMARK_TICKERS = ("SPY", "QQQ", "IWM", "TLT", "GLD", "BTC-USD")

# in-process cache of the loaded book (CSV reads are cheap, book changes rarely)
_BOOK_CACHE: dict = {"ts": 0.0, "panel": None, "meta": None}
_BOOK_TTL = 300.0


def _load_book() -> tuple[pd.DataFrame, list[dict]]:
    now = time.time()
    if _BOOK_CACHE["panel"] is not None and now - _BOOK_CACHE["ts"] < _BOOK_TTL:
        return _BOOK_CACHE["panel"], _BOOK_CACHE["meta"]
    panel, meta = risk_book.load_strategy_returns()
    _BOOK_CACHE.update(ts=now, panel=panel, meta=meta)
    return panel, meta


def _sanitize(obj):
    """Replace NaN/Inf with None so the payload is valid JSON."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _switch_info(classified: pd.DataFrame) -> dict:
    """Current regime + the bar it began + the regime it replaced (the live switch)."""
    spans = rg.segments(classified)
    if not spans:
        return {"current_regime": None, "previous_regime": None,
                "since": None, "bars_in_regime": 0}
    last = spans[-1]
    prev = spans[-2] if len(spans) > 1 else None
    return {
        "current_regime": last["regime"],
        "previous_regime": (prev["regime"] if prev else None),
        "since": last["start"],
        "bars_in_regime": last["bars"],
    }


@router.get("/benchmarks")
def benchmarks() -> dict:
    """The benchmarks that can define the global market regime (the live-indicator source)."""
    by_ticker = {u["ticker"]: u for u in REGIME_UNIVERSE}
    items = [{"ticker": t, "name": by_ticker.get(t, {}).get("name", t),
              "asset_class": by_ticker.get(t, {}).get("asset_class", "other")}
             for t in _BENCHMARK_TICKERS]
    return {"ok": True, "count": len(items), "benchmarks": items}


@router.get("/matrix")
def matrix(
    benchmark: str = Query("SPY", description="ticker whose regime defines the book's market regime"),
    years: int = Query(8, ge=2, le=30),
    min_sharpe: float = Query(0.8),
    min_profit_factor: float = Query(1.2),
    min_trades: int = Query(10, ge=1),
) -> dict:
    """The full switchboard: regime performance matrix + live ACTIVE/PAUSED routing.

    The ``benchmark`` ticker's regime timeline is the *global* market regime; every
    alive sleeve's daily returns are sliced by it. A sleeve is routed ACTIVE for the
    current regime only if its isolated Sharpe > ``min_sharpe`` and Profit Factor >
    ``min_profit_factor`` there (with ≥ ``min_trades`` bars of evidence).
    """
    try:
        if benchmark not in _BENCHMARK_TICKERS:
            return {"ok": False, "error": f"unknown benchmark '{benchmark}'"}
        panel, meta = _load_book()
        if panel.empty:
            return {"ok": False, "error": "no strategies with a parseable trade log"}

        _, classified = _classify(benchmark, years)
        switch = _switch_info(classified)
        snap = rg.current_regime(classified)
        dist = rg.regime_distribution(classified)

        th = sb.RoutingThresholds(
            min_sharpe=min_sharpe, min_profit_factor=min_profit_factor, min_trades=min_trades)
        board = sb.build_switchboard(
            panel, meta, classified, switch["current_regime"], th)

        return _sanitize({
            "ok": True,
            "benchmark": benchmark,
            "benchmark_meta": _meta(benchmark),
            "years": years,
            "current": snap,
            "switch": switch,
            "distribution": dist,
            **board,
        })
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
