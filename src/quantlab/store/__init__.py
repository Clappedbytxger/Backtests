"""Quant-OS data-access layer: DuckDB over the Parquet lake (``data/cache/**``)."""

from .duck import DataLake

__all__ = ["DataLake"]
