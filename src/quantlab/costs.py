"""Transaction-cost model for Interactive Brokers (US stocks/ETFs).

Models commission, slippage and regulatory/exchange fees so backtests report
*net* performance. Defaults follow IBKR's tiered pricing; everything is
parametrizable for other asset classes (futures, FX) later.

Costs are expressed per *trade side* (one buy or one sell). A round-trip
(enter + exit) therefore incurs the cost twice.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostModel:
    """Per-side transaction cost model.

    Attributes:
        commission_per_share: IBKR tiered ~ $0.0035/share.
        min_commission: minimum charge per order ($0.35 tiered).
        max_commission_pct: commission capped at this fraction of trade value (1%).
        slippage_bps: assumed execution slippage in basis points of notional
            (half-spread + impact). 2-5 bps is reasonable for liquid ETFs on
            daily data; raise for illiquid names.
        regulatory_bps: pooled exchange/regulatory fees in basis points.
    """

    commission_per_share: float = 0.0035
    min_commission: float = 0.35
    max_commission_pct: float = 0.01
    slippage_bps: float = 3.0
    regulatory_bps: float = 0.2

    def commission(self, shares: float, price: float) -> float:
        """Commission in currency for one order of ``shares`` at ``price``."""
        notional = abs(shares) * price
        raw = abs(shares) * self.commission_per_share
        raw = max(raw, self.min_commission)
        return min(raw, notional * self.max_commission_pct)

    def cost_per_side(self, shares: float, price: float) -> float:
        """Total cost (commission + slippage + fees) for one buy or sell."""
        notional = abs(shares) * price
        slip = notional * self.slippage_bps / 10_000.0
        reg = notional * self.regulatory_bps / 10_000.0
        return self.commission(shares, price) + slip + reg

    def cost_fraction_per_side(self, price: float, shares: float = 1.0) -> float:
        """Cost of one side expressed as a fraction of notional.

        Useful for return-space (fraction) backtests where positions are sized
        as a weight rather than a share count. With the default model and a
        $1 share this is dominated by the minimum commission, so pass a
        representative ``shares``/``price`` for an accurate estimate.
        """
        notional = abs(shares) * price
        if notional == 0:
            return 0.0
        return self.cost_per_side(shares, price) / notional


# Convenient presets
IBKR_LIQUID_ETF = CostModel(slippage_bps=2.0)
IBKR_DEFAULT = CostModel()
IBKR_ILLIQUID = CostModel(slippage_bps=10.0)
