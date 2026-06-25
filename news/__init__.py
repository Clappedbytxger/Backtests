"""Quant-OS News-Feed — aggregation, agent hypotheses, and a learning loop.

A Bloomberg-style market-news terminal layered on top of the research stack:

  - :mod:`news.models`   — the ``NewsItem`` / ``Hypothesis`` / ``Lesson`` schema
  - :mod:`news.store`    — JSON-backed, thread-safe persistence + filter/sort
  - :mod:`news.agent`    — per-item evaluation (LLM backend + heuristic fallback)
                           that emits a directional hypothesis, few-shot-primed
                           with past lessons
  - :mod:`news.feedback` — verifies hypotheses against real prices (or a manual
                           flag) and records the miss as a reusable lesson
  - :mod:`news.feed`     — source aggregation (seed headlines + ingest hook)

Exposed to the dashboard via :mod:`apps.api.news` under ``/api/news``.
"""

from __future__ import annotations

from .models import (
    Briefing,
    Category,
    Hypothesis,
    HypothesisStatus,
    ImpactDirection,
    Lesson,
    NewsItem,
    Priority,
)
from .store import NewsStore, get_store

__all__ = [
    "Category",
    "Priority",
    "ImpactDirection",
    "HypothesisStatus",
    "NewsItem",
    "Hypothesis",
    "Briefing",
    "Lesson",
    "NewsStore",
    "get_store",
]
