"""Tests for the robustness lab: Monte-Carlo, walk-forward, White's Reality Check."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantlab.robustness import mc_metrics, walk_forward, whites_reality_check


def test_mc_metrics_ci_and_determinism():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.0005, 0.01, 1000))  # positive drift
    m1 = mc_metrics(r, block=20, n_paths=1000, seed=42)
    m2 = mc_metrics(r, block=20, n_paths=1000, seed=42)
    assert m1 == m2  # deterministic for a fixed seed
    assert m1["sharpe"]["ci_low"] < m1["sharpe"]["median"] < m1["sharpe"]["ci_high"]
    assert m1["maxdd"]["median"] < 0  # drawdowns are negative
    assert m1["maxdd"]["ci_low"] <= m1["maxdd"]["ci_high"]


def test_walk_forward_selects_regime_param_no_overlap():
    idx = pd.bdate_range("2010-01-01", periods=2000)
    boundary = pd.Timestamp("2015-01-01")

    def run_fn(p, ix):
        before = np.asarray(ix < boundary)
        base = np.where(before, 1.0, -1.0) if p == 0 else np.where(before, -1.0, 1.0)
        osc = 0.5 * np.sin(np.arange(len(ix)))  # deterministic variation -> std > 0
        return pd.Series((base + osc) * 0.001, index=ix)

    res = walk_forward(idx, [0, 1], run_fn, train=250, test=125)
    assert res["n_windows"] > 4
    early = [c for c in res["chosen"] if c["test_start"] < boundary]
    late = [c for c in res["chosen"] if c["test_start"] > boundary + pd.Timedelta(days=400)]
    assert all(c["params"] == 0 for c in early[:2])   # picks the pre-boundary winner
    assert any(c["params"] == 1 for c in late)        # switches after the regime change
    assert res["oos_sharpe"] > 0
    starts = [c["test_start"] for c in res["chosen"]]
    assert starts == sorted(starts)                   # ordered, non-overlapping OOS


def test_reality_check_detects_real_edge_and_rejects_noise():
    rng = np.random.default_rng(1)
    T, N = 600, 8
    noise = rng.normal(0.0, 0.01, (T, N))
    real = noise.copy()
    real[:, 0] += 0.0015  # strategy 0 has a genuine edge (t ~ 3.6)

    rc_real = whites_reality_check(real, block=10, n_boot=1000, seed=0)
    rc_null = whites_reality_check(noise, block=10, n_boot=1000, seed=0)

    assert rc_real["best_strategy"] == 0
    assert rc_real["p_value"] < 0.05            # survives the best-of-8 snooping penalty
    assert rc_null["p_value"] > rc_real["p_value"]
    assert rc_null["p_value"] > 0.10            # best of 8 noise streams is not significant
