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

# Bitget USDT-M perpetual futures (e.g. BTC/USDT). Bitget standard fees are
# maker 0.02% / taker 0.06%. A systematic hourly strategy crosses the spread with
# market orders (taker) on both entry and exit, so the binding commission is
# 6 bps/side, booked here as ``regulatory_bps``. BTC/USDT perp is one of the most
# liquid instruments on earth (top-of-book spread ~1 bp), so 2 bps/side is a
# conservative slippage pad. Total = 8 bps/side, 16 bps round-trip.
# NOTE: funding (charged every 8h) is NOT in this model — strategies that hold
# across funding windows must treat it as an extra, regime-dependent cost.
BITGET_PERP_TAKER = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=2.0,    # half-spread + impact on BTC/USDT perp
    regulatory_bps=6.0,  # Bitget taker fee 0.06%
)

# Liquid futures (e.g. CL, NG, GC, ZC): IBKR commission is per *contract* and
# tiny relative to notional, so it is folded into a few bps rather than a
# per-share charge. Slippage (half-spread + impact) dominates the round-trip
# cost on daily data; 2 bps/side is realistic for the front month of liquid
# commodity futures, plus a small exchange/regulatory pad.
IBKR_FUTURES = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=2.0,
    regulatory_bps=0.5,
)

# Micro index futures, intraday round-trips (prop-account context).
# These contracts are the cheapest liquid markets per unit of notional because
# the notional is large and the tick is tiny — the exact opposite of the BTC
# perps (16 bps RT) where the intraday tests 0012-0015 died on cost.
#
# Micro E-mini S&P 500 (MES): $5 x index. At ES=5000 -> $25,000 notional.
#   - IBKR commission ~ $0.62/side (commission + exchange + regulatory).
#   - Spread is typically 1 tick = 0.25 pt = $1.25; a market order pays ~half a
#     tick of effective spread + impact per side.
#   - $0.62 comm + ~$0.90 slippage = ~$1.5/side on $25k = ~0.6 bps/side.
# We DELIBERATELY pad this to 1.5 bps/side (3 bps round-trip) so the gross edge
# must clear costs with the safety margin the prop framework demands. The open
# auction can slip more than mid-session, so the pad is intentional.
MES_INTRADAY = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=1.0,    # ~half-tick + opening-auction impact, padded
    regulatory_bps=0.5,  # commission + exchange/regulatory folded into bps
)

# Micro E-mini Nasdaq-100 (MNQ): $2 x index. At NQ=18000 -> $36,000 notional.
# Even cheaper per notional than MES (larger notional, same $0.62 commission,
# 0.25-pt tick = $0.50). Same conservative 1.5 bps/side pad applied.
MNQ_INTRADAY = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=1.0,
    regulatory_bps=0.5,
)

# ── Commodity futures cost presets (Alt-Data Fundamentals framework) ─────────
#
# These cover the 20-market universe in fundamentals/tradeability.md.
# All bps figures are per-side; round-trip = 2×.
#
# Methodology: commission (~1 bps for liquid softs at IBKR, folded into
# regulatory_bps) + effective half-spread including market-impact for daily
# end-of-day entries on continuous front-month contracts.

# Liquid US-traded softs and agricultural futures:
#   SB (Sugar #11, ~$24k notional):  spread 1-2 ticks, ~5 bps RT net commission
#   KC (Coffee, ~$75k notional):     spread 1-2 ticks at market → ~4 bps RT
#   CC (Cocoa, ~$80k notional):      similar to KC
#   CT (Cotton, ~$40k notional):     spread 1 tick at market → ~4 bps RT
#   LE/GF/HE (Live/Feeder/Hogs):     ~4-6 bps RT
# Conservative 8 bps RT (4 bps/side) to ensure gross edge clears costs.
IBKR_SOFTS = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=3.5,   # half-spread + market impact, padded for daily entries
    regulatory_bps=0.5, # IBKR commission + exchange fees folded in
)

# Liquid base and precious metals:
#   HG (Copper, ~$112k notional): very liquid, tight spread → ~4 bps RT
IBKR_METALS_LIQUID = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=1.5,
    regulatory_bps=0.3,
)

# Platinum-group metals (less liquid than gold/copper):
#   PL (Platinum, ~$50k notional): wider spread than HG → ~6 bps RT
#   PA (Palladium, ~$100k notional): similar
IBKR_METALS_PGM = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=2.5,
    regulatory_bps=0.5,
)

# Thin agricultural futures (OJ, ZO/Oats, ZR/Rough Rice, Dairy):
#   OJ (~$22k notional):  spread 5-15 ticks → 35-80 bps RT; 40 bps RT used
#   ZO/ZR: similar or worse
#   Dairy (Class III Milk, Butter, Cheese): prohibitively wide → flag in tradeability.md
# Conservative floor of 40 bps RT (20 bps/side). Actual may be 2-3× worse.
# A fundamental edge must be VERY strong (>40 bps/trade net) to survive here.
IBKR_SOFTS_THIN = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=18.0,  # very wide bid-ask + low electronic liquidity
    regulatory_bps=0.5,
)

# ── CTI / retail CFD cost presets (prop-challenge framework, batch 3) ─────────
#
# City Traders Imperium (and most prop firms) execute on an MT4/MT5 CFD feed.
# There is NO separate commission on the standard CFD plan — the cost is the
# dealer's bid/ask SPREAD MARK-UP, paid in full on every entry AND exit. This is
# the framework's binding "Step-0 cost gate": these intraday ideas (I0067-I0074)
# are re-tests of the liquid-index intraday-direction reject (0012-0015/0038-0041/
# 0049), so the spread must be modelled honestly or the equity curve is fiction.
#
# Spreads below are typical retail/prop MT5 quotes converted to bps of notional
# at representative 2024-26 price levels, then PADDED ~30-50% because prop feeds
# widen vs. an ECN and slip at the open/news. All are per-side; round-trip = 2x.
#
#   US500 (S&P CFD ~5000):  ~0.5 pt spread = 1.0 bps -> pad to 1.5 bps/side
#   US30  (Dow CFD ~40000): ~2.0 pt spread = 0.5 bps -> pad to 1.0 bps/side
#   NAS100(Nasdaq ~18000):  ~1.0 pt spread = 0.55 bps -> pad to 1.5 bps/side
# A blended 1.5 bps/side (3 bps round-trip) is used for index CFDs — on purpose
# the SAME wall as MES_INTRADAY, so a CFD edge faces no easier bar than futures.
CFD_INDEX = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=1.5,    # half-spread mark-up + open/impact, padded
    regulatory_bps=0.0,  # no separate commission on the standard CFD plan
)

# Spot-gold CFD (XAUUSD ~2000-3000): ~0.20-0.30 spread = 1.0-1.3 bps/side.
# Gold CFD spreads widen more than index in fast tape -> pad to 2.0 bps/side.
CFD_GOLD = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=2.0,
    regulatory_bps=0.0,
)

# FX majors CFD (EURUSD/GBPUSD): ~0.3-0.8 pip spread = 0.3-0.7 bps/side.
# The cheapest CFD class. Padded to 0.8 bps/side for prop-feed widening.
CFD_FX = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=0.8,
    regulatory_bps=0.0,
)

# Crypto CFD (BTCUSD/ETHUSD): the HARDEST cost wall (0012-0015). Retail/prop
# crypto-CFD spreads run ~15-40 bps round-trip; modelled at 10 bps/side (20 bps
# RT) as an optimistic floor — actual is often worse.
CFD_CRYPTO = CostModel(
    commission_per_share=0.0,
    min_commission=0.0,
    slippage_bps=10.0,
    regulatory_bps=0.0,
)
