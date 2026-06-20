"""Tests for the TCA module (square-root impact + dollar-cost bridge)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab.tca import ImpactModel, analyze_orders, tca_from_backtest


def test_impact_follows_square_root_law():
    m = ImpactModel(impact_coef=1.0, half_spread_bps=0.0, commission_bps=0.0)
    # 4x the participation -> 2x the impact (sqrt scaling)
    assert m.impact_bps(0.04, 0.02) == pytest.approx(2.0 * m.impact_bps(0.01, 0.02))
    assert m.impact_bps(0.0, 0.02) == 0.0


def test_fixed_cost_floor_at_zero_size():
    m = ImpactModel(half_spread_bps=1.0, commission_bps=0.2, impact_coef=0.5)
    assert m.cost_bps(0.0, 0.02) == pytest.approx(1.2)  # only spread + commission


def test_analyze_orders_monotone_in_participation():
    df = analyze_orders([1e6, 1e6], [1e8, 1e6], [0.02, 0.02])  # 2nd is 100x participation
    assert df["impact_bps"].iloc[1] > df["impact_bps"].iloc[0]
    assert (df["total_bps"] >= df["spread_bps"] + df["commission_bps"]).all()
    assert (df["cost_usd"] > 0).all()


def test_tca_from_backtest_more_turnover_costs_more():
    idx = pd.bdate_range("2020-01-01", periods=200)
    rng = np.random.default_rng(0)
    close = pd.Series(100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx)))), index=idx)
    prices = pd.DataFrame({"Close": close, "Volume": pd.Series(1e6, index=idx)})

    pos_low = pd.Series(0.0, index=idx)
    pos_low.iloc[10:190] = 1.0  # two orders total
    pos_high = pd.Series(np.tile([0.0, 1.0], len(idx) // 2), index=idx)  # flips constantly

    low = tca_from_backtest({"position": pos_low}, prices, account_value=1e6)
    high = tca_from_backtest({"position": pos_high}, prices, account_value=1e6)

    assert low["n_orders"] == 2
    assert high["total_cost_usd"] > low["total_cost_usd"]
    assert high["avg_cost_bps"] > 0
    bd = high["breakdown_bps"]
    assert bd["spread"] > 0 and bd["impact"] >= 0
