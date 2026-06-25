"""Ingestion of the local PDF reference library (``Quant Books/``).

Builds a dependency-free TF-IDF index (reusing :class:`agent.rag.retriever.TfidfIndex`)
over text extracted from the PDFs, so a module can pull the most relevant passages
from your own books as deepening context. Text extraction uses ``pypdf`` if
installed; if not, the library is still *listed* (titles/categories) and ingestion
degrades to metadata-only — never a hard failure.

The extracted-text cache lives under ``data/cache/academy/books_index.json`` so the
slow PDF parse happens once.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from quantlab.config import get_settings


def list_books(books_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """List PDFs in the library with derived title/author/category (folder = category)."""
    root = Path(books_dir) if books_dir else get_settings().books_dir
    if not root.exists():
        return []
    books = []
    for pdf in sorted(root.rglob("*.pdf")):
        rel = pdf.relative_to(root)
        category = rel.parts[0] if len(rel.parts) > 1 else "Uncategorized"
        stem = pdf.stem
        # "Author - Title (year) - libgen.li" -> split on first " - "
        author, _, rest = stem.partition(" - ")
        title = (rest or author).split(" - libgen")[0]
        title = re.sub(r"\s*\(\d{4}.*$", "", title).strip() or stem
        books.append({
            "path": str(pdf),
            "rel": rel.as_posix(),
            "category": category,
            "author": author.strip(),
            "title": title,
        })
    return books


def _extract_text(pdf_path: Path, max_pages: int = 40) -> str:
    """Extract up to ``max_pages`` of text. Returns "" if pypdf is unavailable."""
    try:
        from pypdf import PdfReader  # optional dep
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(pdf_path))
        pages = reader.pages[:max_pages]
        return "\n".join((p.extract_text() or "") for p in pages)
    except Exception:  # noqa: BLE001 - a malformed PDF must not break ingestion
        return ""


def _cache_path() -> Path:
    return get_settings().cache_dir / "academy" / "books_index.json"


def build_index(books_dir: Path | str | None = None, *, force: bool = False) -> dict[str, Any]:
    """Build (and cache) a metadata + first-pages-text index of the library."""
    cache = _cache_path()
    if cache.exists() and not force:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    books = list_books(books_dir)
    pypdf_ok = False
    for b in books:
        txt = _extract_text(Path(b["path"]))
        b["text"] = txt
        pypdf_ok = pypdf_ok or bool(txt)
    index = {"count": len(books), "text_extracted": pypdf_ok, "books": books}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def retrieve(query: str, k: int = 4, books_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Top-k library passages relevant to ``query`` (TF-IDF over extracted text).

    Falls back to a metadata match (title/author/category) when no text could be
    extracted, so the feature still returns useful book pointers without pypdf.
    """
    from agent.rag.retriever import Doc, TfidfIndex

    index = build_index(books_dir)
    docs = [
        Doc(id=b["rel"], text=(b.get("text") or f"{b['title']} {b['author']} {b['category']}"),
            meta={k2: b[k2] for k2 in ("title", "author", "category", "rel")})
        for b in index["books"]
    ]
    hits = TfidfIndex(docs).query(query, k)
    return [{**doc.meta, "score": round(score, 3)} for doc, score in hits]
