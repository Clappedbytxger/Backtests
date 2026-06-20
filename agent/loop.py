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
    "You write ONLY the signal logic for a fixed quant backtest harness. Output a "
    "single ```python code block containing EXACTLY two things and nothing else:\n"
    '  1) INSTRUMENT = "<ticker>"   (a yfinance ticker, e.g. "SPY", "QQQ", "GLD", "^GSPC")\n'
    "  2) def generate_signal(prices): returning a pandas Series of target positions.\n\n"
    "STRICT RULES — the harness does EVERYTHING else, do NOT write any of it:\n"
    "- `prices` is a DataFrame with columns Open, High, Low, Close, Volume and a DatetimeIndex.\n"
    "- Return a pandas Series indexed EXACTLY like `prices`, values in {1.0 long, 0.0 flat, "
    "-1.0 short}. It is the DECISION-TIME target; the engine shifts it +1 for you.\n"
    "- `pd` (pandas) and `np` (numpy) are ALREADY imported — use them directly. Do NOT add "
    "any import, do NOT call get_prices, do NOT compute metrics, do NOT plot, do NOT print.\n"
    "- NO LOOK-AHEAD: a value at row t may use only data up to and including row t "
    "(rolling/shift are fine; never use .shift(-n) or future rows)."
)

_SIGNAL_EXAMPLES = '''Example A — turn-of-month (long the last + first 3 trading days of each month):
```python
INSTRUMENT = "SPY"
def generate_signal(prices):
    idx = prices.index
    g = pd.Series(idx.to_period("M"), index=idx)
    tdom = g.groupby(g).cumcount() + 1                       # trading day of month
    from_end = g.groupby(g).cumcount(ascending=False)       # 0 == last trading day
    return ((tdom <= 3) | (from_end == 0)).astype(float)
```

Example B — 50/200 SMA trend filter (long when the fast average is above the slow):
```python
INSTRUMENT = "QQQ"
def generate_signal(prices):
    c = prices["Close"]
    return (c.rolling(50).mean() > c.rolling(200).mean()).astype(float)
```'''


def _signal_prompt(hypothesis: str, context, dups) -> str:
    dup = "\n".join(f"- {d.id}: {d.meta.get('name', d.text)}" for d, _ in dups) or "(none)"
    return (f"{_SIGNAL_EXAMPLES}\n\nAlready-tested similar strategies (for context):\n{dup}\n\n"
            f"Now write INSTRUMENT and generate_signal for THIS hypothesis (pick the single "
            f"most relevant instrument):\n{hypothesis}")


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
from quantlab.data import get_prices
from quantlab.backtest import run_backtest
from quantlab.metrics import compute_metrics, trade_stats, equity_curve, drawdown_series, sharpe_ratio
from quantlab.significance import permutation_test, bootstrap_ci, deflated_sharpe_ratio
from quantlab.costs import IBKR_LIQUID_ETF, CostModel
from quantlab.robustness.monte_carlo import block_bootstrap_paths

os.makedirs("results", exist_ok=True)
START = "2005-01-01"
INSTRUMENT = "SPY"  # default; the agent section may override

# ===================== AGENT-WRITTEN SECTION (signal only) =====================
# __AGENT_SIGNAL__
# =========================== END AGENT SECTION =================================

prices = get_prices(INSTRUMENT, start=START)
signal = pd.Series(generate_signal(prices), index=prices.index).reindex(prices.index).fillna(0.0).clip(-1, 1)

bt = run_backtest(prices, signal, cost_model=IBKR_LIQUID_ETF)
ret, gross, pos = bt["returns"], bt["gross_returns"], bt["position"]

m = compute_metrics(ret)
ts = trade_stats(bt["trades"])

asset_ret = prices["Close"].pct_change().fillna(0.0)
perm = permutation_test(gross, asset_ret, pos, n_perm=1000, metric="sharpe", return_null=True)
boot = bootstrap_ci(ret, statistic="sharpe", n_boot=1000)
sp_pp = float(ret.mean() / ret.std(ddof=1)) if ret.std(ddof=1) > 0 else 0.0
dsr = deflated_sharpe_ratio(sp_pp, n_obs=int(len(ret)), n_trials=1, returns=ret)

# benchmark: S&P 500 buy & hold
spy = get_prices("SPY", start=START)
spy_ret = spy["Close"].pct_change().fillna(0.0).reindex(ret.index).fillna(0.0)
spy_eq = equity_curve(spy_ret)
eq = equity_curve(ret)
bh = bt["buy_hold"]
ANN = np.sqrt(252)

# 1) equity curve vs Buy & Hold + S&P 500
fig, ax = plt.subplots(figsize=(9, 4.4))
ax.plot(eq.index, eq.values, label=f"Strategy ({INSTRUMENT}, net)", lw=1.7, color="#16a34a")
ax.plot(bh.index, bh.values, label=f"Buy & Hold {INSTRUMENT}", lw=1.1, alpha=0.75, color="#6b7280")
ax.plot(spy_eq.index, spy_eq.values, label="S&P 500 (SPY)", lw=1.1, alpha=0.85, ls="--", color="#2563eb")
ax.set_yscale("log"); ax.set_title("Equity curve (net of costs) vs benchmarks")
ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
fig.savefig("results/01_equity.png", dpi=110); plt.close(fig)

# 2) drawdown (underwater) vs buy & hold
dd = drawdown_series(ret) * 100
bh_dd = drawdown_series(asset_ret) * 100
fig, ax = plt.subplots(figsize=(9, 3.3))
ax.fill_between(dd.index, dd.values, 0, color="#dc2626", alpha=0.45, label="Strategy")
ax.plot(bh_dd.index, bh_dd.values, color="#6b7280", lw=0.8, alpha=0.7, label=f"Buy & Hold {INSTRUMENT}")
ax.set_title("Drawdown (underwater)"); ax.set_ylabel("Drawdown (%)")
ax.legend(loc="lower left"); ax.grid(alpha=0.3); fig.tight_layout()
fig.savefig("results/02_drawdown.png", dpi=110); plt.close(fig)

# 3) monthly returns heatmap
mt = ((1.0 + ret).resample("ME").prod() - 1.0).to_frame("r")
mt["year"], mt["month"] = mt.index.year, mt.index.month
pivot = mt.pivot_table(index="year", columns="month", values="r") * 100.0
fig, ax = plt.subplots(figsize=(9, max(3.0, 0.42 * len(pivot))))
sns.heatmap(pivot, annot=True, fmt=".1f", center=0, cmap="RdYlGn",
            cbar_kws={"label": "Return (%)"}, annot_kws={"size": 7}, ax=ax)
ax.set_title("Monthly returns (%)"); ax.set_xlabel("Month"); ax.set_ylabel("Year")
fig.tight_layout(); fig.savefig("results/03_monthly.png", dpi=110); plt.close(fig)

# 4) Monte-Carlo permutation test (random timing)
null = np.asarray(perm["null_scores"], dtype=float)
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(null, bins=40, color="#3b82f6", alpha=0.7, label="random-timing null")
ax.axvline(perm["observed"], color="#ef4444", lw=2.0, label=f"observed {perm['observed']:.2f}")
ax.set_title(f"Monte-Carlo permutation test  (p = {perm['p_value']:.3f})")
ax.set_xlabel("Sharpe under random timing"); ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
fig.savefig("results/04_permutation.png", dpi=110); plt.close(fig)

# 5) Monte-Carlo block bootstrap — distribution of the realised Sharpe
paths = block_bootstrap_paths(ret, block=20, n_paths=1000, seed=1)
boot_sharpe = paths.mean(1) / (paths.std(1, ddof=1) + 1e-12) * ANN
obs_sharpe = float(ret.mean() / ret.std(ddof=1) * ANN) if ret.std(ddof=1) > 0 else 0.0
lo5, hi95 = np.percentile(boot_sharpe, [5, 95])
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(boot_sharpe, bins=40, color="#8b5cf6", alpha=0.7)
ax.axvspan(lo5, hi95, color="#8b5cf6", alpha=0.12, label=f"5-95%: [{lo5:.2f}, {hi95:.2f}]")
ax.axvline(obs_sharpe, color="#ef4444", lw=2.0, label=f"observed {obs_sharpe:.2f}")
ax.axvline(0, color="#111827", lw=1.0, ls=":")
ax.set_title("Monte-Carlo (block bootstrap) — Sharpe distribution")
ax.set_xlabel("annualized Sharpe"); ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
fig.savefig("results/05_montecarlo.png", dpi=110); plt.close(fig)

# 6) robustness heatmap — net Sharpe across signal lag x cost multiplier
lags = [-3, -2, -1, 0, 1, 2, 3]
cmults = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
base = IBKR_LIQUID_ETF
grid = np.full((len(lags), len(cmults)), np.nan)
for i, lag in enumerate(lags):
    slag = signal.shift(lag).fillna(0.0)
    for j, cm in enumerate(cmults):
        cmodel = CostModel(commission_per_share=base.commission_per_share,
                           min_commission=base.min_commission,
                           max_commission_pct=base.max_commission_pct,
                           slippage_bps=base.slippage_bps * cm,
                           regulatory_bps=base.regulatory_bps * cm)
        grid[i, j] = sharpe_ratio(run_backtest(prices, slag, cost_model=cmodel)["returns"])
robust = pd.DataFrame(grid, index=[f"{l:+d}" for l in lags], columns=[f"{c:g}x" for c in cmults])
fig, ax = plt.subplots(figsize=(7.5, 4.3))
sns.heatmap(robust, annot=True, fmt=".2f", center=0, cmap="RdYlGn",
            cbar_kws={"label": "Sharpe"}, annot_kws={"size": 8}, ax=ax)
ax.set_title("Robustness: net Sharpe across signal lag x cost")
ax.set_xlabel("cost multiplier (x base)"); ax.set_ylabel("signal lag (trading days)")
fig.tight_layout(); fig.savefig("results/06_robustness.png", dpi=110); plt.close(fig)

out = {
    "instrument": INSTRUMENT,
    "metrics": {**m, **ts},
    "permutation": {k: perm[k] for k in ("observed", "p_value", "null_mean", "null_std", "n_perm")},
    "bootstrap_ci": boot,
    "deflated_sharpe": dsr,
    "vs_benchmark": {
        "strategy_total_return": float(m["total_return"]),
        "buy_hold_total_return": float(bh.iloc[-1] - 1.0),
        "sp500_total_return": float(spy_eq.iloc[-1] - 1.0),
    },
}
with open("results/metrics.json", "w") as f:
    json.dump(out, f, indent=2, default=str)
print(f"DONE {INSTRUMENT}: Sharpe {m['sharpe']:.2f} CAGR {m['cagr']*100:.1f}% "
      f"perm_p {perm['p_value']:.3f} DSR {dsr['psr_deflated']:.3f}")
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
    proc = subprocess.run([sys.executable, "run.py"], cwd=sdir, env=env,
                          capture_output=True, text=True, timeout=timeout)
    metrics_path = sdir / "results" / "metrics.json"
    metrics = None
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metrics = None

    report = backend.generate(_report_prompt(hypothesis, metrics, proc.stdout), system=_REPORT_SYSTEM)
    (sdir / "REPORT.md").write_text(report, encoding="utf-8")

    sha = agent_commit(repo_root, f"feat(agent): {num} {slug}",
                       paths=[sdir.relative_to(repo_root).as_posix()])  # GUARDRAIL: no push

    summary.update({
        "status": "ok" if metrics is not None else "no-metrics",
        "returncode": proc.returncode,
        "metrics": metrics,
        "sha": sha,
        "stdout_tail": proc.stdout[-1500:],
    })
    return summary
