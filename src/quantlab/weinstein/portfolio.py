"""Shared-equity, multi-position event-loop backtester for the Weinstein strategy.

Unlike :func:`quantlab.backtest.run_backtest` (single asset, vectorized) this is a
true portfolio simulator: one cash account, **many concurrent long positions**
across a stock universe, risk-based position sizing, and several exit regimes plus
optional pyramiding. It produces a daily equity curve, a per-lot trade log and the
standard metrics so the strategy is judged like every other in the lab.

No look-ahead: a Stage-2 *signal* on bar ``t`` (see :mod:`signals`) is turned into
an **order filled at the open of bar ``t+1``** (:func:`build_orders`). Open lots are
only managed from the bar **after** entry. Intrabar stops fill at the stop price,
or worse at the open on a gap (you cannot do better than the gap).

Exit regimes (``PortfolioConfig.exit_mode``):
  * ``"ma"``        – Weinstein's canonical sell: close back below the 30-day MA
    (exit next open); protective stop below the base meanwhile.
  * ``"trail1r"``   – step a stop up in 1R increments (+1R -> break-even, ...).
  * ``"chandelier"``– stop = highest-high-since-entry - ``chandelier_atr`` * ATR.
  * ``"partial"``   – take ``partial_frac`` off at ``+partial_at_r`` R, move stop
    to break-even, trail the remainder in 1R steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..costs import CostModel, IBKR_DEFAULT
from ..metrics import compute_metrics, trade_stats


@dataclass
class PortfolioConfig:
    """Portfolio / money-management / exit configuration."""

    risk_pct: float = 0.0075          # risk per new lot as a fraction of equity
    max_positions: int = 12           # cap on concurrent distinct tickers held
    max_weight: float = 0.20          # cap on one lot's notional / equity
    start_equity: float = 100_000.0
    allow_leverage: bool = False      # if False, total long notional <= equity

    exit_mode: str = "ma"             # "ma" | "trail1r" | "chandelier" | "partial"
    chandelier_atr: float = 3.0
    partial_at_r: float = 1.0
    partial_frac: float = 0.5

    pyramid: bool = False
    max_adds: int = 0                 # extra lots allowed on an already-held ticker
    cost_model: CostModel = field(default_factory=lambda: IBKR_DEFAULT)


def build_orders(data: dict[str, pd.DataFrame]) -> dict[str, list[tuple]]:
    """Turn per-ticker signal frames into next-open entry orders.

    ``data[ticker]`` must carry the columns from
    :func:`signals.detect_stage2_entries` (``signal`` + ``stop``) plus OHLC. An
    order = ``(fill_date, stop_price)``; the stop is read from the **signal bar**
    and the fill happens on the **next** bar's open.
    """
    orders: dict[str, list[tuple]] = {}
    for tk, df in data.items():
        sig = df["signal"].to_numpy()
        stop = df["stop"].to_numpy()
        idx = df.index
        rows = []
        sig_pos = np.flatnonzero(sig)
        for i in sig_pos:
            if i + 1 >= len(idx):
                continue                      # no next bar to fill on
            sp = stop[i]
            if not np.isfinite(sp):
                continue
            rows.append((idx[i + 1], float(sp)))
        orders[tk] = rows
    return orders


def build_random_orders(
    data: dict[str, pd.DataFrame], counts: dict[str, int], rng: np.random.Generator,
    warmup: int = 60,
) -> dict[str, list[tuple]]:
    """Random-timing null: same number of entries per ticker, random bars.

    Picks ``counts[tk]`` random eligible bars per ticker (after ``warmup``, and
    leaving a next bar to fill on), using each chosen bar's own ``stop`` column so
    sizing stays comparable. Destroys Stage-2 timing skill while preserving the
    universe, the trade count and the exit logic — the test of whether the entry
    *rule* beats random entry into the same (survivorship-biased) survivors.
    """
    orders: dict[str, list[tuple]] = {}
    for tk, df in data.items():
        n = counts.get(tk, 0)
        idx = df.index
        stop = df["stop"].to_numpy()
        hi = len(idx) - 1
        eligible = [j for j in range(warmup, hi) if np.isfinite(stop[j])]
        if n <= 0 or not eligible:
            orders[tk] = []
            continue
        chosen = rng.choice(eligible, size=min(n, len(eligible)), replace=False)
        orders[tk] = [(idx[j + 1], float(stop[j])) for j in sorted(chosen)]
    return orders


def _ratchet_1r(lot: dict, high: float) -> None:
    """Step the stop to +(n-1)R once the bar's high reaches +nR (n>=1)."""
    reached = (high - lot["entry"]) / lot["r"]
    n = int(reached)
    if n >= 1 and n > lot["locked"]:
        lot["locked"] = n
        lot["stop"] = max(lot["stop"], lot["entry"] + (n - 1) * lot["r"])


def _manage(lot: dict, bar: tuple, cfg: PortfolioConfig):
    """Manage one open long lot on one bar. Returns one of:

    ``("exit", price, reason)`` | ``("partial", price)`` | ``("hold", None)``.
    Mutates the lot's stop / peak / locked / flags in place.
    """
    o, h, low, c, ma, atr = bar

    # 0) pending MA-exit from a prior close-below-MA -> fill at today's open.
    if lot.get("ma_exit_pending"):
        return ("exit", o, "ma_exit")

    # 1) protective / trailing stop FIRST (resting order; gap fills at open).
    if low <= lot["stop"]:
        price = min(o, lot["stop"])
        reason = "trail" if lot["stop"] > lot["entry"] else "stop"
        return ("exit", price, reason)

    # 2) mode-specific ratchet / targets (govern FUTURE bars).
    mode = cfg.exit_mode
    if mode == "ma":
        if np.isfinite(ma) and c < ma:
            lot["ma_exit_pending"] = True
    elif mode == "trail1r":
        _ratchet_1r(lot, h)
    elif mode == "chandelier":
        lot["peak"] = max(lot["peak"], h)
        if np.isfinite(atr):
            lot["stop"] = max(lot["stop"], lot["peak"] - cfg.chandelier_atr * atr)
    elif mode == "partial":
        if not lot["partial_done"]:
            target = lot["entry"] + cfg.partial_at_r * lot["r"]
            if h >= target:
                return ("partial", target)
        else:
            _ratchet_1r(lot, h)   # trail the remainder after the partial
    return ("hold", None)


def prepare_data(data: dict[str, pd.DataFrame]) -> tuple[dict, pd.DatetimeIndex]:
    """Pre-build per-ticker numpy arrays + a date->position map and the union
    calendar. Expensive enough that callers running many permutations should do
    it once and pass the result to :func:`run_portfolio` via ``prepared=``.
    """
    arr: dict[str, dict] = {}
    all_dates: set = set()
    for tk, df in data.items():
        idx = pd.DatetimeIndex(df.index)
        arr[tk] = {
            "pos": {d: i for i, d in enumerate(idx)},
            "o": df["Open"].to_numpy(float),
            "h": df["High"].to_numpy(float),
            "l": df["Low"].to_numpy(float),
            "c": df["Close"].to_numpy(float),
            "ma": df["ma"].to_numpy(float),
            "atr": df["atr"].to_numpy(float),
        }
        all_dates.update(idx)
    return arr, pd.DatetimeIndex(sorted(all_dates))


def run_portfolio(
    data: dict[str, pd.DataFrame],
    orders: dict[str, list[tuple]],
    cfg: PortfolioConfig | None = None,
    prepared: tuple[dict, pd.DatetimeIndex] | None = None,
    periods_per_year: int = 252,
) -> dict:
    """Run the multi-position portfolio backtest.

    Args:
        data: ``ticker -> DataFrame`` with at least ``Open/High/Low/Close`` and
            ``ma``/``atr`` columns (from :func:`signals.detect_stage2_entries`).
        orders: ``ticker -> [(fill_date, stop_price), ...]`` from
            :func:`build_orders` (or :func:`build_random_orders` for the null).
        cfg: portfolio configuration.
        prepared: optional ``(arr, calendar)`` from :func:`prepare_data` to skip
            re-building arrays across repeated runs (permutation null).
        periods_per_year: bars per year for metric annualization (252 daily,
            52 weekly). Only affects the returned ``metrics``.

    Returns dict with ``equity`` (Series), ``returns`` (daily), ``trades``
    (DataFrame), ``metrics`` and ``trade_stats`` and ``n_trades``.
    """
    cfg = cfg or PortfolioConfig()
    cm = cfg.cost_model

    arr, calendar = prepared if prepared is not None else prepare_data(data)

    orders_by_date: dict = {}
    for tk, rows in orders.items():
        for fill_date, stop_price in rows:
            orders_by_date.setdefault(fill_date, []).append((tk, stop_price))

    cash = cfg.start_equity
    equity = cfg.start_equity
    open_lots: list[dict] = []
    trades: list[dict] = []
    equity_curve = np.empty(len(calendar))

    for di, d in enumerate(calendar):
        # ---- 1) manage / exit open lots ----
        survivors: list[dict] = []
        for lot in open_lots:
            a = arr[lot["ticker"]]
            pos = a["pos"].get(d)
            if pos is None:                       # ticker did not trade today
                survivors.append(lot)
                continue
            bar = (a["o"][pos], a["h"][pos], a["l"][pos], a["c"][pos],
                   a["ma"][pos], a["atr"][pos])
            action = _manage(lot, bar, cfg)
            if action[0] == "exit":
                cash += _realize(lot, lot["shares"], action[1], action[2],
                                 d, cm, trades, final=True)
            elif action[0] == "partial":
                ps = int(lot["shares"] * cfg.partial_frac)
                if ps >= 1:
                    cash += _realize(lot, ps, action[1], "partial", d, cm, trades,
                                     final=False)
                    lot["shares"] -= ps
                    lot["partial_done"] = True
                    lot["stop"] = max(lot["stop"], lot["entry"])  # break-even
                    lot["locked"] = max(lot["locked"], 1)
                lot["last_close"] = a["c"][pos]
                survivors.append(lot)
            else:
                lot["last_close"] = a["c"][pos]
                survivors.append(lot)
        open_lots = survivors

        # ---- 2) entries filled at today's open ----
        for tk, stop_price in orders_by_date.get(d, []):
            a = arr.get(tk)
            if a is None:
                continue
            pos = a["pos"].get(d)
            if pos is None:
                continue
            entry = a["o"][pos]
            if not np.isfinite(entry) or entry <= stop_price:
                continue                          # invalid stop (>= entry)
            held = [l for l in open_lots if l["ticker"] == tk]
            distinct = len({l["ticker"] for l in open_lots})
            if held:
                if not cfg.pyramid or len(held) >= 1 + cfg.max_adds:
                    continue
            elif distinct >= cfg.max_positions:
                continue

            r = entry - stop_price
            shares = int((cfg.risk_pct * equity) / r)
            shares = min(shares, int((cfg.max_weight * equity) / entry))
            if not cfg.allow_leverage:
                invested = sum(l["shares"] * l["last_close"] for l in open_lots)
                free = max(equity - invested, 0.0)
                shares = min(shares, int(free / entry), int(cash / entry))
            if shares < 1:
                continue
            entry_cost = cm.cost_per_side(shares, entry)
            cash -= shares * entry + entry_cost
            open_lots.append({
                "ticker": tk, "entry_date": d, "entry": entry, "shares": shares,
                "orig_shares": shares, "stop": stop_price, "r": r,
                "peak": a["h"][pos], "locked": 0, "partial_done": False,
                "ma_exit_pending": False, "entry_cost": entry_cost,
                "last_close": a["c"][pos],
            })

        # ---- 3) mark to market ----
        equity = cash + sum(l["shares"] * l["last_close"] for l in open_lots)
        equity_curve[di] = equity

    # End-of-sample liquidation: close any still-open lots at their last close so
    # the trade log and trade-stats are complete. The final equity point already
    # marked these at last_close; deduct only the (small) exit cost to realize.
    if open_lots:
        last_d = calendar[-1]
        extra_cost = 0.0
        for lot in open_lots:
            price = lot["last_close"]
            extra_cost += cm.cost_per_side(lot["shares"], price)
            _realize(lot, lot["shares"], price, "eos", last_d, cm, trades, final=True)
        equity_curve[-1] -= extra_cost

    eq = pd.Series(equity_curve, index=calendar)
    ret = eq.pct_change().fillna(0.0)
    trades_df = pd.DataFrame(trades)
    return {
        "equity": eq,
        "returns": ret,
        "trades": trades_df,
        "metrics": compute_metrics(ret, periods_per_year=periods_per_year),
        "trade_stats": trade_stats(trades_df) if not trades_df.empty else trade_stats(pd.DataFrame()),
        "n_trades": int(len(trades_df)),
        "final_equity": float(equity),
    }


def _realize(lot: dict, shares: int, price: float, reason: str, date,
             cm: CostModel, trades: list, final: bool) -> float:
    """Book a (full or partial) sale: record the trade, return cash proceeds.

    Entry cost is allocated proportionally to the shares sold so partial and final
    legs together account for the whole round-trip commission/slippage.
    """
    exit_cost = cm.cost_per_side(shares, price)
    frac = shares / lot["orig_shares"]
    entry_cost_alloc = lot["entry_cost"] * frac
    pnl = (price - lot["entry"]) * shares - entry_cost_alloc - exit_cost
    holding = int(np.busday_count(np.datetime64(lot["entry_date"], "D"),
                                  np.datetime64(date, "D")))
    trades.append({
        "ticker": lot["ticker"],
        "entry_date": lot["entry_date"],
        "exit_date": date,
        "shares": int(shares),
        "entry": float(lot["entry"]),
        "exit": float(price),
        "reason": reason,
        "r_mult": float((price - lot["entry"]) / lot["r"]),
        "pnl": float(pnl),
        "pnl_pct": float((price - lot["entry"]) / lot["entry"]),
        "holding_days": holding,
        "final": bool(final),
    })
    return shares * price - exit_cost
