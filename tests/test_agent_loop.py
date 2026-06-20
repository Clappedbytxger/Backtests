"""End-to-end test of the agent research cycle (mock LLM, temp git repo)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent.guardrails import current_branch, safe_git
from agent.llm import MockBackend
from agent.loop import next_strategy_number, run_research_cycle

# A minimal, self-contained run.py the mock "LLM" returns (no market data needed).
_CODE = """```python
import json, os
os.makedirs("results", exist_ok=True)
with open("results/metrics.json", "w") as f:
    json.dump({"sharpe": 1.23, "cagr": 0.1, "n_trades": 42}, f)
print("backtest done")
```"""


def _responder(prompt, system):
    if system and "REPORT" in system:
        return "# Agent Report\n\nSharpe 1.23 over 42 trades. Verdict: testing."
    return _CODE


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True,
                   capture_output=True, text=True)
    for k, v in (("user.email", "agent@test.local"), ("user.name", "Agent Test")):
        subprocess.run(["git", "-C", str(tmp_path), "config", k, v], check=True,
                       capture_output=True, text=True)
    (tmp_path / "strategies").mkdir()
    (tmp_path / "strategies" / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True,
                   capture_output=True, text=True)
    return tmp_path


def test_next_strategy_number(repo):
    assert next_strategy_number(repo) == "0001"
    (repo / "strategies" / "0007_x").mkdir()
    (repo / "strategies" / "0042_y").mkdir()
    assert next_strategy_number(repo) == "0043"


def test_full_cycle_commits_on_isolated_branch(repo):
    res = run_research_cycle(
        "turn of month effect on equities",
        backend=MockBackend(responder=_responder),
        repo_root=repo, ideas_dir=repo, slug="tom-test",
    )
    assert res["status"] == "ok"
    assert res["metrics"]["sharpe"] == 1.23
    assert res["branch"] == "agent/tom-test"
    assert res["num"] == "0001"
    assert len(res["sha"]) == 40

    sdir = Path(res["dir"])
    assert (sdir / "run.py").exists()
    assert (sdir / "REPORT.md").exists()
    assert (sdir / "results" / "metrics.json").exists()
    assert current_branch(repo) == "agent/tom-test"

    # the agent never touches main
    safe_git(repo, ["checkout", "main"])
    assert not sdir.exists()


def test_dry_run_writes_code_but_does_not_execute_or_commit(repo):
    res = run_research_cycle(
        "some idea", backend=MockBackend(canned="```python\nprint('noop')\n```"),
        repo_root=repo, ideas_dir=repo, slug="dry", dry_run=True,
    )
    assert res["dry_run"] is True
    assert "sha" not in res
    sdir = Path(res["dir"])
    assert (sdir / "run.py").exists()
    assert not (sdir / "results" / "metrics.json").exists()  # never executed
