"""RAG over the ideas workspace (TF-IDF) + de-dup against the strategy catalog."""

from .retriever import (
    Doc,
    TfidfIndex,
    dedup_against_catalog,
    load_catalog_corpus,
    load_ideas_corpus,
    retrieve_context,
)

__all__ = [
    "Doc", "TfidfIndex", "load_ideas_corpus", "load_catalog_corpus",
    "retrieve_context", "dedup_against_catalog",
]
