"""Prediction panel -> quintile long/short commodity portfolio.

The ML layer outputs a daily prediction panel (date x commodity, higher =
more attractive). This module turns it into a tradeable dollar-neutral book:
long the top quintile, short the bottom quintile, **inverse-vol weights
within each leg** (equal risk contribution per name — a thin-vol soft must
not dominate the book), weekly or monthly rebalancing, turnover-based costs.

Look-ahead contract (same as ``cross_sectional.py``): target weights are
decided from information up to the close of rebalance day ``t``, forward-
filled and ``shift(1)``-ed, so they are first *held* on ``t+1`` and earn that
day's return. Returns must be roll-adjusted (lesson 0048) — pass returns,
not naive continuous closes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .cross_sectional import _rebalance_dates


def quintile_ls_weights(
    pred_row: pd.Series,
    vol_row: pd.Series | None = None,
    quantile: float = 0.2,
    min_names: int = 8,
    long_only: bool = False,
) -> pd.Series:
    """One cross-section of predictions -> dollar-neutral L/S weights.

    Long the top ``quantile`` fraction, short the bottom; within each leg
    weights are proportional to ``1/vol`` (equal-weight if ``vol_row`` is
    None) and normalized so each leg's gross is 1.0 (net 0, gross 2).
    With ``long_only=True`` the short leg is dropped (gross 1, net 1) —
    the crypto roadmap's primary variant (alpha sits in the long leg, no
    borrow problem).
    """
    out = pd.Series(0.0, index=pred_row.index)
    s = pred_row.dropna()
    if len(s) < min_names:
        return out
    k = max(1, int(round(quantile * len(s))))
    ranked = s.sort_values()
    longs, shorts = ranked.index[-k:], ranked.index[:k]

    def leg(names) -> pd.Series:
        if vol_row is None:
            w = pd.Series(1.0, index=names)
        else:
            v = vol_row.reindex(names)
            # A name with unknown vol gets the leg's median risk weight.
            w = 1.0 / v.fillna(v.median())
            if not np.isfinite(w).all() or w.sum() <= 0:
                w = pd.Series(1.0, index=names)
        return w / w.sum()

    out[longs] = leg(longs)
    if not long_only:
        out[shorts] = -leg(shorts)
    return out


def run_ml_portfolio(
    returns: pd.DataFrame,
    predictions: pd.DataFrame,
    vol: pd.DataFrame | None = None,
    rebalance: str = "W",
    quantile: float = 0.2,
    cost_bps_per_side: float | pd.DataFrame = 5.0,
    min_names: int = 8,
    long_only: bool = False,
) -> dict:
    """Backtest a prediction panel as a quintile L/S portfolio.

    Args:
        returns: daily roll-adjusted return panel (columns = roots).
        predictions: daily prediction panel, higher = long. NaN = exclude.
        vol: daily realized-vol panel for inverse-vol leg weights (optional;
            must itself be decision-time, e.g. a trailing window).
        rebalance: "W" (weekly) or "ME" (monthly) — last trading day each.
        quantile: leg fraction (0.2 = quintiles).
        cost_bps_per_side: cost per unit one-sided turnover, in bps — a
            scalar, or a per-name daily panel (liquidity-staged costs; NaN
            falls back to the panel's cross-sectional worst tier that day).
        min_names: minimum names with a valid prediction to hold a book.
        long_only: top-quantile long-only book (gross 1) instead of L/S.

    Returns:
        dict with net/gross returns, equity, held weights, per-rebalance
        turnover and the rebalance dates.
    """
    returns = returns.sort_index()
    idx = returns.index

    rb_dates = _rebalance_dates(idx, rebalance)
    pred_rb = predictions.reindex(rb_dates)
    vol_rb = vol.reindex(rb_dates) if vol is not None else None

    rows = {}
    for dt in rb_dates:
        vrow = vol_rb.loc[dt] if vol_rb is not None else None
        rows[dt] = quintile_ls_weights(
            pred_rb.loc[dt], vrow, quantile=quantile, min_names=min_names,
            long_only=long_only,
        )
    target = pd.DataFrame(rows).T.reindex(columns=returns.columns).fillna(0.0)
    return _settle_targets(returns, target, cost_bps_per_side, rb_dates)


def _settle_targets(
    returns: pd.DataFrame,
    target: pd.DataFrame,
    cost_bps_per_side: float | pd.DataFrame,
    rb_dates: pd.DatetimeIndex,
) -> dict:
    """Target weights at rebalance dates -> held weights, PnL, turnover costs."""
    idx = returns.index
    w_daily = target.reindex(idx, method="ffill").fillna(0.0)
    held = w_daily.shift(1).fillna(0.0)

    gross_ret = (held * returns).sum(axis=1)
    turnover_panel = held.diff().abs().fillna(0.0)
    turnover_daily = turnover_panel.sum(axis=1)
    if isinstance(cost_bps_per_side, pd.DataFrame):
        bps = cost_bps_per_side.reindex(index=idx, columns=returns.columns)
        worst = bps.max(axis=1)
        bps = bps.apply(lambda col: col.fillna(worst))
        cost = (turnover_panel * bps / 1e4).sum(axis=1)
    else:
        cost = turnover_daily * (cost_bps_per_side / 1e4)
    net_ret = gross_ret - cost

    return {
        "returns": net_ret,
        "gross_returns": gross_ret,
        "equity": (1.0 + net_ret).cumprod(),
        "weights": held,
        "turnover": turnover_daily[turnover_daily > 0],
        "rebalance_dates": rb_dates,
    }


def run_buffered_long_portfolio(
    returns: pd.DataFrame,
    predictions: pd.DataFrame,
    vol: pd.DataFrame | None = None,
    rebalance: str = "W",
    quantile: float = 0.2,
    buffer_mult: float = 2.0,
    cost_bps_per_side: float | pd.DataFrame = 5.0,
    min_names: int = 8,
    pred_ffill_limit: int = 6,
    min_k: int = 1,
) -> dict:
    """Long-only top-quantile book with a hold-band against turnover churn.

    At each rebalance a NEW name must rank inside the top ``quantile``
    fraction to enter, but a HELD name stays as long as it remains inside
    the wider ``buffer_mult * quantile`` band (classic rank-buffering — cuts
    the churn of names oscillating around the quantile boundary, which is
    the dominant cost driver of a weekly-refit cross-section).

    ``predictions`` may be sparse (e.g. weekly rows): they are forward-filled
    up to ``pred_ffill_limit`` days so monthly rebalances can use the latest
    weekly prediction — information only travels forward in time.

    The book holds between ``k`` (target) and ``buffer_mult*k`` names;
    inverse-vol weights, gross 1. A date with fewer than ``min_names`` valid
    predictions liquidates the book (same convention as run_ml_portfolio).
    ``min_k`` floors the target book size (concentration guard: a decile of
    a small filtered universe can shrink to 2-3 names — idiosyncratic, not
    cross-sectional); the buffer band widens proportionally.
    """
    returns = returns.sort_index()
    idx = returns.index
    rb_dates = _rebalance_dates(idx, rebalance)

    pred_rb = predictions.reindex(idx).ffill(limit=pred_ffill_limit).reindex(rb_dates)
    vol_rb = vol.reindex(idx).ffill(limit=pred_ffill_limit).reindex(rb_dates) if vol is not None else None

    held: list[str] = []
    rows = {}
    for dt in rb_dates:
        s = pred_rb.loc[dt].dropna()
        out = pd.Series(0.0, index=pred_rb.columns)
        if len(s) < min_names:
            held = []
            rows[dt] = out
            continue
        k = min(len(s), max(1, min_k, int(round(quantile * len(s)))))
        band = max(k, int(round(buffer_mult * quantile * len(s))))
        if min_k > 1:  # widen the band proportionally with the floored k
            band = max(band, int(round(buffer_mult * k)))
        band = min(len(s), band)
        ranked = s.sort_values(ascending=False)
        band_set = set(ranked.index[:band])
        keep = [n for n in held if n in band_set]
        entrants = [n for n in ranked.index[:k] if n not in keep]
        sel = keep + entrants[: max(0, k - len(keep))]
        # if the band kept more than k names, that's fine — fewer trades.

        if vol_rb is not None:
            v = vol_rb.loc[dt].reindex(sel)
            w = 1.0 / v.fillna(v.median())
            if not np.isfinite(w).all() or w.sum() <= 0:
                w = pd.Series(1.0, index=sel)
        else:
            w = pd.Series(1.0, index=sel)
        out[sel] = w / w.sum()
        held = sel
        rows[dt] = out

    target = pd.DataFrame(rows).T.reindex(columns=returns.columns).fillna(0.0)
    return _settle_targets(returns, target, cost_bps_per_side, rb_dates)
