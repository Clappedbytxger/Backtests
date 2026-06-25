"""Per-item evaluation: turn a headline into a directional hypothesis.

Two-tier so the terminal is useful with *or* without a local model:

  1. If an LLM backend is available, prompt it for a structured JSON hypothesis,
     few-shot-primed with the most relevant past :class:`Lesson` entries so the
     agent visibly learns from earlier misses.
  2. On any failure (no model, bad JSON, empty output) fall back to a transparent
     keyword/sentiment **heuristic** so every item still gets a hypothesis.

The heuristic is intentionally simple and auditable — it is a baseline, not the
edge. Both paths share the same :class:`Hypothesis` output shape.
"""

from __future__ import annotations

import json
import re

from .models import (
    Category,
    Hypothesis,
    ImpactDirection,
    Lesson,
    NewsItem,
    Priority,
    default_window_hours,
)

# ── category -> default tradable proxy (yfinance symbols) ────────────────────
CATEGORY_PROXY: dict[Category, str] = {
    Category.MAKRO: "SPY",
    Category.AKTIEN: "SPY",
    Category.KRYPTO: "BTC-USD",
    Category.FX: "EURUSD=X",
    Category.ROHSTOFFE: "GC=F",
    Category.SONSTIGES: "SPY",
}

# ── named-asset keyword -> ticker (scanned in the headline for a sharper call) ─
ASSET_KEYWORDS: dict[str, str] = {
    "bitcoin": "BTC-USD", "btc": "BTC-USD",
    "ethereum": "ETH-USD", "ether": "ETH-USD", "eth": "ETH-USD",
    "solana": "SOL-USD", "sol": "SOL-USD",
    "gold": "GC=F", "silver": "SI=F", "silber": "SI=F",
    "oil": "CL=F", "öl": "CL=F", "crude": "CL=F", "brent": "BZ=F",
    "natural gas": "NG=F", "erdgas": "NG=F",
    "nasdaq": "QQQ", "s&p": "SPY", "s&p 500": "SPY", "dow": "DIA",
    "apple": "AAPL", "tesla": "TSLA", "nvidia": "NVDA", "microsoft": "MSFT",
    "euro": "EURUSD=X", "eur/usd": "EURUSD=X", "dollar": "DX-Y.NYB",
    "yen": "JPY=X", "pound": "GBPUSD=X", "sterling": "GBPUSD=X",
}

# ── bilingual sentiment lexicon (EN + DE) ────────────────────────────────────
BULLISH_WORDS = {
    "surge", "rally", "soar", "jump", "gain", "rise", "beat", "record", "boom",
    "upgrade", "strong", "growth", "expansion", "stimulus", "dovish", "cut",
    "approval", "breakthrough", "optimism", "recovery", "inflow", "buyback",
    "steigt", "rallye", "wächst", "stark", "rekord", "erholung", "aufschwung",
    "gewinn", "zinssenkung", "wachstum", "optimistisch", "durchbruch",
}
BEARISH_WORDS = {
    "plunge", "crash", "slump", "fall", "drop", "miss", "loss", "cut", "layoff",
    "downgrade", "weak", "recession", "default", "hawkish", "hike", "ban",
    "fraud", "selloff", "fear", "warning", "sanction", "collapse", "outflow",
    "fällt", "einbruch", "absturz", "schwach", "rezession", "verlust", "warnung",
    "zinserhöhung", "sanktion", "verbot", "abschwung", "panik", "krise",
}

_TOKEN = re.compile(r"[a-zA-Zäöüß&]+")

SYSTEM_PROMPT = (
    "You are a buy-side market analyst. Given a financial news headline, output a "
    "concise JSON hypothesis about the likely short-term price reaction. "
    "Respond with ONLY a JSON object, no prose."
)


def detect_asset(item: NewsItem) -> tuple[str, str]:
    """(ticker, scope) — a named instrument if one is in the headline, else the proxy."""
    text = f"{item.title} {item.content}".lower()
    for kw in sorted(ASSET_KEYWORDS, key=len, reverse=True):
        if kw in text:
            return ASSET_KEYWORDS[kw], "asset"
    return CATEGORY_PROXY.get(item.category, "SPY"), "market"


def heuristic_hypothesis(item: NewsItem) -> Hypothesis:
    """Transparent keyword-sentiment baseline. Always succeeds."""
    tokens = {t.lower() for t in _TOKEN.findall(f"{item.title} {item.content}")}
    bull = len(tokens & BULLISH_WORDS)
    bear = len(tokens & BEARISH_WORDS)
    score = bull - bear

    if score > 0:
        direction = ImpactDirection.BULLISH
    elif score < 0:
        direction = ImpactDirection.BEARISH
    else:
        direction = ImpactDirection.NEUTRAL

    asset, scope = detect_asset(item)
    # confidence scales with signal strength and headline priority.
    strength = min(abs(score), 3) / 3.0
    prio_boost = {Priority.HIGH: 0.15, Priority.MEDIUM: 0.0, Priority.LOW: -0.1}
    confidence = round(min(0.9, max(0.2, 0.4 + 0.45 * strength + prio_boost[item.priority])), 2)

    if direction is ImpactDirection.NEUTRAL:
        rationale = (f"No clear directional sentiment terms for {asset}; "
                     "treating as noise pending confirmation.")
    else:
        hits = sorted((tokens & (BULLISH_WORDS if score > 0 else BEARISH_WORDS)))
        rationale = (f"{direction.value} read on {asset} — sentiment terms "
                     f"{', '.join(hits[:4]) or 'n/a'} dominate the headline.")

    return Hypothesis(
        direction=direction, asset=asset, scope=scope,
        rationale=rationale, confidence=confidence,
        verify_after_hours=default_window_hours(item.priority),
        model="heuristic",
    )


def _lessons_block(lessons: list[Lesson]) -> str:
    if not lessons:
        return "None yet."
    out = []
    for l in lessons:
        out.append(
            f"- [{l.category.value}] \"{l.headline[:80]}\": predicted "
            f"{l.predicted.value} but actual was {l.actual.value}. "
            f"Lesson: {l.takeaway}"
        )
    return "\n".join(out)


def build_prompt(item: NewsItem, lessons: list[Lesson]) -> str:
    proxy = CATEGORY_PROXY.get(item.category, "SPY")
    return (
        "Past mistakes to learn from (do not repeat these errors):\n"
        f"{_lessons_block(lessons)}\n\n"
        "Now evaluate this headline:\n"
        f"Category: {item.category.value}\n"
        f"Priority: {item.priority.value}\n"
        f"Source: {item.source}\n"
        f"Title: {item.title}\n"
        f"Body: {item.content[:600] or '(headline only)'}\n\n"
        "Return JSON with exactly these keys:\n"
        '{\n'
        '  "direction": "Bullish" | "Bearish" | "Neutral",\n'
        f'  "asset": "<ticker symbol, e.g. {proxy} or BTC-USD>",\n'
        '  "scope": "asset" | "market",\n'
        '  "confidence": <0.0-1.0>,\n'
        '  "rationale": "<one or two sentences>"\n'
        '}\n'
    )


def _parse_llm_json(text: str) -> dict | None:
    """Extract the first JSON object from a model response (tolerant)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _coerce_direction(value: str) -> ImpactDirection:
    v = (value or "").strip().lower()
    if v.startswith("bull"):
        return ImpactDirection.BULLISH
    if v.startswith("bear"):
        return ImpactDirection.BEARISH
    return ImpactDirection.NEUTRAL


def llm_hypothesis(item: NewsItem, backend, lessons: list[Lesson]) -> Hypothesis | None:
    """Ask the LLM backend for a structured hypothesis; ``None`` on any failure."""
    try:
        raw = backend.generate(
            build_prompt(item, lessons), system=SYSTEM_PROMPT,
            max_tokens=400, temperature=0.2,
        )
    except Exception:  # noqa: BLE001 - model/runtime failure -> caller falls back
        return None
    data = _parse_llm_json(raw or "")
    if not data:
        return None

    fallback_asset, fallback_scope = detect_asset(item)
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    return Hypothesis(
        direction=_coerce_direction(str(data.get("direction", "Neutral"))),
        asset=str(data.get("asset") or fallback_asset).strip()[:24] or fallback_asset,
        scope="asset" if str(data.get("scope", fallback_scope)).lower() == "asset" else "market",
        rationale=str(data.get("rationale", "")).strip()[:400],
        confidence=round(min(1.0, max(0.0, confidence)), 2),
        verify_after_hours=default_window_hours(item.priority),
        model=getattr(backend, "name", "llm"),
    )


def evaluate(item: NewsItem, backend=None, lessons: list[Lesson] | None = None) -> Hypothesis:
    """Produce a hypothesis for ``item``: LLM if available, heuristic otherwise.

    ``backend`` is an :class:`~agent.llm.LLMBackend` (or ``None``). A ``mock``
    backend or any failure transparently falls through to the heuristic, so the
    feed is never blocked on model availability.
    """
    lessons = lessons or []
    if backend is not None and getattr(backend, "name", "") not in ("", "mock"):
        hyp = llm_hypothesis(item, backend, lessons)
        if hyp is not None:
            return hyp
    return heuristic_hypothesis(item)
