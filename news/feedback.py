"""The learning loop: verify hypotheses, then distil misses into lessons.

Two ways a hypothesis gets resolved:

  - **Automatic** (:func:`verify_due`) — once a hypothesis is older than its
    ``verify_after_hours`` window, fetch the proxy asset's price change over that
    window and compare its *sign* to the predicted direction.
  - **Manual** (:func:`apply_manual_feedback`) — the analyst flags it
    correct/incorrect from the terminal.

Either way, an **incorrect** call writes a :class:`Lesson` ("soll vs. ist") into
the knowledge base, which :mod:`news.agent` then injects as few-shot context on
the next evaluation — closing the loop.

Price verification degrades gracefully: if data is missing/too recent, the
hypothesis is marked ``unverified`` rather than guessed.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from .models import (
    Hypothesis,
    HypothesisStatus,
    ImpactDirection,
    Lesson,
    NewsItem,
)
from .store import NewsStore

# A move smaller than this (fraction) counts as "no reaction" -> Neutral realized.
NEUTRAL_BAND = 0.003  # 0.3%


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── TTL price cache (so the live loop never hammers yfinance) ─────────────────
_PRICE_CACHE: dict[tuple[str, str], tuple[float, object]] = {}
_PRICE_TTL = 90.0  # seconds
_PRICE_LOCK = threading.Lock()


def _recent_prices(asset: str, interval: str, lookback_days: int):
    """Cached recent OHLCV for ``asset`` (TTL ``_PRICE_TTL``). ``None`` on failure."""
    from quantlab.data import get_prices

    key = (asset, interval)
    now = time.time()
    with _PRICE_LOCK:
        hit = _PRICE_CACHE.get(key)
        if hit and now - hit[0] < _PRICE_TTL:
            return hit[1]
    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    try:
        df = get_prices(asset, start=start, interval=interval, use_cache=False)
    except Exception:  # noqa: BLE001
        df = None
    if df is not None and df.empty:
        df = None
    with _PRICE_LOCK:
        _PRICE_CACHE[key] = (now, df)
    return df


def _utc_index(df):
    idx = df.index
    return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")


def latest_return(asset: str, since: datetime) -> float | None:
    """Signed move of ``asset`` from ``since`` to the most recent available bar.

    Picks a bar granularity from the age of the news and uses the TTL cache, so
    calling it every tick for many items costs at most one download per ticker.
    """
    since = _utc(since)
    age_d = (datetime.now(timezone.utc) - since).total_seconds() / 86400.0
    if age_d <= 5:
        interval, lookback = "5m", 7
    elif age_d <= 55:
        interval, lookback = "1h", 60
    else:
        interval, lookback = "1d", int(age_d) + 5
    df = _recent_prices(asset, interval, lookback)
    if df is None:
        return None
    idx = _utc_index(df)
    close = df["Close"].to_numpy()
    before = idx[idx <= since]
    if len(before) == 0 or len(close) == 0:
        return None
    pos = idx.get_indexer([before[-1]])[0]
    p0, p1 = float(close[pos]), float(close[-1])
    return None if p0 == 0 else p1 / p0 - 1.0


def realized_return(asset: str, start: datetime, end: datetime) -> float | None:
    """Signed price change of ``asset`` from ``start`` to ``end`` (None on failure).

    Uses hourly bars when the window is short and recent, else daily. Any data
    error returns ``None`` so the caller can mark the call ``unverified``.
    """
    from quantlab.data import get_prices

    start, end = _utc(start), _utc(end)
    span_h = (end - start).total_seconds() / 3600.0
    interval = "1h" if span_h <= 168 else "1d"
    try:
        # pad the window so the nearest bars on each side exist
        df = get_prices(
            asset,
            start=(start - timedelta(days=2)).strftime("%Y-%m-%d"),
            end=(end + timedelta(days=2)).strftime("%Y-%m-%d"),
            interval=interval,
            use_cache=False,
        )
    except Exception:  # noqa: BLE001 - bad symbol / no data / network
        return None
    if df is None or df.empty:
        return None

    idx = df.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    close = df["Close"].to_numpy()

    def nearest(ts: datetime) -> float | None:
        before = idx[idx <= ts]
        if len(before) == 0:
            return None
        pos = idx.get_indexer([before[-1]])[0]
        return float(close[pos])

    p0, p1 = nearest(start), nearest(end)
    if p0 is None or p1 is None or p0 == 0:
        return None
    return p1 / p0 - 1.0


def _direction_of(ret: float) -> ImpactDirection:
    if ret > NEUTRAL_BAND:
        return ImpactDirection.BULLISH
    if ret < -NEUTRAL_BAND:
        return ImpactDirection.BEARISH
    return ImpactDirection.NEUTRAL


def _make_lesson(item: NewsItem, hyp: Hypothesis, actual: ImpactDirection) -> Lesson:
    takeaway = (
        f"For {item.category.value} headlines like this, a {hyp.direction.value} "
        f"call on {hyp.asset} was wrong (actual {actual.value}). "
        "Weight this pattern more cautiously / consider the opposite reaction."
    )
    return Lesson(
        news_id=item.id,
        headline=item.title,
        category=item.category,
        predicted=hyp.direction,
        actual=actual,
        realized_return=hyp.realized_return,
        rationale=hyp.rationale,
        takeaway=takeaway,
    )


def _resolve(store: NewsStore, item: NewsItem, hyp: Hypothesis,
             actual: ImpactDirection, realized: float | None, source: str) -> NewsItem:
    """Set status, persist, and record a lesson on a miss. Returns updated item."""
    hyp.realized_return = realized
    hyp.verified_at = datetime.now(timezone.utc)
    hyp.feedback_source = source
    # A Neutral prediction is "right" if nothing much moved; otherwise the
    # predicted sign must match the realized sign.
    correct = (hyp.direction == actual)
    hyp.status = HypothesisStatus.CORRECT if correct else HypothesisStatus.INCORRECT
    if not correct:
        lesson = store.add_lesson(_make_lesson(item, hyp, actual))
        hyp.lesson_id = lesson.id
    store.update_hypothesis(item.id, hyp)
    item.hypothesis = hyp
    return item


def verify_item(store: NewsStore, item: NewsItem, force: bool = False) -> NewsItem | None:
    """Verify one item against price data if its window has elapsed.

    Returns the updated item, or ``None`` if it was skipped (no hypothesis, not
    yet due, or already resolved without ``force``).
    """
    hyp = item.hypothesis
    if hyp is None:
        return None
    if not force and hyp.status is not HypothesisStatus.OPEN:
        return None

    due = _utc(hyp.created_at) + timedelta(hours=hyp.verify_after_hours)
    now = datetime.now(timezone.utc)
    if not force and now < due:
        return None  # still inside the verification window

    realized = realized_return(hyp.asset, _utc(hyp.created_at), min(now, due) if force else due)
    if realized is None:
        hyp.status = HypothesisStatus.UNVERIFIED
        hyp.verified_at = now
        store.update_hypothesis(item.id, hyp)
        item.hypothesis = hyp
        return item
    return _resolve(store, item, hyp, _direction_of(realized), realized, "price")


def verify_due(store: NewsStore, force: bool = False) -> dict:
    """Sweep all items; verify every hypothesis whose window has elapsed.

    ``force`` re-checks even open-but-not-due items (useful for a demo). Returns
    a small summary of what changed.
    """
    updated, correct, incorrect, unverified = 0, 0, 0, 0
    for item in store.all_items():
        res = verify_item(store, item, force=force)
        if res is None or res.hypothesis is None:
            continue
        updated += 1
        st = res.hypothesis.status
        correct += st is HypothesisStatus.CORRECT
        incorrect += st is HypothesisStatus.INCORRECT
        unverified += st is HypothesisStatus.UNVERIFIED
    return {
        "updated": updated, "correct": correct,
        "incorrect": incorrect, "unverified": unverified,
        "lessons_total": len(store.all_lessons()),
    }


def track_open(store: NewsStore) -> dict:
    """Update the *provisional* (live, non-final) outcome of every open hypothesis.

    For each open item, compute the move of its asset since the news broke and
    flag it on_track / off_track / flat versus the predicted direction. This is
    the 'continuously checking against prices' signal — it never settles or
    writes a lesson (that is :func:`verify_due`'s job once the window elapses).
    """
    on = off = flat = 0
    for item in store.all_items():
        hyp = item.hypothesis
        if hyp is None or hyp.status is not HypothesisStatus.OPEN:
            continue
        ret = latest_return(hyp.asset, _utc(hyp.created_at))
        if ret is None:
            continue
        actual = _direction_of(ret)
        if actual is ImpactDirection.NEUTRAL:
            prov = "flat"
            flat += 1
        elif actual == hyp.direction:
            prov = "on_track"
            on += 1
        else:
            prov = "off_track"
            off += 1
        hyp.provisional_return = ret
        hyp.provisional_status = prov
        hyp.last_tracked_at = datetime.now(timezone.utc)
        store.update_hypothesis(item.id, hyp)
    return {"tracked": on + off + flat, "on_track": on, "off_track": off, "flat": flat}


def tick(store: NewsStore, do_refresh: bool = False, backend_provider=None,
         refresh_limit: int = 40) -> dict:
    """One iteration of the live loop: (optional) refresh -> LLM pass -> track -> settle.

    Everything except the (throttled, backgrounded) LLM pass is model-free, so this
    returns fast. ``backend_provider`` is a callable resolving the LLM backend; it
    is only invoked when an LLM pass is actually due (lazy model load).
    """
    from . import llm_workflow

    summary: dict = {"refreshed": 0}
    if do_refresh:
        from . import feed

        try:
            new = feed.refresh_from_sources(store, limit=refresh_limit)
            summary["refreshed"] = len(new)
        except Exception as e:  # noqa: BLE001 - a feed hiccup must not break the loop
            summary["refresh_error"] = f"{type(e).__name__}: {e}"

    # heavy model work — throttled to once per interval, runs in the background
    summary["llm"] = llm_workflow.run_async(store, backend_provider)
    summary["llm_status"] = llm_workflow.status()

    summary["track"] = track_open(store)
    summary["settle"] = verify_due(store, force=False)
    summary["stats"] = store.stats()
    from . import market

    summary["market"] = market.snapshot(store)  # aggregates fresh; narrative cached
    return summary


def apply_manual_feedback(store: NewsStore, item_id: str, correct: bool,
                          note: str = "") -> NewsItem | None:
    """Analyst override: mark a hypothesis correct/incorrect from the terminal.

    On 'incorrect' a lesson is recorded with the assumed opposite direction so the
    knowledge base still learns from a manually-flagged miss.
    """
    item = store.get_item(item_id)
    if item is None or item.hypothesis is None:
        return None
    hyp = item.hypothesis
    if correct:
        actual = hyp.direction
    else:
        # opposite of the (wrong) call; Neutral misses default to Bearish surprise
        actual = {
            ImpactDirection.BULLISH: ImpactDirection.BEARISH,
            ImpactDirection.BEARISH: ImpactDirection.BULLISH,
            ImpactDirection.NEUTRAL: ImpactDirection.BEARISH,
        }[hyp.direction]
    item = _resolve(store, item, hyp, actual, hyp.realized_return, "manual")
    if note and item.hypothesis is not None:
        item.hypothesis.rationale = f"{item.hypothesis.rationale} [analyst: {note}]"
        store.update_hypothesis(item.id, item.hypothesis)
    return item
