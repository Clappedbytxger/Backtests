# Strategy Catalog

Master register of every strategy tested. Status: `idea` → `testing` →
`validated` / `rejected`. Metrics are out-of-sample, net of costs, unless noted.

| ID | Name | Category | Hypothesis | Status | Sharpe | CAGR | MaxDD | #Trades | p-value | DSR | Notes |
|----|------|----------|-----------|--------|--------|------|-------|---------|---------|-----|-------|
| 0001 | Seasonal calendar effects | seasonal | Turn-of-month / year-end / Halloween calendar windows beat buy & hold risk-adjusted | rejected | 0.45 | 7.6% | -38.8% | 16 | 0.114 | 0.00 | No significant standalone edge OOS; sell-in-May consistent across markets → iterate as risk overlay |

## Categories

- **seasonal** — calendar/recurring-date effects
- **mean-reversion** — fade short-term moves
- **momentum / trend** — ride persistence
- **cross-sectional** — relative ranking across assets
- **macro / regime** — driven by macro state

## Legend

- **DSR** = Deflated Sharpe Ratio (prob. true Sharpe > 0 after multiple-testing correction)
- **p-value** = permutation test vs random timing
