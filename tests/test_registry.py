"""Tests for the SQLite strategy registry (CATALOG parsing + ingestion)."""

from __future__ import annotations

import json

from quantlab.registry import (
    build_registry,
    get_strategy,
    list_strategies,
    parse_catalog,
    status_counts,
)

_CATALOG = (
    "# Catalog\n\n"
    "| ID | Name | Kategorie | Hypothese | Status | Sharpe | CAGR | MaxDD | #Trades | p-Wert | DSR | Notiz |\n"
    "| -- | ---- | --------- | --------- | ------ | -----: | ---: | ----: | ------: | -----: | --: | ----- |\n"
    "| 0001 | Alpha | seasonal | h1 | validated | 1.23 | 7.6% | -10% | 50 | 0.01 | 0.90 | a note |\n"
    "| 0002 | Beta | momentum | h2 | rejected | -0.5 | 1% | -5% | ~10 | n/a | 0.00 | b note |\n"
    "| 0003 | Gamma | macro | h3 | overlay | 0.8 | 5% | -8% | 30 | 0.04 | 0.50 | no folder |\n"
)


def _mini_repo(root):
    res = root / "strategies" / "0001_alpha" / "results"
    res.mkdir(parents=True)
    (root / "strategies" / "0001_alpha" / "REPORT.md").write_text("# 0001")
    (res / "metrics.json").write_text(
        json.dumps({"sharpe": 1.23, "cagr": 0.1, "name": "alpha", "passed": True,
                    "nested": {"x": 1}})
    )
    (root / "strategies" / "0002_beta").mkdir(parents=True)  # folder, no metrics
    (root / "CATALOG.md").write_text(_CATALOG, encoding="utf-8")


def test_parse_catalog(tmp_path):
    _mini_repo(tmp_path)
    rows = parse_catalog(tmp_path / "CATALOG.md")
    assert set(rows) == {"0001", "0002", "0003"}
    assert rows["0001"]["sharpe"] == 1.23
    assert rows["0001"]["status"] == "validated"
    assert rows["0002"]["p_value"] is None  # 'n/a' -> None


def test_build_and_query(tmp_path):
    _mini_repo(tmp_path)
    db = tmp_path / "reg.db"
    s = build_registry(repo_root=tmp_path, db_path=db)
    assert s["strategies"] == 3
    assert s["with_folder"] == 2
    assert s["with_metrics"] == 1

    rows = list_strategies(db_path=db)
    assert len(rows) == 3
    a = next(r for r in rows if r["num"] == "0001")
    assert a["slug"] == "0001_alpha" and a["has_metrics"] == 1 and a["has_report"] == 1
    g = next(r for r in rows if r["num"] == "0003")
    assert g["has_folder"] == 0  # catalog row without a strategy folder

    full = get_strategy("0001", db_path=db)
    assert full["metrics"]["sharpe"] == 1.23
    assert full["metrics"]["passed"] == "True"        # bool stored as text
    assert "nested" not in full["metrics"]            # nested dict only in raw blob

    counts = status_counts(db_path=db)
    assert counts == {"validated": 1, "rejected": 1, "overlay": 1}


def test_status_filter(tmp_path):
    _mini_repo(tmp_path)
    db = tmp_path / "reg.db"
    build_registry(repo_root=tmp_path, db_path=db)
    assert [r["num"] for r in list_strategies(db_path=db, status="validated")] == ["0001"]
