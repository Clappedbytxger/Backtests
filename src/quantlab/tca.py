"""Transaction-Cost Analysis (TCA): size-dependent market impact + slippage.

The flat per-side :class:`quantlab.costs.CostModel` answers "does the edge clear a
fixed cost wall?". TCA answers the next question: "what does it cost to trade *this
size* in *this liquidity*?" — the cost that grows with participation (order size /
ADV) and matters once a strategy is scaled.

Impact follows the empirical **square-root law** (Almgren et al.):

    impact(fraction of price) = coefficient * daily_vol * sqrt(order / ADV)

plus a fixed half-spread and commission. All helpers are vectorized, and
:func:`tca_from_backtest` bridges the weight-space engine to dollar costs given an
account size and the instrument's volume.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ImpactModel:
    """Square-root market-impact + fixed-cost model (all bps are per side).

    Attributes:
        impact_coef: square-root-law coefficient (η), ~0.3-1.0 empirically.
        half_spread_bps: half the bid-ask spread, always paid per side.
        commission_bps: broker commission per side.
    """

    impact_coef: float = 0.5
    half_spread_bps: float = 1.0
    commission_bps: float = 0.2

    def impact_bps(self, participation, daily_vol):
        """Market-impact component in bps for a given participation + daily vol."""
        part = np.clip(np.asarray(participation, dtype=float), 0.0, None)
        dv = np.asarray(daily_vol, dtype=float)
        return self.impact_coef * dv * np.sqrt(part) * 1e4

    def cost_bps(self, participation, daily_vol):
        """Total per-side cost in bps = half-spread + commission + impact."""
        return self.half_spread_bps + self.commission_bps + self.impact_bps(participation, daily_vol)

    def cost_fraction(self, participation, daily_vol):
        """Total per-side cost as a fraction of notional."""
        return self.cost_bps(participation, daily_vol) / 1e4


# Presets: a liquid large-cap / index-future regime vs an illiquid name.
TCA_LIQUID = ImpactModel(impact_coef=0.3, half_spread_bps=0.5, commission_bps=0.2)
TCA_DEFAULT = ImpactModel()
TCA_ILLIQUID = ImpactModel(impact_coef=1.0, half_spread_bps=5.0, commission_bps=0.5)


def analyze_orders(order_notional, adv_notional, daily_vol, model: ImpactModel | None = None) -> pd.DataFrame:
    """Per-order TCA breakdown.

    Args:
        order_notional: traded value per order (currency).
        adv_notional: average daily *dollar* volume of the instrument.
        daily_vol: daily return volatility (fraction).
        model: impact model (default :data:`TCA_DEFAULT`).

    Returns:
        DataFrame with participation, the bps breakdown and ``cost_usd`` per order.
    """
    model = model or TCA_DEFAULT
    on = np.abs(np.asarray(order_notional, dtype=float))
    adv = np.asarray(adv_notional, dtype=float)
    participation = np.where(adv > 0, on / adv, 0.0)
    impact = model.impact_bps(participation, daily_vol)
    spread = np.full_like(on, model.half_spread_bps)
    commission = np.full_like(on, model.commission_bps)
    total_bps = spread + commission + impact
    return pd.DataFrame({
        "order_notional": on,
        "participation": participation,
        "spread_bps": spread,
        "commission_bps": commission,
        "impact_bps": impact,
        "total_bps": total_bps,
        "cost_usd": on * total_bps / 1e4,
    })


def tca_from_backtest(
    result: dict,
    prices: pd.DataFrame,
    account_value: float,
    model: ImpactModel | None = None,
    adv_window: int = 20,
) -> dict:
    """Estimate realistic, size-dependent costs for a backtest result.

    Translates the weight-space turnover into dollar orders (``turnover *
    account_value``), derives ADV from ``Volume * Close`` and daily vol from
    returns, and aggregates the square-root-impact TCA.

    Returns a summary dict (n_orders, turnover_usd, total_cost_usd, avg_cost_bps,
    cost_drag_pct_of_equity, bps breakdown) plus the per-order DataFrame.
    """
    model = model or TCA_DEFAULT
    pos = result["position"]
    close = prices["Close"].reindex(pos.index).astype(float)
    turnover = pos.diff().abs().fillna(pos.abs())
    order_notional = turnover * float(account_value)

    if "Volume" in prices:
        adv = (prices["Volume"].reindex(pos.index).astype(float) * close).rolling(
            adv_window, min_periods=5).mean()
    else:
        adv = pd.Series(np.nan, index=pos.index)
    daily_vol = close.pct_change().rolling(adv_window, min_periods=5).std()

    mask = turnover > 0
    if not mask.any():
        return {"n_orders": 0, "turnover_usd": 0.0, "total_cost_usd": 0.0,
                "avg_cost_bps": 0.0, "cost_drag_pct_of_equity": 0.0,
                "breakdown_bps": {"spread": 0.0, "commission": 0.0, "impact": 0.0},
                "orders": pd.DataFrame()}

    adv_f = adv.fillna(adv.median())
    vol_f = daily_vol.fillna(daily_vol.median()).fillna(0.0)
    df = analyze_orders(order_notional[mask], adv_f[mask], vol_f[mask], model)

    total_notional = float(df["order_notional"].sum())
    total_cost = float(df["cost_usd"].sum())
    w = df["order_notional"].to_numpy()
    wsum = w.sum()
    return {
        "n_orders": int(mask.sum()),
        "turnover_usd": total_notional,
        "total_cost_usd": total_cost,
        "avg_cost_bps": (total_cost / total_notional * 1e4) if total_notional > 0 else 0.0,
        "cost_drag_pct_of_equity": total_cost / float(account_value) * 100.0,
        "breakdown_bps": {
            "spread": float(np.average(df["spread_bps"], weights=w)) if wsum else 0.0,
            "commission": float(np.average(df["commission_bps"], weights=w)) if wsum else 0.0,
            "impact": float(np.average(df["impact_bps"], weights=w)) if wsum else 0.0,
        },
        "orders": df,
    }
