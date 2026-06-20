"""SQLite strategy/experiment registry.

Indexes every strategy folder, its ``CATALOG.md`` row and its
``results/metrics.json`` into a single queryable SQLite database (default
``strategies.db``). This is the backbone for the dashboard and for de-dup during
research. Rebuild any time with ``scripts/build_registry.py`` — it is idempotent
(drops and recreates).
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from ..config import get_settings

_NUM_RE = re.compile(r"^\d{4}$")
_FOLDER_RE = re.compile(r"^(\d{4})")

_SCHEMA = """
CREATE TABLE strategies (
  num TEXT PRIMARY KEY, slug TEXT, name TEXT, category TEXT, hypothesis TEXT,
  status TEXT, bucket TEXT, sharpe REAL, cagr TEXT, maxdd TEXT, n_trades TEXT,
  p_value REAL, dsr REAL, note TEXT, rel_path TEXT,
  has_folder INTEGER, has_report INTEGER, has_metrics INTEGER
);
CREATE TABLE metrics (
  num TEXT, key TEXT, value_num REAL, value_text TEXT, PRIMARY KEY (num, key)
);
CREATE TABLE metrics_json (num TEXT PRIMARY KEY, json TEXT);
CREATE INDEX idx_strat_status ON strategies(status);
CREATE INDEX idx_strat_bucket ON strategies(bucket);
"""


def status_bucket(status: str | None) -> str:
    """Map a free-text CATALOG status to a coarse bucket for summaries/filtering.

    The Status column is rich free text (e.g. 'abgelehnt (Roll-Artefakt)',
    'testing (Edge real, ...)'); this collapses it to the canonical lifecycle
    buckets defined in CATALOG.md's header.
    """
    s = (status or "").lower()
    if not s:
        return "none"
    if "abgelehnt" in s or "reject" in s:
        return "rejected"
    if "deferred" in s or "daten-blocker" in s or "nicht getestet" in s:
        return "deferred"
    if "validated" in s or "validiert" in s:
        return "validated"
    if "kandidat" in s or "candidate" in s:
        return "candidate"
    if "testing" in s:
        return "testing"
    if "overlay" in s:
        return "overlay"
    if any(w in s for w in ("abgeschlossen", "dokumentiert", "diagnose", "messlatte")):
        return "done"
    return "other"


def _parse_float(s: str | None) -> float | None:
    """Parse a CATALOG numeric cell ('7.6%', '~10', 'n/a', '-3.65') to float or None."""
    if s is None:
        return None
    cleaned = s.strip().replace("%", "").replace("~", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_catalog(catalog_path: Path) -> dict[str, dict]:
    """Parse the ``CATALOG.md`` markdown table into ``{num: row-dict}``."""
    rows: dict[str, dict] = {}
    if not catalog_path.exists():
        return rows
    for line in catalog_path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not _NUM_RE.match(cells[0]):
            continue
        if len(cells) > 12:  # a Notiz cell containing a literal '|'
            cells = cells[:11] + [" | ".join(cells[11:])]
        cells += [""] * (12 - len(cells))
        rows[cells[0]] = {
            "name": cells[1], "category": cells[2], "hypothesis": cells[3],
            "status": cells[4], "sharpe": _parse_float(cells[5]), "cagr": cells[6],
            "maxdd": cells[7], "n_trades": cells[8], "p_value": _parse_float(cells[9]),
            "dsr": _parse_float(cells[10]), "note": cells[11],
        }
    return rows


def build_registry(repo_root: Path | str | None = None,
                   db_path: Path | str | None = None) -> dict[str, Any]:
    """(Re)build the registry DB from CATALOG.md + strategies/*/results/metrics.json.

    Returns a summary dict (counts + db path). Idempotent: an existing DB is replaced.
    """
    settings = get_settings()
    repo_root = Path(repo_root) if repo_root else settings.backtest_dir
    db_path = Path(db_path) if db_path else settings.registry_db

    catalog = parse_catalog(repo_root / "CATALOG.md")
    folders: dict[str, Path] = {}
    strat_dir = repo_root / "strategies"
    if strat_dir.exists():
        for d in sorted(strat_dir.iterdir()):
            m = d.is_dir() and _FOLDER_RE.match(d.name)
            if m:
                folders[m.group(1)] = d

    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(_SCHEMA)
        nums = sorted(set(catalog) | set(folders))
        n_metric_rows = 0
        for num in nums:
            cat = catalog.get(num, {})
            folder = folders.get(num)
            rel = folder.relative_to(repo_root).as_posix() if folder else None
            report = bool(folder and (folder / "REPORT.md").exists())
            mpath = (folder / "results" / "metrics.json") if folder else None
            has_metrics = bool(mpath and mpath.exists())
            con.execute(
                "INSERT INTO strategies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (num, folder.name if folder else None, cat.get("name"),
                 cat.get("category"), cat.get("hypothesis"), cat.get("status"),
                 status_bucket(cat.get("status")),
                 cat.get("sharpe"), cat.get("cagr"), cat.get("maxdd"),
                 cat.get("n_trades"), cat.get("p_value"), cat.get("dsr"),
                 cat.get("note"), rel, int(folder is not None), int(report),
                 int(has_metrics)),
            )
            if has_metrics:
                n_metric_rows += _ingest_metrics(con, num, mpath)
        con.commit()
        summary = {
            "strategies": len(nums),
            "with_folder": sum(1 for n in nums if n in folders),
            "with_metrics": con.execute(
                "SELECT COUNT(*) FROM strategies WHERE has_metrics=1").fetchone()[0],
            "metric_rows": n_metric_rows,
            "db_path": str(db_path),
        }
    finally:
        con.close()
    return summary


def _ingest_metrics(con: sqlite3.Connection, num: str, mpath: Path) -> int:
    """Store the raw metrics.json blob and flatten its top-level scalars. Returns count."""
    try:
        raw = mpath.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError, ValueError):
        return 0
    con.execute("INSERT INTO metrics_json VALUES (?,?)", (num, raw))
    n = 0
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, bool):
                con.execute("INSERT OR REPLACE INTO metrics VALUES (?,?,?,?)",
                            (num, key, float(val), str(val)))
            elif isinstance(val, (int, float)):
                con.execute("INSERT OR REPLACE INTO metrics VALUES (?,?,?,?)",
                            (num, key, float(val), None))
            elif isinstance(val, str):
                con.execute("INSERT OR REPLACE INTO metrics VALUES (?,?,?,?)",
                            (num, key, None, val))
            else:
                continue  # nested dict/list lives only in the raw blob
            n += 1
    return n


# --------------------------------------------------------------------- query API
def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open the registry with row access by column name."""
    db_path = Path(db_path) if db_path else get_settings().registry_db
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    return con


def list_strategies(db_path: Path | str | None = None,
                    status: str | None = None) -> list[dict]:
    """All strategy rows (optionally filtered by status), ordered by number."""
    con = connect(db_path)
    try:
        q, args = "SELECT * FROM strategies", []
        if status:
            q += " WHERE status = ?"
            args.append(status)
        q += " ORDER BY num"
        return [dict(r) for r in con.execute(q, args).fetchall()]
    finally:
        con.close()


def get_strategy(num: str, db_path: Path | str | None = None) -> dict | None:
    """A single strategy row + its flattened metrics, or None."""
    con = connect(db_path)
    try:
        row = con.execute("SELECT * FROM strategies WHERE num = ?", (num,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["metrics"] = {
            m["key"]: (m["value_num"] if m["value_text"] is None else m["value_text"])
            for m in con.execute("SELECT * FROM metrics WHERE num = ?", (num,)).fetchall()
        }
        return out
    finally:
        con.close()


def status_counts(db_path: Path | str | None = None) -> dict[str, int]:
    """Count of strategies per raw (free-text) status (descending)."""
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT status, COUNT(*) FROM strategies GROUP BY status ORDER BY 2 DESC"
        ).fetchall()
        return {(r[0] or "(none)"): r[1] for r in rows}
    finally:
        con.close()


def bucket_counts(db_path: Path | str | None = None) -> dict[str, int]:
    """Count of strategies per coarse lifecycle bucket (descending)."""
    con = connect(db_path)
    try:
        rows = con.execute(
            "SELECT bucket, COUNT(*) FROM strategies GROUP BY bucket ORDER BY 2 DESC"
        ).fetchall()
        return {r[0]: r[1] for r in rows}
    finally:
        con.close()
