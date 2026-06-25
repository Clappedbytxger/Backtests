"""Dynamic Strategy Routing — the Switchboard between regime detection and the book.

Bridges the Market-Weather-Radar (:mod:`quantlab.regime`) and the strategy book
(:mod:`quantlab.risk_book`). For every sleeve it slices the sleeve's daily returns by
the **global market regime** (the regime timeline of a chosen benchmark, e.g. ``SPY``),
builds a per-strategy × per-regime **performance matrix** — Sharpe, Profit Factor, Win
Rate, Max Drawdown isolated for each of the four canonical regimes — and applies a
rule-based router that marks each sleeve ``ACTIVE`` / ``PAUSED`` for the regime of the
latest closed bar.

Routing rule (per regime cell): a strategy is *qualified* ⇔ Sharpe > ``min_sharpe``
**and** Profit Factor > ``min_profit_factor`` (with at least ``min_trades`` bars of
evidence). The live router activates exactly the sleeves that qualify for the current
regime; everything else is paused. When the benchmark regime flips, re-running the
router (the next bar close) reshuffles the active set — that is the whole point of the
switchboard: only run a strategy in the regime it was shown to earn in.

Look-ahead safety is inherited: the regime classification is a *nowcast* (only bars
``<= t`` enter each label, see :mod:`quantlab.regime`) and the per-regime split never
peeks forward. This module is pure (no I/O); the API layer feeds it the returns panel
and the classified regime frame.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quantlab import regime as rg

# Cell rating → semantic color tier for the dashboard matrix. The router's pass/fail
# (qualified) drives green vs grey; magnitude splits good vs excellent; a losing cell
# is always red regardless of the thresholds.
RATING_EXCELLENT = "excellent"  # tiefgrün — strong, qualified
RATING_GOOD = "good"            # hellgrün — qualified (would be routed ACTIVE)
RATING_NEUTRAL = "neutral"      # grau — flat / too thin / below threshold
RATING_LOSS = "loss"            # rot — money-loser in this regime

# Color codes mirror the radar palette family so the whole app reads consistently.
RATING_COLORS: dict[str, str] = {
    RATING_EXCELLENT: "#15803d",  # deep green
    RATING_GOOD: "#4ade80",       # light green
    RATING_NEUTRAL: "#3f3f46",    # slate-grey
    RATING_LOSS: "#dc2626",       # alarm red
}

STATUS_ACTIVE = "ACTIVE"
STATUS_PAUSED = "PAUSED"


@dataclass(frozen=True)
class RoutingThresholds:
    """Pre-registered gate for routing a strategy ON in a given regime.

    Defaults match the Switchboard spec: a strategy goes ``ACTIVE`` in a regime only if
    its isolated Sharpe exceeds 0.8 *and* its Profit Factor exceeds 1.2 there.
    """

    min_sharpe: float = 0.8
    min_profit_factor: float = 1.2
    min_trades: int = 10          # evidence floor — a 2-bar "edge" is noise, not a route
    excellent_sharpe: float = 1.5  # tier-up boundary for the "tiefgrün" cell
    excellent_profit_factor: float = 2.0

    def as_dict(self) -> dict:
        return {
            "min_sharpe": self.min_sharpe,
            "min_profit_factor": self.min_profit_factor,
            "min_trades": self.min_trades,
            "excellent_sharpe": self.excellent_sharpe,
            "excellent_profit_factor": self.excellent_profit_factor,
        }


def cell_qualified(cell: dict, th: RoutingThresholds) -> bool:
    """Does this regime cell clear the routing gate (Sharpe & PF & enough evidence)?"""
    if cell.get("n", 0) < th.min_trades:
        return False
    return (cell.get("sharpe", 0.0) > th.min_sharpe
            and cell.get("profit_factor", 0.0) > th.min_profit_factor)


def cell_rating(cell: dict, th: RoutingThresholds) -> str:
    """Map a regime cell to one of the four color tiers (excellent/good/neutral/loss)."""
    n = cell.get("n", 0)
    if n < th.min_trades:
        return RATING_NEUTRAL  # not enough evidence to color it green OR red
    if cell.get("total_return", 0.0) < 0 or cell.get("sharpe", 0.0) < 0:
        return RATING_LOSS
    if not cell_qualified(cell, th):
        return RATING_NEUTRAL
    if (cell.get("sharpe", 0.0) >= th.excellent_sharpe
            and cell.get("profit_factor", 0.0) >= th.excellent_profit_factor):
        return RATING_EXCELLENT
    return RATING_GOOD


def strategy_cells(returns: pd.Series, classified: pd.DataFrame,
                   th: RoutingThresholds, ann_factor: float = 252.0) -> dict[str, dict]:
    """Per-regime performance cells for one sleeve, enriched with rating + qualified flag.

    Wraps :func:`quantlab.regime.regime_performance` (which already isolates Sharpe,
    Profit Factor, Win Rate and Max Drawdown per regime) and stamps each cell with its
    routing verdict (``qualified``) and color ``rating``.
    """
    perf = rg.regime_performance(returns, classified, ann_factor=ann_factor)
    for code, cell in perf.items():
        cell["qualified"] = cell_qualified(cell, th)
        cell["rating"] = cell_rating(cell, th)
    return perf


def route_status(cells: dict[str, dict], current_regime: str | None) -> str:
    """ACTIVE iff the sleeve qualifies for the *current* regime, else PAUSED."""
    if not current_regime:
        return STATUS_PAUSED
    cell = cells.get(current_regime)
    return STATUS_ACTIVE if (cell and cell.get("qualified")) else STATUS_PAUSED


def build_switchboard(
    panel: pd.DataFrame,
    meta: list[dict],
    classified: pd.DataFrame,
    current_regime: str | None,
    th: RoutingThresholds | None = None,
    ann_factor: float = 252.0,
) -> dict:
    """Assemble the full switchboard: per-strategy rows + live routing summary.

    Parameters
    ----------
    panel : daily-returns frame (date index × strategy-label columns), from
        :func:`quantlab.risk_book.load_strategy_returns`.
    meta : per-strategy descriptors (``num``/``name``/``label``/``status`` …) aligned to
        the panel columns by ``label``.
    classified : the benchmark's :func:`quantlab.regime.classify` output (the global
        market regime timeline used to slice every sleeve).
    current_regime : the regime code of the latest closed bar (drives ACTIVE/PAUSED).
    th : routing thresholds (defaults to the spec's Sharpe>0.8 & PF>1.2 gate).

    Returns a dict with ``rows`` (one per strategy, each carrying its 4 regime ``cells``,
    the ``active_regimes`` it qualifies for, and its live ``status``) plus a ``summary``
    counting active vs paused sleeves.
    """
    th = th or RoutingThresholds()
    meta_by_label = {m["label"]: m for m in meta}
    rows: list[dict] = []

    for label in panel.columns:
        col = panel[label].dropna()
        if col.empty:
            continue
        cells = strategy_cells(col, classified, th, ann_factor)
        status = route_status(cells, current_regime)
        active_regimes = [c for c in rg.REGIMES if cells[c].get("qualified")]
        m = meta_by_label.get(label, {})
        rows.append({
            "num": m.get("num", label[:4]),
            "label": label,
            "name": m.get("name", label),
            "status_catalog": m.get("status"),
            "category": m.get("category"),
            "n_total": int(sum(cells[c]["n"] for c in rg.REGIMES)),
            "cells": cells,
            "active_regimes": active_regimes,
            "status": status,
        })

    # ACTIVE sleeves first, then by current-regime Sharpe (best route at the top)
    def _sort_key(r: dict):
        cur = r["cells"].get(current_regime or "", {})
        return (r["status"] != STATUS_ACTIVE, -float(cur.get("sharpe", 0.0)))

    rows.sort(key=_sort_key)
    n_active = sum(1 for r in rows if r["status"] == STATUS_ACTIVE)
    return {
        "thresholds": th.as_dict(),
        "current_regime": current_regime,
        "regimes": [
            {"code": c, "label": rg.REGIME_LABELS[c], "color": rg.REGIME_COLORS[c]}
            for c in rg.REGIMES
        ],
        "rating_colors": RATING_COLORS,
        "rows": rows,
        "summary": {
            "n_strategies": len(rows),
            "active": n_active,
            "paused": len(rows) - n_active,
        },
    }
