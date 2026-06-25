"""Cross-platform, atomic learning-progress state (``progress.json``).

One lightweight JSON file holds the whole learning state so it syncs trivially
between Windows and macOS via the git/cloud-synced repo. Writes are atomic
(temp file + ``os.replace``) so a half-written file never corrupts progress —
important when a cloud sync client may read mid-write.

The schema is intentionally permissive: unknown keys are preserved on save, so a
newer client on the other machine never loses fields written by an older one.
"""

from __future__ import annotations

import json
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantlab.config import get_settings

SCHEMA_VERSION = 1

ModuleStatus = str  # locked | available | in_progress | completed


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _device() -> str:
    return f"{platform.system().lower()}-{platform.node()}"[:48]


def _progress_path(path: Path | str | None = None) -> Path:
    return Path(path) if path else get_settings().progress_file


def default_progress() -> dict[str, Any]:
    """A fresh, empty progress document."""
    return {
        "schema_version": SCHEMA_VERSION,
        "user": os.environ.get("QUANTLAB_USER", "robin"),
        "updated_at": _now_iso(),
        "device_last_write": _device(),
        "active_module": None,
        "modules": {},
        "totals": {"xp": 0, "modules_completed": 0, "streak_days": 0},
    }


def load_progress(path: Path | str | None = None) -> dict[str, Any]:
    """Load ``progress.json``; returns a fresh document if missing or unreadable."""
    p = _progress_path(path)
    if not p.exists():
        return default_progress()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_progress()
        data.setdefault("modules", {})
        data.setdefault("totals", {"xp": 0, "modules_completed": 0, "streak_days": 0})
        return data
    except (json.JSONDecodeError, OSError):
        # Never crash the learner over a corrupt/locked file — start clean in memory.
        return default_progress()


def save_progress(data: dict[str, Any], path: Path | str | None = None) -> Path:
    """Atomically write the progress document. Stamps time + device."""
    p = _progress_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {**data}
    data["schema_version"] = SCHEMA_VERSION
    data["updated_at"] = _now_iso()
    data["device_last_write"] = _device()
    data["totals"] = _recompute_totals(data)

    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".progress_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, p)  # atomic on Windows + POSIX
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return p


def _recompute_totals(data: dict[str, Any]) -> dict[str, Any]:
    modules = data.get("modules", {})
    xp = sum(int(m.get("xp", 0) or 0) for m in modules.values())
    done = sum(1 for m in modules.values() if m.get("status") == "completed")
    totals = dict(data.get("totals", {}))
    totals.update(xp=xp, modules_completed=done)
    totals.setdefault("streak_days", 0)
    return totals


def _module_entry(data: dict[str, Any], module_id: str) -> dict[str, Any]:
    return data.setdefault("modules", {}).setdefault(
        module_id,
        {"status": "in_progress", "completed_lessons": [], "quiz_scores": [],
         "xp": 0, "notes_md": "",
         "agent_generated": {"exercises_seen": 0, "last_refresh": None}},
    )


def complete_lesson(module_id: str, lesson_id: str, *, xp: int = 20,
                    path: Path | str | None = None) -> dict[str, Any]:
    """Mark one lesson within a module done; idempotent. Returns the updated doc."""
    data = load_progress(path)
    entry = _module_entry(data, module_id)
    if lesson_id not in entry["completed_lessons"]:
        entry["completed_lessons"].append(lesson_id)
        entry["xp"] = int(entry.get("xp", 0)) + xp
    if entry["status"] == "locked" or entry["status"] == "available":
        entry["status"] = "in_progress"
    data["active_module"] = module_id
    save_progress(data, path)
    return data


def set_module_status(module_id: str, status: ModuleStatus,
                      path: Path | str | None = None) -> dict[str, Any]:
    """Force a module's status (e.g. mark ``completed``)."""
    data = load_progress(path)
    _module_entry(data, module_id)["status"] = status
    if status == "in_progress":
        data["active_module"] = module_id
    save_progress(data, path)
    return data


def record_quiz(module_id: str, score: float, n: int,
                path: Path | str | None = None) -> dict[str, Any]:
    """Append a quiz result; auto-completes the module on a high score (>=0.8)."""
    data = load_progress(path)
    entry = _module_entry(data, module_id)
    entry["quiz_scores"].append({"at": _now_iso(), "score": round(score, 3), "n": n})
    if score >= 0.8:
        entry["status"] = "completed"
        entry["xp"] = int(entry.get("xp", 0)) + 50
    save_progress(data, path)
    return data
