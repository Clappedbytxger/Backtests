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

- **2026-06-06 (0038, Prop-Programm):** **Free intraday-data inventory** for the
  prop research program (Prop-Edge-Framework.md). yfinance daily OHLC is deep and
  clean (SPY 1993+, QQQ 1999+, ES=F/NQ=F 2000+, ^GSPC 1927+). Real intraday is the
  bottleneck: yfinance gives `1h` only ~2.4y (ES=F/MES=F since 2024-01, SPY 1h since
  2023-07), `5m/30m` only 60 days. Stooq's keyless CSV is now behind a JS
  proof-of-work challenge (dead). Consequence: **gap / open-to-close studies are
  fully testable on daily OHLC with decades of history** (gap = `Open_t/Close_(t-1)`,
  trade PnL = `Close_t/Open_t`, flat overnight) — that is the natural first prop
  hypothesis; true intraday hypotheses (opening-range, time-of-day) only have ~2.4y
  of 1h ES and must be treated as thin/exploratory until a deeper source (Databento
  free credit / Alpha Vantage month-param) is wired up. **For gap studies use the
  ETF (SPY/QQQ): its daily `Open` is the real RTH auction open. The futures
  continuous `Open` is the Globex session open (18:00 ET) — NOT a gap instrument**
  (ES/NQ show gross-negative "gap fade" = continuation, an artifact of this).
- **2026-06-07 (0039, Databento wired):** **Real intraday futures data is now
  available** via Databento (`quantlab.futures_intraday`, GLBX.MDP3, Parquet cache,
  cost-guarded; key in gitignored `.databento.key`). Cached: ES.c.0 + NQ.c.0 `ohlcv-1h`
  full (2010-2026, ~$0.94 each) and **ES.c.0 `ohlcv-1m` full (5.5M bars, ~$20.2)** —
  ~$22 of the $125 free credit spent, ~$103 left. Gotchas: continuous symbology
  (`ES.c.0`, `stype_in="continuous"`) **fails to resolve when `end` is omitted** —
  always pass an explicit end (loader defaults to today). Bars are timestamped at the
  interval START; CME RTH = 09:30-16:00 ET (filter on `tz_convert("US/Eastern")`).
  ES intraday returns == MES, so backtest ES.c.0 and apply `MES_INTRADAY` cost. On
  this data the opening-range fade (#1) was a clean cost-gate reject: breakout fade
  AND continuation have gross ~0 / win ~49% across every OR window x holding horizon
  x OR-width tercile — the liquid-index intraday directional edge is ~0 and cost is
  binding, same wall as BTC 0012-0015 and gap 0038 (no look-ahead this time, the
  engine is clean, the signal is simply empty). **Pattern across 0012-0015/0038/0039:
  a single liquid market's intraday DIRECTION is not exploitable net of cost; the
  remaining prop-viable class is relational/market-neutral (ES<->NQ lead-lag) or
  structural time-of-day, not a directional bet on one series.**
- **2026-06-07 (0040/0041, prop intraday list complete):** The framework's whole
  intraday hypothesis list is now tested and **all rejected on cost**: #1 opening-range
  fade (0039), #2 gap fade (0038), #3 time-of-day (0040), #4 breakout continuation
  (in 0039), #5 ES<->NQ lead-lag/RV (0041). Findings worth keeping: (a) **the
  "last-hour / close-auction drift" is empirically ABSENT** on ES 2010-2026 — intraday
  equity gains are spread across the session, not concentrated into the close (NQ 1h
  confirms ET-15:00 hour Sharpe -0.06); the famous equity drift is *overnight*, which
  prop rules forbid holding. (b) **Intraday autocorrelation ~0** (ES morning->afternoon
  +0.02, like BTC 0015) — no time-conditioned directional structure. (c) **ES<->NQ
  lead-lag is fully HFT-arbitraged** (corr(ES[t],NQ[t+1])=+0.001) but the **beta-hedged
  RV spread genuinely reverts** (1-min autocorr -0.107, win rate rises monotonically to
  58% at z=2.5) — the ONLY real intraday signal found, yet only 0.3-0.5 bps/trade vs a
  ~6 bps two-leg cost (needs maker-rebate HFT to clear). **Strategic conclusion: a
  retail/prop cost structure cannot access liquid-index intraday alpha — direction is
  empty, RV is real-but-sub-cost. The confirmed path for this account stays the
  LOW-FREQUENCY seasonal track (Platin 0021 etc.), where ~1 trade/year makes cost
  negligible — the exact opposite regime.** Do not re-litigate intraday index direction
  without a fundamentally cheaper execution (maker fills + rebates), which is out of
  scope for a 2000-EUR prop account.
- **2026-06-06 (0038):** **Look-ahead via a same-bar trend filter** — the framework's
  #1 intraday trap, caught live. A "buy the dip in an uptrend" gap-fade scored
  Sharpe 2.82 (+12.5 bps/trade) only because the trend filter used `Close_t > MA_t`,
  and `Close_t` is unknown at the open. `Close_t > MA` is mechanically correlated
  with a positive open->close (a day closing high vs its average usually rose from
  the open), so the long secretly pre-selected up-days. Lagging the filter to
  open-time info (`Close_(t-1) > MA_(t-1)`) collapsed it to Sharpe −0.22. **Rule: any
  intraday filter/feature must be built from data available at the decision instant;
  a feature that contains the current bar's close while the PnL is also driven by
  that close fabricates the edge.** Also reconfirmed: tiny gross edges (~1-2 bps) on
  liquid index gaps never clear even the cheap ~3 bps MES round-trip (cost gate), and
  a positive-mean cell whose top-5 days are >100% of profit is a fat-tail lottery —
  doubly disqualifying under prop rules (consistency + daily-DD breach risk).
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
- **2026-06-05 (0025):** yfinance has **no reliable LME base-metal series**. The
  zinc front-month `ZNC=F` looks alive (price ~2300, positive) but is a *dead
  symbol*: it froze around 2018–2019 and from 2020 on returns a single repeated
  print — **1 distinct close per year**, ~100% zero-return days. A whole backtest
  ran "fine" and produced numbers (Sharpe −0.54, OOS-"Sharpe" −59) that were pure
  cost-on-zero-movement artifacts. Before any seasonal test on an exotic future,
  **screen data quality first**: `close.groupby(year).nunique()` and the
  zero-return fraction expose a frozen feed in seconds, before a backtest is even
  worth running. This check is now a guard in `0025/run.py`.
  **Free LME workaround found:** westmetall.com publishes daily LME official
  Cash-Settlement (spot, no roll) for Zn/Cu/Al/Pb/Ni/Sn back to 2008, scrapeable —
  wrapped in `src/quantlab/lme_data.py` (`get_lme_zinc`). On that clean series the
  zinc July window actually passes the permutation test (p=0.031) — so the original
  "untestable" verdict was a *data* failure, not a strategy failure. For the full
  35y series Seasonax uses (Bloomberg `BCOMZS`, a futures-TR index), the only free
  route is a manual CSV export from Investing.com/MacroMicro. Stooq and Nasdaq Data
  Link now both require API keys.
- **2026-06-03 (0005):** In-sample optimization Sharpes are meaningless alone.
  Picking the best of 156 weekly windows in-sample gave Sharpes of 4-8 that
  collapsed to ~0 OOS for 7/8 assets. Always charge the Deflated Sharpe the full
  search width (`n_trials` = configs scanned), and treat a single OOS survivor
  among many as a lead needing a pre-registered forward test, not an edge.
- **2026-06-05 (0028/0029):** On **monthly-rolling futures** (`NG=F`, `CL=F`,
  `RB=F`, `HO=F`) every multi-week continuous-series window necessarily contains
  futures-expiry days, and a continuous front-month stitch can fabricate returns
  there (gas autumn 21.9.–1.11. looked like the strongest lead ever: perm p=0.001,
  bootstrap CI excluding zero, median +5.7%, IS≈OOS — *all real but all driven by
  the same yearly expiry cluster*). **105% of the mean trade PnL sat on ~6
  expiry-days/year**; excluding just a tight ±1-day zone around each expiry
  (26–28 Sep / 27–29 Oct) flipped expectancy +15.5%→−0.27% and permutation
  p 0.002→0.773. Permutation + bootstrap + IS/OOS + median **all pass** when the
  artifact is year-over-year consistent, so they are *not enough*. **Mandatory
  pre-step before a continuous-futures seasonal counts as a lead: a roll-day
  exclusion test** — the edge must survive removing a tight zone around every
  in-window expiry. Quarterly rollers (platinum Jan/Apr/Jul/Oct, 0019) are safer
  because a window can exit before its single roll; monthly rollers cannot. The
  54% roll-day hit rate (vs a clean mechanical stitch's 70–90%) also says: this
  was expiry-clustered fat-tails, not a fixed contango gap — but neither is a
  tradable seasonal. Reusable harness: `0029_natgas_roll_check/run.py`.
