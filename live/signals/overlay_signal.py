"""Print the next order ticket for a Quint-Overlay seasonal leg (0036).

Usage:
    .venv/Scripts/python.exe live/signals/overlay_signal.py --leg benzin_kw9
    .venv/Scripts/python.exe live/signals/overlay_signal.py          # all legs
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import events_in_range, load_calendar  # noqa: E402

OVERLAY_LEGS = ["benzin_kw9", "mastrind_kw21", "baumwolle_jahresend",
                "mais_dezember", "platin_jahreswechsel"]


def next_ticket(strategy_id: str, asof=None) -> str:
    asof = pd.Timestamp(asof or pd.Timestamp.today()).normalize()
    cal = [c for c in load_calendar() if c["id"] == strategy_id]
    if not cal:
        return f"{strategy_id}: nicht in calendar.yaml (oder disabled)."
    evs = [e for e in events_in_range(asof, asof + pd.DateOffset(months=14), cal)
           if e.action == "entry"]
    if not evs:
        return f"{strategy_id}: kein Entry in den naechsten 14 Monaten."
    e = evs[0]
    return (f"[{e.strategy_id}] {e.name} ({e.status})\n"
            f"  {e.instruction}\n"
            f"  Erwartung: {e.expectancy}\n"
            f"  Size: {e.size_hint}\n"
            f"  Notiz: {e.notes}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", choices=OVERLAY_LEGS, default=None)
    ap.add_argument("--date", default=None, help="as-of date (default: today)")
    args = ap.parse_args()
    for leg in ([args.leg] if args.leg else OVERLAY_LEGS):
        print(next_ticket(leg, args.date), "\n")


if __name__ == "__main__":
    main()
