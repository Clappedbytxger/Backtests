"""Roll-artifact guard for continuous-futures seasonals.

A continuous front-month futures series is stitched across contract expiries. In
contango/backwardation the stitch can print a spurious return on the roll day —
and a seasonal window that happens to straddle an expiry can look like a strong
edge that is really just that mechanical gap (lesson 0028/0029: the gas autumn
window had 105% of its mean PnL on ~6 expiry days/year; excluding a tight zone
around each roll flipped permutation p from 0.002 to 0.773, and zucker 0034
behaved the same).

This module generalises the roll-day exclusion test from strategy 0029 into a
single reusable function. The rule: a continuous-futures seasonal only counts as
a lead if it *survives* removing a tight zone around every in-window expiry.

``roll_exclusion_test`` runs the window strategy twice — once on all days, once
with the roll-zone calendar days forced flat — and reports expectancy,
significance and the share of the edge that sits on the roll days.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .costs import CostModel, IBKR_FUTURES
from .metrics import compute_metrics, trade_stats
from .significance import permutation_test

# (month, day) ranges, inclusive. A monthly-rolling future terminates ~3 business
# days before the 1st of the delivery month, i.e. late in the prior calendar
# month — so a ±-day zone at each month-end brackets the roll.
MonthDay = tuple[int, int]
Zone = tuple[MonthDay, MonthDay]


def in_roll_zone(month: int, day: int, zones: list[Zone]) -> bool:
    """True if ``(month, day)`` falls inside any inclusive roll zone."""
    return any(lo <= (month, day) <= hi for lo, hi in zones)


def roll_zone_mask(index: pd.DatetimeIndex, zones: list[Zone]) -> np.ndarray:
    """Boolean array marking dates inside any roll zone."""
    idx = pd.DatetimeIndex(index)
    return np.array([in_roll_zone(t.month, t.day, zones) for t in idx])


def roll_exclusion_test(
    prices: pd.DataFrame,
    signal: pd.Series,
    roll_zones: list[Zone],
    *,
    cost_model: CostModel = IBKR_FUTURES,
    n_perm: int = 2000,
    seed: int | None = 42,
) -> dict:
    """Test whether a futures-window edge survives removing the roll-zone days.

    Args:
        prices: OHLCV DataFrame for the continuous future.
        signal: decision-time window signal (0/1), e.g. from
            :func:`quantlab.seasonal.date_window_signal`. The engine applies the
            T+1 shift, so pass the un-shifted signal.
        roll_zones: list of inclusive ``((m, d), (m, d))`` calendar zones around
            the in-window expiries to test for.
        cost_model: futures cost model (default :data:`IBKR_FUTURES`).
        n_perm: permutation iterations.
        seed: RNG seed for reproducibility.

    Returns:
        dict with ``base`` (all days) and ``roll_excluded`` sub-dicts — each
        holding expectancy, win_rate, n_trades, sharpe and perm_p — plus
        ``share_on_roll_days`` (fraction of the summed in-window return that
        accrues on roll-zone days), ``n_roll_days_held`` and ``roll_zones``.
        A real edge keeps a significant ``perm_p`` after exclusion and has a
        modest ``share_on_roll_days``; an artifact loses significance.
    """
    idx = pd.DatetimeIndex(prices.index)
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    mask = roll_zone_mask(idx, roll_zones)
    mask_s = pd.Series(mask, index=idx)

    signal = signal.reindex(idx).fillna(0.0)
    signal_excl = signal.copy()
    signal_excl[mask] = 0.0

    def _bundle(sig: pd.Series) -> dict:
        res = run_backtest(prices, sig, cost_model=cost_model)
        rets = res["returns"]
        ts = trade_stats(res["trades"])
        perm = permutation_test(rets, asset_ret, res["position"], n_perm=n_perm, seed=seed)
        return {
            "expectancy": ts["expectancy"],
            "win_rate": ts["win_rate"],
            "n_trades": ts["n_trades"],
            "sharpe": compute_metrics(rets)["sharpe"],
            "perm_p": perm["p_value"],
        }

    # Share of the summed in-window return that sits on roll-zone days.
    # Use != 0 so the mask is correct for short (-1) windows too.
    held = signal.shift(1).fillna(0.0) != 0
    win_sum = asset_ret[held].sum()
    roll_sum = asset_ret[held & mask_s].sum()
    share = float(roll_sum / win_sum) if win_sum else float("nan")

    return {
        "base": _bundle(signal),
        "roll_excluded": _bundle(signal_excl),
        "share_on_roll_days": share,
        "n_roll_days_held": int((held & mask_s).sum()),
        "roll_zones": [[list(lo), list(hi)] for lo, hi in roll_zones],
    }
