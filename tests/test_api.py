"""Smoke tests for the FastAPI backend over the strategy registry.

Skips if httpx (required by Starlette's TestClient) is unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # make `apps.api.main` importable

from quantlab.registry import build_registry  # noqa: E402


@pytest.fixture(scope="module")
def client():
    build_registry()  # ensure the default registry exists for the API to read
    from apps.api.main import app

    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["registry_exists"] is True


def test_strategies_list(client):
    r = client.get("/strategies")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 50  # the catalog has 100+ strategies
    assert {"num", "name", "bucket", "sharpe"} <= set(rows[0])


def test_buckets(client):
    r = client.get("/strategies/buckets")
    assert r.status_code == 200
    body = r.json()
    assert "buckets" in body and body["buckets"].get("rejected", 0) > 0


def test_single_and_404(client):
    r = client.get("/strategies/0050")
    assert r.status_code == 200
    assert r.json()["num"] == "0050"
    assert client.get("/strategies/9999").status_code == 404


def test_overview(client):
    r = client.get("/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["n_strategies"] > 50
    assert isinstance(body["sharpes"], list) and len(body["sharpes"]) > 10
    assert body["buckets"].get("rejected", 0) > 0
    assert len(body["top"]) > 0 and "sharpe" in body["top"][0]


def test_plots_list_and_serve(client):
    # 0078 (treasury auction) ships results/treasury_auction.png
    lst = client.get("/strategies/0078/plots")
    assert lst.status_code == 200
    names = lst.json()["plots"]
    assert isinstance(names, list)
    if names:
        img = client.get(f"/strategies/0078/plot/{names[0]}")
        assert img.status_code == 200
        assert img.headers["content-type"] == "image/png"


def test_plot_rejects_non_png_and_missing(client):
    assert client.get("/strategies/0078/plot/metrics.json").status_code == 404  # not a .png
    assert client.get("/strategies/0078/plot/nope.png").status_code == 404      # missing


def test_ideas(client):
    r = client.get("/ideas")
    assert r.status_code == 200
    body = r.json()
    assert "ideas" in body and "exists" in body
    if body["exists"]:
        assert body["count"] > 0 and "ID" in body["ideas"][0]


def test_live_book_served_from_cache(client):
    # seed the TTL cache so the endpoint returns without the heavy live compute
    import time as _t

    from apps.api import main as apimain

    apimain._LIVE_CACHE.update(
        ts=_t.time(),
        data={"ok": True, "book_sharpe": 1.21, "gross_exposure_pct": 42.0,
              "positions": [{"instrument": "EURUSD=X", "weight_pct": 3.2}],
              "context": {"vix": 14.0}, "asof": "2026-06-20"},
    )
    r = client.get("/live/book")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["cached"] is True
    assert body["book_sharpe"] == 1.21 and body["positions"][0]["instrument"] == "EURUSD=X"


def test_agent_run_and_poll_mock(client):
    import time as _t

    r = client.post("/agent/run", json={"hypothesis": "turn of month effect on equities",
                                         "backend": "mock", "dry_run": True})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    job = None
    for _ in range(80):
        jr = client.get(f"/agent/job/{job_id}")
        assert jr.status_code == 200
        job = jr.json()
        if job["status"] != "running":
            break
        _t.sleep(0.25)
    assert job["status"] == "done", job
    res = job["result"]
    assert "run_py" in res and "dups" in res
    assert res["branch"].startswith("agent/")  # ran on an isolated sandbox branch


def test_agent_run_requires_hypothesis(client):
    assert client.post("/agent/run", json={"hypothesis": "   "}).status_code == 400


def test_agent_job_unknown_404(client):
    assert client.get("/agent/job/does-not-exist").status_code == 404


def test_agent_evaluate_and_promote_unknown_404(client):
    assert client.post("/agent/evaluate", json={"job_id": "nope", "params": {}}).status_code == 404
    assert client.post("/agent/promote", json={"job_id": "nope"}).status_code == 404


def test_catalog_row_format(client):
    from apps.api.main import _catalog_row

    row = _catalog_row(
        "0200", "my-test-strategy", "A test hypothesis about momentum on equities",
        {"summary": {"sharpe": 1.23, "cagr": 0.15, "max_drawdown": -0.2, "n_trades": 42},
         "permutation": {"p_value": 0.03}, "deflated_sharpe": {"psr_deflated": 0.9}},
    )
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert len(cells) == 12  # matches CATALOG.md columns
    assert cells[0] == "0200" and cells[2] == "agent"
    assert cells[5] == "1.23" and cells[8] == "42"  # Sharpe, #Trades
