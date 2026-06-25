"""Throttled LLM batch workflow — the model runs at most once per interval.

The high-frequency feed (ingest, classification, live price tracking, settling)
is entirely **model-free**: every item gets an instant heuristic hypothesis. The
heavy local LLM is decoupled into a single batched "research pass" that fires at
most once every ``QUANTLAB_NEWS_LLM_INTERVAL`` seconds (default 180 = 3 min):

  1. upgrade the heuristic hypotheses of the most important *open* items to a
     model-generated read (lesson-primed), and
  2. write the bilingual briefing documents for the top items still missing one.

It runs in a background thread (non-blocking, single-flight) so the live loop
stays snappy; its results land in the store and surface on the next tick. The
model is only loaded the first time a pass is actually due — if the page is never
left open long enough, the model never loads at all.
"""

from __future__ import annotations

import os
import threading
import time

from . import agent, briefing, market
from .models import PRIORITY_RANK, HypothesisStatus
from .store import NewsStore

_LOCK = threading.Lock()
_LAST_RUN = 0.0          # epoch of the last started pass (0 = never)
_RUNNING = False
_LAST_RESULT: dict = {"hypotheses_upgraded": 0, "documents_generated": 0,
                      "narrative_updated": False, "finished_at": None}

DEFAULT_INTERVAL = 180.0  # seconds (3 min)


def interval() -> float:
    """LLM cadence in seconds (env ``QUANTLAB_NEWS_LLM_INTERVAL``, min 30)."""
    try:
        return max(30.0, float(os.environ.get("QUANTLAB_NEWS_LLM_INTERVAL", DEFAULT_INTERVAL)))
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL


def status() -> dict:
    """Cadence + last-pass info for the UI."""
    now = time.time()
    iv = interval()
    return {
        "interval_s": iv,
        "running": _RUNNING,
        "seconds_until": 0.0 if _LAST_RUN == 0 else max(0.0, iv - (now - _LAST_RUN)),
        **_LAST_RESULT,
    }


def _by_importance(items):
    items.sort(key=lambda i: (PRIORITY_RANK.get(i.priority.value, 0), i.timestamp), reverse=True)
    return items


def _hyp_candidates(store: NewsStore, k: int):
    """Open items whose hypothesis is still only the heuristic baseline."""
    items = [i for i in store.all_items()
             if i.hypothesis is not None
             and i.hypothesis.model == "heuristic"
             and i.hypothesis.status is HypothesisStatus.OPEN]
    return _by_importance(items)[:k]


def _doc_candidates(store: NewsStore, k: int):
    items = [i for i in store.all_items() if i.document is None]
    return _by_importance(items)[:k]


def _run_batch(store: NewsStore, backend, max_hyp: int, max_docs: int) -> None:
    """The actual model work (runs in a background thread)."""
    global _RUNNING
    up = docs = 0
    narrative_ok = False
    try:
        for item in _hyp_candidates(store, max_hyp):
            lessons = store.recent_lessons(category=item.category, k=5)
            fresh = agent.evaluate(item, backend=backend, lessons=lessons)
            old = item.hypothesis
            if old is None or fresh.model == "heuristic":
                continue  # model failed -> keep the heuristic read, retry next pass
            # refresh only the model's *read*; keep all feedback-loop bookkeeping
            old.direction = fresh.direction
            old.asset = fresh.asset
            old.scope = fresh.scope
            old.rationale = fresh.rationale
            old.confidence = fresh.confidence
            old.model = fresh.model
            store.update_hypothesis(item.id, old)
            up += 1
        for item in _doc_candidates(store, max_docs):
            item.document = briefing.generate(item, backend=backend)
            store.upsert_item(item)
            docs += 1
        # refresh the German market-pulse narrative (uses the just-upgraded reads)
        try:
            market.refresh_narrative(store, backend=backend)
            narrative_ok = True
        except Exception:  # noqa: BLE001 - never let the summary break the pass
            pass
    finally:
        _LAST_RESULT.update(hypotheses_upgraded=up, documents_generated=docs,
                            narrative_updated=narrative_ok, finished_at=time.time())
        _RUNNING = False


def run_async(store: NewsStore, backend_provider, max_hyp: int = 5,
              max_docs: int = 3, force: bool = False) -> dict:
    """Start a batch pass if one is due and none is running. Non-blocking.

    ``backend_provider`` is a callable returning the (possibly heavy) LLM backend,
    invoked only when a pass is actually due — so the model is loaded lazily.
    """
    global _LAST_RUN, _RUNNING
    now = time.time()
    with _LOCK:
        if _RUNNING:
            return {"status": "running"}
        if not force and _LAST_RUN and now - _LAST_RUN < interval():
            return {"status": "waiting", "seconds_until": interval() - (now - _LAST_RUN)}
        backend = backend_provider() if callable(backend_provider) else backend_provider
        if backend is None or getattr(backend, "name", "") in ("", "mock"):
            return {"status": "no_model"}  # heuristic-only deployment
        _LAST_RUN = now      # reserve the slot before spawning (prevents re-trigger)
        _RUNNING = True
    threading.Thread(target=_run_batch, args=(store, backend, max_hyp, max_docs),
                     daemon=True).start()
    return {"status": "started"}
