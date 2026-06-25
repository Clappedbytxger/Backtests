"""Quant-OS Academy API — the interactive learning module.

Mounted under ``/api/academy`` by :mod:`apps.api.main`. Serves the data-driven
curriculum (skill-tree), reads/writes the cross-platform ``progress.json``, and
exposes the interval-gated content agent + local book library. All endpoints
degrade gracefully — a missing book library or LLM never returns a 500.

Endpoints:
  GET  /api/academy/curriculum         skill-tree: modules + derived unlock status + totals
  GET  /api/academy/module/{id}        one module incl. markdown lesson + generated content
  POST /api/academy/lesson/complete    mark a lesson done (xp), unlock cascade
  POST /api/academy/quiz               record a quiz result (auto-completes on >=0.8)
  GET  /api/academy/books              list the local PDF reference library
  POST /api/academy/generate/{id}      run the content agent for a module (interval-gated)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from quantlab.academy import curriculum as cur
from quantlab.academy import progress as prog

router = APIRouter(prefix="/api/academy", tags=["academy"])


@router.get("/curriculum")
def curriculum() -> dict:
    """The full skill-tree payload: modules with derived status + progress totals."""
    try:
        return {"ok": True, **cur.merge_status()}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"curriculum.json missing: {e}") from e


@router.get("/module/{module_id}")
def module(module_id: str, with_generated: bool = False) -> dict:
    """One module incl. its markdown lesson body and (optionally) agent content."""
    mod = cur.get_module(module_id)
    if mod is None:
        raise HTTPException(status_code=404, detail=f"module {module_id} not found")
    progress = prog.load_progress()
    entry = progress.get("modules", {}).get(module_id, {})
    out = {"ok": True, "module": mod, "progress": entry}
    if with_generated:
        from quantlab.academy.generate import load_generated
        out["generated"] = load_generated(module_id)
    return out


class LessonComplete(BaseModel):
    module_id: str
    lesson_id: str
    xp: int = 20


@router.post("/lesson/complete")
def lesson_complete(req: LessonComplete) -> dict:
    """Mark one lesson done; idempotent. Returns the refreshed skill-tree."""
    prog.complete_lesson(req.module_id, req.lesson_id, xp=req.xp)
    return {"ok": True, **cur.merge_status()}


class QuizResult(BaseModel):
    module_id: str
    score: float  # 0..1
    n: int


@router.post("/quiz")
def quiz(req: QuizResult) -> dict:
    """Record a quiz score; >=0.8 auto-completes the module + unlocks successors."""
    if not 0.0 <= req.score <= 1.0:
        raise HTTPException(status_code=400, detail="score must be in [0, 1]")
    prog.record_quiz(req.module_id, req.score, req.n)
    return {"ok": True, **cur.merge_status()}


@router.get("/books")
def books() -> dict:
    """List the local PDF reference library (``Quant Books/``)."""
    from quantlab.academy.ingest import list_books

    items = list_books()
    return {"ok": True, "count": len(items), "books": items}


@router.post("/generate/{module_id}")
def generate(module_id: str, force: bool = False) -> dict:
    """Run the interval-gated content agent for one module (exercises/quiz/examples).

    Returns the cached payload if younger than ``academy_agent_interval_h`` unless
    ``force`` is set. Never raises on a missing LLM — falls back to a template.
    """
    try:
        from quantlab.academy.generate import generate_for_module

        return {"ok": True, **generate_for_module(module_id, force=force)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 - any LLM/data failure degrades gracefully
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
