"""Look-ahead and logic guards for the Weinstein Stage-2 engine (strategy 0074)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.weinstein import signals as sg          # noqa: E402
from quantlab.weinstein.signals import EntryParams, detect_stage2_entries, mansfield_rs
from quantlab.weinstein.portfolio import (            # noqa: E402
    PortfolioConfig, build_orders, run_portfolio,
)


def _synth(n: int = 400, seed: int = 0) -> pd.DataFrame:
    """A base-then-breakout-ish random OHLCV frame for engine tests."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n)
    # range-bound first half, drift up second half -> creates Stage-1 then Stage-2
    base = 100 + np.cumsum(rng.normal(0, 0.4, n))
    trend = np.where(np.arange(n) > n // 2, np.arange(n) - n // 2, 0) * 0.15
    close = base + trend
    high = close + np.abs(rng.normal(0, 0.6, n))
    low = close - np.abs(rng.normal(0, 0.6, n))
    open_ = close + rng.normal(0, 0.3, n)
    vol = rng.integers(1_000_000, 3_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def test_mansfield_rs_sign() -> None:
    """A stock out-performing its benchmark has positive Mansfield RS."""
    idx = pd.bdate_range("2015-01-01", periods=200)
    bench = pd.Series(np.linspace(100, 110, 200), index=idx)
    stock = pd.Series(np.linspace(100, 140, 200), index=idx)  # steeper = outperform
    mrs = mansfield_rs(stock, bench, period=30).dropna()
    assert mrs.iloc[-1] > 0
    # an under-performer is negative
    weak = pd.Series(np.linspace(100, 102, 200), index=idx)
    assert mansfield_rs(weak, bench, period=30).dropna().iloc[-1] < 0


def test_touch_cluster_count() -> None:
    """Three distinct pokes at the ceiling count as three touches; a flat top as one."""
    res = 100.0
    # three separate approaches (dip out of zone between each)
    highs = np.array([99.9, 90, 99.8, 90, 99.95, 90])
    assert sg._count_touch_clusters(highs, res, band=0.01) == 3
    # one long hug of the ceiling = a single cluster
    flat = np.array([99.9, 99.9, 99.9, 99.9])
    assert sg._count_touch_clusters(flat, res, band=0.01) == 1


def test_signal_is_causal() -> None:
    """A signal on bar t must not change when future bars are appended/removed.

    Computing on the full series vs. a series truncated at t must agree on
    signal[:t] — proof that detection uses only data up to and including t.
    """
    df = _synth(360, seed=3)
    bench = pd.Series(np.linspace(100, 120, len(df)), index=df.index)
    full = detect_stage2_entries(df, bench, EntryParams())["signal"]
    cut = 300
    trunc = detect_stage2_entries(df.iloc[:cut], bench.iloc[:cut], EntryParams())["signal"]
    pd.testing.assert_series_equal(full.iloc[:cut], trunc, check_names=False)


def test_entry_fills_next_open_no_same_bar_exit() -> None:
    """An order fills at the OPEN of the bar AFTER the signal, never the signal
    bar, and a freshly opened lot is not exited on its entry bar."""
    df = _synth(400, seed=7)
    bench = pd.Series(np.linspace(100, 130, len(df)), index=df.index)
    det = detect_stage2_entries(df, bench, EntryParams())
    # Plant one deterministic signal so the mapping is testable regardless of the
    # random base (the causality of detection itself is covered separately).
    det["signal"] = False
    sig_pos = 200
    det.iloc[sig_pos, det.columns.get_loc("signal")] = True
    det.iloc[sig_pos, det.columns.get_loc("stop")] = float(df["Low"].iloc[sig_pos] * 0.95)
    data = {"X": df.join(det)}
    orders = build_orders(data)
    assert len(orders["X"]) == 1
    fill_date, _ = orders["X"][0]
    assert fill_date == df.index[sig_pos + 1]      # next bar, never the signal bar

    res = run_portfolio(data, orders, PortfolioConfig(exit_mode="trail1r"))
    tr = res["trades"]
    assert not tr.empty
    # the fill price is the next bar's OPEN (look-ahead-safe execution)
    assert abs(tr["entry"].iloc[0] - df["Open"].iloc[sig_pos + 1]) < 1e-9
    # exit strictly after entry (no same-bar round-trip)
    assert (pd.to_datetime(tr["exit_date"]) > pd.to_datetime(tr["entry_date"])).all()


def test_signal_on_last_bar_makes_no_order() -> None:
    """A signal with no following bar cannot be filled (no future leak)."""
    df = _synth(120, seed=1)
    bench = pd.Series(np.linspace(100, 110, len(df)), index=df.index)
    det = detect_stage2_entries(df, bench, EntryParams()).copy()
    det["signal"] = False
    det.iloc[-1, det.columns.get_loc("signal")] = True
    det.iloc[-1, det.columns.get_loc("stop")] = float(df["Close"].iloc[-1] * 0.9)
    orders = build_orders({"X": df.join(det[["signal", "stop"]], rsuffix="_d")
                           .assign(signal=det["signal"], stop=det["stop"])})
    assert orders["X"] == []


def test_clairvoyant_signal_is_profitable_guardrail() -> None:
    """Sanity that the engine books PnL in the right direction: a planted entry
    right before a known up-move yields a positive trade (catches sign bugs)."""
    n = 200
    idx = pd.bdate_range("2015-01-01", periods=n)
    close = np.concatenate([np.full(100, 100.0), np.linspace(100, 200, 100)])
    df = pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1, "Close": close,
        "Volume": np.full(n, 1e6),
        "ma": close - 5, "atr": np.full(n, 2.0),
    }, index=idx)
    orders = {"X": [(idx[101], 95.0)]}   # enter just as the up-move starts
    res = run_portfolio({"X": df}, orders, PortfolioConfig(exit_mode="trail1r"))
    assert res["trades"]["pnl"].iloc[0] > 0
