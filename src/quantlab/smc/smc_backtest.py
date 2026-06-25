"""SMC sweep+BOS event-loop backtester (spec Teil 4 step 5, Teil 6 costs).

One asset, one open position at a time. Each bar, in order:

1. manage an open position with its exit engine (:mod:`exits`);
2. update the causal structure/sweep/BOS detector (:mod:`signals`);
3. if flat (and not just exited on this bar), open a new position at the BOS
   close when the per-asset direction filter allows it.

Sizing is risk-based: ``size = risk_frac * equity / |entry - stop|`` so every
trade risks the same fraction of equity at its initial stop. Because per-trade
PnL then equals ``risk_frac * realized_R``, both the gross and the cost-adjusted
(net) equity curves are produced from the *same* trade sequence — they differ
only in the realized R-multiple, never in which trades are taken. That is what
lets the report show "before costs / after costs" as a clean apples-to-apples
pair (spec requirement).

Cost model (Teil 6): per side = commission + spread (bps of notional) + slippage
priced off the entry/exit bar range (``slip = slip_coef * range`` with a bps
floor), since the entry sits right after a volatility spike.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..metrics import compute_metrics, trade_stats
from .exits import Fixed1R, TrailingStop
from .signals import SetupDetector
from .structure import atr as atr_series
from .structure import swing_points


@dataclass
class SmcCosts:
    """Per-side transaction-cost model for one asset (spec Teil 6).

    ``commission_bps`` + ``spread_bps`` are charged on the notional of each side.
    ``slip_coef`` prices slippage off the entry/exit bar range (price units);
    ``slip_min_bps`` is a floor in bps of price. Set everything to 0 for the
    gross ("vor Kosten") reference — though the engine already reports gross
    separately, so this preset is the realistic ("nach Kosten") one.
    """

    commission_bps: float = 0.0
    spread_bps: float = 0.0
    slip_coef: float = 0.0
    slip_min_bps: float = 0.0

    def scaled(self, factor: float) -> "SmcCosts":
        """Return a copy with every component multiplied by ``factor`` (Teil 8
        cost-sensitivity: run at {0, 1x, 2x})."""
        return SmcCosts(self.commission_bps * factor, self.spread_bps * factor,
                        self.slip_coef * factor, self.slip_min_bps * factor)


def run_smc_backtest(
    df: pd.DataFrame,
    *,
    direction: str = "both",          # "long", "short", "both"
    exit_type: str = "trailing",      # "trailing" or "fixed1r"
    risk_frac: float = 0.01,
    n: int = 2,
    forward: int | None = None,
    k: int = 3,
    buffer_mult: float = 0.1,
    atr_period: int = 14,
    require_structure: bool = True,
    trail_lock_on_close: bool = False,
    max_concurrent: int = 1,
    costs: SmcCosts | None = None,
    periods_per_year: int | None = None,
) -> dict:
    """Run the SMC engine on one asset's OHLCV frame.

    Returns a dict with ``trades`` (DataFrame), the gross/net daily return series,
    ``metrics_gross`` / ``metrics_net`` (via :func:`compute_metrics`) and
    ``trade_stats_net``. The frame must be pre-filtered to the desired session
    and test period; bars are processed in index order as one sequence.
    """
    costs = costs or SmcCosts()
    allow_long = direction in ("long", "both")
    allow_short = direction in ("short", "both")

    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    low = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    atr = atr_series(df, atr_period).to_numpy(float)
    # n = candles BACK, forward = candles FORWARD (confirmation lag). The
    # reference strategy uses an asymmetric pivot (e.g. 8 back, 4 forward).
    lag = forward if forward is not None else n
    is_sh, is_sl = swing_points(df["High"], df["Low"], n, forward)
    idx = df.index
    m = len(df)

    detector = SetupDetector(n, k, buffer_mult, require_structure=require_structure)
    # Up to ``max_concurrent`` independent positions (each risks ``risk_frac``).
    # max_concurrent=1 = one-at-a-time (blocks new setups while in a trade, the
    # conservative default). >1 lets the strategy pyramid into a trend — more
    # trades, more exposure, more drawdown, the reference's actual profile.
    open_pos: list[tuple[dict, object]] = []
    trades: list[dict] = []

    for i in range(m):
        # 1) manage open positions (entered on prior bars)
        still_open: list[tuple[dict, object]] = []
        exited_this_bar = False
        for pos, mgr in open_pos:
            fill = mgr.update(h[i], low[i], o[i], c[i])
            if fill is not None:
                trades.append(_close(pos, i, idx, fill.price, fill.reason,
                                     h[i] - low[i], costs, risk_frac))
                exited_this_bar = True
            else:
                still_open.append((pos, mgr))
        open_pos = still_open

        # 2) causal structure + setup detection (runs every bar). A pivot at bar
        #    i-lag becomes confirmed now (it needed `forward` bars to its right).
        new_sh = h[i - lag] if i - lag >= 0 and is_sh[i - lag] else None
        new_sl = low[i - lag] if i - lag >= 0 and is_sl[i - lag] else None
        setup = detector.update(i, o[i], h[i], low[i], c[i], atr[i], new_sh, new_sl)

        # 3) entry on the BOS close (Variant A). For max=1 keep the old rule of not
        #    re-entering on the same bar a position closed (byte-identical legacy).
        blocked = exited_this_bar and max_concurrent == 1
        if setup is not None and len(open_pos) < max_concurrent and not blocked:
            ok = (setup.direction == 1 and allow_long) or (setup.direction == -1 and allow_short)
            if ok:
                pos = {
                    "entry_index": i,
                    "entry_time": idx[i],
                    "direction": setup.direction,
                    "entry": setup.entry,
                    "stop": setup.stop,
                    "r_price": setup.r,
                    "entry_range": h[i] - low[i],
                    "sweep_extreme": setup.sweep_extreme,
                }
                if exit_type == "fixed1r":
                    mgr = Fixed1R(setup.direction, setup.entry, setup.r)
                else:
                    mgr = TrailingStop(setup.direction, setup.entry, setup.r,
                                       lock_on_close=trail_lock_on_close)
                open_pos.append((pos, mgr))

    trades_df = pd.DataFrame(trades)

    if periods_per_year is None:
        periods_per_year = _infer_ppy(idx)

    gross = _daily_returns(trades_df, "pnl_frac_gross", idx, periods_per_year)
    net = _daily_returns(trades_df, "pnl_frac_net", idx, periods_per_year)

    return {
        "trades": trades_df,
        "returns_gross": gross,
        "returns_net": net,
        "metrics_gross": compute_metrics(gross, periods_per_year=periods_per_year),
        "metrics_net": compute_metrics(net, periods_per_year=periods_per_year),
        "trade_stats_net": trade_stats(
            trades_df.rename(columns={"pnl_frac_net": "pnl"})
            if not trades_df.empty else trades_df
        ),
        "periods_per_year": periods_per_year,
    }


def _close(pos: dict, exit_i: int, idx, exit_gross: float, reason: str,
           exit_range: float, costs: SmcCosts, risk_frac: float) -> dict:
    """Realize one trade into gross and net R-multiples and equity fractions."""
    d = pos["direction"]
    entry = pos["entry"]
    rp = pos["r_price"]

    # Slippage priced off each bar's range, with a bps-of-price floor.
    slip_e = max(costs.slip_coef * pos["entry_range"], costs.slip_min_bps / 1e4 * entry)
    slip_x = max(costs.slip_coef * exit_range, costs.slip_min_bps / 1e4 * exit_gross)
    entry_fill = entry + d * slip_e            # long buys higher, short sells lower
    exit_fill = exit_gross - d * slip_x        # long sells lower, short buys higher

    # Commission + spread on the notional of each side, expressed in R units.
    cf = (costs.commission_bps + costs.spread_bps) / 1e4
    comm_in_r = cf * (entry + exit_gross) / rp

    r_gross = d * (exit_gross - entry) / rp
    r_net = d * (exit_fill - entry_fill) / rp - comm_in_r

    return {
        "entry_time": pos["entry_time"],
        "exit_time": idx[exit_i],
        "direction": d,
        "entry": entry,
        "stop": pos["stop"],
        "exit": exit_gross,
        "reason": reason,
        "r_price": rp,
        "holding_days": _bars_between(pos["entry_index"], exit_i),
        "r_mult_gross": r_gross,
        "r_mult_net": r_net,
        "pnl_frac_gross": risk_frac * r_gross,
        "pnl_frac_net": risk_frac * r_net,
    }


def _bars_between(a: int, b: int) -> int:
    return int(b - a)


def _daily_returns(trades: pd.DataFrame, col: str, idx: pd.DatetimeIndex,
                   periods_per_year: int) -> pd.Series:
    """Aggregate per-trade PnL fractions onto the asset's trading-day calendar.

    Each trade's realized fraction is booked on its exit date (we are flat and
    realize PnL only at exit); same-day trades compound. The series is reindexed
    over the unique session dates spanned by the trades so Sharpe/CAGR annualize
    on real trading time.
    """
    dates = pd.DatetimeIndex(idx).tz_localize(None).normalize().unique().sort_values()
    daily = pd.Series(0.0, index=dates)
    if trades.empty:
        return daily
    ex = pd.DatetimeIndex(trades["exit_time"]).tz_localize(None).normalize()
    grp = trades.assign(_d=ex).groupby("_d")[col].apply(lambda x: np.prod(1.0 + x) - 1.0)
    span = daily.index[(daily.index >= ex.min()) & (daily.index <= ex.max())]
    daily = daily.loc[span]
    daily.loc[grp.index] = grp.values
    return daily


def _infer_ppy(idx: pd.DatetimeIndex) -> int:
    """Trading periods per year implied by the session-date calendar."""
    dates = pd.DatetimeIndex(idx).tz_localize(None).normalize().unique()
    if len(dates) < 2:
        return 252
    years = (dates.max() - dates.min()).days / 365.25
    return int(round(len(dates) / years)) if years > 0 else 252
