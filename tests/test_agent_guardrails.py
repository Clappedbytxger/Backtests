"""Safety tests for the agent guardrails (branch isolation, no push, allow-list)."""

from __future__ import annotations

import subprocess

import pytest

from agent.guardrails import (
    GuardrailError,
    agent_commit,
    assert_safe_branch,
    current_branch,
    ensure_agent_branch,
    safe_git,
)


def _run(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True,
                   capture_output=True, text=True)
    _run(tmp_path, "config", "user.email", "agent@test.local")
    _run(tmp_path, "config", "user.name", "Agent Test")
    (tmp_path / "seed.txt").write_text("seed")
    _run(tmp_path, "add", "-A")
    _run(tmp_path, "commit", "-m", "init")
    return tmp_path


def test_protected_branch_blocks(repo):
    assert current_branch(repo) == "main"
    with pytest.raises(GuardrailError):
        assert_safe_branch(repo)


def test_ensure_agent_branch_creates_and_is_safe(repo):
    assert ensure_agent_branch(repo, "exp1") == "agent/exp1"
    assert current_branch(repo) == "agent/exp1"
    assert assert_safe_branch(repo) == "agent/exp1"
    assert ensure_agent_branch(repo, "agent/exp1") == "agent/exp1"  # idempotent


def test_ensure_branch_rejects_protected_name(repo):
    with pytest.raises(GuardrailError):
        ensure_agent_branch(repo, "main")


def test_safe_git_blocks_dangerous_commands(repo):
    ensure_agent_branch(repo, "exp")
    for bad in (["push", "origin", "x"], ["remote", "add", "o", "u"],
                ["reset", "--hard"], ["clean", "-fd"], ["pull"], ["merge", "main"]):
        with pytest.raises(GuardrailError):
            safe_git(repo, bad)
    assert safe_git(repo, ["status", "--porcelain"]) == ""  # allow-listed works


def test_agent_commit_on_isolated_branch(repo):
    ensure_agent_branch(repo, "exp")
    (repo / "new.txt").write_text("hello")
    sha = agent_commit(repo, "feat: agent adds a file", paths=["new.txt"])
    assert len(sha) == 40
    assert current_branch(repo) == "agent/exp"
    # main must be untouched by the agent's work
    safe_git(repo, ["checkout", "main"])
    assert not (repo / "new.txt").exists()


def test_agent_commit_refuses_on_protected_branch(repo):
    (repo / "x.txt").write_text("x")
    with pytest.raises(GuardrailError):
        agent_commit(repo, "msg", paths=["x.txt"])  # still on main


def test_agent_commit_empty_raises(repo):
    ensure_agent_branch(repo, "exp")
    with pytest.raises(GuardrailError):
        agent_commit(repo, "nothing changed", paths=["seed.txt"])
