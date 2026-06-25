"""Quant Academy — the interactive learning module backing /api/academy.

Three concerns, kept small and testable like the rest of ``quantlab``:

- :mod:`quantlab.academy.curriculum` — load the data-driven curriculum
  (``content/academy/curriculum.json`` + per-module markdown) and merge it with
  saved progress to compute each module's unlock ``status``.
- :mod:`quantlab.academy.progress` — atomic, cross-platform read/write of the
  single ``progress.json`` state file (git/cloud-synced between Windows and macOS).
- :mod:`quantlab.academy.ingest` — TF-IDF ingestion of the local PDF library
  (``Quant Books/``), reusing the dependency-free index from ``agent.rag``.
"""

from .curriculum import get_module, load_curriculum, merge_status
from .progress import complete_lesson, load_progress, record_quiz, save_progress

__all__ = [
    "load_curriculum", "get_module", "merge_status",
    "load_progress", "save_progress", "complete_lesson", "record_quiz",
]
