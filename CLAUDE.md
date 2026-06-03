# CLAUDE.md — Backtests (Quant Research)

Project-specific instructions. The global `CLAUDE.md` also applies (German
communication, English code/commits, Conventional Commits, etc.).

## Goal

Build a real, statistically validated trading edge — datadriven, not vibes.
Every strategy must survive cost, look-ahead and significance scrutiny.

## Workflow for a new strategy

1. Copy `strategies/REPORT_TEMPLATE.md` into a new `strategies/NNNN_name/` folder.
2. Write `run.py` using `quantlab` (never re-implement metrics/engine).
3. Split in-sample / out-of-sample; only trust out-of-sample numbers.
4. Always run: costs on, permutation test, bootstrap CI, Deflated Sharpe.
5. Write `REPORT.md`, save plots + `metrics.json` + `trades.csv` to `results/`.
6. Append a row to `CATALOG.md`.

## Hard rules (non-negotiable)

- **No look-ahead.** Signals are decision-time; the engine shifts them. Never
  use same-bar or future data in a signal.
- **Costs always modeled** (IBKR). Report net, not gross.
- **Macro rationale required.** No economic cause => mark as suspect/data-mined.
- **Enough trades.** Aim for >30, prefer >100, for statistical meaning.
- **Multiple-testing awareness.** Track how many variants were tried; use the
  Deflated Sharpe Ratio.
- Use **adjusted close** (yfinance `auto_adjust=True`, already default in `data.py`).

## Library map (`src/quantlab`)

- `data.py` — cached yfinance loader (Parquet)
- `metrics.py` — `compute_metrics`, `trade_stats`
- `costs.py` — `CostModel`, IBKR presets
- `backtest.py` — `run_backtest` (vectorized, look-ahead safe, trade log)
- `significance.py` — permutation, bootstrap, Deflated Sharpe, t-test
- `seasonal.py` — calendar features, bucket analysis, signal builders
- `plotting.py` — equity, drawdown, monthly heatmap, bucket bars

## Environment

- venv at `.venv` (Python 3.13). Run: `.\.venv\Scripts\python.exe ...`.
- There is also a separate `D:\AI\Python` 3.10 install on the machine — do not
  use it for this project; always use the project `.venv`.

## Lessons Learned

- **2026-06-03:** On Windows, `python -m pip install --upgrade pip` chained in
  the same command that then installs packages can corrupt pip (`WinError 32`
  file lock + leftover `~ip` dist). Fix: don't self-upgrade pip mid-install; if
  pip breaks, recreate the venv and run `ensurepip --upgrade`.
- **2026-06-03 (0005):** Continuous front-month futures can print a *non-positive*
  price — WTI (`CL=F`) settled at -$37.63 on 2020-04-20. Simple `pct_change`
  returns are undefined across a zero crossing and produce nonsense (CAGR -100%,
  MaxDD -264%). Guard any futures backtest with `if (close <= 0).any(): skip`,
  or use a ratio-adjusted continuous series. "Futures are cleaner than ETFs" is
  only half true — they have their own artifacts (negative prints, roll gaps).
- **2026-06-03 (0005):** In-sample optimization Sharpes are meaningless alone.
  Picking the best of 156 weekly windows in-sample gave Sharpes of 4-8 that
  collapsed to ~0 OOS for 7/8 assets. Always charge the Deflated Sharpe the full
  search width (`n_trials` = configs scanned), and treat a single OOS survivor
  among many as a lead needing a pre-registered forward test, not an edge.
