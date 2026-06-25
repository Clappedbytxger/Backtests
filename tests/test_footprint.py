"""Tests for quantlab.footprint — volume conservation, POC, delta sign, no look-ahead."""

from __future__ import annotations

import pandas as pd
import pytest

from quantlab.footprint import (
    aggregate_candles,
    build_footprint,
    choose_bin_size,
    split_adjust,
)


def _bars(rows, start="2024-01-02 14:30", freq="1min"):
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"], index=idx)


def test_volume_is_conserved():
    # 15 one-minute bars -> one 15m cluster. Every unit of volume must land in a
    # level, and bid+ask must reconcile to total at each level.
    rows = [[100 + i * 0.1, 100 + i * 0.1 + 0.3, 100 + i * 0.1 - 0.2,
             100 + i * 0.1 + (0.1 if i % 2 else -0.1), 100 + 10 * i] for i in range(15)]
    clusters = build_footprint(_bars(rows), "15m", ticker="ES")
    assert len(clusters) == 1
    c = clusters[0]
    level_total = sum(lv["total"] for lv in c["levels"])
    assert level_total == pytest.approx(c["total_volume"], rel=1e-6)
    for lv in c["levels"]:
        assert lv["bid_volume"] + lv["ask_volume"] == pytest.approx(lv["total"], abs=0.05)


def test_poc_is_highest_volume_price():
    # Volume concentrated at ~100, a little noise at ~105 -> POC sits at 100.
    rows = [[100, 100.1, 99.9, 100, 1000] for _ in range(10)]
    rows += [[105, 105.1, 104.9, 105, 10] for _ in range(2)]
    clusters = build_footprint(_bars(rows), "15m", ticker="ES")
    assert len(clusters) == 1
    assert clusters[0]["poc_price"] == pytest.approx(100, abs=0.25)


def test_delta_sign_follows_tick_rule():
    # One up bar then one down bar, each its own 1m cluster.
    rows = [[100, 101, 100, 101, 500],   # up  -> all ask (delta > 0)
            [101, 101, 100, 100, 400]]   # down-> all bid (delta < 0)
    clusters = build_footprint(_bars(rows), "1m", ticker="ES")
    assert len(clusters) == 2
    up, down = clusters
    assert sum(lv["bid_volume"] for lv in up["levels"]) == pytest.approx(0, abs=0.01)
    assert sum(lv["ask_volume"] for lv in up["levels"]) == pytest.approx(500, rel=1e-6)
    assert sum(lv["ask_volume"] for lv in down["levels"]) == pytest.approx(0, abs=0.01)
    assert sum(lv["bid_volume"] for lv in down["levels"]) == pytest.approx(400, rel=1e-6)


def test_no_lookahead_completed_cluster_is_stable():
    # A finished cluster must not change when later bars are appended.
    rows = [[100 + (i % 5) * 0.1, 100 + (i % 5) * 0.1 + 0.2,
             100 + (i % 5) * 0.1 - 0.2, 100 + (i % 5) * 0.1, 50 + i] for i in range(30)]
    full = build_footprint(_bars(rows), "15m", ticker="ES")
    prefix = build_footprint(_bars(rows[:15]), "15m", ticker="ES")
    assert len(full) == 2 and len(prefix) == 1
    assert full[0] == prefix[0]  # first cluster identical with/without future bars


def test_aggregate_candles_ohlcv():
    rows = [[100, 105, 99, 101, 10],
            [101, 106, 100, 104, 20],
            [104, 107, 103, 106, 30]]
    # all three within the 14:30 15m bucket
    candles = aggregate_candles(_bars(rows), "15m")
    assert len(candles) == 1
    c = candles[0]
    assert (c["open"], c["high"], c["low"], c["close"], c["volume"]) == (100, 107, 99, 106, 60)


def test_aggregate_candles_time_is_epoch_seconds_any_resolution():
    # DuckDB hands back microsecond-resolution stamps; time must still be epoch seconds.
    bars = _bars([[100, 101, 99, 100, 5]], start="2026-06-05 14:30")
    bars.index = bars.index.as_unit("us")
    candles = aggregate_candles(bars, "1m")
    assert len(candles) == 1
    assert candles[0]["time"] == int(pd.Timestamp("2026-06-05 14:30", tz="UTC").timestamp())


def test_split_adjust_divides_pre_split_only():
    # daily bars on 3 trading days; a 2:1 split takes effect on day 2 (the ex-date).
    idx = pd.DatetimeIndex(["2021-01-04 15:00", "2021-01-05 15:00", "2021-01-06 15:00"], tz="UTC")
    bars = pd.DataFrame(
        {"Open": [100, 50, 52], "High": [110, 55, 57], "Low": [90, 45, 47],
         "Close": [100, 50, 52], "Volume": [10.0, 20.0, 20.0]},
        index=idx,
    )
    adj = split_adjust(bars, {pd.Timestamp("2021-01-05", tz="UTC"): 2.0})
    # pre-split bar: price halved, volume doubled, dollar-volume preserved
    assert adj["Close"].iloc[0] == pytest.approx(50)
    assert adj["Volume"].iloc[0] == pytest.approx(20)
    assert adj["Close"].iloc[0] * adj["Volume"].iloc[0] == pytest.approx(100 * 10)
    # ex-date bar and after: untouched (exchange already prints post-split)
    assert adj["Close"].iloc[1] == pytest.approx(50)
    assert adj["Volume"].iloc[1] == pytest.approx(20)
    # no splits -> unchanged
    assert split_adjust(bars, {})["Close"].iloc[0] == 100


def test_choose_bin_size_snaps_to_tick():
    bs = choose_bin_size(100.0, 160.0, tick=0.25, target_rows=80)
    assert bs >= 0.25
    assert round(bs / 0.25, 6) == round(bs / 0.25)  # exact multiple of the tick
    # a tiny range collapses to one tick
    assert choose_bin_size(100.0, 100.1, tick=0.25, target_rows=80) == 0.25
