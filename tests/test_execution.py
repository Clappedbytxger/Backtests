"""Tests for the Advanced Execution Simulator & Slippage Radar.

Verifies the slippage math: Corwin-Schultz spread sanity, the square-root impact
scaling law, Implementation-Shortfall decomposition, and that the adaptive cost
makes the realised curve sit below the theoretical one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantlab import execution as ex


def _synthetic_ohlcv(n: int = 600, seed: int = 3, base_vol: float = 5e6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n, name="Date")
    rets = rng.normal(0.0004, 0.011, n)
    close = 100.0 * np.exp(np.cumsum(rets))
    spread = np.abs(rng.normal(0.0, 0.005, n)) + 0.003
    open_ = close * (1.0 + rng.normal(0.0, 0.003, n))
    high = np.maximum(open_, close) * (1.0 + spread)
    low = np.minimum(open_, close) * (1.0 - spread)
    vol = rng.integers(int(base_vol * 0.5), int(base_vol * 1.5), n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def test_corwin_schultz_spread_bounds():
    df = _synthetic_ohlcv()
    s = ex.corwin_schultz_spread(df, smooth=10, floor_bps=1.0, cap_bps=500.0)
    assert s.index.equals(df.index)
    assert (s >= 1.0 / 1e4 - 1e-12).all()      # respects the floor
    assert (s <= 500.0 / 1e4 + 1e-12).all()    # respects the cap
    assert s.notna().all()


def test_square_root_law_scaling():
    """Quadrupling participation must exactly double the impact (√4 = 2)."""
    vol = 0.02
    i1 = ex.square_root_impact(0.01, vol, y=0.5)
    i4 = ex.square_root_impact(0.04, vol, y=0.5)
    assert i4 == pytest.approx(2.0 * i1, rel=1e-12)
    # closed-form value
    assert i1 == pytest.approx(0.5 * 0.02 * np.sqrt(0.01), rel=1e-12)


def test_impact_grows_with_capital():
    """Bigger account → bigger orders → strictly more impact cost (super-linear)."""
    df = _synthetic_ohlcv()
    turnover = pd.Series(0.0, index=df.index)
    turnover.iloc[50:] = 1.0  # full turnover each bar from day 50
    small = ex.adaptive_cost_components(df, turnover, capital=1e5)["impact_cost"].sum()
    big = ex.adaptive_cost_components(df, turnover, capital=1e8)["impact_cost"].sum()
    assert big > small
    # impact ∝ √capital for fixed turnover → ~√1000 ≈ 31.6x for 1000x capital
    assert big / small == pytest.approx(np.sqrt(1000.0), rel=0.05)


def test_realized_below_theoretical():
    df = _synthetic_ohlcv()
    # simple SMA-cross signal so there are real trades
    sma_f = df["Close"].rolling(10).mean()
    sma_s = df["Close"].rolling(50).mean()
    signal = (sma_f > sma_s).astype(float)
    res = ex.run_adaptive_backtest(df, signal, capital=5e6)
    theo = res["equity_theoretical"].iloc[-1]
    real = res["equity_realized"].iloc[-1]
    assert real < theo  # costs always erode the curve
    b = res["breakdown"]
    assert b["spread"]["return_drag"] > 0
    assert b["impact"]["return_drag"] >= 0
    assert b["n_trades"] > 0


def test_implementation_shortfall_decomposition():
    # buy: signal 100, arrival 100.05 (latency drift up), fill 100.08 (exec slip)
    isf = ex.implementation_shortfall(
        side=1, signal_price=100.0, arrival_price=100.05, fill_price=100.08,
        commission=2.0, notional=100_080.0,
        signal_time="2024-01-01 09:30:00", fill_time="2024-01-01 09:30:02",
    )
    assert isf["latency_bps"] == pytest.approx(5.0, rel=1e-6)      # +0.05% of 100
    assert isf["execution_bps"] == pytest.approx(2.9985, rel=1e-3)  # +0.03/100.05
    assert isf["fee_bps"] == pytest.approx(0.1998, rel=1e-3)
    assert isf["total_bps"] == pytest.approx(
        isf["latency_bps"] + isf["execution_bps"] + isf["fee_bps"], rel=1e-9)
    assert isf["latency_seconds"] == 2.0


def test_sell_side_sign():
    """For a sell, a LOWER fill than signal is a cost (positive bps)."""
    isf = ex.implementation_shortfall(
        side=-1, signal_price=100.0, arrival_price=99.9, fill_price=99.8,
        commission=0.0, notional=99_800.0)
    assert isf["latency_bps"] > 0
    assert isf["execution_bps"] > 0


def test_liquidity_gauge_zones():
    assert ex.liquidity_gauge(1e4, 1e8)["zone"] == "safe"      # 0.01%
    assert ex.liquidity_gauge(2e6, 1e8)["zone"] == "caution"   # 2%
    assert ex.liquidity_gauge(8e6, 1e8)["zone"] == "warning"   # 8%
    assert ex.liquidity_gauge(2e7, 1e8)["zone"] == "danger"    # 20%
    assert ex.liquidity_gauge(1e4, 0)["zone"] == "unknown"


def test_ledger_roundtrip(tmp_path):
    led = ex.SlippageLedger(path=tmp_path / "log.csv")
    led.log_fill("trend", "SPY", side=1, qty=100, signal_price=100.0,
                 arrival_price=100.02, fill_price=100.05, commission=1.0)
    led.log_fill("trend", "SPY", side=-1, qty=100, signal_price=101.0,
                 arrival_price=100.95, fill_price=100.9, commission=1.0)
    df = led.load()
    assert len(df) == 2
    agg = led.aggregate()
    assert agg["n"] == 2
    assert agg["by_strategy"][0]["strategy"] == "trend"
    assert agg["overall"]["total_bps"] == pytest.approx(df["total_bps"].mean(), rel=1e-9)
