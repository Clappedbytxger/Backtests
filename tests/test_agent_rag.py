"""Tests for the RAG retriever (TF-IDF ranking, corpus loading, catalog de-dup)."""

from __future__ import annotations

from agent.rag import (
    Doc,
    TfidfIndex,
    dedup_against_catalog,
    load_ideas_corpus,
    retrieve_context,
)


def test_tfidf_ranks_relevant_doc_top():
    docs = [
        Doc("A", "gold platinum seasonal turn of year jewelry demand"),
        Doc("B", "bitcoin intraday momentum session volatility crypto"),
        Doc("C", "treasury bond auction concession dealer supply rates"),
    ]
    idx = TfidfIndex(docs)
    assert idx.query("bond auction dealer supply concession", k=2)[0][0].id == "C"
    assert idx.query("crypto momentum intraday", k=1)[0][0].id == "B"


def test_empty_index_is_safe():
    assert TfidfIndex([]).query("anything") == []


def test_load_ideas_corpus(tmp_path):
    (tmp_path / "HYPOTHESES.csv").write_text(
        "ID,Titel,Markt,Kategorie,Kernidee_kurz,Prioritaet,Quelle,Verwandt,Status,Datei\n"
        "I0001,Gold turn of year,GC,seasonal,Long platinum over the new year,Hoch,#s1,neu,testing,x.md\n"
        "I0002,BTC momentum,BTC,momentum,Intraday session continuation,Mittel,#s2,neu,rejected,y.md\n",
        encoding="utf-8",
    )
    docs = load_ideas_corpus(tmp_path)
    assert len(docs) == 2 and docs[0].id == "I0001"
    res = retrieve_context("platinum new year seasonal", ideas_dir=tmp_path, k=1)
    assert res and res[0][0].id == "I0001"


def test_dedup_against_catalog(tmp_path):
    (tmp_path / "CATALOG.md").write_text(
        "| ID | Name | Kategorie | Hypothese | Status | Sharpe | CAGR | MaxDD | #Trades | p-Wert | DSR | Notiz |\n"
        "| -- | ---- | --------- | --------- | ------ | -----: | ---: | ----: | ------: | -----: | --: | ----- |\n"
        "| 0050 | Turn of Month | seasonal | long around month boundary equities | testing | 0.3 | 5% | -10% | 300 | 0.03 | 0.9 | flow |\n"
        "| 0012 | BTC intraday | momentum | crypto session momentum direction | rejected | -3 | -50% | -90% | 1250 | 1.0 | 0.0 | cost |\n",
        encoding="utf-8",
    )
    hits = dedup_against_catalog("turn of month long overlay on equities at month boundary",
                                 repo_root=tmp_path, k=2)
    assert hits and hits[0][0].id == "0050"  # flags the existing similar strategy
