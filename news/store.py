"""JSON-backed, thread-safe persistence for the news terminal.

One process-wide store (``get_store()``) over two files under
``data_dir/news/``:

  - ``items.json``   — every :class:`NewsItem` (with its embedded hypothesis)
  - ``lessons.json`` — the :class:`Lesson` knowledge base for few-shot priming

JSON (not SQLite) keeps it inspectable and trivially diffable, matching the
project's other local-state stores (``live/state/*.json``). Writes are atomic
(temp file + ``os.replace``) and guarded by a re-entrant lock so the API's
background verification and request handlers never corrupt the file.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from quantlab.config import get_settings

from .models import (
    PRIORITY_RANK,
    Category,
    Hypothesis,
    Lesson,
    NewsItem,
    Priority,
)


class NewsStore:
    """A tiny atomic JSON store for news items + lessons."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (get_settings().data_dir / "news")
        self.root.mkdir(parents=True, exist_ok=True)
        self.items_path = self.root / "items.json"
        self.lessons_path = self.root / "lessons.json"
        self.market_path = self.root / "market.json"
        self._lock = threading.RLock()

    # ── low-level atomic IO ────────────────────────────────────────────────
    @staticmethod
    def _read(path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=2, default=str)
            os.replace(tmp, path)  # atomic on POSIX + Windows
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    # ── items ──────────────────────────────────────────────────────────────
    def all_items(self) -> list[NewsItem]:
        with self._lock:
            return [NewsItem.model_validate(r) for r in self._read(self.items_path)]

    def get_item(self, item_id: str) -> NewsItem | None:
        return next((it for it in self.all_items() if it.id == item_id), None)

    def upsert_item(self, item: NewsItem) -> NewsItem:
        """Insert or replace an item by id (returns the stored item)."""
        with self._lock:
            rows = self._read(self.items_path)
            rows = [r for r in rows if r.get("id") != item.id]
            rows.append(json.loads(item.model_dump_json()))
            self._write(self.items_path, rows)
        return item

    def update_hypothesis(self, item_id: str, hyp: Hypothesis) -> NewsItem | None:
        with self._lock:
            item = self.get_item(item_id)
            if item is None:
                return None
            item.hypothesis = hyp
            return self.upsert_item(item)

    def query_items(
        self,
        category: Category | None = None,
        priority: Priority | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[NewsItem]:
        """Filter, then sort by priority desc, then most-recent first."""
        items = self.all_items()
        if category is not None:
            items = [i for i in items if i.category == category]
        if priority is not None:
            items = [i for i in items if i.priority == priority]
        if status is not None:
            items = [
                i for i in items
                if i.hypothesis is not None and i.hypothesis.status.value == status
            ]
        items.sort(
            key=lambda i: (PRIORITY_RANK.get(i.priority.value, 0), i.timestamp),
            reverse=True,
        )
        return items[:limit]

    # ── lessons ────────────────────────────────────────────────────────────
    def all_lessons(self) -> list[Lesson]:
        with self._lock:
            return [Lesson.model_validate(r) for r in self._read(self.lessons_path)]

    def add_lesson(self, lesson: Lesson) -> Lesson:
        with self._lock:
            rows = self._read(self.lessons_path)
            rows.append(json.loads(lesson.model_dump_json()))
            self._write(self.lessons_path, rows)
        return lesson

    def recent_lessons(self, category: Category | None = None, k: int = 5) -> list[Lesson]:
        """Most recent lessons (optionally same-category first) for few-shot priming."""
        lessons = sorted(self.all_lessons(), key=lambda l: l.created_at, reverse=True)
        if category is not None:
            same = [l for l in lessons if l.category == category]
            other = [l for l in lessons if l.category != category]
            lessons = same + other
        return lessons[:k]

    # ── market summary (single cached object) ──────────────────────────────
    def get_market(self) -> dict:
        with self._lock:
            if not self.market_path.exists():
                return {}
            try:
                return json.loads(self.market_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}

    def set_market(self, data: dict) -> None:
        with self._lock:
            self._write(self.market_path, data)  # atomic write (dict is JSON-fine)

    # ── housekeeping ───────────────────────────────────────────────────────
    def clear(self, include_lessons: bool = False) -> dict:
        """Wipe the feed (e.g. to drop demo seeds). Keeps lessons by default."""
        with self._lock:
            n_items = len(self._read(self.items_path))
            self._write(self.items_path, [])
            n_lessons = 0
            if include_lessons:
                n_lessons = len(self._read(self.lessons_path))
                self._write(self.lessons_path, [])
        return {"cleared_items": n_items, "cleared_lessons": n_lessons}

    def stats(self) -> dict:
        items = self.all_items()
        evaluated = [i for i in items if i.hypothesis is not None]
        verified = [
            i for i in evaluated
            if i.hypothesis.status.value in ("correct", "incorrect")
        ]
        hits = sum(1 for i in verified if i.hypothesis.status.value == "correct")
        return {
            "n_items": len(items),
            "n_evaluated": len(evaluated),
            "n_open": sum(1 for i in evaluated if i.hypothesis.status.value == "open"),
            "n_verified": len(verified),
            "n_correct": hits,
            "n_incorrect": len(verified) - hits,
            "accuracy": round(hits / len(verified), 3) if verified else None,
            "n_lessons": len(self.all_lessons()),
        }


_STORE: NewsStore | None = None
_STORE_LOCK = threading.Lock()


def get_store() -> NewsStore:
    """Process-wide singleton store."""
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                _STORE = NewsStore()
    return _STORE
