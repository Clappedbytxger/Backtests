"""The autonomous research cycle.

One cycle, on an isolated ``agent/*`` branch:
  1. ensure the agent branch (guardrail — never main/master)
  2. RAG: pull relevant hypotheses + de-dup against the catalog
  3. LLM: generate a self-contained ``run.py`` for the hypothesis
  4. run the backtest in a subprocess; parse ``results/metrics.json``
  5. LLM: write ``REPORT.md`` from the metrics
  6. commit on the agent branch — **never pushes**

The LLM-generated ``run.py`` is arbitrary code executed in a subprocess; the
safety model is isolation (dedicated branch + no push) plus a human review before
any merge. There are NO live-order tools in the agent's reach.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from quantlab.config import get_settings

from .guardrails import agent_commit, ensure_agent_branch
from .llm import LLMBackend, get_backend
from .rag import dedup_against_catalog, retrieve_context

_CODE_SYSTEM = (
    "You are a meticulous quant researcher. Write a SINGLE self-contained Python "
    "run.py that tests the hypothesis using the `quantlab` library (data, backtest, "
    "metrics, significance). No look-ahead (signals are decision-time, the engine "
    "shifts T+1). Always model costs. Save results/metrics.json. Output ONLY a "
    "```python``` code block."
)
_REPORT_SYSTEM = (
    "Write a concise REPORT.md for a quant strategy: hypothesis, method, the key "
    "metrics, an honest verdict (edge real? cost-robust? look-ahead-safe?). Markdown only."
)


def _slugify(text: str, maxlen: int = 30) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:maxlen].strip("-") or "idea"


def _extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def next_strategy_number(repo_root: Path) -> str:
    sdir = repo_root / "strategies"
    nums = [int(p.name[:4]) for p in sdir.glob("[0-9][0-9][0-9][0-9]_*")
            if p.name[:4].isdigit()] if sdir.exists() else []
    return f"{(max(nums) + 1) if nums else 1:04d}"


def _code_prompt(hypothesis: str, context, dups) -> str:
    ctx = "\n".join(f"- {d.id}: {d.text}" for d, _ in context) or "(none)"
    dup = "\n".join(f"- {d.id} (sim {s:.2f}): {d.meta.get('name', d.text)}" for d, s in dups) or "(none)"
    return (f"Hypothesis:\n{hypothesis}\n\nRelated backlog ideas:\n{ctx}\n\n"
            f"Already-tested similar strategies (avoid duplicating their reject reasons):\n{dup}\n\n"
            "Write run.py now.")


def _report_prompt(hypothesis: str, metrics: dict | None, stdout: str) -> str:
    return (f"Hypothesis:\n{hypothesis}\n\nmetrics.json:\n{json.dumps(metrics, indent=2, default=str)}\n\n"
            f"run.py output (tail):\n{stdout[-1500:]}\n\nWrite REPORT.md.")


# ── Constrained ("harness") generation ──────────────────────────────────────
# The model writes ONLY the signal logic; this fixed, audited harness computes
# every metric, the benchmark equity curves, the permutation test, bootstrap CI,
# DSR and the plots — so none of those can be hallucinated.

_SIGNAL_SYSTEM = (
    "You write ONLY the signal logic for a fixed quant backtest harness. Output a single "
    "```python code block and NOTHING else, containing:\n"
    '  1) INSTRUMENT = "<ticker>"  (a yfinance ticker, e.g. "SPY", "QQQ", "GLD", "BTC-USD").\n'
    "  2) def generate_signal(prices, **params): returning a pandas Series of target positions.\n"
    '  3) OPTIONAL: TIMEFRAME = "1d" (default) or an intraday bar "1h"/"30m"/"15m"/"5m". Use '
    "intraday for time-of-day / session ideas; then prices.index has .hour and .minute "
    "(intraday history is ~2 years).\n"
    "  4) OPTIONAL — only if the strategy has tunable numeric parameters: declare module-level "
    "PARAMS = {name: default} and PARAM_GRID = {name: [3-6 sweep values]}, and make "
    "generate_signal take those names as keyword args (same defaults). The harness turns them "
    "into LIVE SLIDERS and a parameter heatmap.\n"
    "  5) REQUIRED — declare ALLOWED_MARKET_REGIMES = [...], the subset of the four market "
    "regimes you CLAIM this edge lives in, chosen from exactly: \"high_vol_trend\" (agitated "
    "directional move), \"low_vol_trend\" (calm orderly trend), \"high_vol_range\" (choppy/"
    "whipsaw), \"low_vol_range\" (quiet accumulation). E.g. a trend-following rule → "
    "[\"low_vol_trend\", \"high_vol_trend\"]; a mean-reversion rule → [\"high_vol_range\", "
    "\"low_vol_range\"]. The harness slices your returns by regime and checks this claim.\n\n"
    "STRICT RULES — the harness does EVERYTHING else (data, metrics, plots, significance):\n"
    '- Daily by default. For an intraday idea you MUST set TIMEFRAME (e.g. "1h") so the bars '
    "carry the time of day; otherwise a rule that reads .hour is all-zero (every daily bar is "
    "midnight).\n"
    "- `prices` has columns Open, High, Low, Close, Volume and a DatetimeIndex.\n"
    "- Return a pandas Series indexed EXACTLY like `prices`, values in {1.0 long, 0.0 flat, "
    "-1.0 short}. DECISION-TIME target; the engine shifts it +1 for you.\n"
    "- `pd` and `np` are already imported. Do NOT import anything, call get_prices, compute "
    "metrics, plot or print.\n"
    "- Return NUMERIC values: cast booleans to float before any arithmetic — e.g. "
    "(h==12).astype(float) - (h==18).astype(float), or np.where(cond, 1.0, 0.0). NEVER subtract "
    "two boolean conditions directly (numpy forbids bool - bool).\n"
    "- ★ NO LOOK-AHEAD — THIS IS ENFORCED, not a suggestion. Row t may use ONLY data up to and "
    "including row t. Trailing rolling windows and shift(+n) (looking BACKWARD) are fine; anything "
    "that reads a FUTURE bar is forbidden and will be CAUGHT and rejected automatically:\n"
    "    • NEVER use a negative shift: prices['Close'].shift(-1), .shift(-n), .diff(-1) — these read "
    "tomorrow. The classic cheat 'go long if Close.shift(-1) > Close' (buy because tomorrow rises) "
    "scores a fake Sharpe of 8+ and is the #1 rejected bug.\n"
    "    • NEVER compare today's bar to a future bar to define a 'gap'/'signal' (e.g. "
    "Close.shift(-1) - Open).\n"
    "    • NEVER normalise with a FULL-SAMPLE statistic (c - c.mean())/c.std() or c.max()/c.min() "
    "over the whole series — that leaks the future into row t. Use a TRAILING rolling mean/std "
    "(c.rolling(W).mean()) instead.\n"
    "  The harness recomputes your signal on truncated history and verifies bar t is unchanged when "
    "future bars are appended; if not, the run is discarded. Write a genuinely causal rule.\n"
    "- NO DATA-MINING: propose ONE economically-motivated rule with a real cause. Do not bury many "
    "free parameters hoping one combination fits — the search breadth is charged against the Deflated "
    "Sharpe, so an over-tuned fluke fails the gate. A modest, robust edge beats a high-Sharpe fit."
)

_SIGNAL_EXAMPLES = '''Example A — turn-of-month, no parameters (a calm-range / quiet effect):
```python
INSTRUMENT = "SPY"
ALLOWED_MARKET_REGIMES = ["low_vol_range", "low_vol_trend"]
def generate_signal(prices, **params):
    idx = prices.index
    g = pd.Series(idx.to_period("M"), index=idx)
    tdom = g.groupby(g).cumcount() + 1                       # trading day of month
    from_end = g.groupby(g).cumcount(ascending=False)       # 0 == last trading day
    return ((tdom <= 3) | (from_end == 0)).astype(float)
```

Example B — SMA trend WITH tunable parameters (a trend-regime edge; exposes sliders + heatmap):
```python
INSTRUMENT = "QQQ"
ALLOWED_MARKET_REGIMES = ["low_vol_trend", "high_vol_trend"]
PARAMS = {"fast": 50, "slow": 200}
PARAM_GRID = {"fast": [10, 20, 50, 100, 150], "slow": [100, 150, 200, 250, 300]}
def generate_signal(prices, fast=50, slow=200):
    c = prices["Close"]
    return (c.rolling(int(fast)).mean() > c.rolling(int(slow)).mean()).astype(float)
```

Example C — intraday time-of-day (long Bitcoin from 18:00 until 02:00 UTC):
```python
INSTRUMENT = "BTC-USD"
TIMEFRAME = "1h"
ALLOWED_MARKET_REGIMES = ["low_vol_trend", "high_vol_trend"]
def generate_signal(prices, **params):
    h = prices.index.hour
    return pd.Series((h >= 18) | (h < 2), index=prices.index).astype(float)
```'''


def _signal_prompt(hypothesis: str, context, dups) -> str:
    dup = "\n".join(f"- {d.id}: {d.meta.get('name', d.text)}" for d, _ in dups) or "(none)"
    return (f"{_SIGNAL_EXAMPLES}\n\nAlready-tested similar strategies (for context):\n{dup}\n\n"
            f"Now write INSTRUMENT and generate_signal for THIS hypothesis (pick the single "
            f"most relevant instrument):\n{hypothesis}")


def _signal_fix_prompt(hypothesis: str, prev_signal: str, error: str) -> str:
    """Feed a failed signal's error back to the model for one self-correction."""
    return (f"Your signal for this hypothesis FAILED when run — fix it.\n\nHYPOTHESIS:\n{hypothesis}\n\n"
            f"YOUR SIGNAL:\n```python\n{prev_signal}\n```\n\nERROR:\n{error[:600]}\n\n"
            "Rewrite it in the SAME format (INSTRUMENT, optional TIMEFRAME/PARAMS, generate_signal). "
            "Common fix: cast booleans to float before arithmetic — (cond).astype(float) — or use "
            "np.where(cond, 1.0, 0.0). Return ONLY the ```python code block.")


# Fixed harness. ``# __AGENT_SIGNAL__`` is replaced with the model's signal code.
_HARNESS_TEMPLATE = '''\
"""Agent-generated strategy backtest (constrained harness).

Only INSTRUMENT and generate_signal() were written by the model. Everything below
the agent section is the fixed Quant-OS harness (metrics, benchmark, permutation
test, bootstrap CI, DSR, plots) and cannot be hallucinated.
"""
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import seaborn as sns
from quantlab.ib_data import load_prices
from quantlab.backtest import run_backtest
from quantlab.metrics import compute_metrics, trade_stats, equity_curve, drawdown_series, sharpe_ratio
from quantlab.significance import permutation_test, bootstrap_ci, deflated_sharpe_ratio
from quantlab.causality import assess_causality
from quantlab.costs import IBKR_LIQUID_ETF, CostModel
from quantlab.robustness.monte_carlo import block_bootstrap_paths

os.makedirs("results", exist_ok=True)
START = "2005-01-01"
ANN = np.sqrt(252.0)
INSTRUMENT = "SPY"   # the agent section may override
TIMEFRAME = "1d"     # "1d" (daily) or intraday: "1h" / "30m" / "15m" / "5m" / "1m"
PARAMS = {}          # {name: default}; declare to expose live sliders + a parameter heatmap
PARAM_GRID = {}      # {name: [values, ...]}; sweep values for the parameter heatmap
ALLOWED_MARKET_REGIMES = []  # subset of {high_vol_trend, low_vol_trend, high_vol_range, low_vol_range}
                             # the agent CLAIMS the edge lives in; harness checks it (Weather Radar)

# ===================== AGENT-WRITTEN SECTION (signal only) =====================
# __AGENT_SIGNAL__
# =========================== END AGENT SECTION =================================

MODE = os.environ.get("QOS_MODE", "full")
try:
    _override = json.loads(os.environ.get("QOS_PARAMS", "{}"))
except Exception:
    _override = {}
params = {k: _override.get(k, PARAMS[k]) for k in PARAMS}


def _make_signal(p, px=None):
    px = prices if px is None else px
    if p:
        try:
            sig = generate_signal(px, **p)
        except TypeError:
            sig = generate_signal(px)  # parameter-signature fallback only
    else:
        sig = generate_signal(px)
    return pd.Series(sig, index=px.index).reindex(px.index).fillna(0.0).clip(-1, 1)


def _causality_check(p):
    """HARD look-ahead guard — the harness ENFORCES decision-time causality.

    Delegates to ``quantlab.causality.assess_causality`` (importable in this
    sandboxed subprocess). A causal signal's value at bar t must not change when
    future bars are appended; any mismatch means the signal peeked into the future
    (e.g. ``Close.shift(-1)`` or full-sample normalisation) and the run is rejected.
    """
    return assess_causality(lambda px: _make_signal(p, px=px), prices)


def _save():
    with open("results/metrics.json", "w") as f:
        json.dump(out, f, indent=2, default=str)


def _plot(fn, name):
    try:
        fn()
    except Exception as e:  # one bad plot must never lose the metrics or the rest
        out.setdefault("plot_errors", {})[name] = repr(e)
        plt.close("all"); _save()


prices = load_prices(INSTRUMENT, timeframe=TIMEFRAME, start=START)
asset_ret = prices["Close"].pct_change().fillna(0.0)
try:
    signal = _make_signal(params)
    causality = _causality_check(params)   # HARD look-ahead guard (decision-time enforcement)
except Exception as _sig_err:  # a broken model signal must fail gracefully, not crash blank
    with open("results/metrics.json", "w") as _f:
        json.dump({"instrument": INSTRUMENT, "timeframe": TIMEFRAME, "params": params,
                   "param_grid": PARAM_GRID, "metrics": {}, "warning": None,
                   "signal_error": f"{type(_sig_err).__name__}: {_sig_err}"}, _f, default=str)
    print("SIGNAL_ERROR " + repr(_sig_err))
    raise SystemExit(0)

bt = run_backtest(prices, signal, cost_model=IBKR_LIQUID_ETF)
ret, gross, pos = bt["returns"], bt["gross_returns"], bt["position"]
years = max((ret.index[-1] - ret.index[0]).days / 365.25, 1e-9)
PPY = len(ret) / years          # bars per year, auto-adapting to any timeframe
ANN = np.sqrt(PPY)
m = compute_metrics(ret, periods_per_year=PPY)
ts = trade_stats(bt["trades"])

warning = None
if int(ts.get("n_trades", 0)) == 0:
    warning = ("The strategy never opens a position on DAILY bars (0 trades). If this is an "
               "intraday / time-of-day idea (buy at 18:00, sell at 02:00), the daily-bar harness "
               "cannot express it — reformulate as a daily rule.")

eq = equity_curve(ret); bh = bt["buy_hold"]
spy_eq = None
sp500_tr = None
if TIMEFRAME in ("1d", "1day", "daily", "d"):  # S&P 500 benchmark only makes sense daily
    spy = load_prices("SPY", timeframe="1d", start=START)
    spy_ret = spy["Close"].pct_change().fillna(0.0).reindex(ret.index).fillna(0.0)
    spy_eq = equity_curve(spy_ret)
    sp500_tr = float(spy_eq.iloc[-1] - 1.0)

out = {
    "instrument": INSTRUMENT, "timeframe": TIMEFRAME, "mode": MODE, "params": params,
    "param_grid": PARAM_GRID, "warning": warning, "causality": causality, "metrics": {**m, **ts},
    "vs_benchmark": {
        "strategy_total_return": float(m["total_return"]),
        "buy_hold_total_return": float(bh.iloc[-1] - 1.0),
        "sp500_total_return": sp500_tr,
    },
}
_save()  # numbers persisted BEFORE any plot can fail

# ── Market Weather Radar: in which regime did THIS strategy actually earn? ──
# Always-on, cheap. Classifies the instrument and slices the strategy's net
# returns by regime, then checks the agent's ALLOWED_MARKET_REGIMES claim.
try:
    from quantlab import regime as _rg
    _cls = _rg.classify(prices)
    _by = _rg.regime_performance(ret, _cls, ann_factor=PPY)
    out["regime_performance"] = _by
    out["regime_current"] = _rg.current_regime(_cls)
    out["allowed_market_regimes"] = list(ALLOWED_MARKET_REGIMES)
    if ALLOWED_MARKET_REGIMES:
        _allow = set(ALLOWED_MARKET_REGIMES)
        _in = {k: v for k, v in _by.items() if k in _allow}
        _outr = {k: v for k, v in _by.items() if k not in _allow}
        _ret_in = sum(v["total_return"] for v in _in.values())
        _ret_out = sum(v["total_return"] for v in _outr.values())
        _sh_in = (sum(v["sharpe"] * v["n"] for v in _in.values())
                  / max(sum(v["n"] for v in _in.values()), 1))
        _sh_out = (sum(v["sharpe"] * v["n"] for v in _outr.values())
                   / max(sum(v["n"] for v in _outr.values()), 1))
        _pct_in = sum(v["pct_of_time"] for v in _in.values())
        out["regime_claim"] = {
            "allowed": list(ALLOWED_MARKET_REGIMES),
            "return_in_allowed": float(_ret_in), "return_out_allowed": float(_ret_out),
            "sharpe_in_allowed": float(_sh_in), "sharpe_out_allowed": float(_sh_out),
            "pct_time_in_allowed": float(_pct_in),
            # the claim holds if the strategy genuinely does better inside its regimes
            "claim_supported": bool(_ret_in > _ret_out and _sh_in >= _sh_out),
        }
    _save()
except Exception as _e:  # regime breakdown must never lose the core metrics
    out["regime_error"] = repr(_e); _save()

perm = None
if MODE == "full" and warning is None:
    try:
        perm = permutation_test(gross, asset_ret, pos, n_perm=1000, metric="sharpe", return_null=True)
        sp_pp = float(ret.mean() / ret.std(ddof=1)) if ret.std(ddof=1) > 0 else 0.0
        out["permutation"] = {k: perm[k] for k in ("observed", "p_value", "null_mean", "null_std", "n_perm")}
        out["bootstrap_ci"] = bootstrap_ci(ret, statistic="sharpe", n_boot=1000)
        # Data-mining deflation: charge the Deflated Sharpe the number of hypotheses the
        # search actually tried (the Alpha Factory streams its running trial count via
        # QOS_N_TRIALS). With n_trials=1 the DSR ignores selection and a lucky pick among
        # hundreds looks "significant"; the true bar rises with the breadth of the search.
        try:
            _ntrials = max(int(os.environ.get("QOS_N_TRIALS", "1") or 1), 1)
        except ValueError:
            _ntrials = 1
        out["n_trials"] = _ntrials
        out["deflated_sharpe"] = deflated_sharpe_ratio(sp_pp, n_obs=int(len(ret)), n_trials=_ntrials, returns=ret)
        _save()
    except Exception as e:
        out["significance_error"] = repr(e); _save()


def _p_equity():
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(eq.index, eq.values, label=f"Strategy ({INSTRUMENT}, net)", lw=1.7, color="#16a34a")
    ax.plot(bh.index, bh.values, label=f"Buy & Hold {INSTRUMENT}", lw=1.1, alpha=0.75, color="#6b7280")
    if spy_eq is not None:
        ax.plot(spy_eq.index, spy_eq.values, label="S&P 500 (SPY)", lw=1.1, alpha=0.85, ls="--", color="#2563eb")
    ax.set_yscale("log"); ax.set_title("Equity curve (net of costs) vs benchmarks")
    ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig("results/01_equity.png", dpi=110); plt.close(fig)


def _p_drawdown():
    sdd = drawdown_series(ret) * 100; bdd = drawdown_series(asset_ret) * 100
    fig, ax = plt.subplots(figsize=(9, 3.3))
    ax.fill_between(sdd.index, sdd.values, 0, color="#dc2626", alpha=0.45, label="Strategy")
    ax.plot(bdd.index, bdd.values, color="#6b7280", lw=0.8, alpha=0.7, label=f"Buy & Hold {INSTRUMENT}")
    ax.set_title("Drawdown (underwater)"); ax.set_ylabel("Drawdown (%)")
    ax.legend(loc="lower left"); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig("results/02_drawdown.png", dpi=110); plt.close(fig)


def _p_monthly():
    mt = ((1.0 + ret).resample("ME").prod() - 1.0).to_frame("r")
    mt["year"], mt["month"] = mt.index.year, mt.index.month
    pv = mt.pivot_table(index="year", columns="month", values="r") * 100.0
    fig, ax = plt.subplots(figsize=(9, max(3.0, 0.42 * len(pv))))
    sns.heatmap(pv, annot=True, fmt=".1f", center=0, cmap="RdYlGn", cbar_kws={"label": "Return (%)"},
                annot_kws={"size": 7}, ax=ax)
    ax.set_title("Monthly returns (%)"); ax.set_xlabel("Month"); ax.set_ylabel("Year")
    fig.tight_layout(); fig.savefig("results/03_monthly.png", dpi=110); plt.close(fig)


_plot(_p_equity, "01_equity")
_plot(_p_drawdown, "02_drawdown")
_plot(_p_monthly, "03_monthly")

if MODE == "full" and warning is None:
    if perm is not None:
        def _p_perm():
            null = np.asarray(perm["null_scores"], dtype=float); null = null[np.isfinite(null)]
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.hist(null, bins=40, color="#3b82f6", alpha=0.7, label="random-timing null")
            ax.axvline(perm["observed"], color="#ef4444", lw=2.0, label=f"observed {perm['observed']:.2f}")
            ax.set_title(f"Monte-Carlo permutation test  (p = {perm['p_value']:.3f})")
            ax.set_xlabel("Sharpe under random timing"); ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
            fig.savefig("results/04_permutation.png", dpi=110); plt.close(fig)
        _plot(_p_perm, "04_permutation")

    def _p_montecarlo():
        bp = block_bootstrap_paths(ret, block=20, n_paths=1000, seed=1)
        bs = bp.mean(1) / (bp.std(1, ddof=1) + 1e-12) * ANN; bs = bs[np.isfinite(bs)]
        obs = float(ret.mean() / ret.std(ddof=1) * ANN) if ret.std(ddof=1) > 0 else 0.0
        lo5, hi95 = np.percentile(bs, [5, 95])
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(bs, bins=40, color="#8b5cf6", alpha=0.7)
        ax.axvspan(lo5, hi95, color="#8b5cf6", alpha=0.12, label=f"5-95%: [{lo5:.2f}, {hi95:.2f}]")
        ax.axvline(obs, color="#ef4444", lw=2.0, label=f"observed {obs:.2f}")
        ax.axvline(0, color="#111827", lw=1.0, ls=":")
        ax.set_title("Monte-Carlo (block bootstrap) — Sharpe distribution")
        ax.set_xlabel("annualized Sharpe"); ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
        fig.savefig("results/05_montecarlo.png", dpi=110); plt.close(fig)
    _plot(_p_montecarlo, "05_montecarlo")

    def _p_robust():
        lags = [-3, -2, -1, 0, 1, 2, 3]; cmults = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]; base = IBKR_LIQUID_ETF
        g = np.full((len(lags), len(cmults)), np.nan)
        for i, lag in enumerate(lags):
            slag = signal.shift(lag).fillna(0.0)
            for j, cm in enumerate(cmults):
                cmodel = CostModel(commission_per_share=base.commission_per_share, min_commission=base.min_commission,
                                   max_commission_pct=base.max_commission_pct,
                                   slippage_bps=base.slippage_bps * cm, regulatory_bps=base.regulatory_bps * cm)
                g[i, j] = sharpe_ratio(run_backtest(prices, slag, cost_model=cmodel)["returns"],
                                       periods_per_year=PPY)
        df = pd.DataFrame(g, index=[f"{l:+d}" for l in lags], columns=[f"{c:g}x" for c in cmults])
        fig, ax = plt.subplots(figsize=(7.5, 4.3))
        sns.heatmap(df, annot=True, fmt=".2f", center=0, cmap="RdYlGn", cbar_kws={"label": "Sharpe"},
                    annot_kws={"size": 8}, ax=ax)
        ax.set_title("Robustness: net Sharpe across signal lag x cost")
        ax.set_xlabel("cost multiplier (x base)"); ax.set_ylabel("signal lag (trading days)")
        fig.tight_layout(); fig.savefig("results/06_robustness.png", dpi=110); plt.close(fig)
    _plot(_p_robust, "06_robustness")

    gp = [k for k in PARAM_GRID if k in PARAMS][:2]
    if len(gp) == 2:
        def _p_param():
            av, bv = PARAM_GRID[gp[0]], PARAM_GRID[gp[1]]
            g = np.full((len(av), len(bv)), np.nan)
            for i, a in enumerate(av):
                for j, b in enumerate(bv):
                    g[i, j] = sharpe_ratio(run_backtest(
                        prices, _make_signal({**params, gp[0]: a, gp[1]: b}),
                        cost_model=IBKR_LIQUID_ETF)["returns"], periods_per_year=PPY)
            df = pd.DataFrame(g, index=[str(x) for x in av], columns=[str(x) for x in bv])
            fig, ax = plt.subplots(figsize=(7.5, 4.6))
            sns.heatmap(df, annot=True, fmt=".2f", center=0, cmap="RdYlGn", cbar_kws={"label": "Sharpe"},
                        annot_kws={"size": 8}, ax=ax)
            ax.set_title(f"Parameter robustness: Sharpe across {gp[0]} x {gp[1]}")
            ax.set_xlabel(gp[1]); ax.set_ylabel(gp[0]); fig.tight_layout()
            fig.savefig("results/07_paramheatmap.png", dpi=110); plt.close(fig)
        _plot(_p_param, "07_paramheatmap")

# ── Opt-in EXTRA robustness for the Alpha Factory (OOS split + walk-forward + MC) ──
# Off by default (the dashboard is unaffected); the factory sets QOS_ROBUST_EXTRA=1.
if MODE == "full" and warning is None and os.environ.get("QOS_ROBUST_EXTRA"):
    try:
        import itertools
        from quantlab.robustness.walk_forward import walk_forward

        def _sh(r):
            r = pd.Series(r).dropna()
            sd = r.std(ddof=1)
            return float(r.mean() / sd * ANN) if len(r) > 2 and sd > 0 else 0.0

        # (a) explicit In-Sample / Out-of-Sample split (70/30 by time)
        n = len(ret); split = int(n * 0.7)
        is_ret, oos_ret = ret.iloc[:split], ret.iloc[split:]
        out["oos"] = {
            "is_frac": 0.7,
            "split_date": str(ret.index[split].date()) if 0 < split < n else None,
            "is_sharpe": _sh(is_ret), "oos_sharpe": _sh(oos_ret),
            "is_return": float((1.0 + is_ret).prod() - 1.0),
            "oos_return": float((1.0 + oos_ret).prod() - 1.0),
        }

        # (b) walk-forward: re-backtest the signal on each rolling OOS slice
        def _sig_on(sl, p):
            try:
                s = generate_signal(sl, **p) if p else generate_signal(sl)
            except TypeError:
                s = generate_signal(sl)
            return pd.Series(s, index=sl.index).reindex(sl.index).fillna(0.0).clip(-1, 1)

        def _run_fn(p, idx):
            sl = prices.loc[idx]
            return run_backtest(sl, _sig_on(sl, p), cost_model=IBKR_LIQUID_ETF)["returns"]

        if PARAM_GRID:
            keys = list(PARAM_GRID)
            combos = [dict(zip(keys, c)) for c in itertools.product(*(PARAM_GRID[k] for k in keys))]
            grid = combos[:12] if len(combos) > 12 else combos
        else:
            grid = [params or {}]
        tr = int(min(max(PPY * 2, 40), n // 2)); te = int(max(PPY * 0.5, 15))
        if tr + te < n:
            wf = walk_forward(ret.index, grid, _run_fn, train=tr, test=te)
            full_sh = _sh(ret)
            out["walk_forward"] = {
                "oos_sharpe": float(wf["oos_sharpe"]), "n_windows": int(wf["n_windows"]),
                "efficiency": (float(wf["oos_sharpe"]) / full_sh) if full_sh > 0 else 0.0,
                "train_bars": tr, "test_bars": te,
            }
        else:
            out["walk_forward"] = {"oos_sharpe": 0.0, "n_windows": 0, "efficiency": 0.0,
                                   "note": "series too short for walk-forward"}

        # (c) Monte-Carlo (block bootstrap) Sharpe percentiles
        bp = block_bootstrap_paths(ret, block=20, n_paths=1000, seed=1)
        bs = bp.mean(1) / (bp.std(1, ddof=1) + 1e-12) * ANN; bs = bs[np.isfinite(bs)]
        p5, p50, p95 = (float(x) for x in np.percentile(bs, [5, 50, 95]))
        out["monte_carlo"] = {"p5": p5, "p50": p50, "p95": p95,
                              "observed": _sh(ret), "frac_negative": float((bs < 0).mean())}
        _save()
    except Exception as e:  # extra robustness must never lose the core metrics
        out["robust_extra_error"] = repr(e); _save()

_save()
print(f"DONE {INSTRUMENT} mode={MODE} trades={ts.get('n_trades')} Sharpe {m['sharpe']:.2f}")
'''


def _build_run_py(signal_code: str) -> str:
    """Wrap the model's signal code in the fixed harness, producing a full run.py."""
    return _HARNESS_TEMPLATE.replace("# __AGENT_SIGNAL__", signal_code.strip())


def run_research_cycle(
    hypothesis: str,
    *,
    backend: LLMBackend | None = None,
    repo_root: Path | str | None = None,
    ideas_dir: Path | str | None = None,
    slug: str | None = None,
    k: int = 5,
    dry_run: bool = False,
    timeout: int = 600,
    harness: bool = True,
) -> dict:
    """Run one autonomous research cycle. Returns a summary dict.

    ``harness=True`` (default): the model writes only the signal logic, wrapped in
    the fixed metrics/significance/plot harness (no hallucinated analysis).
    ``harness=False``: the model writes the whole run.py (legacy/free-form).
    """
    repo_root = Path(repo_root) if repo_root else get_settings().backtest_dir
    backend = backend or get_backend()
    slug = slug or _slugify(hypothesis)

    branch = ensure_agent_branch(repo_root, slug)  # GUARDRAIL: isolated branch only
    context = retrieve_context(hypothesis, ideas_dir=ideas_dir, k=k)
    dups = dedup_against_catalog(hypothesis, repo_root=repo_root, k=k)

    signal_code = None
    if harness:
        signal_code = _extract_code(
            backend.generate(_signal_prompt(hypothesis, context, dups), system=_SIGNAL_SYSTEM))
        code = _build_run_py(signal_code)
    else:
        code = _extract_code(
            backend.generate(_code_prompt(hypothesis, context, dups), system=_CODE_SYSTEM))
    num = next_strategy_number(repo_root)
    sdir = repo_root / "strategies" / f"{num}_agent_{slug}"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "run.py").write_text(code, encoding="utf-8")

    summary = {
        "branch": branch, "num": num, "dir": str(sdir), "slug": slug,
        "dups": [(d.id, round(s, 3)) for d, s in dups],
        "context": [d.id for d, _ in context],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if signal_code is not None:
        summary["signal_code"] = signal_code
    if dry_run:
        summary["dry_run"] = True
        return summary

    # The generated run.py imports quantlab: make BOTH the run repo's src and the
    # real project src importable (so a sandboxed run_root still finds quantlab).
    src_paths = [str(repo_root / "src"), str(get_settings().backtest_dir / "src")]
    env = {**os.environ,
           "PYTHONPATH": os.pathsep.join([*src_paths, os.environ.get("PYTHONPATH", "")])}
    def _run_and_parse():
        p = subprocess.run([sys.executable, "run.py"], cwd=sdir, env=env,
                           capture_output=True, text=True, timeout=timeout)
        mp = sdir / "results" / "metrics.json"
        m = None
        if mp.exists():
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                m = None
        return m, p

    metrics, proc = _run_and_parse()
    # One self-correcting retry: feed a signal error (or a blank crash) back to the model.
    if harness and signal_code is not None:
        err = (metrics or {}).get("signal_error")
        if err or metrics is None:
            fail = err or ((proc.stdout or "")[-800:] + "\n" + (proc.stderr or "")[-1600:])
            signal_code = _extract_code(backend.generate(
                _signal_fix_prompt(hypothesis, signal_code, fail), system=_SIGNAL_SYSTEM))
            summary["signal_code"] = signal_code
            summary["retried"] = True
            (sdir / "run.py").write_text(_build_run_py(signal_code), encoding="utf-8")
            metrics, proc = _run_and_parse()

    report = backend.generate(_report_prompt(hypothesis, metrics, proc.stdout), system=_REPORT_SYSTEM)
    (sdir / "REPORT.md").write_text(report, encoding="utf-8")

    sha = agent_commit(repo_root, f"feat(agent): {num} {slug}",
                       paths=[sdir.relative_to(repo_root).as_posix()])  # GUARDRAIL: no push

    output = proc.stdout or ""
    if proc.returncode != 0 and proc.stderr:
        output += "\n--- stderr ---\n" + proc.stderr  # surface the real failure
    summary.update({
        "status": "ok" if metrics is not None else "no-metrics",
        "returncode": proc.returncode,
        "metrics": metrics,
        "sha": sha,
        "stdout_tail": output[-3000:],
    })
    return summary
