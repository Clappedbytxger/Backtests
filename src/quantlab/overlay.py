"""Multi-leg seasonal overlay — assemble several calendar windows into one book.

A *seasonal calendar* is a list of legs, each a short window in a different
instrument (e.g. gasoline KW9, feeder-cattle KW21, platinum turn-of-year). This
module combines them into a single net-return series two ways:

* ``mode="overlay"``   — hold a base instrument (an equity index) all year and
  step into the relevant future only inside each window. Capital-efficient: the
  book is invested in the index the rest of the time.
* ``mode="standalone"`` — hold cash outside the windows; the book is the bare
  seasonal basket with no index beta.

When two windows overlap (e.g. three December seasonals on three instruments)
two allocation rules are offered:

* ``allocation="equal-weight"`` — on a day with *k* active legs each gets ``1/k``
  of the seasonal notional (realistic: separate futures held on margin; lowers
  concentration on crowded days). Mirrors strategy 0036.
* ``allocation="priority"`` — earlier legs (list order) win the overlap; later
  legs are forced flat while an earlier one is active, so at most one leg is held
  at a time. Mirrors strategy 0033.

This is the reusable extraction of the ``build_overlay`` logic that was
copy-pasted across strategies 0007/0010/0020/0033/0036.

Look-ahead safety: leg signals are decision-time; positions are shifted one bar
(T+1) here before any return is realised, exactly like :mod:`quantlab.backtest`.
"""

from __future__ import annotations

import warnings

import pandas as pd

from .costs import CostModel, IBKR_FUTURES, IBKR_LIQUID_ETF
from .seasonal import leg_signal


def _leg_key(leg: dict) -> str:
    """Stable identifier for a leg (prefers ``name``, falls back to ``ticker``)."""
    return str(leg.get("name", leg.get("ticker", "leg")))


def _side_fraction(cost: CostModel) -> float:
    """Per-side cost as a fraction of notional (slippage + regulatory bps)."""
    return (cost.slippage_bps + cost.regulatory_bps) / 10_000.0


def build_seasonal_overlay(
    legs: list[dict],
    legs_px: dict[str, pd.DataFrame],
    base_px: pd.DataFrame | None = None,
    *,
    mode: str = "overlay",
    allocation: str = "equal-weight",
    fut_cost: CostModel = IBKR_FUTURES,
    base_cost: CostModel = IBKR_LIQUID_ETF,
    conflict_warn_legs: int = 3,
) -> dict:
    """Combine seasonal legs into one net-return series.

    Args:
        legs: list of leg dicts (see :func:`quantlab.seasonal.leg_signal` for the
            recognised keys: ``kind``, ``week``/``hold_days`` or ``start_md``/
            ``end_md``, ``ticker``, ``name``).
        legs_px: ``{ticker: OHLCV DataFrame}`` price data for every leg's ticker.
        base_px: OHLCV DataFrame for the base instrument; required for
            ``mode="overlay"``, ignored for ``mode="standalone"``.
        mode: ``"overlay"`` (hold base outside windows) or ``"standalone"``
            (hold cash outside windows).
        allocation: ``"equal-weight"`` or ``"priority"`` (see module docstring).
        fut_cost: cost model for the seasonal-future legs.
        base_cost: cost model for the base instrument (overlay mode only).
        conflict_warn_legs: emit a warning if at least this many legs are ever
            active on the same day.

    Returns:
        dict with keys:
          ``df``        -- aligned close prices (base + every leg),
          ``base_ret``  -- base buy&hold returns (zeros in standalone mode),
          ``net``       -- overlay net returns after switching costs,
          ``gross``     -- overlay returns before costs,
          ``weights``   -- per-leg held weight matrix (T+1 shifted),
          ``n_active``  -- number of legs held each day,
          ``turnover``  -- summed |Δweight| each day (cost basis).
    """
    if mode not in {"overlay", "standalone"}:
        raise ValueError(f"mode must be 'overlay' or 'standalone', got {mode!r}")
    if allocation not in {"equal-weight", "priority"}:
        raise ValueError(
            f"allocation must be 'equal-weight' or 'priority', got {allocation!r}"
        )
    if mode == "overlay" and base_px is None:
        raise ValueError("mode='overlay' requires base_px")

    keys = [_leg_key(leg) for leg in legs]
    if len(set(keys)) != len(keys):
        raise ValueError(f"leg keys must be unique, got {keys}")

    # --- Align all price series on a common (dropna) index --------------------
    cols: dict[str, pd.Series] = {}
    if mode == "overlay":
        cols["__base__"] = base_px["Close"].astype(float)
    for leg, key in zip(legs, keys):
        cols[key] = legs_px[leg["ticker"]]["Close"].astype(float)
    df = pd.DataFrame(cols).dropna()

    base_ret = (
        df["__base__"].pct_change().fillna(0.0)
        if mode == "overlay"
        else pd.Series(0.0, index=df.index, name="cash")
    )
    leg_ret = {key: df[key].pct_change().fillna(0.0) for key in keys}

    # --- Held (T+1) indicator per leg -----------------------------------------
    held_raw = {}
    for leg, key in zip(legs, keys):
        sig = leg_signal(df.index, leg).reindex(df.index).fillna(0.0)
        held_raw[key] = (sig.shift(1).fillna(0.0) > 0).astype(float)
    held_mat = pd.DataFrame(held_raw)

    raw_overlap = int((held_mat.sum(axis=1) >= conflict_warn_legs).sum())
    if raw_overlap:
        warnings.warn(
            f"{raw_overlap} day(s) have >= {conflict_warn_legs} legs active "
            f"simultaneously; allocation='{allocation}' will resolve them.",
            stacklevel=2,
        )

    # --- Allocation weights ----------------------------------------------------
    if allocation == "equal-weight":
        n_raw = held_mat.sum(axis=1)
        weights = held_mat.div(n_raw.where(n_raw > 0, 1.0), axis=0)
        weights[n_raw == 0] = 0.0
    else:  # priority: earlier legs in list order win the overlap
        weights = pd.DataFrame(0.0, index=df.index, columns=keys)
        held_any = pd.Series(False, index=df.index)
        for key in keys:
            take = (held_mat[key] > 0) & ~held_any
            weights[key] = take.astype(float)
            held_any = held_any | take

    n_active = (weights > 0).sum(axis=1)
    total_w = weights.sum(axis=1)  # 0.0 or 1.0 for both allocation models

    seasonal_ret = sum(weights[key] * leg_ret[key] for key in keys)
    gross = (1.0 - total_w) * base_ret + seasonal_ret

    # --- Switching cost on weight turnover ------------------------------------
    # Overlay swaps trade both a futures side and an index side; the standalone
    # basket trades only the futures side (cash has no slippage).
    switch_unit = _side_fraction(fut_cost)
    if mode == "overlay":
        switch_unit += _side_fraction(base_cost)
    turnover = weights.diff().abs().fillna(weights.abs()).sum(axis=1)
    net = gross - turnover * switch_unit

    return {
        "df": df,
        "base_ret": base_ret,
        "net": net,
        "gross": gross,
        "weights": weights,
        "n_active": n_active,
        "turnover": turnover,
    }
