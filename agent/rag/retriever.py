"""Lightweight RAG over the ideas workspace + de-dup against the catalog.

Retrieval uses a dependency-free TF-IDF index (pure NumPy) — no embedding model
needed — over the hypothesis backlog (``HYPOTHESES.csv``). The de-dup helper runs
the same index over ``CATALOG.md`` so a new idea can be checked against the 100+
strategies already tested (the RESEARCH-PROCESS de-dup requirement) before the
agent spends effort on it.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from quantlab.config import get_settings

_TOKEN = re.compile(r"[a-z0-9]+")
# small English + German stop-list (the corpus is bilingual)
_STOP = {
    "the", "a", "an", "of", "to", "in", "on", "and", "or", "is", "for", "as", "by",
    "von", "der", "die", "das", "und", "mit", "im", "auf", "ein", "eine", "den", "des",
}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 2 and t not in _STOP]


@dataclass
class Doc:
    id: str
    text: str
    meta: dict = field(default_factory=dict)


class TfidfIndex:
    """A tiny in-memory TF-IDF index with cosine retrieval."""

    def __init__(self, docs: list[Doc]) -> None:
        self.docs = docs
        toks = [_tokens(d.text) for d in docs]
        vocab: dict[str, int] = {}
        for tl in toks:
            for t in set(tl):
                vocab.setdefault(t, len(vocab))
        self.vocab = vocab
        n, v = len(docs), len(vocab)
        self.idf = np.ones(v)
        self.matrix = np.zeros((n, v))
        if n == 0 or v == 0:
            return
        tf = np.zeros((n, v))
        df = np.zeros(v)
        for i, tl in enumerate(toks):
            for t in tl:
                tf[i, vocab[t]] += 1.0
            for t in set(tl):
                df[vocab[t]] += 1.0
        self.idf = np.log((1.0 + n) / (1.0 + df)) + 1.0
        mat = tf * self.idf
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.matrix = mat / norms

    def _vectorize(self, text: str) -> np.ndarray:
        v = np.zeros(len(self.vocab))
        for t in _tokens(text):
            j = self.vocab.get(t)
            if j is not None:
                v[j] += 1.0
        v = v * self.idf
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def query(self, text: str, k: int = 5) -> list[tuple[Doc, float]]:
        if not self.docs or not self.vocab:
            return []
        sims = self.matrix @ self._vectorize(text)
        order = np.argsort(-sims)[:k]
        return [(self.docs[i], float(sims[i])) for i in order if sims[i] > 0]


def load_ideas_corpus(ideas_dir: Path | str | None = None) -> list[Doc]:
    """Docs from ``IDEAS_DIR/HYPOTHESES.csv`` (one per hypothesis)."""
    ideas_dir = Path(ideas_dir) if ideas_dir else get_settings().ideas_dir
    csv_path = ideas_dir / "HYPOTHESES.csv"
    if not csv_path.exists():
        return []
    docs = []
    with open(csv_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            text = (f"{row.get('Titel', '')}. {row.get('Kernidee_kurz', '')} "
                    f"[{row.get('Kategorie', '')} {row.get('Markt', '')}]")
            docs.append(Doc(id=row.get("ID", ""), text=text, meta=row))
    return docs


def load_catalog_corpus(repo_root: Path | str | None = None) -> list[Doc]:
    """Docs from ``CATALOG.md`` (one per tested strategy)."""
    from quantlab.registry import parse_catalog

    repo_root = Path(repo_root) if repo_root else get_settings().backtest_dir
    rows = parse_catalog(repo_root / "CATALOG.md")
    return [
        Doc(id=num, text=f"{r.get('name', '')}. {r.get('hypothesis', '')} [{r.get('category', '')}]",
            meta=r)
        for num, r in rows.items()
    ]


def retrieve_context(query: str, ideas_dir: Path | str | None = None, k: int = 5) -> list[tuple[Doc, float]]:
    """Top-k hypotheses from the backlog most relevant to ``query``."""
    return TfidfIndex(load_ideas_corpus(ideas_dir)).query(query, k)


def dedup_against_catalog(idea_text: str, repo_root: Path | str | None = None,
                          k: int = 5) -> list[tuple[Doc, float]]:
    """Top-k already-tested strategies resembling ``idea_text`` (de-dup check)."""
    return TfidfIndex(load_catalog_corpus(repo_root)).query(idea_text, k)
