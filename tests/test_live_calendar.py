"""Trigger-logic tests for the live trading system (live/engine.py).

The dates asserted here were hand-checked against the 2026 calendar; the
backtest T+1 convention (buy MOC on signal day, hold one bar past the
window) is what the live instructions must reproduce.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "live"))

from engine import (  # noqa: E402
    FOMC_ANNOUNCEMENTS,
    events_in_range,
    is_trading_day,
    load_calendar,
    next_trading_day,
    prev_trading_day,
)


def _events(strategy_id: str, start: str, end: str):
    cal = [c for c in load_calendar() if c["id"] == strategy_id]
    assert cal, f"{strategy_id} fehlt in calendar.yaml"
    return events_in_range(start, end, cal)


# ------------------------------------------------------------ calendar basics

def test_us_holidays_are_not_trading_days():
    assert not is_trading_day("2026-07-03")   # July 4th observed (Sat -> Fri)
    assert not is_trading_day("2026-11-26")   # Thanksgiving
    assert not is_trading_day("2026-04-03")   # Good Friday (exchange holiday)
    assert not is_trading_day("2026-06-13")   # Saturday
    assert is_trading_day("2026-06-15")       # ordinary Monday


def test_next_prev_trading_day_skip_weekend():
    assert next_trading_day("2026-06-12") == pd.Timestamp("2026-06-15")
    assert prev_trading_day("2026-06-15") == pd.Timestamp("2026-06-12")


# ------------------------------------------------------------------ triggers

def test_benzin_kw9_2026_entry_exit():
    evs = _events("benzin_kw9", "2026-01-01", "2026-12-31")
    entry = [e for e in evs if e.action == "entry"][0]
    exit_ = [e for e in evs if e.action == "exit"][0]
    # ISO week 9 of 2026 starts Monday 2026-02-23; hold 5 trading days.
    assert entry.date == pd.Timestamp("2026-02-23")
    assert exit_.date == pd.Timestamp("2026-03-02")
    assert entry.ticket_id == exit_.ticket_id  # exit pairs back to entry date


def test_platin_window_wraps_year_end():
    evs = _events("platin_jahreswechsel", "2025-12-01", "2026-01-31")
    entry = [e for e in evs if e.action == "entry"][0]
    exit_ = [e for e in evs if e.action == "exit"][0]
    assert entry.date == pd.Timestamp("2025-12-18")
    # last trading day <= Jan 10 is Fri Jan 9; +1-shift exits the next day.
    assert exit_.date == pd.Timestamp("2026-01-12")


def test_turn_of_month_feb_2026():
    evs = _events("turn_of_month", "2026-02-20", "2026-03-10")
    entry = [e for e in evs if e.action == "entry"][0]
    exit_ = [e for e in evs if e.action == "exit"][0]
    # Last trading day of Feb 2026 = Fri 27.2.; 4th trading day of March = 5.3.
    assert entry.date == pd.Timestamp("2026-02-27")
    assert exit_.date == pd.Timestamp("2026-03-05")


def test_turn_of_month_over_new_year_holiday():
    evs = _events("turn_of_month", "2026-12-28", "2027-01-15")
    entry = [e for e in evs if e.action == "entry"][0]
    exit_ = [e for e in evs if e.action == "exit"][0]
    assert entry.date == pd.Timestamp("2026-12-31")
    # Jan 1 2027 (Fri) is a holiday -> trading days 4.,5.,6.,7. Jan.
    assert exit_.date == pd.Timestamp("2027-01-07")


def test_pre_fomc_june_2026():
    evs = _events("pre_fomc", "2026-06-01", "2026-06-30")
    entry = [e for e in evs if e.action == "entry"][0]
    exit_ = [e for e in evs if e.action == "exit"][0]
    # Announcement Wed 17.6.2026 -> buy MOC 16.6., sell MOO 17.6.
    assert entry.date == pd.Timestamp("2026-06-16")
    assert exit_.date == pd.Timestamp("2026-06-17")
    assert "MOC" in entry.instruction and "ERÖFFNUNG" in exit_.instruction


def test_fomc_list_is_sane():
    dates = pd.to_datetime(FOMC_ANNOUNCEMENTS)
    assert (pd.Series(1, index=dates).groupby(dates.year).sum() == 8).all()
    assert dates.is_monotonic_increasing


def test_all_strategies_produce_paired_events_2026():
    for cfg in load_calendar():
        if cfg["trigger"]["type"] in ("daily_gate", "monthly_task"):
            continue
        evs = _events(cfg["id"], "2026-01-01", "2027-03-31")
        entries = [e for e in evs if e.action == "entry"]
        exits = [e for e in evs if e.action == "exit"]
        assert entries, f"{cfg['id']}: kein Entry in 2026"
        for e in entries:
            assert e.paired_date is not None and e.paired_date > e.date
            assert is_trading_day(e.date), f"{cfg['id']}: Entry an Nicht-Handelstag"


def test_monthly_task_fires_each_month():
    evs = _events("crypto_rebalance", "2026-01-01", "2026-12-31")
    assert len(evs) == 12 and all(e.action == "task" for e in evs)
