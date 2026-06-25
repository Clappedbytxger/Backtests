"""Interval-gated background agent that generates fresh practice content.

Designed to run *not* on every tick but after a module is completed (or on demand,
respecting ``academy_agent_interval_h``). It reuses the project's local LLM backend
(:class:`agent.llm.LLMBackend`) and the book index (:mod:`quantlab.academy.ingest`)
to produce new exercises, a market example, and a deepening quiz for one module.

When no LLM is configured it degrades to a deterministic template, so the feature
is always functional offline (same philosophy as the news heuristic fallback).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quantlab.config import get_settings

from .curriculum import get_module
from .ingest import retrieve

_SYSTEM = (
    "Du bist ein Quant-Tutor. Erzeuge prägnante, didaktisch saubere Übungsaufgaben "
    "auf Deutsch für einen Lernenden, der vom Abitur-Niveau zum Senior Quant aufsteigt. "
    "Jede Aufgabe baut auf dem Modulthema auf, ist konkret und lösbar. Antworte NUR mit JSON."
)


def _cache_path(module_id: str) -> Path:
    return get_settings().cache_dir / "academy" / "generated" / f"{module_id}.json"


def _hours_since(iso: str | None) -> float:
    if not iso:
        return 1e9
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - then).total_seconds() / 3600.0
    except ValueError:
        return 1e9


def load_generated(module_id: str) -> dict[str, Any] | None:
    p = _cache_path(module_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def _fallback(module: dict[str, Any]) -> dict[str, Any]:
    topics = module.get("topics", [])
    exercises = [
        {"prompt": f"Erkläre in eigenen Worten: {t}", "type": "explain"}
        for t in topics[:3]
    ]
    return {
        "exercises": exercises,
        "market_example": f"Wende „{module['title']}“ auf deine eigenen Repo-Returns an "
                          f"(Anker: {module.get('repo_anchor', '')}).",
        "quiz": [],
        "source": "template",
    }


def _parse_json(text: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def generate_for_module(
    module_id: str, *, backend: Any | None = None, force: bool = False,
    content_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Generate (and cache) practice content for one module, interval-gated.

    Returns the cached payload unchanged if it is younger than
    ``academy_agent_interval_h`` and ``force`` is False.
    """
    settings = get_settings()
    cached = load_generated(module_id)
    if cached and not force and _hours_since(cached.get("generated_at")) < settings.academy_agent_interval_h:
        return {**cached, "cached": True}

    module = get_module(module_id, content_dir)
    if module is None:
        raise ValueError(f"unknown module {module_id}")

    if backend is None:
        try:
            from quantlab.config import get_settings as _gs
            if _gs().llm_model:
                from agent.llm import get_backend
                backend = get_backend()
        except Exception:  # noqa: BLE001
            backend = None

    book_hits = retrieve(module["title"] + " " + " ".join(module.get("topics", [])), k=3)
    if backend is None:
        payload = _fallback(module)
    else:
        prompt = (
            f"Modul: {module['title']} — {module.get('subtitle', '')}\n"
            f"Themen:\n- " + "\n- ".join(module.get("topics", [])) + "\n"
            f"Repo-Anker: {module.get('repo_anchor', '')}\n\n"
            "Erzeuge JSON mit den Schlüsseln: exercises (Liste von {prompt, type}), "
            "market_example (string), quiz (Liste von {question, options[4], answer_index}). "
            "3 Übungen, 3 Quizfragen."
        )
        try:
            raw = backend.generate(prompt, system=_SYSTEM, max_tokens=1200, temperature=0.4)
            payload = _parse_json(raw) or _fallback(module)
            payload.setdefault("source", getattr(backend, "name", "llm"))
        except Exception:  # noqa: BLE001
            payload = _fallback(module)

    payload["books"] = book_hits
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    payload["module_id"] = module_id
    p = _cache_path(module_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**payload, "cached": False}
