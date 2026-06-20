"""Event-driven (bar-by-bar) backtest engine.

Complements the vectorized :func:`quantlab.backtest.run_backtest`. On a plain
target-weight signal it produces **identical** results (parity-tested), but it
processes bars one at a time, so it can model rules the vectorized engine cannot:
intrabar **stop-loss / take-profit** (using the bar's High/Low/Open, including
open-gap fills). When no path-dependent rule is active it takes a fast path that
reuses the optional C++ kernel (``quant_kernel``) and is bit-for-bit equal to the
vectorized engine.

Same no-look-ahead convention: a signal is decided on ``close[t]`` and the
position is held from ``t+1``. Same result-dict shape as ``run_backtest``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .costs import CostModel, IBKR_DEFAULT

try:  # optional native accelerator (see cpp/quant_kernel)
    import quant_kernel as _kernel
except ImportError:  # pragma: no cover - kernel is optional
    _kernel = None


def run_event_backtest(
    prices: pd.DataFrame,
    signal: pd.Series,
    cost_model: CostModel | None = None,
    representative_price: float | None = None,
    representative_shares: float = 100.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    use_kernel: bool = True,
) -> dict:
    """Event-driven backtest with optional intrabar stop-loss / take-profit.

    Args:
        prices: OHLC(V) DataFrame; needs ``Close`` (and ``Open/High/Low`` if stops used).
        signal: decision-time target weight per bar; the engine holds it ``T+1``.
        cost_model: per-side cost model (default IBKR tiered).
        representative_price/representative_shares: translate the cost model into a
            per-turnover fraction (defaults match ``run_backtest``).
        stop_loss: adverse move from entry that flattens the position (e.g. ``0.05``).
        take_profit: favourable move from entry that flattens the position.
        use_kernel: use the C++ kernel for the no-stops fast path when available.

    Returns:
        Same keys as :func:`run_backtest`: ``returns, gross_returns, equity,
        position, trades, buy_hold``.
    """
    cost_model = cost_model or IBKR_DEFAULT
    close = prices["Close"].astype(float)
    idx = close.index
    asset_ret = close.pct_change().fillna(0.0)
    held = signal.reindex(idx).fillna(0.0).shift(1).fillna(0.0)

    rep_price = representative_price if representative_price else float(close.mean())
    cost_frac = cost_model.cost_fraction_per_side(rep_price, representative_shares)

    if stop_loss is None and take_profit is None:
        gross, eff = _fast_path(held.to_numpy(), asset_ret.to_numpy())
    else:
        gross, eff = _event_loop(
            prices["Open"].to_numpy(float) if "Open" in prices else close.to_numpy(),
            prices["High"].to_numpy(float) if "High" in prices else close.to_numpy(),
            prices["Low"].to_numpy(float) if "Low" in prices else close.to_numpy(),
            close.to_numpy(), held.to_numpy(), stop_loss, take_profit,
        )

    turnover = np.abs(np.diff(eff, prepend=0.0))
    cost = turnover * cost_frac
    net = gross - cost

    if use_kernel and _kernel is not None:
        equity_arr = _kernel.equity_curve(net)
    else:
        equity_arr = np.cumprod(1.0 + net)

    eff_s = pd.Series(eff, index=idx, name="position")
    out = {
        "returns": pd.Series(net, index=idx, name="returns"),
        "gross_returns": pd.Series(gross, index=idx, name="gross_returns"),
        "equity": pd.Series(equity_arr, index=idx, name="equity"),
        "position": eff_s,
        "trades": _extract_event_trades(eff, gross, idx, cost_frac),
        "buy_hold": (1.0 + asset_ret).cumprod().rename("buy_hold"),
    }
    return out


def _fast_path(held: np.ndarray, asset_ret: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """No stops: held position earns the close-to-close return (== vectorized engine)."""
    return held * asset_ret, held.copy()


def _event_loop(open_, high, low, close, held, stop_loss, take_profit):
    """Bar-by-bar loop with intrabar stop-loss / take-profit and post-stop suppression."""
    n = len(close)
    gross = np.zeros(n)
    eff = np.zeros(n)
    in_pos = False
    weight = 0.0
    direction = 0.0
    entry_price = np.nan
    suppressed_dir = 0  # sign stopped out of; blocks re-entry until the target resets

    for t in range(n):
        tgt = held[t]
        if suppressed_dir != 0 and (tgt == 0.0 or np.sign(tgt) != suppressed_dir):
            suppressed_dir = 0
        # signal-driven exit: target went flat or flipped
        if in_pos and (tgt == 0.0 or np.sign(tgt) != direction):
            in_pos = False
            weight = direction = 0.0
            entry_price = np.nan
        # entry (decision was on the prior close -> entry price = close[t-1])
        if (not in_pos) and tgt != 0.0 and suppressed_dir == 0:
            in_pos = True
            weight = tgt
            direction = float(np.sign(tgt))
            entry_price = close[t - 1] if t > 0 else close[t]

        if not in_pos:
            continue

        pc = close[t - 1] if t > 0 else close[t]
        exit_price = _intrabar_exit(open_[t], high[t], low[t], entry_price, direction,
                                    stop_loss, take_profit)
        if exit_price is not None:
            gross[t] = weight * (exit_price / pc - 1.0)
            eff[t] = weight
            in_pos = False
            suppressed_dir = int(direction)
            weight = direction = 0.0
            entry_price = np.nan
        else:
            gross[t] = weight * (close[t] / pc - 1.0)
            eff[t] = weight
    return gross, eff


def _intrabar_exit(o, h, l, entry, direction, stop_loss, take_profit):
    """Return the fill price if a stop/TP triggers this bar, else ``None``.

    Stop-loss is a stop (market) order — a gap through it fills at the worse open.
    Take-profit is a limit order — a gap past it fills at the better open. The
    stop is checked first (worst-case when both could trigger in one bar).
    """
    if direction > 0:
        if stop_loss is not None:
            s = entry * (1.0 - stop_loss)
            if l <= s:
                return min(o, s)
        if take_profit is not None:
            tp = entry * (1.0 + take_profit)
            if h >= tp:
                return o if o >= tp else tp
    else:
        if stop_loss is not None:
            s = entry * (1.0 + stop_loss)
            if h >= s:
                return max(o, s)
        if take_profit is not None:
            tp = entry * (1.0 - take_profit)
            if l <= tp:
                return o if o <= tp else tp
    return None


def _extract_event_trades(eff, gross, dates, cost_frac) -> pd.DataFrame:
    """Trade log from the realized (stop-aware) per-bar returns and held position."""
    records = []
    in_trade = False
    start = 0
    direction = 0

    def close_trade(a, b, d):
        g = float(np.prod(1.0 + gross[a:b]) - 1.0)
        return {
            "entry_date": dates[a],
            "exit_date": dates[min(b, len(dates) - 1)],
            "direction": int(d),
            "holding_days": int(b - a),
            "gross_return": g,
            "pnl": g - 2.0 * cost_frac,
        }

    for t in range(len(eff)):
        s = np.sign(eff[t])
        if not in_trade and s != 0:
            in_trade, start, direction = True, t, s
        elif in_trade and s != direction:
            records.append(close_trade(start, t, direction))
            if s != 0:
                in_trade, start, direction = True, t, s
            else:
                in_trade = False
    if in_trade:
        records.append(close_trade(start, len(eff), direction))
    return pd.DataFrame(records)
