"""Real-news aggregation from keyless financial RSS feeds.

No API keys, no third-party deps — fetched with ``urllib`` and parsed with the
stdlib XML parser. Two kinds of source:

  - **Category Google-News queries** — robust, high-volume, and let us tag the
    category directly from the query (broad coverage incl. minor headlines).
  - **A few direct publisher feeds** (CNBC markets, CoinDesk) for freshness.

Each :func:`fetch_all` call returns de-duplicated ``RawHeadline`` records; the
caller (:mod:`news.feed`) classifies priority, evaluates, and persists. Any feed
that fails (network/parse) is skipped silently so one bad source never blocks the
others.
"""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from .models import Category

_UA = "Mozilla/5.0 (Quant-OS NewsTerminal; +local)"
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


@dataclass
class RawHeadline:
    title: str
    content: str
    source: str
    url: str
    category: Category | None
    published: datetime


def _gnews(query: str) -> str:
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}+when:2d&hl=en-US&gl=US&ceid=US:en"


# Category -> Google-News query. Broad queries => lots of items, many low-prio.
_CATEGORY_QUERIES: dict[Category, str] = {
    Category.MAKRO: "federal reserve OR inflation OR interest rates OR economy OR treasury yields",
    Category.KRYPTO: "bitcoin OR ethereum OR crypto OR solana",
    Category.AKTIEN: "stock market OR earnings OR S&P 500 OR nasdaq OR shares",
    Category.FX: "forex OR US dollar OR euro currency OR yen OR exchange rate",
    Category.ROHSTOFFE: "oil price OR gold price OR natural gas OR commodities OR copper",
}

# Direct publisher feeds (category=None -> auto-classify downstream).
_DIRECT_FEEDS: list[tuple[str, str, Category | None]] = [
    ("CNBC", "https://www.cnbc.com/id/15839135/device/rss/rss.html", None),       # markets
    ("CNBC", "https://www.cnbc.com/id/20910258/device/rss/rss.html", Category.MAKRO),  # economy
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", Category.KRYPTO),
    ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/", None),
]


def _clean(text: str) -> str:
    # strip tags, decode entities (&nbsp; &amp; …), collapse whitespace.
    stripped = _TAG.sub(" ", text or "")
    return _WS.sub(" ", html.unescape(stripped).replace("\xa0", " ")).strip()


def _parse_pubdate(text: str | None) -> datetime:
    if text:
        try:
            dt = parsedate_to_datetime(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc)


def _split_source(title: str, default: str) -> tuple[str, str]:
    """Google-News titles are 'Headline - Publisher'; split the publisher out."""
    if " - " in title:
        head, src = title.rsplit(" - ", 1)
        if 0 < len(src) <= 40:
            return head.strip(), src.strip()
    return title.strip(), default


def _fetch(url: str, timeout: float = 8.0) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - any network/HTTP error -> skip this feed
        return None


def _parse_rss(xml_text: str, default_source: str, category: Category | None,
               limit: int) -> list[RawHeadline]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[RawHeadline] = []
    for item in root.iter("item"):
        raw_title = _clean(item.findtext("title") or "")
        if not raw_title:
            continue
        title, source = _split_source(raw_title, default_source)
        out.append(RawHeadline(
            title=title,
            content=_clean(item.findtext("description") or "")[:600],
            source=source,
            url=(item.findtext("link") or "").strip(),
            category=category,
            published=_parse_pubdate(item.findtext("pubDate")),
        ))
        if len(out) >= limit:
            break
    return out


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())[:80]


def fetch_all(per_feed: int = 12) -> list[RawHeadline]:
    """Fetch every source, de-dup by normalized title, newest first."""
    heads: list[RawHeadline] = []
    for cat, query in _CATEGORY_QUERIES.items():
        xml = _fetch(_gnews(query))
        if xml:
            heads += _parse_rss(xml, "Google News", cat, per_feed)
    for src, url, cat in _DIRECT_FEEDS:
        xml = _fetch(url)
        if xml:
            heads += _parse_rss(xml, src, cat, per_feed)

    seen: set[str] = set()
    deduped: list[RawHeadline] = []
    for h in sorted(heads, key=lambda x: x.published, reverse=True):
        key = _norm_title(h.title)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(h)
    return deduped
