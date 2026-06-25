"""Bilingual (EN + DE) deeper briefing for a headline — generated on demand.

Two tiers, mirroring :mod:`news.agent`:

  1. If an LLM backend is available, prompt it for a thorough JSON write-up in
     both languages (what happened, why it matters, market impact, key risks).
  2. Otherwise build a structured template briefing from the item + its
     hypothesis, so every item still gets a readable document in both languages.

Generation is lazy and cached on ``NewsItem.document`` (the feed has high volume;
we never pre-generate a document for every item — only for the ones a user opens).
"""

from __future__ import annotations

import json
import re

from .models import Briefing, ImpactDirection, NewsItem

SYSTEM_PROMPT = (
    "You are a senior market strategist writing a concise research briefing on a "
    "single news headline. Be specific and neutral. Respond with ONLY a JSON "
    "object, no prose around it."
)

_IMPACT_DE = {
    ImpactDirection.BULLISH: "bullisch",
    ImpactDirection.BEARISH: "bärisch",
    ImpactDirection.NEUTRAL: "neutral",
}


def build_prompt(item: NewsItem) -> str:
    h = item.hypothesis
    hyp_line = (
        f"The agent's hypothesis: {h.direction.value} on {h.asset} "
        f"(confidence {h.confidence:.0%}). Reason: {h.rationale}"
        if h else "No hypothesis yet."
    )
    return (
        f"Headline: {item.title}\n"
        f"Category: {item.category.value}\n"
        f"Source: {item.source}\n"
        f"Body: {item.content[:600] or '(headline only)'}\n"
        f"{hyp_line}\n\n"
        "Write a briefing of ~120-160 words EACH in English and German covering: "
        "what happened, why it matters, the likely market impact (name the affected "
        "assets), and the key risk/uncertainty. Return JSON exactly as:\n"
        '{ "en": "<english briefing>", "de": "<deutsche Zusammenfassung>" }'
    )


def _parse_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _heuristic(item: NewsItem) -> Briefing:
    """Template briefing assembled from the structured fields. Always works."""
    h = item.hypothesis
    cat = item.category.value
    body = item.content.strip() or item.title
    if h is not None:
        impact_en = (
            f"The agent reads this as {h.direction.value.lower()} for {h.asset} "
            f"(confidence {h.confidence:.0%}). {h.rationale}"
        )
        impact_de = (
            f"Der Agent bewertet dies als {_IMPACT_DE[h.direction]} für {h.asset} "
            f"(Konfidenz {h.confidence:.0%}). {h.rationale}"
        )
        risk_en = (
            "Key risk: the move may already be priced in, or a second-order driver "
            "could dominate the immediate reaction."
        )
        risk_de = (
            "Hauptrisiko: Die Bewegung könnte bereits eingepreist sein, oder ein "
            "übergeordneter Treiber dominiert die unmittelbare Reaktion."
        )
    else:
        impact_en = "No hypothesis has been generated for this item yet."
        impact_de = "Für diesen Eintrag wurde noch keine Hypothese erstellt."
        risk_en = risk_de = ""

    en = (
        f"**What happened.** {body}\n\n"
        f"**Why it matters.** This is a {cat} headline from {item.source}. "
        f"Such developments typically move {cat.lower()}-sensitive assets.\n\n"
        f"**Market impact.** {impact_en}\n\n"
        f"{risk_en}"
    ).strip()
    de = (
        f"**Was ist passiert.** {body}\n\n"
        f"**Warum es relevant ist.** Eine {cat}-Meldung von {item.source}. "
        f"Solche Entwicklungen bewegen üblicherweise {cat.lower()}-sensitive Märkte.\n\n"
        f"**Markteinschätzung.** {impact_de}\n\n"
        f"{risk_de}"
    ).strip()
    return Briefing(en=en, de=de, model="heuristic")


def generate(item: NewsItem, backend=None) -> Briefing:
    """Produce a bilingual briefing: LLM if available, template otherwise."""
    if backend is not None and getattr(backend, "name", "") not in ("", "mock"):
        try:
            raw = backend.generate(build_prompt(item), system=SYSTEM_PROMPT,
                                   max_tokens=700, temperature=0.3)
            data = _parse_json(raw or "")
            if data and (data.get("en") or data.get("de")):
                return Briefing(
                    en=str(data.get("en", "")).strip(),
                    de=str(data.get("de", "")).strip(),
                    model=getattr(backend, "name", "llm"),
                )
        except Exception:  # noqa: BLE001 - model failure -> heuristic
            pass
    return _heuristic(item)
