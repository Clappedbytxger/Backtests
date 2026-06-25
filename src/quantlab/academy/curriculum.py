"""Load the data-driven Academy curriculum and merge it with saved progress.

``content/academy/curriculum.json`` is the single source of truth (generated from
``Quant Books/QUANT-LERNSYSTEM.md``). Each module references its prose lesson via
a ``content`` markdown file. The unlock ``status`` of every module is *derived*
at read time from progress + the prerequisite graph, never stored in the
curriculum file:

    completed  -> learner finished it (from progress.json)
    in_progress-> started (from progress.json)
    available  -> all prerequisites completed (or none) and not yet started
    locked     -> a prerequisite is still unfinished
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quantlab.config import get_settings

from .progress import load_progress


def _content_dir(content_dir: Path | str | None = None) -> Path:
    return Path(content_dir) if content_dir else get_settings().academy_content_dir


def load_curriculum(content_dir: Path | str | None = None) -> dict[str, Any]:
    """Read ``curriculum.json``. Raises ``FileNotFoundError`` if absent."""
    path = _content_dir(content_dir) / "curriculum.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_module(module_id: str, content_dir: Path | str | None = None) -> dict[str, Any] | None:
    """One module dict, with its markdown lesson body loaded into ``content_md``."""
    cur = load_curriculum(content_dir)
    mod = next((m for m in cur["modules"] if m["id"] == module_id), None)
    if mod is None:
        return None
    mod = dict(mod)
    md_rel = mod.get("content")
    if md_rel:
        md_path = _content_dir(content_dir) / md_rel
        mod["content_md"] = md_path.read_text(encoding="utf-8") if md_path.exists() else None
    return mod


def _derive_status(mod: dict[str, Any], progress: dict[str, Any]) -> str:
    """Compute a module's unlock status from progress + prerequisite completion."""
    entry = progress.get("modules", {}).get(mod["id"], {})
    saved = entry.get("status")
    if saved in ("completed", "in_progress"):
        return saved
    prereqs = mod.get("prerequisites", [])
    done = {mid for mid, e in progress.get("modules", {}).items()
            if e.get("status") == "completed"}
    return "available" if all(p in done for p in prereqs) else "locked"


def merge_status(
    content_dir: Path | str | None = None,
    progress_path: Path | str | None = None,
) -> dict[str, Any]:
    """Curriculum + per-module derived status + progress summary, for the UI.

    This is the single payload the skill-tree dashboard consumes: it never has to
    re-derive the unlock logic on the client.
    """
    cur = load_curriculum(content_dir)
    progress = load_progress(progress_path)
    pmods = progress.get("modules", {})

    modules = []
    for mod in cur["modules"]:
        entry = pmods.get(mod["id"], {})
        status = _derive_status(mod, progress)
        n_topics = len(mod.get("topics", []))
        n_done = len(entry.get("completed_lessons", []))
        modules.append({
            **mod,
            "status": status,
            "xp": int(entry.get("xp", 0) or 0),
            "completed_lessons": entry.get("completed_lessons", []),
            "quiz_scores": entry.get("quiz_scores", []),
            "progress_pct": round(100 * n_done / n_topics) if n_topics else 0,
        })

    return {
        "title": cur.get("title"),
        "subtitle": cur.get("subtitle"),
        "design_principle": cur.get("design_principle"),
        "active_module": progress.get("active_module"),
        "totals": progress.get("totals", {}),
        "modules": modules,
    }
