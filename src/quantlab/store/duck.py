"""DuckDB analytical layer over the Parquet data lake.

Queries the ~2,600 cached Parquet files under ``data/cache/**`` *in place* (no
duplication — DuckDB scans Parquet directly). The point-in-time helper
:meth:`DataLake.as_of` enforces the no-look-ahead rule structurally: it never
returns a row whose timestamp is newer than the as-of instant.

Example::

    from quantlab.store import DataLake
    lake = DataLake()
    lake.list_datasets("futures")          # ['futures/ZC_F_1d_....parquet', ...]
    lake.sql("SELECT 42 AS x")             # arbitrary DuckDB SQL
    lake.as_of("futures/ZC_F_1d_x.parquet", "2020-06-15")  # PIT-safe slice
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

from ..config import get_settings

# Column-name hints used when no native DATE/TIMESTAMP column is present.
_TIME_HINTS = ("date", "datetime", "timestamp", "time", "ts")


class DataLake:
    """Read-only DuckDB view over the Parquet cache.

    Args:
        cache_dir: lake root. Defaults to ``get_settings().cache_dir``.
    """

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else get_settings().cache_dir
        self._con = duckdb.connect(database=":memory:")

    # ------------------------------------------------------------------ discovery
    def list_datasets(self, subdir: str | None = None) -> list[str]:
        """Relative POSIX paths of every Parquet dataset (optionally under ``subdir``)."""
        root = self.cache_dir / subdir if subdir else self.cache_dir
        if not root.exists():
            return []
        return [f.relative_to(self.cache_dir).as_posix() for f in sorted(root.rglob("*.parquet"))]

    def path(self, dataset: str) -> Path:
        """Absolute path of a dataset id; raises if it does not exist."""
        p = self.cache_dir / dataset
        if not p.exists():
            raise FileNotFoundError(f"dataset not found: {dataset!r} ({p})")
        return p

    # --------------------------------------------------------------------- queries
    def sql(self, query: str, params: list | None = None) -> pd.DataFrame:
        """Run arbitrary DuckDB SQL and return a DataFrame."""
        return self._con.execute(query, params or []).df()

    def read(self, dataset: str, columns: Iterable[str] | None = None) -> pd.DataFrame:
        """Read a whole dataset (optionally a column subset) into a DataFrame."""
        cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        return self._con.execute(
            f"SELECT {cols} FROM read_parquet({self._lit(self.path(dataset))})"
        ).df()

    def schema(self, dataset: str) -> pd.DataFrame:
        """Column names/types of a dataset (DuckDB ``DESCRIBE``)."""
        return self._con.execute(
            f"DESCRIBE SELECT * FROM read_parquet({self._lit(self.path(dataset))})"
        ).df()

    def _types(self, dataset: str) -> dict[str, str]:
        """Ordered ``{column_name: UPPER column_type}`` for a dataset."""
        desc = self.schema(dataset)
        return {str(r["column_name"]): str(r["column_type"]).upper() for _, r in desc.iterrows()}

    @staticmethod
    def _pick_time_col(types: dict[str, str]) -> str | None:
        for name, t in types.items():
            if t.startswith(("DATE", "TIMESTAMP")):
                return name
        for name in types:
            if name.lower() in _TIME_HINTS:
                return name
        return None

    def time_column(self, dataset: str) -> str | None:
        """Best-guess timestamp column: a native DATE/TIMESTAMP, else a name hint."""
        return self._pick_time_col(self._types(dataset))

    # ------------------------------------------------------------------------- PIT
    def as_of(self, dataset: str, asof, ts_col: str | None = None) -> pd.DataFrame:
        """Point-in-time slice: rows with ``ts_col <= asof`` only (no look-ahead).

        Args:
            dataset: dataset id (relative path under the cache root).
            asof: as-of timestamp (anything ``pd.Timestamp`` accepts).
            ts_col: timestamp column; auto-detected when ``None``.

        Returns:
            DataFrame ordered by the time column, containing only rows up to and
            including ``asof``. A row stamped after ``asof`` is structurally
            impossible to return.
        """
        asof_ts = pd.Timestamp(asof)
        types = self._types(dataset)
        col = ts_col or self._pick_time_col(types)
        if col is None:
            raise ValueError(f"no time column detected in {dataset!r}; pass ts_col=")
        # Align tz so the comparison is unambiguous. A tz-aware column (Parquet
        # TIMESTAMP WITH TIME ZONE stores UTC instants) is compared against a
        # UTC-normalized as-of; a naive column against a naive as-of.
        if "WITH TIME ZONE" in types.get(col, ""):
            asof_ts = asof_ts.tz_localize("UTC") if asof_ts.tzinfo is None else asof_ts.tz_convert("UTC")
        elif asof_ts.tzinfo is not None:
            asof_ts = asof_ts.tz_localize(None)
        query = (
            f"SELECT * FROM read_parquet({self._lit(self.path(dataset))}) "
            f'WHERE "{col}" <= ? ORDER BY "{col}"'
        )
        return self._con.execute(query, [asof_ts.to_pydatetime()]).df()

    # ----------------------------------------------------------------------- misc
    @staticmethod
    def _lit(p: Path) -> str:
        """A safely-quoted SQL string literal for a filesystem path."""
        return "'" + p.as_posix().replace("'", "''") + "'"

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> "DataLake":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
