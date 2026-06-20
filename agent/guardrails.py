"""Safety guardrails for the autonomous research agent — enforced, not just documented.

The agent may stage/commit on an isolated branch only. These functions are the
single boundary through which the agent touches git; anything outside the
allow-list (push, remote, reset, clean, rebase, ...) raises :class:`GuardrailError`.
Tested in ``tests/test_agent_guardrails.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

PROTECTED_BRANCHES = {"main", "master"}
AGENT_BRANCH_PREFIX = "agent/"

# git subcommands the agent is allowed to run. Everything else is refused.
ALLOWED_GIT = {
    "add", "commit", "checkout", "switch", "branch",
    "status", "rev-parse", "diff", "log", "show",
}
# explicitly named here for clarity; none of these are in ALLOWED_GIT either.
FORBIDDEN_GIT = {"push", "remote", "reset", "clean", "rebase", "filter-branch",
                 "update-ref", "fetch", "pull", "merge", "cherry-pick"}


class GuardrailError(RuntimeError):
    """Raised when the agent attempts an action outside its safety envelope."""


def _git(repo: Path | str, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise GuardrailError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def current_branch(repo: Path | str) -> str:
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD")


def assert_safe_branch(repo: Path | str) -> str:
    """Raise unless the current branch is a non-protected branch."""
    b = current_branch(repo)
    if b in PROTECTED_BRANCHES:
        raise GuardrailError(f"refusing to operate on protected branch {b!r}")
    return b


def ensure_agent_branch(repo: Path | str, name: str) -> str:
    """Create/checkout an isolated ``agent/<name>`` branch (never a protected one)."""
    if name in PROTECTED_BRANCHES:
        raise GuardrailError(f"{name!r} is a protected branch")
    branch = name if name.startswith(AGENT_BRANCH_PREFIX) else AGENT_BRANCH_PREFIX + name
    if _git(repo, "branch", "--list", branch):
        _git(repo, "checkout", branch)
    else:
        _git(repo, "checkout", "-b", branch)
    return branch


def safe_git(repo: Path | str, args: list[str]) -> str:
    """Run a git command only if its subcommand is on the allow-list."""
    if not args:
        raise GuardrailError("empty git command")
    sub = args[0]
    if sub in FORBIDDEN_GIT or sub not in ALLOWED_GIT:
        raise GuardrailError(f"git subcommand {sub!r} is not permitted for the agent")
    return _git(repo, *args)


def agent_commit(repo: Path | str, message: str, paths: list[str] | None = None) -> str:
    """Stage the given paths (or all changes) and commit on the current safe branch.

    Refuses if the current branch is protected. Never pushes.
    """
    assert_safe_branch(repo)
    safe_git(repo, ["add", *(paths if paths else ["-A"])])
    # nothing to commit -> surface a clear error rather than a cryptic git one
    if not _git(repo, "status", "--porcelain"):
        raise GuardrailError("nothing staged to commit")
    safe_git(repo, ["commit", "-m", message])
    return _git(repo, "rev-parse", "HEAD")
