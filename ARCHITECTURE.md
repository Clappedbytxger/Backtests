# Quant-OS — Architecture

> Internal operating system for the full lifecycle of a trading strategy:
> **research → validation → promotion → live execution → monitoring.**
> This is a *living* document; the Changelog at the bottom tracks progress.

---

## 1. Purpose & scope

`D:\Backtests` already contains a mature, bias-aware research stack: a tested
library (`src/quantlab`), **108 strategies**, a **live system** (`live/`), and one
frozen production book (**0108 CTI CORE**, IB + MT5 adapters). Quant-OS is **not a
rewrite** — it is a thin **productization layer on top of `quantlab`** that closes
the real gaps: central cross-platform config, a queryable data lake, a formal
strategy contract (`IStrategy`) generalizing the ad-hoc parity logic already used
by 0108, a strategy/experiment registry, a dashboard, and an autonomous research
agent. Bewährtes wird wiederverwendet, nicht ersetzt.

## 2. Guiding decisions (and *why*)

| # | Decision | Rationale (grounded in this repo's record) |
|---|----------|--------------------------------------------|
| **D1** | **Build on `quantlab`**, not greenfield/rewrite | The vectorized engine, cost models, significance battery (DSR), and CPCV+PBO already exist and are unit-tested. A Polars/clean-slate rewrite would risk 108 strategies for zero gain at daily frequency. |
| **D2** | **C++ = backtest-speed kernel only**, no live-HFT core | Every intraday/HFT *directional* edge tested here died on the cost wall (0012–0015, 0038–0041, 0049, 0067–0074 — 9+ measured nulls). **All** validated edges are low-frequency (turn-of-month, pre-FOMC overnight, Treasury-auction, monthly-rebalanced books; 0108 holds days–weeks). A latency core solves a problem this account does not have. C++ accelerates the *event-driven backtest inner loop* via pybind11/CMake; nothing more. |
| **D3** | **Autonomous research agent, hard-walled** | The agent may run the full loop (hypothesis → code → backtest → analyze → REPORT → commit) but **only on an isolated branch, never `main`, never `push`**, and with **no live-order tools** in its toolset. Live execution stays the deterministic 0108 bot — **no LLM in the order path** (per the `funded_account_direction` decision). Look-ahead bugs are subtle (the 0069 near-miss needed human insistence), so every agent-authored strategy must pass the same planted-clairvoyant + parity gates as human ones. |

Non-negotiable hard rules from `CLAUDE.md` continue to apply: no look-ahead
(engine shifts signals T+1), costs always modeled (report net), macro rationale
required, ≥30 (prefer >100) trades, multiple-testing awareness (DSR).

## 3. Existing assets (the foundation we build on)

**`src/quantlab/` — ~40 modules.** Core: `data.py` (yfinance + Parquet cache),
`backtest.py` (vectorized, look-ahead-safe, trade log), `metrics.py`, `costs.py`
(~15 presets incl. IBKR/MES/Futures/CFD), `significance.py` (permutation, bootstrap,
**Deflated Sharpe**, t-test), `cross_sectional.py`, `cpcv.py` (**CPCV + PBO**),
`ml_portfolio.py`. Data domains: `futures_curve.py`/`futures_chain.py` (roll-clean
term structure), `cot_data.py`, `commodity_features.py`, `fundamental_data.py`
(+ PIT `as_of`/`build_pit_series`), `ic.py`, crypto (`crypto_xsection.py`,
`crypto_features.py`, `price_images.py`), `equities_intraday.py`. Strategy packages:
`smc/`, `weinstein/`. Betting: `football_data.py`, `devig.py`, `clv.py`, `odds_live.py`.

**`strategies/NNNN_name/`** — 108 folders, each `run.py` + `REPORT.md` + `results/`
(`metrics.json`, plots, `trades.csv`). Pattern: standalone script, `sys.path` to
`src`, run engine, write JSON/PNG, print verdict.

**`live/`** — `calendar.yaml` (triggers) → `engine.py` (dated order tickets, T+1) →
`ledger.py` (forward ledger) → `run_daily.py` (08:00 scheduler) → `notify.py`
(Telegram) + `signals/` (daily gates) + `state/`.

**`strategies/0108_cti_core_book_live/`** — frozen 4-sleeve CTI book. `signal_engine.py`
**validates reconstructed streams against saved research streams** (correlation +
Sharpe match) before emitting live targets — this is research-to-production parity,
done by hand. Quant-OS generalizes it (`strategy/parity.py`).

**Data:** ~2,600 Parquet files under `data/cache/` (subdirs: `cot/ crypto/
crypto_xsection/ curve/ edgar/ equities/ football/ fundamentals/ futures/ fx/`).
yfinance daily is the spine; Databento for intraday/curve; CMC/Binance for crypto;
CFTC/FRED/EIA/NASS for fundamentals.

**Environment:** Python 3.13 venv, setuptools + `pyproject.toml`, pytest (~20 tests).
Toolchain present: **MSVC (VS 2022 Community 17.7)**, **gcc 10.3 (tdm64)**; CMake to be
installed via winget.

## 4. Target architecture (layers)

```
config.yaml + .env             central paths/secrets (Windows + macOS), pathlib only
└─ src/quantlab/               existing research core (extended, not replaced)
   ├─ config.py     [P1]       pydantic-settings loader (env -> yaml -> defaults)
   ├─ store/        [P1]       DuckDB layer over data/cache/**.parquet (PIT-safe)
   ├─ strategy/     [P1]       IStrategy contract + runner + parity check
   ├─ registry/     [P1]       SQLite index of strategies / runs / metrics
   ├─ robustness/   [P2]       Monte Carlo, Walk-Forward, White's Reality Check
   ├─ backtest_event.py [P2]   event-driven engine (C++ kernel in the inner loop)
   └─ tca.py        [P2]       market-impact / slippage on top of costs.py
cpp/quant_kernel/  [P1/P2]     C++ speed kernel (CMake, pybind11)
apps/api/          [P1]        FastAPI backend (reads registry / lake)
apps/web/          [P3]        Next.js + Tailwind dashboard
agent/             [P4]        autonomous quant agent (LLM HW abstraction, RAG, loop)
live/              [exists]    live system; the IStrategy live path docks in here
```

**Reuse (do not reinvent):** `run_backtest` (`backtest.py:21`); `significance.*` +
`cpcv` for robustness; `costs.CostModel` for TCA; `fundamental_data.as_of` /
`build_pit_series` for the lake's PIT helper; `0108 signal_engine.validate()`
(`signal_engine.py:242`) → `strategy/parity.py`; `live/engine.py` Event/trigger
system for the live path; `strategies/REPORT_TEMPLATE.md` + the look-ahead tests
(`test_backtest.py`, `test_pit.py`, `test_smc_causality.py`) as patterns.

## 5. Strategy lifecycle & the `IStrategy` contract

A strategy moves through four stages with explicit gates:

1. **Research** — exploratory `strategies/NNNN/run.py` (stays as-is; the agent or a
   human authors these). Output: `results/metrics.json`, plots, REPORT.
2. **Validation** — full battery: costs-on, permutation, bootstrap CI, Deflated
   Sharpe, IS/OOS split, CPCV/PBO where applicable (existing `quantlab` tools).
3. **Promotion** — a validated strategy is re-expressed as an **`IStrategy`** class:
   `generate_signals(prices) -> Series` (decision-time weights; identical contract to
   `run_backtest`), `size_position()`, `manage_risk()`, `on_data(bar)` (event/live
   hook). **The same object runs in backtest and live.** A `parity.validate_parity()`
   check asserts the live reconstruction matches the saved research stream
   (correlation > 0.99 + Sharpe match) — the 0108 pattern, generalized.
4. **Live** — the live engine (`live/`) schedules and the deterministic bot executes;
   human-in-the-loop for orders. No LLM in this path.

The **registry** (SQLite) indexes every strategy/run/metric for the dashboard and
for de-dup during research.

## 6. Data architecture (PIT lake)

`store/DataLake` opens a **DuckDB** connection and exposes `data/cache/**/*.parquet`
as queryable views with **zero duplication** (DuckDB scans Parquet in place). A
generic **PIT helper** (`as_of(dataset, asof_ts)`) enforces the look-ahead rule
(`ts <= asof`); vintage/fundamental series reuse `fundamental_data.build_pit_series`.
A unit test guards that a PIT query never returns a row newer than the as-of stamp.

## 7. The autonomous agent (P4) — design & guardrails

- **HW abstraction** (`agent/llm/backend.py`): `MLXBackend` (macOS/Apple Silicon,
  `mlx-lm`) vs `LlamaCppBackend` (Windows, `llama-cpp-python`), auto-selected by
  platform. Models: DeepSeek-Coder (code) + Llama-3 (RAG/analysis).
- **RAG** (`agent/rag/`) over `IDEAS_DIR` (`HYPOTHESES.md`, `ideas/*.md`, `SOURCES.md`)
  with mandatory de-dup against `CATALOG.md`.
- **Loop** (`agent/loop.py`): read hypothesis → scaffold `run.py` (from
  `REPORT_TEMPLATE` + nearest existing strategies) → run backtest in a subprocess →
  parse `metrics.json` → write `REPORT.md` → **commit on an isolated branch**.
- **Guardrails (enforced & tested):** `assert current_branch != "main"/"master"`,
  **no `git push`**, **no broker/live-order tools** in the agent toolset, every
  generated strategy must pass the planted-clairvoyant + parity gates.

## 8. Cross-platform & toolchain (REGEL 1)

No hardcoded absolute paths — `pathlib` everywhere, all base paths from `config.yaml`
/ env (`QUANTLAB_*`). C++ builds via **CMake** (MSVC on Windows, Clang on macOS) so the
kernel compiles unchanged on both. LLM inference picks the backend per platform.
Targets: Windows 11 (AMD GPU) and macOS (Apple Silicon, 24 GB).

## 9. Roadmap & status

| Phase | Content | Status |
|-------|---------|--------|
| **P1** | Config/cross-platform · DuckDB lake · `IStrategy` + parity · SQLite registry · C++ scaffold · API/UI skeletons | **complete (2026-06-20)** |
| **P2** | Event-driven backtester (C++ inner loop) · TCA · robustness lab (MC, WFA, White's Reality Check; reuse DSR/CPCV) | **complete (2026-06-20)** |
| **P3** | Next.js + Tailwind dashboard (overview charts, strategy detail + plots, research hub) · live-book monitor → P4 | **core complete (2026-06-20)** |
| **P4** | Autonomous agent (LLM HW abstraction, RAG, loop) · OMS/broker (IB + CTI) formalized, human-in-the-loop | **core complete (2026-06-20)** |

## 10. Non-goals / deferred / rejected (with rationale)

- **Full HFT latency execution core** — deferred; cost-wall record (D2). C++ stays a
  backtest accelerator.
- **PostgreSQL** — not needed for a single-user local stack; **SQLite** for metadata,
  **DuckDB** for analytics.
- **Polars rewrite of existing modules** — additive use only; no churn at daily freq.
- **LLM in the live-order path** — stays deterministic.
- **New GitHub repo / Notion pages** — repo already exists; Notion suspended for this
  project (standing preference).

## 11. Changelog

- **2026-06-20** — Pre-analysis complete; architecture decisions D1–D3 fixed.
  Phase 1 started on branch `feat/quant-os-phase1`.
- **2026-06-20** — P1 config & cross-platform layer landed: `src/quantlab/config.py`
  (pydantic-settings, env > yaml > defaults, no hardcoded paths), `config.yaml` /
  `config.example.yaml` / `.env.example`, `data.py` cache root now config-driven
  (same default), `pyproject.toml` optional-deps (`platform`/`cpp`/`agent`),
  `.gitignore` updated. Precedence verified; 113 tests collect, 24 core pass. Next:
  DuckDB lake (`store/duck.py`).
- **2026-06-20** — **Phase 1 complete.** Added: `quantlab.store.DataLake` (DuckDB over
  2,399 Parquet datasets, PIT `as_of` with tz-aware guard); `quantlab.strategy`
  (`IStrategy` + runner + `validate_parity`, reference `TurnOfMonthStrategy` = 0050,
  real-data parity vs engine corr=1.0000); `quantlab.registry` (SQLite over CATALOG.md
  + metrics.json → 109 strategies, 96 with metrics, lifecycle buckets) +
  `scripts/build_registry.py`; `cpp/quant_kernel` (pybind11/CMake speed kernel,
  reproduces `run_backtest` net returns to 1e-12); `apps/api` (FastAPI over registry)
  and `apps/web` (Next.js + Tailwind dashboard, builds clean). **134 Python tests pass**
  (+21 new), frontend `next build` green. Toolchain: CMake via pip `cmake` pkg (the
  `D:\CMake` dir was source-only). Next: Phase 2 (event-driven backtester on the C++
  kernel, TCA, robustness lab).
- **2026-06-20** — **Phase 2 complete.** Added: `quantlab.backtest_event` (bar-by-bar
  engine, bit-for-bit parity with the vectorized engine on plain signals via the C++
  kernel, plus intrabar stop-loss/take-profit with open-gap fills and post-stop
  suppression); `quantlab.tca` (square-root market-impact TCA; `tca_from_backtest`
  bridges weight-space turnover to dollar costs); `quantlab.robustness` (moving-block
  Monte-Carlo with a max-drawdown distribution, walk-forward harness, White's Reality
  Check — re-exporting the existing permutation/bootstrap/DSR battery). **147 Python
  tests pass** (+13 new). Next: Phase 3 (dashboard) and Phase 4 (autonomous agent + OMS).
- **2026-06-20** — **Phase 3 core complete.** API gained dashboard endpoints
  (`/overview` aggregate, `/strategies/{num}/plots` + path-safe PNG serving,
  `/ideas` from `IDEAS_DIR/HYPOTHESES.csv`). Dashboard (`apps/web`, recharts) now has
  an overview (lifecycle buckets, Sharpe histogram, category bar, top-by-Sharpe,
  full table), a strategy detail page (catalog metrics + flattened metrics.json +
  result plots) and a research hub (105-hypothesis backlog). **151 Python tests
  pass** (+4 API), `next build` green (5 routes). Deferred to P4: live-book monitor
  + interactive equity curves. Next: Phase 4 (autonomous agent + OMS).
- **2026-06-20** — **Phase 4 core complete.** `agent/` — hard-walled autonomous
  research agent: `guardrails` (branch isolation, no-push allow-list, `agent_commit`),
  `llm/` (HW-abstracted backend + Mock + lazy llama.cpp/mlx + auto-select), `rag/`
  (TF-IDF over HYPOTHESES.csv + de-dup vs CATALOG.md), `loop` (hypothesis → code →
  backtest subprocess → REPORT → commit on `agent/*`, never `main`/push), `cli`
  (`python -m agent`). `live/oms.py` — broker-agnostic OMS with PaperBroker, bracket
  OCO orders and a human-in-the-loop confirm gate (deterministic, **no LLM in the
  order path**). **24 new tests** (guardrails 7, llm 5, rag 4, loop 3, oms 5);
  the full cycle is verified end-to-end with the mock backend (no model needed).
  Real local inference is an optional one-time `pip install -e ".[agent]"` + model
  download (see `agent/README.md`). **All four phases now landed.**
