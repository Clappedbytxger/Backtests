"""Pure-logic tests for the Alternative Data pipeline (no network).

Covers the analytical heart the dashboard trusts: lexicon sentiment polarity +
negation, risk-factor extraction, TF-IDF text divergence ordering, and the robust
anomaly z-score. The scrapers (github/sec) are network I/O and are exercised separately
when run with the sandbox disabled.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.altdata import nlp


def test_sentiment_polarity_and_negation():
    pos = nlp.sentiment_score("strong revenue growth and record profit, very favorable")
    neg = nlp.sentiment_score("severe losses, bankruptcy risk and litigation, weak demand")
    assert pos["compound"] > 0.3
    assert neg["compound"] < -0.3
    # a negator flips polarity
    plain = nlp.sentiment_score("growth")
    negated = nlp.sentiment_score("no growth")
    assert plain["compound"] > 0 and negated["compound"] < plain["compound"]
    # empty / non-lexical text is neutral
    assert nlp.sentiment_score("")["compound"] == 0.0
    assert nlp.sentiment_score("the a of to")["compound"] == 0.0


def test_extract_risk_factors():
    text = ("Item 1. Business. We sell things. Item 1A. Risk Factors. "
            "Our business faces supply disruption and litigation risk. "
            "Item 1B. Unresolved Staff Comments. None.")
    rf = nlp.extract_risk_factors(text)
    assert "supply disruption" in rf
    assert "We sell things" not in rf  # the Business section is excluded
    # no markers → returns full text rather than empty
    assert nlp.extract_risk_factors("plain text no items") == "plain text no items"


def test_text_divergence_ordering_and_bounds():
    a = "the company faces litigation risk and supply disruption in key markets"
    same = nlp.text_divergence(a, a)
    similar = nlp.text_divergence(a, a + " and modest currency effects")
    different = nlp.text_divergence(a, "we launched innovative products with record growth")
    assert same == 0.0
    assert 0.0 <= similar < different <= 1.0
    # one empty doc is maximal divergence
    assert nlp.text_divergence("", a) == 1.0
    assert nlp.text_divergence("", "") == 0.0


def test_robust_z_flags_outlier():
    rng = np.random.default_rng(1)
    base = list(10.0 + rng.normal(0, 1.5, 40))  # realistic baseline with variance
    z_normal = nlp.robust_z(base, 11.0)
    z_spike = nlp.robust_z(base, 80.0)
    assert abs(z_normal) < abs(z_spike)
    assert abs(z_spike) > 3
    # too little history → 0, no crash
    assert nlp.robust_z([1.0, 2.0]) == 0.0


def test_rolling_anomaly_z_causal_shape():
    rng = np.random.default_rng(0)
    s = pd.Series(rng.poisson(8, 200).astype(float),
                  index=pd.date_range("2024-01-01", periods=200, freq="D"))
    s.iloc[-1] = 90.0  # a fresh spike
    z = nlp.rolling_anomaly_z(s, window=60)
    assert len(z) == len(s)
    assert z.iloc[-1] > 3  # the spike is flagged against its own trailing baseline
