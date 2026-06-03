# Backtests — Quantitative Trading Research

A systematic, bias-aware framework for researching trading strategies.
Reusable library (`src/quantlab`) + one folder per strategy + a master catalog.

## Setup

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Layout

| Path | Purpose |
|------|---------|
| `src/quantlab/` | Reusable engine: data, metrics, costs, backtest, significance, seasonal, plotting |
| `strategies/NNNN_name/` | One strategy: `run.py`, `research.ipynb`, `REPORT.md`, `results/` |
| `CATALOG.md` | Master register of every strategy tested (ID, hypothesis, status, key metrics) |
| `tests/` | Unit tests (metrics correctness, look-ahead protection) |
| `data/cache/` | Cached yfinance downloads (Parquet, git-ignored) |

## Running a strategy

```powershell
.\.venv\Scripts\python.exe strategies\0001_seasonal_calendar\run.py
```

Each run writes `metrics.json`, `trades.csv` and plots into the strategy's
`results/`, and you append a row to `CATALOG.md`.

## Methodology principles

- **No look-ahead**: signals are shifted one bar by the engine; positions are
  decided on data up to *t* and held from *t+1*.
- **Costs always on**: IBKR commission + slippage + fees, reported net.
- **Significance over story**: permutation test, bootstrap CI, and the
  **Deflated Sharpe Ratio** (corrects for how many variants we tried).
- **In-sample / out-of-sample** split before trusting any pattern.
- **Macro rationale required**: a pattern without an economic cause is treated
  as suspect (likely data-mined).

## Key metrics

CAGR, Sharpe, Sortino, Calmar, max drawdown (+ duration), volatility, win rate,
profit factor, payoff ratio, expectancy, average holding period, number of trades.
