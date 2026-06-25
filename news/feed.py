"""Source aggregation + the ingest pipeline.

``ingest`` is the one entry point that turns a raw headline into a fully-formed,
evaluated :class:`NewsItem`:

    raw text -> classify (category + priority) -> agent hypothesis (lesson-primed)
             -> persist

Real feeds (RSS, vendor APIs, websockets) only need to call :func:`ingest` per
headline — the classification + evaluation + storage are handled here. A small
set of seed headlines (:func:`seed_sample`) lets the terminal be demoed without
any external source or API key.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from . import agent, briefing
from .models import Category, NewsItem, Priority
from .store import NewsStore

# ── lightweight auto-classification (used when the source omits the fields) ───
_CATEGORY_HINTS: dict[Category, tuple[str, ...]] = {
    Category.KRYPTO: ("bitcoin", "btc", "ethereum", "eth", "crypto", "krypto",
                      "solana", "token", "defi", "binance", "coinbase", "etf btc"),
    Category.FX: ("eur/usd", "euro", "dollar", "yen", "forex", "fx ", "currency",
                  "pound", "sterling", "franc", "devisen", "wechselkurs"),
    Category.ROHSTOFFE: ("oil", "öl", "crude", "brent", "gold", "silver", "silber",
                         "gas", "copper", "kupfer", "wheat", "weizen", "commodit"),
    Category.MAKRO: ("fed", "ecb", "ezb", "inflation", "cpi", "gdp", "bip", "rate",
                     "zins", "unemployment", "payroll", "central bank", "treasury",
                     "yield", "recession", "rezession", "tariff", "zoll"),
    Category.AKTIEN: ("stock", "aktie", "earnings", "shares", "nasdaq", "s&p",
                      "dow", "ipo", "buyback", "guidance", "quarterly", "revenue"),
}

_HIGH_WORDS = ("crash", "surge", "plunge", "emergency", "default", "war", "krieg",
               "ban", "hike", "cut", "shock", "collapse", "record", "sanction",
               "einbruch", "absturz", "notfall", "rekord")
_MEDIUM_WORDS = ("beat", "miss", "warning", "upgrade", "downgrade", "guidance",
                 "rises", "falls", "steigt", "fällt", "warnt")


def classify_category(text: str) -> Category:
    t = text.lower()
    best, best_hits = Category.SONSTIGES, 0
    for cat, hints in _CATEGORY_HINTS.items():
        hits = sum(1 for h in hints if h in t)
        if hits > best_hits:
            best, best_hits = cat, hits
    return best


def classify_priority(text: str) -> Priority:
    t = text.lower()
    if any(w in t for w in _HIGH_WORDS):
        return Priority.HIGH
    if any(w in t for w in _MEDIUM_WORDS):
        return Priority.MEDIUM
    return Priority.LOW


def ingest(
    store: NewsStore,
    title: str,
    content: str = "",
    source: str = "manual",
    category: Category | None = None,
    priority: Priority | None = None,
    backend=None,
    timestamp: datetime | None = None,
    url: str | None = None,
) -> NewsItem:
    """Classify, evaluate (lesson-primed), persist, and return the new item."""
    title = " ".join(title.split())
    blob = f"{title}. {content}"
    item = NewsItem(
        title=title,
        content=content,
        source=source,
        url=url,
        category=category or classify_category(blob),
        priority=priority or classify_priority(blob),
        timestamp=timestamp or datetime.now(timezone.utc),
    )
    lessons = store.recent_lessons(category=item.category, k=5)
    item.hypothesis = agent.evaluate(item, backend=backend, lessons=lessons)
    return store.upsert_item(item)


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:80]


def refresh_from_sources(store: NewsStore, limit: int = 40,
                         per_feed: int = 12) -> list[NewsItem]:
    """Pull real headlines from the RSS sources, ingest the new ones (deduped).

    Ingest is intentionally **model-free** (heuristic hypothesis) so the feed stays
    fast at high volume; the throttled :mod:`news.llm_workflow` upgrades the
    important items to a model read once per cycle.
    """
    from . import sources

    heads = sources.fetch_all(per_feed=per_feed)
    existing = store.all_items()
    seen_titles = {_norm(it.title) for it in existing}
    seen_urls = {it.url for it in existing if it.url}

    new: list[NewsItem] = []
    for h in heads:
        if len(new) >= limit:
            break
        if _norm(h.title) in seen_titles or (h.url and h.url in seen_urls):
            continue
        seen_titles.add(_norm(h.title))
        if h.url:
            seen_urls.add(h.url)
        new.append(ingest(
            store, title=h.title, content=h.content, source=h.source,
            category=h.category, backend=None, timestamp=h.published, url=h.url,
        ))
    return new


def generate_document(store: NewsStore, item_id: str, backend=None,
                      regenerate: bool = False) -> NewsItem | None:
    """Lazily generate (and cache) the bilingual briefing for one item."""
    item = store.get_item(item_id)
    if item is None:
        return None
    if item.document is None or regenerate:
        item.document = briefing.generate(item, backend=backend)
        store.upsert_item(item)
    return item


def reevaluate(store: NewsStore, item_id: str, backend=None) -> NewsItem | None:
    """Regenerate a hypothesis for an existing item (e.g. after new lessons)."""
    item = store.get_item(item_id)
    if item is None:
        return None
    lessons = store.recent_lessons(category=item.category, k=5)
    item.hypothesis = agent.evaluate(item, backend=backend, lessons=lessons)
    return store.upsert_item(item)


# ── demo seed (dated in the past so the feedback loop has something to verify) ─
_SEED: tuple[tuple[str, str, str], ...] = (
    ("Reuters", "Fed signals it may cut rates as inflation cools to 2.4%",
     "Officials struck a dovish tone, lifting risk appetite across equities."),
    ("Bloomberg", "Bitcoin surges past $90k on record spot-ETF inflows",
     "Institutional demand drove the largest single-day inflow on record."),
    ("WSJ", "Nvidia beats earnings but warns of softening data-center demand",
     "Revenue topped estimates; forward guidance disappointed investors."),
    ("FT", "Oil plunges as OPEC+ unexpectedly raises output quotas",
     "Crude fell sharply on the surprise supply decision."),
    ("Reuters", "ECB holds rates steady, euro little changed",
     "The decision was widely expected and markets barely reacted."),
    ("CNBC", "Gold hits record high as investors seek safe haven amid tariff fears",
     "Escalating trade tensions fueled a flight to safety."),
    ("Bloomberg", "Tesla shares slump after deliveries miss expectations",
     "Quarterly deliveries came in well below consensus."),
    ("MarketWatch", "Dollar strengthens on hawkish Fed minutes",
     "Minutes revealed officials open to another hike if inflation persists."),
)


def seed_sample(store: NewsStore, backend=None) -> list[NewsItem]:
    """Load a spread of demo headlines (timestamped 1-5 days back)."""
    now = datetime.now(timezone.utc)
    out = []
    for i, (src, title, body) in enumerate(_SEED):
        out.append(ingest(
            store, title=title, content=body, source=src, backend=backend,
            timestamp=now - timedelta(days=1 + i * 0.5, hours=i),
        ))
    return out
