"""Swarm Command Center engine — hybrid local/cloud multi-agent orchestration.

This module is the *generic, framework-free* core of the Swarm desk. It owns the
two LLM transports and the aggregation/verdict logic, but knows nothing about
FastAPI or where the drones' data comes from (that wiring lives in
``apps/api/swarm.py``). Everything here is unit-testable without a network.

Architecture
------------
* **Worker drones (local, Ollama):** small specialised models that each narrate
  one isolated, already-computed signal into a lean JSON line. Cheap, parallel.
* **Commander (cloud, Gemini free tier):** receives the *aggregated* drone JSON
  (one compact prompt — saves API requests) and returns the final routing verdict
  (which strategies ACTIVE/PAUSED + allocation weight + an honest reasoning).

Robustness is the whole point: if Ollama is unreachable the drones fall back to a
deterministic template; if Gemini is unreachable / out of quota the commander
falls back to a transparent rule engine. The Gemini client additionally walks a
**model fallback chain** (e.g. ``gemini-2.5-flash`` → ``gemini-2.0-flash``) with
exponential backoff on ``429``/``503``, so a free-tier quota hit degrades to the
next model rather than failing.
"""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

# ── public status vocabulary (shared with the frontend) ─────────────────────
DRONE_STATUSES = ("idle", "computing", "done", "error")


class SwarmUnavailable(RuntimeError):
    """Raised by a transport when its service can't satisfy a request."""


# ── JSON extraction from messy LLM text ─────────────────────────────────────
def extract_json(text: str | None) -> Any | None:
    """Best-effort parse of a JSON object/array out of a raw LLM response.

    Handles ```code fences``` and leading/trailing prose by scanning for the
    first balanced ``{...}`` / ``[...]``. Returns ``None`` if nothing parses.
    """
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_]*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t).strip()
    try:
        return json.loads(t)
    except (json.JSONDecodeError, ValueError):
        pass
    start = next((i for i, ch in enumerate(t) if ch in "{["), None)
    if start is None:
        return None
    # shrink from the end until a prefix parses (tolerates trailing junk)
    for end in range(len(t), start, -1):
        if t[end - 1] not in "}]":
            continue
        try:
            return json.loads(t[start:end])
        except (json.JSONDecodeError, ValueError):
            continue
    return None


# ── Ollama transport (local worker drones) ──────────────────────────────────
class OllamaClient:
    """Thin client for a local Ollama server (the drones' brain).

    Args:
        base_url: e.g. ``http://localhost:11434`` (point at the Mac M5 over LAN
            by changing this in config — no code change needed).
        model: the small model the drones share (e.g. ``llama3``).
        timeout: per-request timeout in seconds.
    """

    def __init__(self, base_url: str, model: str, timeout: float = 45.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def available(self) -> tuple[bool, list[str]]:
        """``(reachable, [model names])`` — a fast ping of ``/api/tags``."""
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=min(self.timeout, 4.0))
            r.raise_for_status()
            models = [m.get("name", "") for m in r.json().get("models", [])]
            return True, models
        except (httpx.HTTPError, ValueError):
            return False, []

    def generate_json(self, prompt: str, system: str | None = None,
                      temperature: float = 0.2) -> dict:
        """Run the model with ``format=json`` and return the parsed object.

        Raises :class:`SwarmUnavailable` on any transport/parse failure so the
        caller can fall back deterministically.
        """
        body: dict[str, Any] = {
            "model": self.model, "prompt": prompt, "stream": False,
            "format": "json", "options": {"temperature": temperature},
        }
        if system:
            body["system"] = system
        try:
            r = httpx.post(f"{self.base_url}/api/generate", json=body, timeout=self.timeout)
            r.raise_for_status()
            text = r.json().get("response", "")
        except httpx.HTTPError as e:
            raise SwarmUnavailable(f"ollama: {type(e).__name__}: {e}") from e
        data = extract_json(text)
        if not isinstance(data, dict):
            raise SwarmUnavailable("ollama: response was not JSON")
        return data


# ── Gemini transport (cloud commander) with model fallback + backoff ─────────
_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


@dataclass
class GeminiResult:
    """Outcome of a commander call: the parsed JSON plus provenance."""

    data: dict
    model_used: str
    attempts: int
    raw: str = ""


class GeminiClient:
    """Google AI Studio (Gemini) client with a model fallback chain.

    On ``429`` (rate/quota) or ``503`` it retries the *same* model with
    exponential backoff; once a model is exhausted it advances to the next model
    in ``models`` (the dynamic ``2.5-flash`` → ``2.0-flash`` switch the user
    asked for). ``400/401/403`` fail fast (bad key / bad request — retrying won't
    help). ``responseMimeType=application/json`` forces parseable output.
    """

    def __init__(self, api_key: str, models: list[str], timeout: float = 60.0,
                 max_retries: int = 3, base_delay: float = 1.5,
                 _sleep=time.sleep) -> None:
        self.api_key = api_key
        self.models = [m for i, m in enumerate(models) if m and m not in models[:i]]
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._sleep = _sleep  # injectable for tests

    def _call(self, model: str, prompt: str, system: str | None,
              temperature: float) -> str:
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        r = httpx.post(
            _GEMINI_ENDPOINT.format(model=model),
            params={"key": self.api_key},
            json=body, timeout=self.timeout,
        )
        if r.status_code in (429, 503):
            raise _Retryable(r.status_code)
        r.raise_for_status()
        cands = r.json().get("candidates", [])
        if not cands:
            raise SwarmUnavailable("gemini: no candidates (possibly blocked)")
        parts = cands[0].get("content", {}).get("parts", [{}])
        return "".join(p.get("text", "") for p in parts)

    def generate_json(self, prompt: str, system: str | None = None,
                      temperature: float = 0.3) -> GeminiResult:
        """Return the commander's parsed JSON, walking models + backing off.

        Raises :class:`SwarmUnavailable` only if *every* model is exhausted or a
        non-retryable error occurs.
        """
        attempts = 0
        last_err: Exception | None = None
        for model in self.models:
            for retry in range(self.max_retries):
                attempts += 1
                try:
                    text = self._call(model, prompt, system, temperature)
                    data = extract_json(text)
                    if not isinstance(data, dict):
                        raise SwarmUnavailable("gemini: response was not JSON")
                    return GeminiResult(data=data, model_used=model,
                                        attempts=attempts, raw=text)
                except _Retryable as e:
                    last_err = e
                    if retry < self.max_retries - 1:
                        delay = self.base_delay * (2 ** retry) + random.uniform(0, 0.4)
                        self._sleep(delay)
                    # else: exhausted this model -> fall through to next model
                except httpx.HTTPStatusError as e:  # 4xx (bad key/request): fail fast
                    raise SwarmUnavailable(f"gemini: HTTP {e.response.status_code}") from e
                except httpx.HTTPError as e:
                    last_err = e
                    break  # transport error -> try next model
        raise SwarmUnavailable(f"gemini: all models exhausted ({last_err})")


class _Retryable(Exception):
    """Internal marker for a retryable Gemini status (429/503)."""

    def __init__(self, status: int) -> None:
        super().__init__(f"retryable {status}")
        self.status = status


# ── drone narration (Ollama → headline, with deterministic fallback) ─────────
_DRONE_SYSTEM = (
    "You are a specialised quant worker drone. You receive ONE pre-computed market "
    "signal as JSON and must return STRICT JSON: {\"headline\": <one terse German "
    "sentence, <=140 chars, trader tone>, \"stance\": one of \"risk_on\"|\"risk_off\""
    "|\"neutral\"}. No commentary, JSON only."
)


def drone_narrate(kind: str, signal: dict, fallback_headline: str,
                  fallback_stance: str, ollama: OllamaClient | None) -> tuple[str, str, str]:
    """Turn a drone's raw ``signal`` into ``(headline, stance, model_used)``.

    Uses the local model when available; otherwise the deterministic
    ``fallback_*`` the caller computed from the same data. Never raises.
    """
    if ollama is not None:
        try:
            prompt = (f"Drone task: {kind}\nSignal JSON:\n"
                      f"{json.dumps(signal, ensure_ascii=False)}")
            out = ollama.generate_json(prompt, system=_DRONE_SYSTEM, temperature=0.2)
            headline = str(out.get("headline") or "").strip() or fallback_headline
            stance = str(out.get("stance") or "").strip().lower()
            if stance not in ("risk_on", "risk_off", "neutral"):
                stance = fallback_stance
            return headline[:200], stance, ollama.model
        except SwarmUnavailable:
            pass
    return fallback_headline, fallback_stance, "deterministic"


# ── commander aggregation + verdict ─────────────────────────────────────────
_COMMANDER_SYSTEM = (
    "Du bist der COMMANDER eines Quant-Trading-Desks. Du erhältst (1) das aktuelle "
    "Marktregime, (2) die aggregierten JSON-Berichte mehrerer lokaler Analyse-Drohnen "
    "(Marktregime, Saisonalität, COT-Positionierung) und (3) die Liste handelbarer "
    "Strategien — jede mit ihrem regime-konditionalen Status (regime_status ACTIVE/"
    "PAUSED aus echtem Conditional-Backtesting), den erlaubten Regimes (allowed_regimes) "
    "und ihrer Sharpe IM AKTUELLEN Regime. Fälle ein finales, ungeschöntes Urteil, "
    "WELCHE Strategien jetzt ACTIVE oder PAUSED sein sollen und mit welchem "
    "Allokationsgewicht. WICHTIG: Respektiere regime_status als starkes Prior — eine "
    "Strategie, die im aktuellen Regime nicht qualifiziert (PAUSED) ist, nur dann ACTIVE "
    "schalten, wenn die Drohnen das klar rechtfertigen, und das begründen. Antworte "
    "AUSSCHLIESSLICH mit striktem JSON in genau diesem Schema:\n"
    "{\n"
    '  "regime_summary": "<1 Satz: aktuelles Gesamtbild>",\n'
    '  "verdict": "<2-4 Sätze ungeschönte Begründung, deutsch>",\n'
    '  "risk_note": "<1 Satz Risiko-/Vorbehalt>",\n'
    '  "allocations": [\n'
    '    {"num": "<strategie-num>", "action": "ACTIVE"|"PAUSED", '
    '"weight": <0..1>, "reason": "<knapp, deutsch>"}\n'
    "  ]\n"
    "}\n"
    "Gewichte der ACTIVE-Strategien sollten in Summe ~1.0 ergeben. PAUSED -> weight 0. "
    "Begründe Pausierungen explizit (z.B. 'COT überhitzt', 'Regime passt nicht')."
)


def build_commander_prompt(drones: list[dict], strategies: list[dict],
                           regime_context: dict | None = None) -> str:
    """Compose the single aggregated prompt the commander reasons over.

    ``drones`` are the lean drone result dicts; ``strategies`` is the routable book.
    When a strategy carries Phase-2 regime fields (``regime_status``/``allowed_regimes``
    /``current_regime_sharpe`` from :mod:`quantlab.conditional`) they are included so the
    commander routes on realised regime evidence, not a blunt top-Sharpe list.
    ``regime_context`` (current/previous regime + switch) frames the whole decision.
    One prompt for all drones = fewer API requests, the explicit goal of the design.
    """
    drone_view = [{"drone": d.get("drone"), "task": d.get("task"),
                   "status": d.get("status"), "headline": d.get("headline"),
                   "signal": d.get("signal")} for d in drones]
    strat_view = []
    for s in strategies:
        item = {"num": s.get("num"), "name": s.get("name"),
                "category": s.get("category"), "sharpe": s.get("sharpe")}
        if s.get("regime_status") is not None:
            item["regime_status"] = s.get("regime_status")
            item["allowed_regimes"] = s.get("allowed_regimes", [])
            item["current_regime_sharpe"] = s.get("current_regime_sharpe")
        strat_view.append(item)
    parts = []
    if regime_context:
        parts.append("=== AKTUELLES MARKTREGIME ===\n"
                     f"{json.dumps(regime_context, ensure_ascii=False, indent=1)}")
    parts.append("=== DROHNEN-BERICHTE (aggregiert) ===\n"
                 f"{json.dumps(drone_view, ensure_ascii=False, indent=1)}")
    parts.append("=== HANDELBARE STRATEGIEN (mit Regime-Status) ===\n"
                 f"{json.dumps(strat_view, ensure_ascii=False, indent=1)}")
    parts.append("Erstelle jetzt das JSON-Urteil.")
    return "\n\n".join(parts)


def _overall_stance(drones: list[dict]) -> str:
    """Reduce the drones' stances to one book-level stance (majority, regime-weighted)."""
    weight = {"regime": 2, "seasonal": 1, "cot": 1}
    score = 0.0
    for d in drones:
        st = (d.get("signal") or {}).get("stance") or d.get("stance")
        w = weight.get(d.get("drone"), 1)
        if st == "risk_on":
            score += w
        elif st == "risk_off":
            score -= w
    if score > 0.5:
        return "risk_on"
    if score < -0.5:
        return "risk_off"
    return "neutral"


# categories that structurally tolerate any regime (low-frequency flow / neutral)
_REGIME_AGNOSTIC = {"seasonal", "event", "event-driven", "rates", "flow",
                    "calendar", "carry", "stat-arb", "pairs", "market-neutral"}


def deterministic_commander(drones: list[dict], strategies: list[dict]) -> dict:
    """Transparent rule-based verdict used when Gemini is unavailable.

    Two modes: if the strategies carry Phase-2 regime fields (``regime_status``), route
    strictly by the conditional-backtest verdict (ACTIVE = qualifies in the current
    regime), weighting by current-regime Sharpe — the honest, evidence-based fallback.
    Otherwise fall back to the older category/stance heuristic. The cloud commander is
    the real brain; this just keeps the desk running with a sane default.
    """
    stance = _overall_stance(drones)
    cot_extreme = next((d for d in drones if d.get("drone") == "cot"
                        and (d.get("signal") or {}).get("n_extremes", 0) > 0), None)
    regime_mode = any(s.get("regime_status") is not None for s in strategies)
    allocs: list[dict] = []
    for s in strategies:
        if regime_mode:
            active = s.get("regime_status") == "ACTIVE"
            allowed = s.get("allowed_regimes") or []
            csh = s.get("current_regime_sharpe")
            reason = (f"qualifiziert im aktuellen Regime (Sharpe {csh:.2f})"
                      if active and isinstance(csh, (int, float))
                      else f"im aktuellen Regime nicht qualifiziert; erlaubt in {allowed or 'keinem'}")
            w = float(csh) if (active and isinstance(csh, (int, float))) else float(s.get("sharpe") or 0.0)
        else:
            cat = (s.get("category") or "").lower()
            agnostic = any(tok in cat for tok in _REGIME_AGNOSTIC)
            if agnostic or stance == "risk_on":
                active, reason = True, ("regime-agnostisches Flow-Bein" if agnostic
                                        else f"Regime {stance} → direktional zulässig")
            elif stance == "neutral":
                active = agnostic
                reason = "neutrales Regime, halbes Risiko" if agnostic else "neutrales Regime, direktional pausiert"
            else:
                active, reason = False, f"Regime {stance} → direktional pausiert"
            w = float(s.get("sharpe") or 0.0)
        allocs.append({"num": s.get("num"), "name": s.get("name"),
                       "action": "ACTIVE" if active else "PAUSED",
                       "weight": 0.0, "reason": reason, "_w": w})

    active = [a for a in allocs if a["action"] == "ACTIVE"]
    tot = sum(max(a["_w"], 0.1) for a in active)
    for a in allocs:
        a["weight"] = round(max(a["_w"], 0.1) / tot, 4) if (a in active and tot) else 0.0
        a.pop("_w", None)

    if regime_mode:
        summary = (f"Regime-konditionales Routing: {len(active)} von {len(allocs)} Beinen "
                   f"qualifizieren im aktuellen Marktregime.")
        verdict = (f"Routing nach Conditional-Backtest: nur Strategien aktiv, die im "
                   f"aktuellen Regime nachweislich verdienen ({len(active)} aktiv). "
                   f"Drohnen-Gesamtbild {stance.upper()}; Gewichte ∝ Regime-Sharpe.")
    else:
        summary = {"risk_on": "Risk-On — direktionale Beine zugelassen",
                   "risk_off": "Risk-Off — nur strukturelle Flow-Beine aktiv",
                   "neutral": "Gemischtes Regime — Flow aktiv, Direktional pausiert"}[stance]
        verdict = (f"Aggregiertes Drohnen-Bild: {stance.upper()}. {summary}. "
                   f"Gewichte Sharpe-proportional über die aktiven Beine.")
    note = ("COT zeigt institutionelle Extreme — Positionsgrößen vorsichtig."
            if cot_extreme else "Standard-Risiko; keine COT-Extreme gemeldet.")
    return {
        "regime_summary": summary,
        "verdict": verdict,
        "risk_note": note,
        "allocations": [{k: v for k, v in a.items()} for a in allocs],
        "model_used": "deterministic",
    }


def normalize_verdict(raw: dict, strategies: list[dict], model_used: str) -> dict:
    """Coerce an LLM verdict into the canonical shape + reconcile with the book.

    Guarantees every routable strategy appears exactly once (LLM omissions are
    filled as PAUSED), clamps weights to ``[0,1]``, and renormalises ACTIVE
    weights to sum ~1.0 so the UI/allocator can trust them.
    """
    by_num = {str(s.get("num")): s for s in strategies}
    seen: dict[str, dict] = {}
    for a in (raw.get("allocations") or []):
        num = str(a.get("num"))
        if num not in by_num or num in seen:
            continue
        action = "ACTIVE" if str(a.get("action", "")).upper() == "ACTIVE" else "PAUSED"
        try:
            w = max(0.0, min(1.0, float(a.get("weight", 0.0))))
        except (TypeError, ValueError):
            w = 0.0
        seen[num] = {"num": num, "name": by_num[num].get("name"), "action": action,
                     "weight": w if action == "ACTIVE" else 0.0,
                     "reason": str(a.get("reason") or "")[:240]}
    for num, s in by_num.items():  # fill omissions
        seen.setdefault(num, {"num": num, "name": s.get("name"), "action": "PAUSED",
                              "weight": 0.0, "reason": "vom Commander nicht erwähnt → pausiert"})
    allocs = list(seen.values())
    active = [a for a in allocs if a["action"] == "ACTIVE"]
    tot = sum(a["weight"] for a in active)
    if tot > 0:
        for a in active:
            a["weight"] = round(a["weight"] / tot, 4)
    elif active:  # ACTIVE but all-zero weights -> equal split
        for a in active:
            a["weight"] = round(1.0 / len(active), 4)
    return {
        "regime_summary": str(raw.get("regime_summary") or "")[:300],
        "verdict": str(raw.get("verdict") or "")[:1200],
        "risk_note": str(raw.get("risk_note") or "")[:400],
        "allocations": allocs,
        "model_used": model_used,
    }


def run_commander(drones: list[dict], strategies: list[dict],
                  gemini: GeminiClient | None, regime_context: dict | None = None) -> dict:
    """Produce the final routing verdict (cloud commander, else rule fallback).

    Returns the normalized verdict dict plus ``source`` ("gemini"|"deterministic")
    and ``commander_attempts``. ``regime_context`` (the current/previous regime + switch)
    grounds the cloud commander in the live market regime. Never raises.
    """
    if gemini is not None and strategies:
        try:
            prompt = build_commander_prompt(drones, strategies, regime_context)
            res = gemini.generate_json(prompt, system=_COMMANDER_SYSTEM, temperature=0.3)
            verdict = normalize_verdict(res.data, strategies, res.model_used)
            verdict.update(source="gemini", commander_attempts=res.attempts)
            return verdict
        except SwarmUnavailable as e:
            fb = deterministic_commander(drones, strategies)
            fb.update(source="deterministic", commander_attempts=0,
                      degraded_reason=str(e))
            return fb
    fb = deterministic_commander(drones, strategies)
    fb.update(source="deterministic", commander_attempts=0)
    return fb


@dataclass
class DroneSpec:
    """Static description of one worker drone (its identity + task)."""

    key: str
    label: str
    task: str
    accent: str
    fn: Any = field(default=None, repr=False)  # callable() -> signal dict
