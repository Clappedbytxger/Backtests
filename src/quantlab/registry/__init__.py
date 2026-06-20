"""Quant-OS strategy/experiment registry (SQLite over CATALOG.md + metrics.json)."""

from .db import (
    bucket_counts,
    build_registry,
    connect,
    get_strategy,
    list_strategies,
    parse_catalog,
    status_bucket,
    status_counts,
)

__all__ = [
    "build_registry", "connect", "get_strategy", "list_strategies",
    "parse_catalog", "status_counts", "bucket_counts", "status_bucket",
]
