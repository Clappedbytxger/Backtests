"""Quant-OS news API — aggregated feed, agent hypotheses, and the learning loop.

Mounted under ``/api/news`` by :mod:`apps.api.main`. All endpoints degrade
gracefully and reuse the project's local LLM backend (falling back to the
transparent heuristic when no model is configured). State lives in
``data/news/*.json`` via :class:`news.store.NewsStore`.

Endpoints:
  GET  /api/news/items            filter (category/priority/status) + sorted feed
  GET  /api/news/stats            accuracy + counts for the header
  GET  /api/news/lessons          the lessons-learned knowledge base
  POST /api/news/ingest           push one headline -> classify + evaluate
  POST /api/news/seed             load demo headlines (idempotent-ish)
  POST /api/news/evaluate/{id}    regenerate a hypothesis (re-prime with lessons)
  POST /api/news/verify           sweep + verify due hypotheses against prices
  POST /api/news/feedback/{id}    manual correct/incorrect override
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from news import feed, feedback
from news.models import (
    Category,
    FeedbackRequest,
    IngestRequest,
    Priority,
)
from news.store import get_store

router = APIRouter(prefix="/api/news", tags=["news"])

# Reuse the API's cached agent backend resolver if present; else lazy-load.
_BACKEND_CACHE: dict[str, object] = {}


def _backend():
    """The configured LLM backend, or None to force the heuristic path.

    Never raises: if the model can't be loaded (no GGUF on this machine), we
    return None and every evaluation falls back to the keyword heuristic.
    """
    if "b" in _BACKEND_CACHE:
        return _BACKEND_CACHE["b"]
    try:
        from quantlab.config import get_settings

        if not get_settings().llm_model:
            _BACKEND_CACHE["b"] = None
        else:
            from agent.llm import get_backend

            _BACKEND_CACHE["b"] = get_backend()
    except Exception:  # noqa: BLE001 - any import/model failure -> heuristic
        _BACKEND_CACHE["b"] = None
    return _BACKEND_CACHE["b"]


@router.get("/items")
def items(
    category: Category | None = None,
    priority: Priority | None = None,
    status: str | None = Query(None, description="open|correct|incorrect|unverified"),
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    store = get_store()
    rows = store.query_items(category=category, priority=priority, status=status, limit=limit)
    return {"ok": True, "count": len(rows),
            "items": [r.model_dump(mode="json") for r in rows]}


@router.get("/stats")
def stats() -> dict:
    return {"ok": True, **get_store().stats()}


@router.get("/lessons")
def lessons(limit: int = Query(50, ge=1, le=500)) -> dict:
    rows = sorted(get_store().all_lessons(), key=lambda l: l.created_at, reverse=True)[:limit]
    return {"ok": True, "count": len(rows),
            "lessons": [r.model_dump(mode="json") for r in rows]}


@router.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    # model-free (instant heuristic); the throttled LLM pass upgrades it later.
    item = feed.ingest(
        get_store(), title=title, content=req.content, source=req.source,
        category=req.category, priority=req.priority, backend=None,
    )
    return {"ok": True, "item": item.model_dump(mode="json")}


@router.post("/seed")
def seed() -> dict:
    items_ = feed.seed_sample(get_store(), backend=None)
    return {"ok": True, "seeded": len(items_)}


@router.post("/clear")
def clear(include_lessons: bool = Query(False, description="also wipe the lessons knowledge base")) -> dict:
    """Wipe the feed (drop demo seeds / start clean). Keeps lessons unless asked."""
    return {"ok": True, **get_store().clear(include_lessons=include_lessons)}


@router.post("/refresh")
def refresh(limit: int = Query(40, ge=1, le=200)) -> dict:
    """Pull real headlines from the keyless RSS sources and ingest the new ones."""
    try:
        new = feed.refresh_from_sources(get_store(), limit=limit)
    except Exception as e:  # noqa: BLE001 - network/parse issues degrade gracefully
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "new": 0}
    return {"ok": True, "new": len(new),
            "items": [i.model_dump(mode="json") for i in new]}


@router.post("/tick")
def tick(refresh: bool = Query(False, description="also pull fresh RSS news this tick"),
         limit: int = Query(200, ge=1, le=1000)) -> dict:
    """One live-loop iteration: (optional) refresh -> track open -> settle due.

    The News page polls this while it is open. Returns the loop summary *and* the
    refreshed feed so the UI updates in a single round-trip.
    """
    store = get_store()
    # pass the resolver (not the loaded model) so the LLM loads only when a pass is due.
    summary = feedback.tick(store, do_refresh=refresh, backend_provider=_backend)
    items_ = store.query_items(limit=limit)
    return {"ok": True, "summary": summary,
            "items": [i.model_dump(mode="json") for i in items_]}


@router.get("/document/{item_id}")
def document(item_id: str, regenerate: bool = False) -> dict:
    """The bilingual (EN+DE) briefing for one item.

    Model-free (instant heuristic) so opening an item never blocks; the throttled
    LLM pass writes richer briefings for the most important items in the background.
    """
    item = feed.generate_document(get_store(), item_id, backend=None,
                                  regenerate=regenerate)
    if item is None or item.document is None:
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True, "id": item_id, "document": item.document.model_dump(mode="json")}


@router.post("/evaluate/{item_id}")
def evaluate(item_id: str) -> dict:
    item = feed.reevaluate(get_store(), item_id, backend=_backend())
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return {"ok": True, "item": item.model_dump(mode="json")}


@router.post("/verify")
def verify(force: bool = Query(False, description="re-check open-but-not-due items too")) -> dict:
    summary = feedback.verify_due(get_store(), force=force)
    return {"ok": True, **summary}


@router.post("/feedback/{item_id}")
def manual_feedback(item_id: str, req: FeedbackRequest) -> dict:
    item = feedback.apply_manual_feedback(get_store(), item_id, req.correct, req.note)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found or not evaluated")
    return {"ok": True, "item": item.model_dump(mode="json")}
