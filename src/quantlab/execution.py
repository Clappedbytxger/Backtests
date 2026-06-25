"""Advanced Execution Simulator & Slippage Radar.

Closes the gap between the *theoretical* backtest equity curve ("the lie", costs
modelled as a flat bps) and the *realised* curve ("the truth", costs that scale
with order size and market conditions). Three parts:

1. **Adaptive slippage model** (:func:`adaptive_cost_components`,
   :func:`run_adaptive_backtest`) — instead of a fixed per-side fee the engine
   charges, per fill:

   * **Dynamic bid-ask spread** — estimated from the price history with the
     Corwin-Schultz (2012) high-low estimator (:func:`corwin_schultz_spread`); no
     bid/ask feed required and look-ahead-safe (uses bars ``t-1, t`` only).
   * **Market impact** via the **square-root law**
     ``impact = Y · σ · √(order_volume / daily_volume)`` (:func:`square_root_impact`)
     — a large order moves the price super-linearly in its size.
   * **Commission** in bps of notional.

2. **Post-trade Slippage Radar** (:func:`implementation_shortfall`,
   :class:`SlippageLedger`) — for live/paper fills, decompose Perold's
   *Implementation Shortfall* into **latency** (price drift between the signal and
   the order), **execution slippage** (fill vs. arrival price) and **fees**.

3. Payload helpers the Execution-Desk dashboard consumes (breakdown, theoretical
   vs. realised curves, liquidity gauge) live in :mod:`apps.api.execution`.

Look-ahead: every series here is causal — spread/vol/ADV use only data up to the
execution bar; the backtest engine itself shifts the position by one bar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import get_settings

# ── dynamic spread (Corwin-Schultz 2012 high-low estimator) ─────────────────────


def corwin_schultz_spread(
    prices: pd.DataFrame, smooth: int = 20, floor_bps: float = 1.0, cap_bps: float = 500.0
) -> pd.Series:
    """Estimate the proportional bid-ask spread from daily High/Low.

    Returns the spread as a *fraction* of price (e.g. ``0.0008`` = 8 bps), one
    value per bar, derived from each pair of consecutive bars ``(t-1, t)`` — known
    at the close of ``t``, so there is no look-ahead. Negative estimates (noise) are
    floored to zero, then a ``floor_bps`` minimum and ``cap_bps`` ceiling keep the
    series sane for liquid and pathological assets alike. ``smooth`` applies a
    trailing rolling mean for stability.

    Reference: Corwin & Schultz (2012), *A Simple Way to Estimate Bid-Ask Spreads
    from Daily High and Low Prices*, Journal of Finance.
    """
    high = prices["High"].astype(float)
    low = prices["Low"].astype(float).replace(0.0, np.nan)
    hl = np.log(high / low) ** 2
    beta = hl + hl.shift(1)  # two consecutive single-day log-range squares

    high2 = pd.concat([high, high.shift(1)], axis=1).max(axis=1)
    low2 = pd.concat([low, low.shift(1)], axis=1).min(axis=1)
    gamma = np.log(high2 / low2) ** 2

    k = 3.0 - 2.0 * np.sqrt(2.0)
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    spread = spread.clip(lower=0.0)
    if smooth and smooth > 1:
        spread = spread.rolling(smooth, min_periods=1).mean()
    spread = spread.fillna(floor_bps / 1e4)
    return spread.clip(lower=floor_bps / 1e4, upper=cap_bps / 1e4)


def rolling_volatility(prices: pd.DataFrame, window: int = 20) -> pd.Series:
    """Trailing daily return volatility (std of close-to-close), causal."""
    r = prices["Close"].astype(float).pct_change()
    return r.rolling(window, min_periods=max(2, window // 2)).std()


def dollar_adv(prices: pd.DataFrame, window: int = 20) -> pd.Series:
    """Trailing average daily *dollar* volume (Volume × Close), causal.

    A generic liquidity proxy. For share-settled instruments (ETFs/stocks) this is
    exact; for some futures/crypto feeds ``Volume`` is in contracts/native units, so
    treat the figure as an order-of-magnitude liquidity gauge there.
    """
    dv = prices["Volume"].astype(float) * prices["Close"].astype(float)
    return dv.rolling(window, min_periods=max(2, window // 2)).mean()


def square_root_impact(
    participation: pd.Series | np.ndarray | float,
    volatility: pd.Series | np.ndarray | float,
    y: float = 0.5,
) -> pd.Series | np.ndarray | float:
    """Square-root market-impact law: ``impact = Y · σ · √participation``.

    ``participation`` is the order size as a fraction of average daily volume
    (``order_volume / daily_volume``); ``volatility`` is the daily return vol; the
    result is the price move (a fraction of price) caused by the order. ``Y`` is the
    dimensionless impact coefficient (≈ 0.3–1.0 empirically; default 0.5).
    """
    return y * volatility * np.sqrt(np.clip(participation, 0.0, None))


# ── adaptive cost model ─────────────────────────────────────────────────────────


@dataclass
class SlippageModel:
    """Adaptive, size-aware execution cost model.

    Attributes:
        impact_y: ``Y`` in the square-root impact law.
        commission_bps: per-side commission in bps of notional.
        spread_smooth: rolling window for the Corwin-Schultz spread.
        spread_floor_bps / spread_cap_bps: bounds on the estimated spread.
        vol_window / adv_window: lookbacks for volatility and dollar ADV.
        min_half_spread_bps: hard floor on the half-spread actually charged.
    """

    impact_y: float = 0.5
    commission_bps: float = 0.5
    spread_smooth: int = 20
    spread_floor_bps: float = 1.0
    spread_cap_bps: float = 500.0
    vol_window: int = 20
    adv_window: int = 20
    min_half_spread_bps: float = 0.5


def adaptive_cost_components(
    prices: pd.DataFrame,
    turnover: pd.Series,
    capital: float,
    model: SlippageModel | None = None,
) -> pd.DataFrame:
    """Per-bar execution-cost components in **return space** (fraction of capital).

    Args:
        prices: OHLCV frame (needs High/Low/Close/Volume).
        turnover: |Δposition| per bar — the fraction of capital traded that bar.
        capital: account size in currency; sets absolute order notional → impact.
        model: the :class:`SlippageModel`; defaults to ``SlippageModel()``.

    Returns a DataFrame aligned to ``prices.index`` with columns:
        ``spread_cost, impact_cost, commission_cost, total_cost`` (each a fraction
        of capital, i.e. directly subtractable from a return series), plus the raw
        diagnostics ``participation`` and ``half_spread``.
    """
    model = model or SlippageModel()
    turnover = turnover.reindex(prices.index).fillna(0.0).clip(lower=0.0)

    spread = corwin_schultz_spread(prices, model.spread_smooth,
                                   model.spread_floor_bps, model.spread_cap_bps)
    half_spread = (spread / 2.0).clip(lower=model.min_half_spread_bps / 1e4)
    vol = rolling_volatility(prices, model.vol_window).fillna(0.0)
    adv = dollar_adv(prices, model.adv_window)

    traded_notional = turnover * float(capital)
    participation = (traded_notional / adv.replace(0.0, np.nan)).fillna(0.0)
    impact = square_root_impact(participation, vol, model.impact_y)

    spread_cost = turnover * half_spread
    impact_cost = turnover * impact
    commission_cost = turnover * (model.commission_bps / 1e4)
    total_cost = spread_cost + impact_cost + commission_cost

    return pd.DataFrame({
        "spread_cost": spread_cost,
        "impact_cost": impact_cost,
        "commission_cost": commission_cost,
        "total_cost": total_cost,
        "participation": participation,
        "half_spread": half_spread,
    }, index=prices.index)


def run_adaptive_backtest(
    prices: pd.DataFrame,
    signal: pd.Series,
    capital: float = 5_000_000.0,
    model: SlippageModel | None = None,
) -> dict:
    """Backtest with the adaptive slippage model — theoretical *and* realised.

    Same look-ahead convention as :func:`quantlab.backtest.run_backtest` (the
    position is the signal shifted one bar). Returns both equity curves and the
    decomposed cost so the Execution Desk can show "the lie vs. the truth".

    Returns dict:
        ``gross_returns`` / ``net_returns`` — before / after adaptive cost
        ``equity_theoretical`` — cumprod of gross (no slippage)
        ``equity_realized``    — cumprod of net (with slippage)
        ``costs``     — the per-bar component DataFrame
        ``breakdown`` — totals: each component's return drag + % of gross profit
        ``participation`` — per-bar order participation rate
    """
    model = model or SlippageModel()
    close = prices["Close"].astype(float)
    asset_ret = close.pct_change().fillna(0.0)

    position = signal.reindex(close.index).fillna(0.0).shift(1).fillna(0.0)
    gross_ret = position * asset_ret
    turnover = position.diff().abs().fillna(position.abs())

    costs = adaptive_cost_components(prices, turnover, capital, model)
    net_ret = gross_ret - costs["total_cost"]

    equity_theo = (1.0 + gross_ret).cumprod()
    equity_real = (1.0 + net_ret).cumprod()

    gross_total = float(equity_theo.iloc[-1] - 1.0) if len(equity_theo) else 0.0
    denom = abs(gross_total) if abs(gross_total) > 1e-9 else 1.0

    def _drag(col: str) -> dict:
        total = float(costs[col].sum())
        return {"return_drag": total, "pct_of_gross": 100.0 * total / denom}

    breakdown = {
        "gross_total_return": gross_total,
        "net_total_return": float(equity_real.iloc[-1] - 1.0) if len(equity_real) else 0.0,
        "spread": _drag("spread_cost"),
        "impact": _drag("impact_cost"),
        "commission": _drag("commission_cost"),
        "total_cost_return": float(costs["total_cost"].sum()),
        "n_trades": int((turnover > 1e-9).sum()),
        "avg_participation": float(costs.loc[turnover > 1e-9, "participation"].mean())
        if (turnover > 1e-9).any() else 0.0,
        "max_participation": float(costs["participation"].max()),
    }

    return {
        "gross_returns": gross_ret,
        "net_returns": net_ret,
        "equity_theoretical": equity_theo,
        "equity_realized": equity_real,
        "position": position,
        "turnover": turnover,
        "participation": costs["participation"],
        "costs": costs,
        "breakdown": breakdown,
    }


# ── liquidity gauge ─────────────────────────────────────────────────────────────

# Participation-rate zones (order size as a fraction of average daily volume).
LIQUIDITY_ZONES = [
    (0.01, "safe", "≤1% des ADV — vernachlässigbarer Impact"),
    (0.05, "caution", "1–5% des ADV — spürbarer Impact"),
    (0.10, "warning", "5–10% des ADV — hoher Slippage"),
    (float("inf"), "danger", ">10% des ADV — extremer Impact, Order splitten"),
]


def liquidity_gauge(order_notional: float, dollar_adv_value: float) -> dict:
    """Classify a planned order's participation rate into a liquidity warning zone."""
    if dollar_adv_value <= 0:
        return {"participation": None, "zone": "unknown", "label": "keine Liquiditätsdaten",
                "order_notional": order_notional, "dollar_adv": dollar_adv_value}
    part = order_notional / dollar_adv_value
    zone, label = "danger", LIQUIDITY_ZONES[-1][2]
    for thresh, z, lab in LIQUIDITY_ZONES:
        if part <= thresh:
            zone, label = z, lab
            break
    return {"participation": part, "zone": zone, "label": label,
            "order_notional": order_notional, "dollar_adv": dollar_adv_value}


# ── post-trade slippage radar (Implementation Shortfall) ───────────────────────


def implementation_shortfall(
    side: int,
    signal_price: float,
    arrival_price: float,
    fill_price: float,
    commission: float,
    notional: float,
    signal_time: pd.Timestamp | str | None = None,
    fill_time: pd.Timestamp | str | None = None,
) -> dict:
    """Decompose Perold's Implementation Shortfall for one fill (in bps).

    ``side`` is +1 (buy) or −1 (sell). All prices in the same currency. The IS is
    measured against the **decision (signal) price** and split into:

    * **latency** — drift between the signal and the order's arrival price
      ``side·(arrival − signal)/signal`` (cost of acting slowly).
    * **execution slippage** — fill vs. arrival ``side·(fill − arrival)/arrival``
      (spread + market impact while executing).
    * **fees** — commission / notional.

    Positive bps = cost (worse than the decision price). Returns the three
    components, the total, and the signal→fill latency in seconds when timestamps
    are given.
    """
    side = 1 if side >= 0 else -1
    latency_bps = side * (arrival_price - signal_price) / signal_price * 1e4
    exec_bps = side * (fill_price - arrival_price) / arrival_price * 1e4
    fee_bps = (commission / notional * 1e4) if notional else 0.0
    total_bps = latency_bps + exec_bps + fee_bps

    latency_s = None
    if signal_time is not None and fill_time is not None:
        latency_s = (pd.Timestamp(fill_time) - pd.Timestamp(signal_time)).total_seconds()

    return {
        "latency_bps": float(latency_bps),
        "execution_bps": float(exec_bps),
        "fee_bps": float(fee_bps),
        "total_bps": float(total_bps),
        "latency_seconds": latency_s,
    }


_LEDGER_COLUMNS = [
    "ts", "strategy", "ticker", "side", "qty", "notional",
    "signal_time", "signal_price", "arrival_price", "fill_time", "fill_price", "commission",
    "latency_bps", "execution_bps", "fee_bps", "total_bps", "latency_seconds",
]


class SlippageLedger:
    """Append-only CSV ledger of live/paper fills with their IS decomposition."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else get_settings().data_dir / "execution_log.csv"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_fill(
        self, strategy: str, ticker: str, side: int, qty: float,
        signal_price: float, arrival_price: float, fill_price: float,
        commission: float = 0.0,
        signal_time: pd.Timestamp | str | None = None,
        fill_time: pd.Timestamp | str | None = None,
    ) -> dict:
        """Compute the IS for a fill and append it to the ledger; returns the row."""
        notional = abs(qty) * fill_price
        isf = implementation_shortfall(side, signal_price, arrival_price, fill_price,
                                       commission, notional, signal_time, fill_time)
        row = {
            "ts": pd.Timestamp.now("UTC").isoformat(),
            "strategy": strategy, "ticker": ticker, "side": int(np.sign(side) or 1),
            "qty": qty, "notional": notional,
            "signal_time": str(signal_time) if signal_time is not None else "",
            "signal_price": signal_price, "arrival_price": arrival_price,
            "fill_time": str(fill_time) if fill_time is not None else "",
            "fill_price": fill_price, "commission": commission, **isf,
        }
        header = not self.path.exists()
        pd.DataFrame([row], columns=_LEDGER_COLUMNS).to_csv(
            self.path, mode="a", header=header, index=False)
        return row

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(columns=_LEDGER_COLUMNS)
        return pd.read_csv(self.path)

    def aggregate(self) -> dict:
        """Aggregate the ledger by strategy → mean IS components + counts."""
        df = self.load()
        if df.empty:
            return {"n": 0, "by_strategy": [], "overall": {}}
        grp = df.groupby("strategy").agg(
            n=("total_bps", "size"),
            latency_bps=("latency_bps", "mean"),
            execution_bps=("execution_bps", "mean"),
            fee_bps=("fee_bps", "mean"),
            total_bps=("total_bps", "mean"),
            latency_seconds=("latency_seconds", "mean"),
        ).reset_index()
        by_strategy = grp.to_dict("records")
        overall = {
            "n": int(len(df)),
            "latency_bps": float(df["latency_bps"].mean()),
            "execution_bps": float(df["execution_bps"].mean()),
            "fee_bps": float(df["fee_bps"].mean()),
            "total_bps": float(df["total_bps"].mean()),
            "latency_seconds": float(df["latency_seconds"].dropna().mean())
            if df["latency_seconds"].notna().any() else None,
        }
        return {"n": int(len(df)), "by_strategy": by_strategy, "overall": overall}
