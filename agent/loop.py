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
) -> dict:
    """Run one autonomous research cycle. Returns a summary dict."""
    repo_root = Path(repo_root) if repo_root else get_settings().backtest_dir
    backend = backend or get_backend()
    slug = slug or _slugify(hypothesis)

    branch = ensure_agent_branch(repo_root, slug)  # GUARDRAIL: isolated branch only
    context = retrieve_context(hypothesis, ideas_dir=ideas_dir, k=k)
    dups = dedup_against_catalog(hypothesis, repo_root=repo_root, k=k)

    code = _extract_code(backend.generate(_code_prompt(hypothesis, context, dups), system=_CODE_SYSTEM))
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
