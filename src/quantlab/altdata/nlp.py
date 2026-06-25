"""Local NLP for the Alternative Data pipeline — sentiment, text divergence, anomaly.

Dependency-light by design (no network, no model download): the sentiment scorer is a
compact finance lexicon in the Loughran-McDonald / VADER tradition (a curated polarity
word list plus negators and intensifiers, producing a VADER-style ``compound`` in
[-1, 1]); text divergence is TF-IDF cosine distance (scikit-learn when present, with a
pure-Python Jaccard fallback so tests and offline runs never break). All functions are
pure and deterministic — the heavy I/O lives in :mod:`quantlab.altdata.github` /
:mod:`quantlab.altdata.sec`.

An optional FinBERT backend can be plugged in later (``transformers`` + a local model);
the lexicon is the always-available default so the desk works on a fresh clone.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

# ── finance sentiment lexicon (Loughran-McDonald flavoured, compact) ─────────────
# Word → valence in roughly [-3, 3]. Tilted toward 10-K/news vocabulary, not generic
# social-media slang, because the inputs are filings and headlines.
_POSITIVE = {
    "growth": 1.5, "grow": 1.3, "grew": 1.3, "profit": 1.8, "profitable": 2.0,
    "gain": 1.6, "gains": 1.6, "gained": 1.6, "strong": 1.7, "strength": 1.6,
    "record": 1.8, "beat": 2.0, "beats": 2.0, "exceeded": 2.0, "exceed": 1.8,
    "outperform": 2.2, "upgrade": 2.0, "upgraded": 2.0, "improve": 1.5,
    "improved": 1.6, "improvement": 1.5, "expansion": 1.4, "expand": 1.3,
    "increase": 1.2, "increased": 1.2, "rising": 1.3, "robust": 1.7, "surge": 2.0,
    "surged": 2.0, "rally": 1.8, "bullish": 2.2, "opportunity": 1.4,
    "opportunities": 1.4, "innovative": 1.5, "innovation": 1.4, "leading": 1.4,
    "leader": 1.4, "success": 1.7, "successful": 1.7, "dividend": 1.0,
    "favorable": 1.6, "favourable": 1.6, "efficient": 1.3, "momentum": 1.4,
    "accelerate": 1.5, "breakthrough": 2.0, "resilient": 1.5, "outpaced": 1.8,
}
_NEGATIVE = {
    "loss": -1.8, "losses": -1.8, "decline": -1.6, "declined": -1.6,
    "declines": -1.6, "weak": -1.7, "weakness": -1.7, "fell": -1.4, "drop": -1.5,
    "dropped": -1.5, "plunge": -2.2, "plunged": -2.2, "miss": -2.0, "missed": -2.0,
    "downgrade": -2.0, "downgraded": -2.0, "risk": -1.0, "risks": -1.0,
    "risky": -1.4, "uncertain": -1.4, "uncertainty": -1.4, "litigation": -1.6,
    "lawsuit": -1.6, "investigation": -1.6, "default": -2.2, "bankruptcy": -2.6,
    "bearish": -2.2, "recession": -2.0, "headwind": -1.5, "headwinds": -1.5,
    "impairment": -1.8, "writedown": -1.8, "restructuring": -1.3, "layoff": -1.7,
    "layoffs": -1.7, "shortfall": -1.8, "deteriorate": -1.8, "deteriorated": -1.8,
    "volatile": -1.2, "volatility": -1.0, "adverse": -1.6, "concern": -1.2,
    "concerns": -1.2, "warning": -1.6, "warn": -1.5, "warned": -1.5,
    "disruption": -1.5, "delay": -1.3, "delayed": -1.3, "fraud": -2.6,
    "underperform": -2.0, "slowdown": -1.7, "deficit": -1.5, "fear": -1.6,
    "fears": -1.6, "crisis": -2.0, "collapse": -2.4, "sell-off": -2.0,
}
_NEGATORS = {"not", "no", "never", "without", "lack", "lacks", "lacking",
             "fails", "fail", "failed", "cannot", "n't", "less", "least"}
_INTENSIFIERS = {"very": 1.4, "significantly": 1.5, "substantially": 1.5,
                 "materially": 1.4, "highly": 1.4, "extremely": 1.6,
                 "sharply": 1.5, "considerably": 1.4, "slightly": 0.6, "somewhat": 0.7}

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z'\-]+")
_NORM_ALPHA = 15.0  # VADER normalisation constant (controls how fast |compound|→1)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def sentiment_score(text: str) -> dict:
    """VADER-style finance sentiment for a block of text.

    Returns ``{compound, pos, neg, neu, n_tokens, n_hits}`` where ``compound`` is the
    normalised polarity in [-1, 1]. Negators within two tokens flip a term's sign;
    intensifiers scale the next polar term. Empty / non-lexical text scores 0.
    """
    tokens = _tokenize(text)
    n = len(tokens)
    if n == 0:
        return {"compound": 0.0, "pos": 0.0, "neg": 0.0, "neu": 1.0,
                "n_tokens": 0, "n_hits": 0}
    total = 0.0
    pos_sum = 0.0
    neg_sum = 0.0
    hits = 0
    for i, tok in enumerate(tokens):
        val = _POSITIVE.get(tok, 0.0) + _NEGATIVE.get(tok, 0.0)
        if val == 0.0:
            continue
        hits += 1
        # look back up to 3 tokens for negators / intensifiers
        window = tokens[max(0, i - 3):i]
        if any(w in _NEGATORS for w in window):
            val = -val * 0.7
        for w in window:
            if w in _INTENSIFIERS:
                val *= _INTENSIFIERS[w]
        total += val
        if val > 0:
            pos_sum += val
        else:
            neg_sum += -val
    compound = total / math.sqrt(total * total + _NORM_ALPHA) if total else 0.0
    denom = pos_sum + neg_sum or 1.0
    return {
        "compound": float(max(-1.0, min(1.0, compound))),
        "pos": float(pos_sum / denom),
        "neg": float(neg_sum / denom),
        "neu": float(max(0.0, 1.0 - hits / n)),
        "n_tokens": int(n),
        "n_hits": int(hits),
    }


# ── text divergence (current filing vs prior quarter) ────────────────────────────

# SEC 10-K/10-Q "Item 1A. Risk Factors" runs until "Item 1B"/"Item 2". Heuristic slice.
_RISK_START = re.compile(r"item[\s\.\-]*1a[\.\:\s].{0,40}?risk\s+factors", re.I | re.S)
_RISK_END = re.compile(r"item[\s\.\-]*(1b|2)[\.\:\s]", re.I)


def extract_risk_factors(text: str) -> str:
    """Best-effort slice of the 'Item 1A. Risk Factors' section of a filing.

    Returns the whole text if the section markers are not found (so divergence still
    has something to compare). Never raises.
    """
    if not text:
        return ""
    m = _RISK_START.search(text)
    if not m:
        return text
    start = m.end()
    e = _RISK_END.search(text, start)
    section = text[start:e.start()] if e else text[start:]
    return section.strip() or text


def _shingles(text: str, k: int = 3) -> set:
    toks = _tokenize(text)
    if len(toks) < k:
        return set(toks)
    return {" ".join(toks[i:i + k]) for i in range(len(toks) - k + 1)}


def text_divergence(a: str, b: str) -> float:
    """Divergence in [0, 1] between two documents (1 = completely different).

    Uses TF-IDF cosine distance when scikit-learn is available, else a 3-shingle
    Jaccard distance. Two empty docs → 0 (identical), one empty → 1.
    """
    a, b = (a or "").strip(), (b or "").strip()
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        tfidf = TfidfVectorizer(stop_words="english", max_features=5000).fit_transform([a, b])
        sim = float(cosine_similarity(tfidf[0], tfidf[1])[0, 0])
    except Exception:  # noqa: BLE001 - any sklearn issue → robust fallback
        sa, sb = _shingles(a), _shingles(b)
        inter = len(sa & sb)
        union = len(sa | sb) or 1
        sim = inter / union
    return float(max(0.0, min(1.0, 1.0 - sim)))


# ── anomaly statistics (the radar) ───────────────────────────────────────────────


def robust_z(values: "pd.Series | np.ndarray | list", value: float | None = None) -> float:
    """Robust z-score (median / MAD) of ``value`` against ``values`` history.

    If ``value`` is None, scores the last element of ``values``. MAD is scaled by
    1.4826 to be a consistent σ-estimator for normal data; a zero MAD falls back to
    std. Returns 0 when there is too little history.
    """
    arr = np.asarray(pd.Series(values, dtype="float64").dropna().values, dtype=float)
    if value is None:
        if arr.size == 0:
            return 0.0
        value = float(arr[-1])
        arr = arr[:-1]
    if arr.size < 3:
        return 0.0
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    scale = mad * 1.4826 if mad > 0 else float(np.std(arr))
    if scale <= 0:
        return 0.0
    return float((value - med) / scale)


def rolling_anomaly_z(series: pd.Series, window: int = 60) -> pd.Series:
    """Causal rolling robust z-score of a daily series (look-ahead-safe).

    Each point is scored against its own trailing ``window`` (median/MAD), so a spike
    in commits or a sentiment swing reads as a large |z| only relative to the asset's
    own recent baseline.
    """
    s = pd.Series(series, dtype="float64")
    med = s.rolling(window, min_periods=max(5, window // 4)).median()
    mad = (s - med).abs().rolling(window, min_periods=max(5, window // 4)).median()
    scale = (mad * 1.4826).replace(0.0, np.nan)
    std = s.rolling(window, min_periods=max(5, window // 4)).std()
    scale = scale.fillna(std)
    z = (s - med) / scale
    return z.replace([np.inf, -np.inf], np.nan)
