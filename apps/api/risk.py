"""Quant-OS Risk Desk API — institutional risk management over the active book.

Mounted under ``/api/risk`` by :mod:`apps.api.main`. Aggregates the daily return
streams of the alive strategies (:mod:`quantlab.risk_book`) and runs the institutional
risk engine (:mod:`quantlab.risk`): VaR / Expected Shortfall (historical + parametric,
95/99, 1d/10d), the dynamic correlation matrix, capital allocation (MVO max-Sharpe /
min-variance, HRP, equal-weight) and the Euler risk-contribution decomposition.

Endpoints:
* ``/book``        — the selectable sleeves (meta) + default selection + windows
* ``/dashboard``   — the one combined payload behind the risk desk (cards, heatmap,
                     allocation-vs-risk-contribution), parametrised by window / selection
                     / capital / weighting / VaR limit
* ``/correlation`` — rolling correlation time series for one pair (the drill-down)

Every endpoint degrades to ``{"ok": false, "error": ...}`` and all floats are
NaN/Inf-sanitised so the response is always valid JSON — the dashboard convention.
"""

from __future__ import annotations

import math
import time

import pandas as pd
from fastapi import APIRouter, Query

from quantlab import risk, risk_book

router = APIRouter(prefix="/api/risk", tags=["risk"])

# weighting scheme → human label (single source of truth for the UI toggle)
WEIGHTINGS = {
    "equal_weight": "Equal Weight (1/N)",
    "mvo_max_sharpe": "Max-Sharpe (MVO)",
    "mvo_min_variance": "Min-Variance (MVO)",
    "hrp": "Hierarchical Risk Parity",
}
WINDOWS = [
    {"key": "30", "days": 30, "label": "30 Tage"},
    {"key": "90", "days": 90, "label": "90 Tage"},
    {"key": "252", "days": 252, "label": "1 Jahr"},
    {"key": "full", "days": None, "label": "Gesamt"},
]

# in-process cache of the loaded book (CSV reads are cheap, but the book changes rarely)
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


def _window_days(window: str) -> int | None:
    if window in (None, "", "full", "0"):
        return None
    try:
        return int(window)
    except ValueError:
        return None


def _select(panel: pd.DataFrame, nums: str | None) -> pd.DataFrame:
    """Restrict the panel columns to the requested strategy numbers (``num`` prefix)."""
    if not nums:
        return panel
    wanted = {n.strip() for n in nums.split(",") if n.strip()}
    cols = [c for c in panel.columns if c[:4] in wanted]
    return panel[cols] if cols else panel


def _warn_level(value: float | None, yellow: float, red: float) -> str:
    """green / yellow / red traffic light for a loss magnitude vs its limits."""
    if value is None or not math.isfinite(value):
        return "unknown"
    if value >= red:
        return "red"
    if value >= yellow:
        return "yellow"
    return "green"


# ── endpoints ─────────────────────────────────────────────────────────────────


@router.get("/book")
def book() -> dict:
    """The selectable sleeves (meta), the default selection and the window presets."""
    try:
        panel, meta = _load_book()
        return _sanitize({
            "ok": True,
            "count": len(meta),
            "strategies": meta,
            "default_selection": [m["num"] for m in meta],
            "weightings": [{"key": k, "label": v} for k, v in WEIGHTINGS.items()],
            "windows": WINDOWS,
            "span": {"start": risk._isodate(panel.index.min()) if len(panel) else None,
                     "end": risk._isodate(panel.index.max()) if len(panel) else None},
        })
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _allocation_block(mtx: pd.DataFrame) -> dict:
    """Every allocation model + its risk-contribution decomposition (for the chart)."""
    allocs = {
        "equal_weight": risk.equal_weight(mtx),
        "mvo_max_sharpe": risk.mean_variance_optimization(mtx, objective="max_sharpe"),
        "mvo_min_variance": risk.mean_variance_optimization(mtx, objective="min_variance"),
        "hrp": risk.hierarchical_risk_parity(mtx),
    }
    cov = risk.covariance_matrix(mtx)
    out = {}
    for key, a in allocs.items():
        rc = risk.risk_contributions(a.weights, cov)
        out[key] = {
            **a.as_dict(),
            "risk_contribution": {c: float(rc.loc[c, "pct"]) for c in rc.index},
        }
    return out


@router.get("/dashboard")
def dashboard(
    window: str = Query("full", description="30 | 90 | 252 | full"),
    nums: str | None = Query(None, description="comma-separated strategy numbers; empty = all"),
    capital: float = Query(100_000.0, gt=0),
    weighting: str = Query("equal_weight"),
    var_limit_pct: float = Query(0.02, gt=0, description="daily 95% VaR red line as fraction of capital"),
) -> dict:
    """The full risk-desk payload for the selected book, window and weighting scheme.

    Returns: portfolio risk cards (VaR/ES grid + currency + traffic-light vs the VaR
    limit + diversification benefit), the correlation matrix, every allocation model
    with its risk-contribution split, and the per-strategy risk table — everything the
    dashboard renders, in one call.
    """
    try:
        panel, meta = _load_book()
        if panel.empty:
            return {"ok": False, "error": "no strategies with a parseable trade log"}
        sub = _select(panel, nums)
        mtx = risk_book.to_risk_matrix(sub, _window_days(window))
        if mtx.shape[1] < 1:
            return {"ok": False, "error": "selection has no sleeve alive in this window"}

        weighting = weighting if weighting in WEIGHTINGS else "equal_weight"
        allocations = _allocation_block(mtx)
        active_weights = allocations[weighting]["weights"]

        summary = risk.book_risk_summary(mtx, active_weights, capital=capital)
        v95 = summary["portfolio"]["var_es"]["95_1d"]["var_historical"]
        var_pct = v95 if v95 is not None else None
        level = _warn_level(var_pct, yellow=var_limit_pct * 0.5, red=var_limit_pct)

        corr = risk.correlation_matrix(mtx)
        labels = list(corr.columns)
        matrix = [[None if pd.isna(corr.iat[i, j]) else round(float(corr.iat[i, j]), 4)
                   for j in range(len(labels))] for i in range(len(labels))]

        meta_by_num = {m["num"]: m for m in meta}
        selected_meta = [meta_by_num[c[:4]] for c in mtx.columns if c[:4] in meta_by_num]

        return _sanitize({
            "ok": True,
            "window": window,
            "weighting": weighting,
            "weighting_label": WEIGHTINGS[weighting],
            "capital": capital,
            "var_limit_pct": var_limit_pct,
            "warn_level": level,
            "n_obs": summary["n_obs"],
            "span": summary["span"],
            "summary": summary,
            "allocations": allocations,
            "active_weights": active_weights,
            "correlation": {"labels": labels, "matrix": matrix},
            "strategies": selected_meta,
        })
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/correlation")
def correlation(
    a: str = Query(..., description="strategy number A"),
    b: str = Query(..., description="strategy number B"),
    rolling_window: int = Query(90, ge=20, le=504),
) -> dict:
    """Rolling correlation between two sleeves — 'is the diversification still there?'."""
    try:
        panel, _ = _load_book()
        cols = {c[:4]: c for c in panel.columns}
        if a not in cols or b not in cols:
            return {"ok": False, "error": "unknown strategy number(s)"}
        ca, cb = cols[a], cols[b]
        joined = panel[[ca, cb]].dropna()
        roll = risk.rolling_correlation(joined.fillna(0.0), ca, cb, rolling_window).dropna()
        series = [{"t": risk._isodate(ix), "corr": round(float(v), 4)}
                  for ix, v in roll.items()]
        full = joined[ca].corr(joined[cb])
        return _sanitize({
            "ok": True, "a": ca, "b": cb, "rolling_window": rolling_window,
            "full_correlation": float(full) if pd.notna(full) else None,
            "series": series,
        })
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
