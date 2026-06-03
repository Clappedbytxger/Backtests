# Strategy 0001 — Seasonal Calendar Effects

- **Category:** seasonal
- **Status:** rejected (as a standalone edge) / iterate (sell-in-May as overlay)
- **Date:** 2026-06-03
- **Universe:** SPY, QQQ, ^GDAXI, ^FTSE, ^N225 (broad equity indices)
- **Sample:** in-sample ≤ 2010 (selection only) / out-of-sample 2011–2026 (evaluation)

## 1. Hypothesis

Recurring calendar windows — turn-of-month, year-end, and the May–October
"summer lull" — produce abnormal equity-index returns that can be traded long-only
with a better risk-adjusted profile than buy & hold, net of IBKR costs.

## 2. Macro rationale

- **Turn-of-month:** month-end pension/salary inflows, fund reinvestment and
  index rebalancing concentrate buying pressure at the boundary.
- **Turn-of-year:** tax-loss selling exhausts into year-end, window dressing,
  thin holiday liquidity, new-year inflows.
- **Sell-in-May (Halloween):** historically weaker summer returns linked to
  seasonal liquidity and risk-appetite cycles.

## 3. Rules

Long-only position weight of 1.0 inside the calendar window, else flat.
Signals are decision-time and shifted one bar by the engine (no look-ahead).
Effect/ticker for the deep-dive was chosen **only** on in-sample Sharpe.

## 4. Cost & execution assumptions

IBKR tiered commission ($0.0035/share, $0.35 min, 1% cap), **2 bps** slippage
(`IBKR_LIQUID_ETF`), 0.2 bps regulatory. Costs charged on every position change;
all numbers below are **net**.

## 5. Out-of-sample panel (net of costs, 2011–2026)

| Ticker | Effect | OOS Sharpe | Buy&Hold Sharpe | CAGR | Exposure | #Trades | Win rate | Profit factor |
|--------|--------|-----------:|----------------:|-----:|---------:|--------:|---------:|--------------:|
| SPY | turn_of_month | 0.12 | 0.75 | 2.7% | 19% | 186 | 60% | 1.38 |
| SPY | turn_of_year | -0.48 | 0.75 | 0.6% | 4% | 16 | 69% | 1.76 |
| SPY | sell_in_may | 0.46 | 0.75 | 7.4% | 50% | 16 | 75% | 7.72 |
| QQQ | turn_of_month | 0.18 | 0.87 | 3.3% | 19% | 186 | 61% | 1.37 |
| QQQ | sell_in_may | 0.46 | 0.87 | 8.2% | 50% | 16 | 81% | 6.40 |
| ^GDAXI | turn_of_month | -0.20 | 0.42 | -0.4% | 19% | 186 | 56% | 1.01 |
| ^GDAXI | sell_in_may | 0.45 | 0.42 | 7.6% | 50% | 16 | 69% | 3.97 |
| ^FTSE | sell_in_may | 0.23 | 0.18 | 4.0% | 50% | 16 | 88% | 3.81 |
| ^N225 | sell_in_may | 0.33 | 0.59 | 6.2% | 50% | 16 | 69% | 3.46 |

(Full panel incl. all turn_of_year rows in `results/oos_panel.csv`.)

### Deep-dive: selected effect (sell_in_may on ^GDAXI)

| Metric | Value |
|--------|-------|
| CAGR | 7.57% |
| Sharpe | 0.45 (buy & hold 0.42) |
| Sortino | 0.59 |
| Max drawdown | -38.8% |
| Win rate | 68.8% |
| Profit factor | 3.97 |
| Avg holding period | 121 days |
| # Trades | 16 |

## 6. Significance

- **Permutation test p-value:** 0.114 — not significant (≈11% of random timings
  matched it).
- **Deflated Sharpe Ratio:** ≈0.000 — after correcting for the 15 variants tried,
  the result is fully consistent with selection luck.
- Conclusion: the in-sample winner does **not** survive honest significance testing.

## 7. Robustness

- **turn_of_month** has the statistical power (186 trades) but **no OOS edge**
  after costs (Sharpe 0.12 / 0.18 / -0.20 / -0.01 / -0.11). The classic anomaly
  appears largely arbitraged away post-2010. Note exposure is only ~19%.
- **sell_in_may** is **positive and consistent across all five markets**
  (Sharpe 0.23–0.46) — a genuine robustness signal — but:
  - it **underperforms buy & hold in strong bull markets** (US) because it sits
    out half the year;
  - only 16 trades per market → weak power individually;
  - it does its real job on the **drawdown** side: the equity curve
    (`results/plots/equity.png`) shows it sidesteps the 2011 selloff and softens
    2020 while ending near buy & hold — i.e. similar return at ~half the exposure.

## 8. Verdict

**Rejected as a standalone return edge.** No calendar effect beats buy & hold
net of costs with statistical significance in the OOS sample, and the in-sample
winner is killed by the Deflated Sharpe Ratio. This is the framework working
correctly — it refuses to confirm a data-mined pattern.

**Worth iterating:** sell-in-May's cross-market consistency and exposure-halving
drawdown reduction make it a candidate **risk-overlay**, not an alpha source.
Next steps: (a) pool the 5 markets to lift trade count and test significance
with real power; (b) test it as a tactical de-risking filter on top of a
buy-and-hold core; (c) compare staying in T-bills (`^IRX`) during the summer
months rather than flat cash.

### Artifacts
`results/metrics.json`, `results/oos_panel.csv`, `results/trades.csv`,
`results/plots/{equity,drawdown,monthly_heatmap,bucket_tdom_from_end}.png`
