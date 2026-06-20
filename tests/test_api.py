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
