"""Tests for the Swarm Command Center engine (:mod:`quantlab.swarm`).

Network-free: the Gemini transport is exercised by monkeypatching ``httpx.post``
to simulate a ``429`` quota hit (backoff) and a model fallback. Proves the JSON
data flow — drone aggregation, verdict normalisation, and the deterministic
fallbacks that keep the desk running without Ollama/Gemini.
"""

import json

import httpx
import pytest

from quantlab import swarm as sw


# ── JSON extraction ─────────────────────────────────────────────────────────
def test_extract_json_handles_fences_and_prose():
    assert sw.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert sw.extract_json('Hier das Urteil: {"action": "ACTIVE"} fertig.') == {"action": "ACTIVE"}
    assert sw.extract_json('[{"x": 1}, {"x": 2}]') == [{"x": 1}, {"x": 2}]
    assert sw.extract_json("not json at all") is None
    assert sw.extract_json("") is None


# ── deterministic commander + stance ────────────────────────────────────────
_DRONES_RISKON = [
    {"drone": "regime", "task": "t", "status": "done",
     "signal": {"stance": "risk_on"}, "headline": "h"},
    {"drone": "seasonal", "task": "t", "status": "done",
     "signal": {"stance": "risk_on"}, "headline": "h"},
    {"drone": "cot", "task": "t", "status": "done",
     "signal": {"stance": "neutral", "n_extremes": 2}, "headline": "h"},
]
_STRATS = [
    {"num": "0050", "name": "Turn-of-Month", "category": "seasonal", "sharpe": 0.9},
    {"num": "0070", "name": "SMC Portfolio", "category": "trend", "sharpe": 1.1},
    {"num": "0078", "name": "Auction Concession", "category": "rates", "sharpe": 0.8},
]


def test_overall_stance_regime_weighted():
    assert sw._overall_stance(_DRONES_RISKON) == "risk_on"
    riskoff = [{"drone": "regime", "signal": {"stance": "risk_off"}}]
    assert sw._overall_stance(riskoff) == "risk_off"
    assert sw._overall_stance([{"drone": "cot", "signal": {"stance": "neutral"}}]) == "neutral"


def test_deterministic_commander_shape_and_weights():
    v = sw.deterministic_commander(_DRONES_RISKON, _STRATS)
    assert set(v) >= {"regime_summary", "verdict", "risk_note", "allocations", "model_used"}
    assert v["model_used"] == "deterministic"
    assert len(v["allocations"]) == len(_STRATS)
    active = [a for a in v["allocations"] if a["action"] == "ACTIVE"]
    assert active, "risk-on should activate sleeves"
    assert abs(sum(a["weight"] for a in active) - 1.0) < 1e-6  # weights renormalised
    # the COT extreme should be flagged in the risk note
    assert "COT" in v["risk_note"]


def test_risk_off_pauses_directional_keeps_flow():
    drones = [{"drone": "regime", "signal": {"stance": "risk_off"}}]
    v = sw.deterministic_commander(drones, _STRATS)
    by = {a["num"]: a for a in v["allocations"]}
    assert by["0070"]["action"] == "PAUSED"        # directional trend paused
    assert by["0050"]["action"] == "ACTIVE"         # seasonal flow stays on
    assert by["0078"]["action"] == "ACTIVE"         # rates flow stays on


# ── verdict normalisation ───────────────────────────────────────────────────
def test_normalize_fills_omissions_and_renormalises():
    raw = {"regime_summary": "x", "verdict": "y", "risk_note": "z",
           "allocations": [{"num": "0050", "action": "ACTIVE", "weight": 0.3, "reason": "r"},
                           {"num": "0070", "action": "ACTIVE", "weight": 0.3, "reason": "r"}]}
    v = sw.normalize_verdict(raw, _STRATS, "gemini-2.5-flash")
    by = {a["num"]: a for a in v["allocations"]}
    assert set(by) == {"0050", "0070", "0078"}      # omitted 0078 filled
    assert by["0078"]["action"] == "PAUSED"
    active = [a for a in v["allocations"] if a["action"] == "ACTIVE"]
    assert abs(sum(a["weight"] for a in active) - 1.0) < 1e-6
    assert v["model_used"] == "gemini-2.5-flash"


def test_normalize_equal_split_when_active_but_zero_weight():
    raw = {"allocations": [{"num": "0050", "action": "ACTIVE", "weight": 0},
                           {"num": "0070", "action": "ACTIVE", "weight": 0}]}
    v = sw.normalize_verdict(raw, _STRATS, "m")
    active = [a for a in v["allocations"] if a["action"] == "ACTIVE"]
    assert all(abs(a["weight"] - 0.5) < 1e-6 for a in active)


# ── drone narration falls back without Ollama ───────────────────────────────
def test_drone_narrate_fallback_without_ollama():
    headline, stance, model = sw.drone_narrate(
        "regime", {"x": 1}, "FALLBACK HEADLINE", "risk_on", None)
    assert headline == "FALLBACK HEADLINE"
    assert stance == "risk_on"
    assert model == "deterministic"


# ── Gemini transport: backoff + model fallback (monkeypatched) ───────────────
class _FakeResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)


def _ok_payload(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_gemini_backs_off_then_succeeds(monkeypatch):
    """First two calls 429 (retry same model), third returns JSON."""
    calls = {"n": 0, "models": []}

    def fake_post(url, params=None, json=None, timeout=None):
        calls["n"] += 1
        calls["models"].append(url)
        if calls["n"] < 3:
            return _FakeResp(429)
        return _FakeResp(200, _ok_payload('{"verdict": "ok"}'))

    monkeypatch.setattr(sw.httpx, "post", fake_post)
    sleeps: list[float] = []
    gc = sw.GeminiClient("KEY", ["gemini-2.5-flash", "gemini-2.0-flash"],
                         max_retries=3, base_delay=0.01, _sleep=sleeps.append)
    res = gc.generate_json("p", system="s")
    assert res.data == {"verdict": "ok"}
    assert res.model_used == "gemini-2.5-flash"   # succeeded before falling back
    assert res.attempts == 3
    assert len(sleeps) == 2                         # backed off twice


def test_gemini_falls_back_to_second_model_on_quota(monkeypatch):
    """Primary model exhausts its retries on 429 → switch to fallback model."""
    def fake_post(url, params=None, json=None, timeout=None):
        if "gemini-2.5-flash" in url:
            return _FakeResp(429)                   # primary always rate-limited
        return _FakeResp(200, _ok_payload('{"verdict": "from-fallback"}'))

    monkeypatch.setattr(sw.httpx, "post", fake_post)
    gc = sw.GeminiClient("KEY", ["gemini-2.5-flash", "gemini-2.0-flash"],
                         max_retries=2, base_delay=0.0, _sleep=lambda _x: None)
    res = gc.generate_json("p")
    assert res.data == {"verdict": "from-fallback"}
    assert res.model_used == "gemini-2.0-flash"     # dynamic switch on quota


def test_gemini_bad_key_fails_fast(monkeypatch):
    def fake_post(url, params=None, json=None, timeout=None):
        return _FakeResp(403)

    monkeypatch.setattr(sw.httpx, "post", fake_post)
    gc = sw.GeminiClient("KEY", ["gemini-2.5-flash"], max_retries=3,
                         base_delay=0.0, _sleep=lambda _x: None)
    with pytest.raises(sw.SwarmUnavailable):
        gc.generate_json("p")


def test_run_commander_uses_deterministic_without_gemini():
    v = sw.run_commander(_DRONES_RISKON, _STRATS, None)
    assert v["source"] == "deterministic"
    assert v["allocations"]
