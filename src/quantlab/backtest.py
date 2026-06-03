"""Vectorized single-asset backtest engine with look-ahead protection.

Convention (no look-ahead):
    A *signal* is the target position decided using information available up to
    and including the close of day ``t``. The engine shifts it by one bar, so the
    position is only *held* from day ``t+1`` onward and earns that day's
    close-to-close return. This makes future leakage structurally impossible.

Positions are target weights (e.g. ``1.0`` fully long, ``-1.0`` short, ``0`` flat).
Transaction costs from :mod:`quantlab.costs` are charged on position changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .costs import CostModel, IBKR_DEFAULT


def run_backtest(
    prices: pd.DataFrame,
    signal: pd.Series,
    cost_model: CostModel | None = None,
    representative_price: float | None = None,
    representative_shares: float = 100.0,
) -> dict:
    """Run a vectorized backtest.

    Args:
        prices: DataFrame with at least a ``Close`` column, datetime-indexed.
        signal: target position weight per day, aligned to ``prices.index``.
            Decided at the close of each day; the engine applies ``.shift(1)``.
        cost_model: transaction-cost model; defaults to IBKR tiered.
        representative_price / representative_shares: used to translate the
            cost model into a per-turnover fraction. Defaults to the mean close.

    Returns:
        dict with:
            ``returns``  – net strategy return series
            ``gross_returns`` – before costs
            ``equity``   – compounded net equity curve (start = 1.0)
            ``position`` – the actually-held position (shifted)
            ``trades``   – DataFrame trade log
            ``buy_hold`` – benchmark equity of holding the asset
    """
    cost_model = cost_model or IBKR_DEFAULT
    close = prices["Close"].astype(float)
    asset_ret = close.pct_change().fillna(0.0)

    # Look-ahead protection: hold yesterday's decision today.
    position = signal.reindex(close.index).fillna(0.0).shift(1).fillna(0.0)

    gross_ret = position * asset_ret

    # Cost as a fraction of notional per unit of turnover (one side).
    rep_price = representative_price if representative_price else float(close.mean())
    cost_frac = cost_model.cost_fraction_per_side(rep_price, representative_shares)
    turnover = position.diff().abs().fillna(position.abs())
    cost = turnover * cost_frac

    net_ret = gross_ret - cost

    equity = (1.0 + net_ret).cumprod()
    buy_hold = (1.0 + asset_ret).cumprod()

    trades = _extract_trades(close, position, asset_ret, cost_frac)

    return {
        "returns": net_ret,
        "gross_returns": gross_ret,
        "equity": equity,
        "position": position,
        "trades": trades,
        "buy_hold": buy_hold,
    }


def _extract_trades(
    close: pd.Series,
    position: pd.Series,
    asset_ret: pd.Series,
    cost_frac: float,
) -> pd.DataFrame:
    """Build a trade log from a (held) position series.

    A trade spans contiguous bars with the same non-zero position sign. PnL is
    the compounded net return earned while in that position.
    """
    records = []
    in_trade = False
    entry_idx = None
    direction = 0

    pos_values = position.values
    dates = position.index

    for i in range(len(pos_values)):
        p = pos_values[i]
        sign = np.sign(p)
        if not in_trade and sign != 0:
            in_trade = True
            entry_idx = i
            direction = sign
        elif in_trade and sign != direction:
            records.append(
                _close_trade(close, asset_ret, dates, entry_idx, i, direction, cost_frac)
            )
            if sign != 0:  # immediate reversal opens a new trade
                in_trade = True
                entry_idx = i
                direction = sign
            else:
                in_trade = False

    if in_trade:  # still open at the end of the sample
        records.append(
            _close_trade(close, asset_ret, dates, entry_idx, len(pos_values), direction, cost_frac)
        )

    return pd.DataFrame(records)


def _close_trade(close, asset_ret, dates, entry_i, exit_i, direction, cost_frac) -> dict:
    """Compute one trade record for the half-open bar range [entry_i, exit_i)."""
    bar_rets = asset_ret.values[entry_i:exit_i] * direction
    gross = float(np.prod(1.0 + bar_rets) - 1.0)
    net = gross - 2.0 * cost_frac  # entry + exit cost
    holding = exit_i - entry_i
    return {
        "entry_date": dates[entry_i],
        "exit_date": dates[min(exit_i, len(dates) - 1)],
        "direction": int(direction),
        "holding_days": int(holding),
        "gross_return": gross,
        "pnl": net,
    }
