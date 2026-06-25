"""Trigger engine for the live trading system (NEXT-STRATEGIES Teil 3).

Turns the strategy definitions in ``live/calendar.yaml`` into concrete,
dated entry/exit events ("order tickets"). All date logic mirrors the
backtest convention exactly (signals are decision-time, the engine holds
T+1), so the live instructions reproduce what the backtests measured:

- ``isoweek``      buy MOC on the first trading day of ISO week W, sell MOC
                   ``hold_days`` trading days later (0006/0009 via 0036).
- ``date_window``  buy MOC on the first trading day >= start, sell MOC on the
                   first trading day AFTER the last in-window trading day
                   (the backtest's +1-shift holds one day past the window).
- ``month_turn``   buy MOC on the last trading day of the month, sell MOC on
                   the 4th trading day of the next month (0050: signal days
                   [last 1 + first 3] -> position days [D1..D4]).
- ``fomc``         buy MOC on the trading day before a scheduled FOMC
                   announcement, sell at the OPEN on announcement day (0052).
- ``monthly_task`` a non-trade task on the first calendar day of each month
                   (e.g. run the crypto live-signal refresh, 0060).
- ``daily_gate``   evaluated every trading day by its signal module (e.g.
                   VIX term-structure gate, 0056); alerts only on state flips.

Trading calendar: NYSE-like (Mon-Fri minus US federal holidays). Good Friday
is NOT a federal holiday but IS an exchange holiday, so it is added manually.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    USFederalHolidayCalendar,
)
from pandas.tseries.offsets import CustomBusinessDay

ROOT = Path(__file__).resolve().parents[1]
CALENDAR_YAML = Path(__file__).resolve().parent / "calendar.yaml"


class _ExchangeCalendar(AbstractHolidayCalendar):
    rules = USFederalHolidayCalendar.rules + [GoodFriday]


US_BDAY = CustomBusinessDay(calendar=_ExchangeCalendar())

# Scheduled FOMC announcement days (last day of each meeting). Source:
# federalreserve.gov/monetarypolicy/fomccalendars.htm, verified 2026-06-13.
# MAINTENANCE: extend every year when the Fed publishes the next schedule
# (the FRED release feed is useless for this — see 0052/0055 lesson).
FOMC_ANNOUNCEMENTS = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]

# 30-year Treasury Bond auction dates (for the auction-concession short, 0078).
# 30y bonds auction monthly (new issue Feb/May/Aug/Nov + reopenings), ~2nd week.
# The live trigger PREFERS the live TreasuryDirect feed (auctions are announced
# ~7 trading days ahead, before the T-5 entry) and caches it; this hard-coded list
# is the OFFLINE fallback. Source: treasurydirect.gov, verified 2026-06-15.
BOND_30Y_AUCTIONS_FALLBACK = [
    "2024-01-11", "2024-02-08", "2024-03-13", "2024-04-11", "2024-05-09", "2024-06-13",
    "2024-07-11", "2024-08-08", "2024-09-12", "2024-10-10", "2024-11-06", "2024-12-12",
    "2025-01-08", "2025-02-13", "2025-03-13", "2025-04-10", "2025-05-08", "2025-06-12",
    "2025-07-10", "2025-08-07", "2025-09-11", "2025-10-09", "2025-11-13", "2025-12-11",
    "2026-01-13", "2026-02-12", "2026-03-12", "2026-04-09", "2026-05-13", "2026-06-11",
    # H2-2026 PROJECTED from the regular monthly ~2nd-week pattern (Treasury
    # tentative auction schedule). The live feed refines each to the exact date
    # once announced (~5 td ahead); human-in-the-loop confirms before the T-5 entry.
    "2026-07-09", "2026-08-12", "2026-09-09", "2026-10-08", "2026-11-12", "2026-12-09",
]
_AUCTION_CACHE = Path(__file__).resolve().parent / "state" / "auctions_30y.json"
_30Y_TERMS = {"30-Year", "29-Year 11-Month", "29-Year 10-Month", "29-Year 9-Month"}


def load_30y_auctions(refresh: bool = True) -> list[str]:
    """30y auction dates: live TreasuryDirect feed (cached) + offline fallback.

    Tries to fetch upcoming + recently-auctioned 30y bonds (announced ~7 td ahead,
    before the T-5 entry), unions with the cache and the hard-coded fallback, and
    persists. On any network failure falls back to cache/hard-coded list — so the
    offline ``run_daily.py --no-gates`` path still works.
    """
    import json
    dates: set[str] = set(BOND_30Y_AUCTIONS_FALLBACK)
    if _AUCTION_CACHE.exists():
        try:
            dates |= set(json.loads(_AUCTION_CACHE.read_text()))
        except Exception:  # noqa: BLE001
            pass
    if refresh:
        import urllib.request
        for ep in ("upcoming", "auctioned?type=Bond"):
            try:
                url = f"https://www.treasurydirect.gov/TA_WS/securities/{ep}{'&' if '?' in ep else '?'}format=json"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                rows = json.load(urllib.request.urlopen(req, timeout=20))
                dates |= {r["auctionDate"][:10] for r in rows
                          if r.get("securityType") == "Bond" and r.get("securityTerm") in _30Y_TERMS}
            except Exception:  # noqa: BLE001
                pass
        try:
            _AUCTION_CACHE.parent.mkdir(parents=True, exist_ok=True)
            _AUCTION_CACHE.write_text(json.dumps(sorted(dates)))
        except Exception:  # noqa: BLE001
            pass
    return sorted(dates)


def trading_days(start, end) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq=US_BDAY)


def is_trading_day(date) -> bool:
    d = pd.Timestamp(date).normalize()
    return len(pd.date_range(d, d, freq=US_BDAY)) == 1


def next_trading_day(date, n: int = 1) -> pd.Timestamp:
    return (pd.Timestamp(date).normalize() + n * US_BDAY).normalize()


def prev_trading_day(date, n: int = 1) -> pd.Timestamp:
    return (pd.Timestamp(date).normalize() - n * US_BDAY).normalize()


@dataclass
class Event:
    strategy_id: str
    name: str
    action: str  # "entry" | "exit" | "task" | "gate-check"
    date: pd.Timestamp
    instruction: str
    instrument: str = ""
    direction: str = ""
    status: str = ""  # "confirmed" | "testing"
    size_hint: str = ""
    expectancy: str = ""
    notes: str = ""
    paired_date: pd.Timestamp | None = None  # exit date for entries & v.v.

    @property
    def ticket_id(self) -> str:
        anchor = self.date if self.action != "exit" else (self.paired_date or self.date)
        return f"{self.strategy_id}-{anchor:%Y%m%d}"


def load_calendar(path: Path | None = None) -> list[dict]:
    raw = yaml.safe_load((path or CALENDAR_YAML).read_text(encoding="utf-8"))
    return [c for c in raw if c.get("enabled", True)]


# ---------------------------------------------------------------- triggers

def _isoweek_events(cfg: dict, year: int) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    week = int(cfg["trigger"]["week"])
    hold = int(cfg["trigger"].get("hold_days", 5))
    days = trading_days(f"{year}-01-01", f"{year}-12-31")
    iso = days.isocalendar()
    in_week = days[(iso["week"].values == week) & (iso["year"].values == year)]
    if len(in_week) == 0:
        return []
    entry = in_week[0]
    exit_ = next_trading_day(entry, hold)
    return [("entry", entry, exit_), ("exit", exit_, entry)]


def _date_window_events(cfg: dict, year: int) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    sm, sd = cfg["trigger"]["start_md"]
    em, ed = cfg["trigger"]["end_md"]
    start = pd.Timestamp(year, sm, sd)
    end = pd.Timestamp(year if (em, ed) > (sm, sd) else year + 1, em, ed)
    win = trading_days(start, end)
    if len(win) == 0:
        return []
    entry = win[0]
    exit_ = next_trading_day(win[-1])  # backtest +1-shift holds one day past window
    return [("entry", entry, exit_), ("exit", exit_, entry)]


def _month_turn_events(cfg: dict, year: int) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    days_after = int(cfg["trigger"].get("days_after_start", 3))
    out = []
    for month in range(1, 13):
        month_days = trading_days(f"{year}-{month:02d}-01",
                                  pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0))
        if len(month_days) == 0:
            continue
        entry = month_days[-1]  # last trading day of month
        exit_ = next_trading_day(entry, days_after + 1)  # 4th td of next month
        out.append(("entry", entry, exit_))
        out.append(("exit", exit_, entry))
    return out


def _month_end_events(cfg: dict, year: int) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """End-of-month Treasury turn (0075): buy MOC ``before`` trading days from the
    month end, hold the last day + first day of next month, sell MOC on the first
    trading day of next month. before=2 -> held {last day, first next day} (matches
    turn_of_month_signal(before=2, after=0))."""
    before = int(cfg["trigger"].get("before", 2))
    out = []
    for month in range(1, 13):
        month_days = trading_days(f"{year}-{month:02d}-01",
                                  pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0))
        if len(month_days) < before:
            continue
        entry = month_days[-before]          # e.g. 2nd-to-last trading day
        exit_ = next_trading_day(month_days[-1])  # first trading day of next month
        out.append(("entry", entry, exit_))
        out.append(("exit", exit_, entry))
    return out


def _treasury_auction_events(cfg: dict, year: int) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """Treasury auction concession short (0078): short MOC ``pre_days`` trading days
    before each 30y auction, cover MOC on the auction day (end of the concession,
    before the post-auction reversal)."""
    pre = int(cfg["trigger"].get("pre_days", 5))
    auctions = cfg.setdefault("_auction_dates", load_30y_auctions(refresh=cfg["trigger"].get("refresh", True)))
    out = []
    for ds in auctions:
        a = pd.Timestamp(ds)
        if a.year != year:
            continue
        ad = a if is_trading_day(a) else next_trading_day(a)
        entry = prev_trading_day(ad, pre)
        out.append(("entry", entry, ad))
        out.append(("exit", ad, entry))
    return out


def _fomc_events(cfg: dict, year: int) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    out = []
    for d in pd.to_datetime(FOMC_ANNOUNCEMENTS):
        if d.year != year:
            continue
        ann = d if is_trading_day(d) else next_trading_day(d)
        entry = prev_trading_day(ann)
        out.append(("entry", entry, ann))
        out.append(("exit", ann, entry))
    return out


def _monthly_task_events(cfg: dict, year: int) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    return [("task", pd.Timestamp(year, m, 1), pd.Timestamp(year, m, 1))
            for m in range(1, 13)]


_TRIGGERS = {
    "isoweek": _isoweek_events,
    "date_window": _date_window_events,
    "month_turn": _month_turn_events,
    "month_end": _month_end_events,
    "treasury_auction": _treasury_auction_events,
    "fomc": _fomc_events,
    "monthly_task": _monthly_task_events,
}


def _instruction(cfg: dict, action: str, date: pd.Timestamp,
                 paired: pd.Timestamp) -> str:
    inst, direction = cfg.get("instrument", ""), cfg.get("direction", "long")
    ttype = cfg["trigger"]["type"]
    if action == "task":
        return cfg.get("task", "Task ausführen")
    if ttype == "fomc":
        if action == "entry":
            return (f"{direction.upper()} {inst} zum BÖRSENSCHLUSS (MOC) am {date:%a %d.%m.%Y} "
                    f"— Verkauf zur ERÖFFNUNG am FOMC-Tag {paired:%a %d.%m.%Y}.")
        return (f"Position {inst} zur ERÖFFNUNG (MOO) am {date:%a %d.%m.%Y} schließen "
                f"(VOR der 14-Uhr-ET-Ankündigung — nur die Nacht halten).")
    if action == "entry":
        return (f"{direction.upper()} {inst} zum BÖRSENSCHLUSS (MOC) am {date:%a %d.%m.%Y} "
                f"— geplanter Exit MOC {paired:%a %d.%m.%Y}.")
    return f"Position {inst} zum BÖRSENSCHLUSS (MOC) am {date:%a %d.%m.%Y} schließen."


def events_in_range(start, end, calendar: list[dict] | None = None) -> list[Event]:
    """All dated events of all enabled strategies within [start, end]."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    calendar = calendar if calendar is not None else load_calendar()
    out: list[Event] = []
    for cfg in calendar:
        ttype = cfg["trigger"]["type"]
        if ttype == "daily_gate":
            continue  # handled live by its signal module, not pre-dated
        fn = _TRIGGERS[ttype]
        for year in range(start.year - 1, end.year + 1):
            for action, date, paired in fn(cfg, year):
                if start <= date <= end:
                    out.append(Event(
                        strategy_id=cfg["id"], name=cfg.get("name", cfg["id"]),
                        action=action, date=date,
                        instruction=_instruction(cfg, action, date, paired),
                        instrument=cfg.get("instrument", ""),
                        direction=cfg.get("direction", ""),
                        status=cfg.get("status", ""),
                        size_hint=cfg.get("size_hint", ""),
                        expectancy=cfg.get("expectancy", ""),
                        notes=cfg.get("notes", ""),
                        paired_date=paired,
                    ))
    out.sort(key=lambda e: (e.date, e.strategy_id, e.action))
    return out
