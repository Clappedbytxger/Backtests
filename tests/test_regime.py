"""Causality + sanity tests for the market-regime engine (quantlab.regime).

The decisive property is **look-ahead safety**: the regime label at bar ``t`` must
depend only on bars ``<= t``. We pin that by truncating the series at random points
and checking the last-bar classification is identical to the full-series value at
that bar — if any window peeked forward, the two would diverge.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab import regime


def _synthetic_ohlc(n: int = 900, seed: int = 7) -> pd.DataFrame:
    """A reproducible OHLC random walk with regime-ish stretches (trend + chop)."""
    rng = np.random.default_rng(seed)
    drift = np.concatenate([
        np.full(300, 0.0008),    # uptrend
        np.full(200, -0.0002),   # chop
        np.full(200, -0.0010),   # downtrend
        np.full(n - 700, 0.0003),
    ])
    vol = np.concatenate([
        np.full(300, 0.008),
        np.full(200, 0.020),     # high-vol patch
        np.full(200, 0.012),
        np.full(n - 700, 0.006),
    ])
    ret = drift + vol * rng.standard_normal(n)
    close = 100 * np.exp(np.cumsum(ret))
    idx = pd.bdate_range("2018-01-01", periods=n)
    high = close * (1 + np.abs(rng.standard_normal(n)) * 0.004)
    low = close * (1 - np.abs(rng.standard_normal(n)) * 0.004)
    open_ = close * (1 + rng.standard_normal(n) * 0.002)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                         "Volume": rng.integers(1e6, 5e6, n)}, index=idx)


def test_no_lookahead_last_bar_matches_truncated():
    """Regime at t on the full series == regime of the truncated-at-t series's last bar."""
    df = _synthetic_ohlc()
    full = regime.classify(df)
    rng = np.random.default_rng(0)
    # sample bars in the valid region (past warm-up, with room to spare)
    for t in rng.choice(range(300, len(df)), size=25, replace=False):
        trunc = regime.classify(df.iloc[: t + 1])
        a = full["regime"].iloc[t]
        b = trunc["regime"].iloc[-1]
        assert (a == b) or (pd.isna(a) and pd.isna(b)), f"look-ahead at bar {t}: {a!r} != {b!r}"


def test_metrics_are_causal():
    """Core numeric columns must also be truncation-stable (ADX/vol-rank/MA stack)."""
    df = _synthetic_ohlc()
    full = regime.classify(df)
    for t in (350, 500, 720, 880):
        trunc = regime.classify(df.iloc[: t + 1])
        for col in ("adx", "vol_rank", "sma_slow", "ema_fast", "atr_pct"):
            a, b = full[col].iloc[t], trunc[col].iloc[-1]
            if pd.isna(a) and pd.isna(b):
                continue
            assert abs(float(a) - float(b)) < 1e-9, f"{col} not causal at {t}: {a} vs {b}"


def test_every_label_is_canonical():
    df = _synthetic_ohlc()
    out = regime.classify(df)
    labels = set(out["regime"].dropna().unique())
    assert labels.issubset(set(regime.REGIMES))
    # a multi-regime synthetic series should exercise more than one regime
    assert len(labels) >= 3


def test_segments_reconstruct_the_series():
    """Concatenated segment spans must cover exactly the classified (non-null) bars."""
    df = _synthetic_ohlc()
    out = regime.classify(df)
    spans = regime.segments(out)
    total_bars = sum(s["bars"] for s in spans)
    assert total_bars == int(out["regime"].notna().sum())
    # adjacent spans never share a regime (they would have been merged)
    for a, b in zip(spans, spans[1:]):
        assert a["regime"] != b["regime"]


def test_regime_performance_partitions_returns():
    """Per-regime bar counts must sum to the number of classified return bars."""
    df = _synthetic_ohlc()
    out = regime.classify(df)
    ret = df["Close"].pct_change().fillna(0.0)
    perf = regime.regime_performance(ret, out)
    n_classified = int(out["regime"].reindex(ret.index).notna().sum())
    assert sum(p["n"] for p in perf.values()) == n_classified
    # shares of time are a valid distribution
    assert abs(sum(p["pct_of_time"] for p in perf.values()) - 1.0) < 1e-6


def test_distribution_sums_to_one():
    df = _synthetic_ohlc()
    out = regime.classify(df)
    dist = regime.regime_distribution(out)
    assert abs(sum(d["pct"] for d in dist.values()) - 1.0) < 1e-9
