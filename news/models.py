"""Schema for the news terminal — items, agent hypotheses, and lessons.

Pydantic v2 models (the rest of the API already speaks pydantic). Enums are
``str``-valued so they serialize to readable JSON and survive a round-trip
through the JSON store untouched. Timestamps are timezone-aware UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex[:12]


class Category(str, Enum):
    """Coarse market bucket a headline belongs to."""

    MAKRO = "Makro"
    KRYPTO = "Krypto"
    AKTIEN = "Aktien"
    FX = "FX"
    ROHSTOFFE = "Rohstoffe"
    SONSTIGES = "Sonstiges"


class Priority(str, Enum):
    """Editorial urgency — drives sort order and colour in the terminal."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ImpactDirection(str, Enum):
    """The agent's expected price reaction."""

    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"


class HypothesisStatus(str, Enum):
    """Lifecycle of a hypothesis in the feedback loop."""

    OPEN = "open"            # awaiting its verification window
    CORRECT = "correct"      # realized move matched the predicted direction
    INCORRECT = "incorrect"  # realized move contradicted it -> a lesson
    UNVERIFIED = "unverified"  # window passed but price data was unavailable


# Sort weights (higher = shown first) so the store can rank without branching.
PRIORITY_RANK: dict[str, int] = {
    Priority.HIGH.value: 3,
    Priority.MEDIUM.value: 2,
    Priority.LOW.value: 1,
}


def default_window_hours(priority: "Priority") -> float:
    """Verification horizon by priority — shorter for urgent news so the live
    loop can settle (and learn) within a long session, longer for low-prio noise."""
    return {
        Priority.HIGH: 2.0,
        Priority.MEDIUM: 6.0,
        Priority.LOW: 24.0,
    }.get(priority, 6.0)


class Hypothesis(BaseModel):
    """The agent's read on a single :class:`NewsItem`."""

    direction: ImpactDirection = ImpactDirection.NEUTRAL
    asset: str = "MARKET"          # ticker/proxy the call is about (e.g. "BTC-USD")
    scope: str = "market"          # "asset" (named instrument) | "market" (broad)
    rationale: str = ""            # one or two sentences, the agent's reasoning
    confidence: float = 0.5        # 0..1
    model: str = "heuristic"       # which backend produced it
    created_at: datetime = Field(default_factory=_now)

    # Feedback-loop bookkeeping.
    status: HypothesisStatus = HypothesisStatus.OPEN
    verify_after_hours: float = 6.0
    verified_at: datetime | None = None
    realized_return: float | None = None  # signed price change over the window
    feedback_source: str | None = None    # "price" | "manual"
    lesson_id: str | None = None          # set when a miss was recorded

    # Live (provisional) tracking — updated every tick while open, not final.
    provisional_return: float | None = None   # signed move since the news, so far
    provisional_status: str | None = None      # "on_track" | "off_track" | "flat"
    last_tracked_at: datetime | None = None


class Briefing(BaseModel):
    """A bilingual (EN + DE) deeper write-up of a headline, generated on demand."""

    en: str = ""
    de: str = ""
    model: str = "heuristic"
    generated_at: datetime = Field(default_factory=_now)


class NewsItem(BaseModel):
    """A single aggregated headline plus the agent's hypothesis."""

    id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_now)
    source: str = "manual"
    title: str
    content: str = ""
    url: str | None = None          # link to the original article (for real feeds)
    category: Category = Category.SONSTIGES
    priority: Priority = Priority.MEDIUM
    hypothesis: Hypothesis | None = None
    document: Briefing | None = None  # bilingual briefing, lazily generated

    def touch_priority_rank(self) -> int:
        return PRIORITY_RANK.get(self.priority.value, 0)


class Lesson(BaseModel):
    """A 'soll vs. ist' miss, distilled for few-shot priming of future calls."""

    id: str = Field(default_factory=_new_id)
    created_at: datetime = Field(default_factory=_now)
    news_id: str
    headline: str
    category: Category
    predicted: ImpactDirection
    actual: ImpactDirection
    realized_return: float | None = None
    rationale: str = ""        # the original (wrong) reasoning
    takeaway: str = ""         # the distilled lesson, injected into later prompts


class IngestRequest(BaseModel):
    """Payload to push one external/manual headline into the feed."""

    title: str
    content: str = ""
    source: str = "manual"
    category: Category | None = None
    priority: Priority | None = None


class FeedbackRequest(BaseModel):
    """Manual override of a hypothesis outcome from the terminal."""

    correct: bool
    note: str = ""
