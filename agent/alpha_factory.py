"""Alpha Factory — an autonomous, continuously running research worker.

Runs an *infinite* loop (until stopped) that, per iteration:
  A. generates ONE specific trading hypothesis (LLM + RAG, de-duplicated),
  B. backtests it via the fixed Quant-OS harness (``agent.loop.run_research_cycle``),
  C. runs the mandatory robustness battery — OOS split, walk-forward, Monte-Carlo
     permutation + block-bootstrap, parameter/cost robustness — all inside an
     isolated subprocess (``run.py``) so heavy DataFrames never live in this worker,
  D. applies a strict quality gate; passers get a structured Markdown report in
     ``reports/pending_review/``, rejects get one line in a JSONL log (for de-dup).

RAM discipline (target: stable well under 16/24 GB):
  * the only heavy compute (backtest + bootstrap) runs in a child process that is
    torn down every iteration — the OS reclaims all of it;
  * each hypothesis runs in a throwaway temp git repo that is ``rmtree``'d in a
    ``finally``; nothing is committed to the real repo;
  * the worker keeps NO per-iteration history in memory — only small counters and a
    compact set of seen slugs (strings); every iteration ends with an explicit
    ``del`` of its locals and ``gc.collect()``.

Run:
    .venv/Scripts/python.exe -m agent.alpha_factory                 # real model, infinite
    .venv/Scripts/python.exe -m agent.alpha_factory --backend mock --max-iter 2   # smoke
    .venv/Scripts/python.exe -m agent.alpha_factory --once          # a single iteration
Stop: Ctrl-C, or create the file ``reports/alpha_factory/STOP``.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from quantlab.config import get_settings

from .llm import get_backend
from .loop import _slugify, next_strategy_number, run_research_cycle

# ── strict, catalog-conform quality gate ─────────────────────────────────────


@dataclass
class GateThresholds:
    min_oos_sharpe: float = 0.7
    max_drawdown: float = 0.25          # absolute fraction
    max_perm_p: float = 0.05
    min_dsr: float = 0.5
    min_trades: int = 30
    min_wf_windows: int = 3
    require_beats_buyhold: bool = True
    require_mc_p5_positive: bool = True  # 5th-pct block-bootstrap Sharpe > 0
    require_causal: bool = True          # hard look-ahead guard must pass
    max_sane_sharpe: float = 4.0         # net-of-cost Sharpe above this ⇒ look-ahead/data bug


def _num(d, *path, default=None):
    """Safe nested lookup returning a float (or default)."""
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur or cur[k] is None:
            return default
        cur = cur[k]
    try:
        return float(cur)
    except (TypeError, ValueError):
        return default


def evaluate_gate(metrics: dict, th: GateThresholds) -> dict:
    """Return {'passed': bool, 'checks': {name: {ok, value, threshold}}, 'reason': str}."""
    if not metrics or metrics.get("warning") or metrics.get("signal_error"):
        return {"passed": False, "checks": {},
                "reason": metrics.get("signal_error") or metrics.get("warning") or "no metrics"}

    n_trades = _num(metrics, "metrics", "n_trades", default=0)
    oos_sharpe = _num(metrics, "oos", "oos_sharpe")
    maxdd = _num(metrics, "metrics", "max_drawdown")
    perm_p = _num(metrics, "permutation", "p_value")
    dsr = _num(metrics, "deflated_sharpe", "psr_deflated")
    wf_windows = _num(metrics, "walk_forward", "n_windows", default=0)
    wf_oos = _num(metrics, "walk_forward", "oos_sharpe", default=0.0)
    strat_tr = _num(metrics, "vs_benchmark", "strategy_total_return")
    bh_tr = _num(metrics, "vs_benchmark", "buy_hold_total_return")
    mc_p5 = _num(metrics, "monte_carlo", "p5")
    full_sharpe = _num(metrics, "metrics", "sharpe")
    causal = metrics.get("causality") if isinstance(metrics.get("causality"), dict) else None

    checks = {
        "trades": {"ok": n_trades is not None and n_trades >= th.min_trades, "value": n_trades, "threshold": f">= {th.min_trades}"},
        "oos_sharpe": {"ok": oos_sharpe is not None and oos_sharpe >= th.min_oos_sharpe, "value": oos_sharpe, "threshold": f">= {th.min_oos_sharpe}"},
        "max_drawdown": {"ok": maxdd is not None and abs(maxdd) <= th.max_drawdown, "value": maxdd, "threshold": f"<= {th.max_drawdown}"},
        "permutation_p": {"ok": perm_p is not None and perm_p <= th.max_perm_p, "value": perm_p, "threshold": f"<= {th.max_perm_p}"},
        "deflated_sharpe": {"ok": dsr is not None and dsr >= th.min_dsr, "value": dsr, "threshold": f">= {th.min_dsr}"},
        "walk_forward": {"ok": wf_windows is not None and wf_windows >= th.min_wf_windows and (wf_oos or 0) > 0,
                          "value": f"{wf_windows} win / oos {wf_oos:.2f}" if wf_oos is not None else None,
                          "threshold": f">= {th.min_wf_windows} windows, oos>0"},
    }
    if th.require_beats_buyhold:
        ok = strat_tr is not None and bh_tr is not None and strat_tr > bh_tr
        checks["beats_buy_hold"] = {"ok": ok, "value": (None if strat_tr is None else round(strat_tr, 3)), "threshold": f"> buy&hold ({bh_tr})"}
    if th.require_mc_p5_positive:
        checks["mc_p5_positive"] = {"ok": mc_p5 is not None and mc_p5 > 0, "value": mc_p5, "threshold": "> 0"}
    if th.require_causal:
        # HARD look-ahead gate: the harness's causality probe must have run AND passed.
        ok = bool(causal and causal.get("causal") is True)
        checks["causal_no_lookahead"] = {
            "ok": ok,
            "value": (f"{causal.get('violations')} viol / {causal.get('boundary_bars_checked')} bars"
                      if causal else "MISSING"),
            "threshold": "no future data (0 violations)"}
    # Sanity ceiling: a net-of-cost Sharpe this high is not a real edge — it is the
    # signature of look-ahead or a data artifact (e.g. the shift(-1) cheat → Sharpe 8).
    checks["sane_sharpe"] = {
        "ok": full_sharpe is not None and abs(full_sharpe) <= th.max_sane_sharpe,
        "value": full_sharpe, "threshold": f"|Sharpe| <= {th.max_sane_sharpe}"}

    failed = [k for k, v in checks.items() if not v["ok"]]
    return {"passed": not failed, "checks": checks,
            "reason": "PASS" if not failed else "fail: " + ", ".join(failed)}


# ── hypothesis generation (LLM + rotating context, de-duplicated) ─────────────

_HYP_SYSTEM = (
    "You are a senior quant idea generator. Propose ONE specific, testable trading "
    "hypothesis in 2-3 sentences. State: the SINGLE instrument (a liquid yfinance "
    "ticker like SPY, QQQ, GLD, TLT, BTC-USD, EURUSD=X, CL=F), the timeframe (daily or "
    "intraday), the exact indicator/logic, and a one-line ECONOMIC rationale (why the "
    "edge should exist). It must be implementable on price/volume data alone with no "
    "look-ahead. CRUCIALLY, also state in which MARKET REGIME(S) the edge should work — "
    "choose from: high-vol trending, low-vol trending, high-vol choppy/range, low-vol "
    "quiet/range — because a strategy's edge is regime-dependent (a trend rule needs a "
    "trending tape; a mean-reversion rule needs a range). You MAY also gate the edge on "
    "INSTITUTIONAL POSITIONING from the weekly CFTC Commitments-of-Traders data (available "
    "for futures/commodities/FX/indices via quantlab.cot): e.g. 'go long gold only when the "
    "commercial COT index > 80' (smart money very net-long) or 'fade managed money when its "
    "COT z-score > +2' (overcrowded trend-follower long). State any such COT condition "
    "explicitly. Be original and avoid the listed already-tried ideas. Output ONLY the "
    "hypothesis text, no preamble."
)

_THEMES = [
    "a mean-reversion effect on a liquid equity index ETF",
    "a cross-asset momentum / trend-following rule on a commodity future",
    "a seasonal or turn-of-month calendar effect",
    "a volatility-regime filter that gates exposure",
    "a gap / overnight-vs-intraday effect on an ETF",
    "a relative-strength rotation between two related assets",
    "a moving-average or breakout trend rule on gold or bonds",
    "a crypto trend or weekend-effect rule on BTC-USD",
    "an RSI / oscillator mean-reversion rule on a single name",
    "a term-structure / carry proxy on a commodity ETF",
    "a COT-positioning filter (commercial extreme or managed-money overcrowding) on a futures market",
]


def generate_hypothesis(backend, avoid_slugs: set[str], ideas_dir: Path, rng: random.Random) -> tuple[str, str]:
    """Generate one fresh hypothesis + slug, biased toward an unused theme."""
    theme = rng.choice(_THEMES)
    recent = list(avoid_slugs)
    rng.shuffle(recent)
    avoid = ", ".join(recent[:25]) or "(none yet)"
    prompt = (f"Theme to explore this round: {theme}.\n\n"
              f"Already-tried ideas to AVOID (do not repeat these):\n{avoid}\n\n"
              "Write the hypothesis now.")
    text = backend.generate(prompt, system=_HYP_SYSTEM, max_tokens=220, temperature=0.9).strip()
    text = " ".join(text.split())[:600]
    return text, _slugify(text)


# ── one isolated iteration (throwaway temp repo + subprocess backtest) ────────


def _limit_threads() -> None:
    """Cap BLAS/OpenMP threads in this process (inherited by the backtest subprocess).

    Two reasons: (1) on many-core Windows OpenBLAS pre-allocates huge per-thread buffers
    and dies with 'Memory allocation failed after 10 retries'; (2) fewer threads = a
    smaller, more predictable memory footprint — exactly the factory's RAM goal.
    """
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(var, "4")


def _seed_repo(tmp: Path, real_repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(tmp)], capture_output=True)
    for k, v in (("user.email", "alpha-factory@quant-os.local"), ("user.name", "Alpha Factory")):
        subprocess.run(["git", "-C", str(tmp), "config", k, v], capture_output=True)
    (tmp / "strategies").mkdir()
    (tmp / "strategies" / ".gitkeep").write_text("")
    catalog = real_repo / "CATALOG.md"
    if catalog.exists():
        shutil.copy(catalog, tmp / "CATALOG.md")  # seed de-dup against the real catalog
    subprocess.run(["git", "-C", str(tmp), "add", "-A"], capture_output=True)
    subprocess.run(["git", "-C", str(tmp), "commit", "-m", "seed"], capture_output=True)


def run_iteration(hypothesis: str, slug: str, backend, settings, timeout: int = 600) -> dict:
    """Run one full research+robustness cycle in an isolated temp repo.

    Returns a small dict: {metrics, signal_code, instrument, plots:{name->abs path in
    a PERSISTENT temp that the caller must clean}, stdout_tail}. Heavy data never
    crosses back — only the parsed metrics.json and (for passers) plot files.
    """
    _limit_threads()
    tmp = Path(tempfile.mkdtemp(prefix="alpha_factory_"))
    try:
        _seed_repo(tmp, settings.backtest_dir)
        res = run_research_cycle(hypothesis, backend=backend, repo_root=tmp,
                                 ideas_dir=settings.ideas_dir, slug=slug,
                                 dry_run=False, timeout=timeout)
        sdir = Path(res["dir"])
        metrics = res.get("metrics") if isinstance(res.get("metrics"), dict) else {}
        plots = {}
        rdir = sdir / "results"
        if rdir.exists():
            for png in sorted(rdir.glob("*.png")):
                plots[png.stem] = png.read_bytes()  # bytes; small, freed after the report writes
        return {
            "metrics": metrics,
            "signal_code": res.get("signal_code"),
            "instrument": metrics.get("instrument"),
            "timeframe": metrics.get("timeframe"),
            "plots": plots,
            "stdout_tail": res.get("stdout_tail", "")[-1500:],
            "retried": res.get("retried", False),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # GUARANTEE: temp data gone every iteration


# ── report generation (strict 5-section schema) ──────────────────────────────

_NARRATIVE_SYSTEM = (
    "You are the agent author of a quant strategy review. Given a hypothesis, its signal "
    "code and its measured metrics, write THREE sections of German prose, each preceded by "
    "its exact heading and nothing else:\n"
    "### 1. Theoretische Fundierung & Hypothese\n"
    "### 2. Exakte Regeln (Entry, Exit, Position Sizing, Risikomanagement)\n"
    "### 5. Fazit & Risikowarnung des Agenten\n"
    "Section 1: why this alpha should exist (economic cause). Section 2: the precise rules in "
    "words (entry, exit, sizing, risk) consistent with the code. Section 5: an HONEST verdict — "
    "where are the weaknesses, cost/regime risks, is it standalone or overlay. Explicitly state "
    "that the signal passed the harness's causality (no-look-ahead) probe and is decision-time "
    "honest, and flag if the edge looks like beta rather than timing skill. Be concise and "
    "specific. Do NOT invent numbers; refer to the metrics qualitatively."
)


def _fmt(x, suffix="", scale=1.0, d=2):
    return f"{x * scale:.{d}f}{suffix}" if isinstance(x, (int, float)) else "n/a"


def write_report(report_dir: Path, num: str, slug: str, hypothesis: str, result: dict,
                 gate: dict, backend) -> Path:
    """Assemble the strict-schema Markdown report for a passing strategy."""
    m = result["metrics"]
    mm = m.get("metrics", {})
    oos = m.get("oos", {})
    wf = m.get("walk_forward", {})
    perm = m.get("permutation", {})
    mc = m.get("monte_carlo", {})
    dsr = m.get("deflated_sharpe", {})
    vb = m.get("vs_benchmark", {})
    name = slug.replace("-", " ").title()
    sid = f"AF-{num}"

    # LLM narrative (sections 1, 2, 5) — numbers stay out of the model's hands.
    prompt = (f"HYPOTHESIS:\n{hypothesis}\n\nINSTRUMENT: {result.get('instrument')} "
              f"({result.get('timeframe')})\n\nSIGNAL CODE:\n```python\n{result.get('signal_code')}\n```\n\n"
              f"KEY METRICS (for context, do not quote verbatim): full Sharpe "
              f"{_fmt(mm.get('sharpe'))}, OOS Sharpe {_fmt(oos.get('oos_sharpe'))}, MaxDD "
              f"{_fmt(mm.get('max_drawdown'), '%', 100, 1)}, perm p {_fmt(perm.get('p_value'), '', 1, 3)}.\n\n"
              "Write sections 1, 2 and 5 now.")
    try:
        narrative = backend.generate(prompt, system=_NARRATIVE_SYSTEM, max_tokens=900, temperature=0.4).strip()
    except Exception as e:  # narrative is best-effort; the numbers are the substance
        narrative = (f"### 1. Theoretische Fundierung & Hypothese\n{hypothesis}\n\n"
                     f"### 2. Exakte Regeln (Entry, Exit, Position Sizing, Risikomanagement)\n"
                     f"Siehe Signal-Code unten.\n\n"
                     f"### 5. Fazit & Risikowarnung des Agenten\n(Agenten-Narrativ nicht verfügbar: {e})")

    # programmatic, hallucination-proof sections 3 & 4
    sec3 = (
        "### 3. Backtest-Ergebnisse (In-Sample vs. Out-of-Sample)\n\n"
        f"Instrument: **{result.get('instrument')}** ({result.get('timeframe')}), Trades: "
        f"**{int(mm.get('n_trades') or 0)}**\n\n"
        "| Kennzahl | Wert |\n|---|---|\n"
        f"| Sharpe (voll, netto) | {_fmt(mm.get('sharpe'))} |\n"
        f"| Sharpe In-Sample (70%) | {_fmt(oos.get('is_sharpe'))} |\n"
        f"| **Sharpe Out-of-Sample (30%)** | **{_fmt(oos.get('oos_sharpe'))}** |\n"
        f"| OOS-Split-Datum | {oos.get('split_date', 'n/a')} |\n"
        f"| CAGR | {_fmt(mm.get('cagr'), '%', 100, 1)} |\n"
        f"| Max Drawdown | {_fmt(mm.get('max_drawdown'), '%', 100, 1)} |\n"
        f"| Gesamt-Return Strategie | {_fmt(vb.get('strategy_total_return'), '%', 100, 1)} |\n"
        f"| Gesamt-Return Buy & Hold | {_fmt(vb.get('buy_hold_total_return'), '%', 100, 1)} |\n"
        f"| Gesamt-Return S&P 500 | {_fmt(vb.get('sp500_total_return'), '%', 100, 1)} |\n\n"
        "Equity-Kurve (netto) vs. Benchmarks: siehe `assets/01_equity.png`.\n"
    )
    sec4 = (
        "### 4. Ergebnisse der Robustheitstests\n\n"
        "| Test | Ergebnis |\n|---|---|\n"
        f"| Monte-Carlo Permutation (p-Value) | {_fmt(perm.get('p_value'), '', 1, 3)} "
        f"(Null Ø {_fmt(perm.get('null_mean'))}, n={int(perm.get('n_perm') or 0)}) |\n"
        f"| Block-Bootstrap Sharpe 5/50/95-Perzentil | {_fmt(mc.get('p5'))} / {_fmt(mc.get('p50'))} / {_fmt(mc.get('p95'))} |\n"
        f"| Anteil negativer Bootstrap-Pfade | {_fmt(mc.get('frac_negative'), '%', 100, 1)} |\n"
        f"| Walk-Forward OOS-Sharpe ({int(wf.get('n_windows') or 0)} Fenster) | {_fmt(wf.get('oos_sharpe'))} |\n"
        f"| Walk-Forward-Effizienz (OOS/voll) | {_fmt(wf.get('efficiency'))} |\n"
        f"| Deflated Sharpe Ratio | {_fmt(dsr.get('psr_deflated'))} |\n\n"
        "Parameter-Robustheit (Sharpe über Parameter-Gitter): siehe `assets/07_paramheatmap.png` "
        "(falls Parameter vorhanden); Lag×Kosten-Sensitivität: `assets/06_robustness.png`; "
        "Monte-Carlo-Verteilung: `assets/05_montecarlo.png`.\n\n"
        "**Gate-Auswertung (alle bestanden):**\n\n| Check | Wert | Schwelle |\n|---|---|---|\n"
        + "".join(f"| {k} | {v['value']} | {v['threshold']} |\n" for k, v in gate["checks"].items())
    )
    sec4 += _regime_section(m)

    body = (f"## {name} (ID: {sid})\n\n"
            f"> Autonom generiert von der Alpha Factory am "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. "
            f"Vor jeder Verwendung manuell prüfen.\n\n"
            f"**Hypothese:** {hypothesis}\n\n"
            f"{_section(narrative, '### 1')}\n\n{_section(narrative, '### 2')}\n\n"
            f"{sec3}\n{sec4}\n\n{_section(narrative, '### 5')}\n\n"
            f"---\n\n<details><summary>Signal-Code</summary>\n\n```python\n"
            f"{result.get('signal_code')}\n```\n</details>\n")

    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / f"{sid}_{slug}.md"
    out_path.write_text(body, encoding="utf-8")
    # copy the key plots next to the report
    assets = report_dir / "assets" / f"{sid}_{slug}"
    if result.get("plots"):
        assets.mkdir(parents=True, exist_ok=True)
        for stem, data in result["plots"].items():
            (assets / f"{stem}.png").write_bytes(data)
    return out_path


def _section(narrative: str, heading: str) -> str:
    """Extract a '### N ...' section from the LLM narrative; fallback to the heading."""
    import re
    m = re.search(rf"({re.escape(heading)}[^\n]*\n.*?)(?=\n###\s|\Z)", narrative, re.S)
    return m.group(1).strip() if m else f"{heading}. (nicht generiert)"


_REGIME_LABEL = {
    "high_vol_trend": "High Vol · Trending", "low_vol_trend": "Low Vol · Trending",
    "high_vol_range": "High Vol · Choppy", "low_vol_range": "Low Vol · Quiet",
}


def _regime_section(metrics: dict) -> str:
    """Market-Weather-Radar breakdown: per-regime PnL + the agent's claim check."""
    by = metrics.get("regime_performance")
    if not isinstance(by, dict) or not by:
        return ""
    rows = "".join(
        f"| {_REGIME_LABEL.get(k, k)} | {_fmt(v.get('pct_of_time'), '%', 100, 1)} | "
        f"{_fmt(v.get('total_return'), '%', 100, 1)} | {_fmt(v.get('sharpe'))} | "
        f"{_fmt(v.get('win_rate'), '%', 100, 1)} | {_fmt(v.get('max_drawdown'), '%', 100, 1)} |\n"
        for k, v in by.items()
    )
    out = (
        "\n\n#### Market-Weather-Radar — Performance je Marktregime\n\n"
        "| Regime | Zeitanteil | Return | Sharpe | Trefferquote | MaxDD |\n"
        "|---|---|---|---|---|---|\n" + rows
    )
    claim = metrics.get("regime_claim")
    if isinstance(claim, dict) and claim.get("allowed"):
        allowed = ", ".join(_REGIME_LABEL.get(c, c) for c in claim["allowed"])
        verdict = "✅ BESTÄTIGT" if claim.get("claim_supported") else "⚠️ NICHT bestätigt"
        out += (
            f"\n**Agenten-Claim (Soll vs. Ist):** Edge soll in *{allowed}* leben — {verdict}. "
            f"Return innerhalb der erlaubten Regimes {_fmt(claim.get('return_in_allowed'), '%', 100, 1)} "
            f"vs. außerhalb {_fmt(claim.get('return_out_allowed'), '%', 100, 1)}; "
            f"Sharpe innen {_fmt(claim.get('sharpe_in_allowed'))} vs. außen "
            f"{_fmt(claim.get('sharpe_out_allowed'))} "
            f"(Zeitanteil in erlaubten Regimes {_fmt(claim.get('pct_time_in_allowed'), '%', 100, 1)}).\n"
        )
    return out


# ── the infinite loop ────────────────────────────────────────────────────────

_STOP = False


def _install_signal_handlers():
    def _handler(signum, frame):
        global _STOP
        _STOP = True
        print("\n[alpha-factory] stop signal received — finishing current iteration…", flush=True)
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _handler)
        except (ValueError, OSError):
            pass  # not in main thread / unsupported


def _load_seen(reject_log: Path, real_repo: Path) -> set[str]:
    """Compact set of already-seen slugs (rejects + catalog), for de-dup. Strings only."""
    seen: set[str] = set()
    if reject_log.exists():
        for line in reject_log.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line).get("slug", ""))
            except json.JSONDecodeError:
                continue
    try:
        from quantlab.registry import parse_catalog
        for _num_, row in parse_catalog(real_repo / "CATALOG.md").items():
            seen.add(_slugify(row.get("name", "")))
    except Exception:
        pass
    seen.discard("")
    return seen


def _rss_mb() -> float | None:
    try:
        import psutil  # optional
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        return None


def run_forever(*, backend_name: str | None = None, max_iter: int | None = None,
                timeout: int = 600, seed: int = 0) -> int:
    settings = get_settings()
    af_dir = settings.reports_dir / "alpha_factory"
    pending = settings.reports_dir / "pending_review"
    af_dir.mkdir(parents=True, exist_ok=True)
    pending.mkdir(parents=True, exist_ok=True)
    reject_log = af_dir / "rejected.jsonl"
    state_file = af_dir / "state.json"
    stop_file = af_dir / "STOP"

    os.environ["QOS_ROBUST_EXTRA"] = "1"  # turn on the harness OOS + walk-forward block
    _limit_threads()
    _install_signal_handlers()
    backend = get_backend(backend_name)
    th = GateThresholds()
    rng = random.Random(seed or None)
    seen = _load_seen(reject_log, settings.backtest_dir)

    n_iter = passed = rejected = errored = 0
    started = time.time()
    print(f"[alpha-factory] start · backend={getattr(backend, 'name', '?')} · gate={asdict(th)}", flush=True)

    while not _STOP and not stop_file.exists() and (max_iter is None or n_iter < max_iter):
        n_iter += 1
        t0 = time.time()
        # default per-iteration locals so the finally-cleanup never NameErrors
        hypothesis = slug = result = metrics = gate = None
        try:
            # A. hypothesis (regenerate up to 3x to dodge a duplicate slug)
            for _ in range(3):
                hypothesis, slug = generate_hypothesis(backend, seen, settings.ideas_dir, rng)
                if slug and slug not in seen:
                    break
            if not slug or slug in seen:
                print(f"[{n_iter}] duplicate/empty hypothesis, skipping", flush=True)
                continue
            seen.add(slug)

            # Data-mining deflation: tell the harness how broad the search has been so the
            # Deflated Sharpe is charged for multiple testing (a lucky pick among hundreds of
            # tried hypotheses must clear a much higher bar than a single pre-registered test).
            os.environ["QOS_N_TRIALS"] = str(max(len(seen), n_iter, 1))

            # B+C. backtest + robustness in an isolated subprocess (heavy data freed on exit)
            result = run_iteration(hypothesis, slug, backend, settings, timeout=timeout)
            metrics = result["metrics"]

            # D. gate
            gate = evaluate_gate(metrics, th)
            if gate["passed"]:
                num = next_strategy_number(settings.backtest_dir)
                path = write_report(pending, num, slug, hypothesis, result, gate, backend)
                passed += 1
                print(f"[{n_iter}] ✅ PASS {slug} → {path.name}", flush=True)
            else:
                # minimal reject record (for de-dup); NOT kept in RAM beyond the write
                mm = (metrics or {}).get("metrics", {})
                rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "slug": slug, "reason": gate["reason"],
                       "sharpe": _num(metrics, "metrics", "sharpe"),
                       "oos_sharpe": _num(metrics, "oos", "oos_sharpe"),
                       "perm_p": _num(metrics, "permutation", "p_value"),
                       "n_trades": mm.get("n_trades"),
                       "hypothesis": hypothesis[:200]}
                with open(reject_log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, default=str) + "\n")
                rejected += 1
                print(f"[{n_iter}] ✗ reject {slug} — {gate['reason']}", flush=True)
        except KeyboardInterrupt:
            break
        except Exception as e:  # one bad iteration must never kill the loop
            errored += 1
            print(f"[{n_iter}] ⚠ error: {type(e).__name__}: {e}", flush=True)
        finally:
            # stream state to disk, then aggressively free this iteration's memory
            rss = _rss_mb()
            state = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "iterations": n_iter, "passed": passed, "rejected": rejected,
                     "errored": errored, "seen": len(seen),
                     "elapsed_s": round(time.time() - started, 1),
                     "last_iter_s": round(time.time() - t0, 1), "rss_mb": rss}
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
            del hypothesis, slug, result, metrics, gate
            gc.collect()

    print(f"[alpha-factory] stopped · iters={n_iter} passed={passed} rejected={rejected} errored={errored}", flush=True)
    if stop_file.exists():
        stop_file.unlink()  # consume the stop file so the next run starts clean
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="alpha-factory", description="Autonomous continuous research worker")
    ap.add_argument("--backend", default=None, help="auto|mock|llamacpp|mlx (default: config)")
    ap.add_argument("--max-iter", type=int, default=None, help="stop after N iterations (default: infinite)")
    ap.add_argument("--once", action="store_true", help="run exactly one iteration")
    ap.add_argument("--timeout", type=int, default=600, help="per-backtest subprocess timeout (s)")
    ap.add_argument("--seed", type=int, default=0, help="RNG seed for theme/hypothesis variety")
    args = ap.parse_args(argv)
    max_iter = 1 if args.once else args.max_iter
    return run_forever(backend_name=args.backend, max_iter=max_iter, timeout=args.timeout, seed=args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
