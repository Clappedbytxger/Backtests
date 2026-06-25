"""Conditional Backtesting Engine — regime-tagged trades + the live Router.

Phase-2 bridge between the Market-Weather-Radar (:mod:`quantlab.regime`) and the
strategy book. It adds three things *on top of* the rule-based Switchboard
(:mod:`quantlab.switchboard`, which slices daily returns by a global benchmark
regime) — without duplicating it:

1. **Regime-tagged trades** (``tag_trades`` / ``regime_trade_stats``): stamp every
   historical trade with the market regime that was *nowcast-active at its entry*
   (look-ahead-safe ``merge_asof``), then aggregate per-regime win-rate / expectancy.
2. **The Regime Performance Matrix** (``conditional_matrix``): per-strategy
   per-regime cells + the ``allowed_market_regimes`` set the Alpha Factory needs to
   validate a strategy's regime claim.
3. **The automatic live-switch** (``detect_switch`` / ``live_switch_delta`` /
   ``build_router``): detect when the benchmark regime flips on the latest closed bar
   and compute exactly which sleeves flip ACTIVE↔PAUSED — the trigger the Swarm
   commander consumes.

Pure (no I/O): the API layer feeds it the returns panel, the classified regime frame
and (for trade tagging) the raw trade log.
"""

from __future__ import annotations

import pandas as pd

from quantlab import regime as rg
from quantlab import switchboard as sb

# A regime segment this short on the latest bar means the book just switched — the
# live router should treat it as a fresh ACTIVE/PAUSED reshuffle, not steady state.
SWITCH_FRESH_BARS = 3

# tolerant column detection across the heterogeneous trades.csv schemas
_ENTRY_COLS = ("entry_date", "entry", "open_date", "date", "entry_time")
_RET_COLS = ("net_return", "gross_return", "ret_primary", "pnl_pct", "return", "ret")


def _find_col(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    low = {c.lower(): c for c in df.columns}
    return next((low[n] for n in names if n in low), None)


# ── 2.1 trade-level regime tagging ──────────────────────────────────────────
def tag_trades(trades: pd.DataFrame, classified: pd.DataFrame) -> pd.DataFrame:
    """Attach the regime that was active at each trade's entry (look-ahead-safe).

    Uses a backward ``merge_asof``: a trade entered on date *d* inherits the most
    recent regime label at/<= *d* — exactly the nowcast a live desk would have seen.
    Adds ``entry_regime`` + ``entry_regime_label`` columns. Trades whose entry predates
    the first classified bar get ``<NA>``.
    """
    out = trades.copy()
    ec = _find_col(out, _ENTRY_COLS)
    if ec is None or classified.empty:
        out["entry_regime"] = pd.NA
        out["entry_regime_label"] = pd.NA
        return out
    entries = pd.to_datetime(out[ec], errors="coerce")
    reg = classified.dropna(subset=["regime"])["regime"].copy()
    reg.index = pd.to_datetime(reg.index)
    reg = reg.sort_index()
    # Series.asof: the regime nowcast active at/<= each entry (NaN if pre-history / NaT).
    # Robust to mismatched datetime resolutions across the heterogeneous trade logs,
    # which a strict merge_asof key-dtype comparison is not.
    looked = reg.asof(entries)
    out["entry_regime"] = looked.to_numpy()
    out["entry_regime_label"] = out["entry_regime"].map(rg.REGIME_LABELS)
    return out


def regime_trade_stats(tagged: pd.DataFrame) -> dict[str, dict]:
    """Per-regime trade aggregation from a frame already tagged by :func:`tag_trades`.

    Returns ``{regime_code: {n_trades, win_rate, mean_return, total_return,
    profit_factor}}`` for each of the four regimes (zeros when no trade fell in it).
    Operates on the trade-level net-return column, so this is the *event-level* read
    that complements the daily-returns matrix.
    """
    rc = _find_col(tagged, _RET_COLS)
    out: dict[str, dict] = {}
    for code in rg.REGIMES:
        sub = tagged[tagged.get("entry_regime") == code] if "entry_regime" in tagged else tagged.iloc[0:0]
        r = pd.to_numeric(sub[rc], errors="coerce").dropna() if (rc and len(sub)) else pd.Series(dtype=float)
        n = int(len(r))
        out[code] = {
            "label": rg.REGIME_LABELS[code],
            "color": rg.REGIME_COLORS[code],
            "n_trades": n,
            "win_rate": float((r > 0).mean()) if n else 0.0,
            "mean_return": float(r.mean()) if n else 0.0,
            "total_return": float(r.sum()) if n else 0.0,
            "profit_factor": rg.profit_factor(r) if n else 0.0,
        }
    return out


# ── 2.2 the Regime Performance Matrix (for the Alpha Factory) ────────────────
def conditional_matrix(returns: pd.Series, classified: pd.DataFrame,
                       th: sb.RoutingThresholds | None = None,
                       ann_factor: float = 252.0) -> dict:
    """One strategy's regime cells + its ``allowed_market_regimes`` + best regime.

    Wraps :func:`quantlab.switchboard.strategy_cells` (Sharpe/PF/WinRate/MaxDD per
    regime, each with a ``qualified`` gate) and derives the regimes the strategy is
    *allowed* to trade in — the exact claim the Alpha Factory pre-registers and this
    engine checks against realised, regime-sliced performance.
    """
    th = th or sb.RoutingThresholds()
    cells = sb.strategy_cells(returns, classified, th, ann_factor)
    allowed = [c for c in rg.REGIMES if cells[c].get("qualified")]
    ranked = sorted(rg.REGIMES, key=lambda c: cells[c].get("sharpe", 0.0), reverse=True)
    best = ranked[0] if cells[ranked[0]].get("n", 0) >= th.min_trades else None
    return {"cells": cells, "allowed_market_regimes": allowed, "best_regime": best,
            "thresholds": th.as_dict()}


# ── 2.3 regime-switch detection + the live router ───────────────────────────
def detect_switch(classified: pd.DataFrame) -> dict:
    """The latest regime transition: current vs previous segment + a just-switched flag.

    ``just_switched`` is True when the current regime segment is only a few bars old
    (≤ :data:`SWITCH_FRESH_BARS`) — i.e. the live ACTIVE/PAUSED set should be treated
    as a fresh reshuffle rather than steady state.
    """
    spans = rg.segments(classified)
    if not spans:
        return {"current_regime": None, "previous_regime": None, "since": None,
                "bars_in_regime": 0, "just_switched": False, "n_switches": 0,
                "current_label": None, "previous_label": None}
    last = spans[-1]
    prev = spans[-2] if len(spans) > 1 else None
    return {
        "current_regime": last["regime"], "current_label": last["label"],
        "current_color": last["color"],
        "previous_regime": (prev["regime"] if prev else None),
        "previous_label": (prev["label"] if prev else None),
        "since": last["start"], "bars_in_regime": int(last["bars"]),
        "just_switched": int(last["bars"]) <= SWITCH_FRESH_BARS,
        "n_switches": len(spans) - 1,
    }


def live_switch_delta(rows: list[dict], current_regime: str | None,
                      previous_regime: str | None) -> dict:
    """Which sleeves flip ACTIVE↔PAUSED going *previous → current* regime.

    Uses each row's ``active_regimes`` (the regimes it qualifies for). This is the
    "automatic live-switch": when the regime changes, ``activated`` come online and
    ``deactivated`` go flat — the desk's mechanical response to the new weather.
    """
    activated, deactivated = [], []
    for r in rows:
        allowed = r.get("active_regimes", [])
        prev_on = bool(previous_regime) and previous_regime in allowed
        cur_on = bool(current_regime) and current_regime in allowed
        ref = {"num": r.get("num"), "name": r.get("name")}
        if cur_on and not prev_on:
            activated.append(ref)
        elif prev_on and not cur_on:
            deactivated.append(ref)
    return {"previous_regime": previous_regime, "current_regime": current_regime,
            "activated": activated, "deactivated": deactivated,
            "n_activated": len(activated), "n_deactivated": len(deactivated)}


def build_router(panel: pd.DataFrame, meta: list[dict], classified: pd.DataFrame,
                 th: sb.RoutingThresholds | None = None,
                 ann_factor: float = 252.0) -> dict:
    """The full live Router: the Switchboard matrix + switch event + flip plan.

    Reuses :func:`quantlab.switchboard.build_switchboard` for the per-strategy ×
    per-regime rows, then layers on the regime-change detection and the ACTIVE/PAUSED
    flip delta. Every row also exposes ``allowed_market_regimes`` (alias of its
    qualified ``active_regimes``) so a single payload serves both the live router and
    the Alpha-Factory regime claim.
    """
    th = th or sb.RoutingThresholds()
    switch = detect_switch(classified)
    cur = switch["current_regime"]
    board = sb.build_switchboard(panel, meta, classified, cur, th, ann_factor)
    for row in board["rows"]:
        row["allowed_market_regimes"] = row.get("active_regimes", [])
    board["switch"] = switch
    board["switch_delta"] = live_switch_delta(board["rows"], cur, switch["previous_regime"])
    return board


def commander_strategy_view(rows: list[dict], current_regime: str | None,
                            limit: int = 12) -> list[dict]:
    """Compact, regime-annotated strategy list for the Swarm commander.

    Each entry carries the sleeve's identity plus its *current-regime* evidence
    (status, Sharpe, profit factor) and ``allowed_regimes`` — so the commander routes
    on realised regime performance instead of a blunt top-Sharpe heuristic. ACTIVE
    sleeves first, then by current-regime Sharpe.
    """
    view = []
    for r in rows:
        cur_cell = (r.get("cells") or {}).get(current_regime or "", {})
        view.append({
            "num": r.get("num"), "name": r.get("name"), "category": r.get("category"),
            "sharpe": cur_cell.get("sharpe"),
            "regime_status": r.get("status"),
            "allowed_regimes": r.get("allowed_market_regimes", []),
            "current_regime_sharpe": cur_cell.get("sharpe"),
            "current_regime_pf": cur_cell.get("profit_factor"),
        })
    view.sort(key=lambda v: (v["regime_status"] != sb.STATUS_ACTIVE,
                             -(v["current_regime_sharpe"] or -99)))
    return view[:limit]
