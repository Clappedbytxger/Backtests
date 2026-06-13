"""Live-forward ledger: expected signals vs real fills (NEXT-STRATEGIES Teil 3).

Two versioned CSVs under ``live/state/``:

- ``signals.csv``  every due entry/exit signal, auto-appended by run_daily.py
                   (idempotent on ticket_id+action) — what the system SAID.
- ``fills.csv``    what was actually DONE, entered manually after each fill.

Usage:
    .venv/Scripts/python.exe live/ledger.py fill benzin_kw9-20260223 \
        --side entry --price 2.415 --qty 1 [--date 2026-02-23] [--note "..."]
    .venv/Scripts/python.exe live/ledger.py report

``report`` pairs entry+exit fills per ticket, computes the realized return
(direction-aware) and compares the per-strategy mean against the backtest
expectancy from calendar.yaml — the live-vs-backtest protocol registered for
the forward tests.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import pandas as pd

LIVE = Path(__file__).resolve().parent
sys.path.insert(0, str(LIVE))

STATE = LIVE / "state"
SIGNALS_CSV = STATE / "signals.csv"
FILLS_CSV = STATE / "fills.csv"

SIGNAL_COLS = ["ticket_id", "strategy_id", "action", "date", "instrument",
               "direction", "status", "instruction", "logged_at"]
FILL_COLS = ["ticket_id", "strategy_id", "side", "date", "price", "qty", "note"]


def _append(path: Path, cols: list[str], row: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerow({c: row.get(c, "") for c in cols})


def log_signal(event) -> bool:
    """Append a due signal once (dedupe on ticket_id+action). Returns True if new."""
    if SIGNALS_CSV.exists():
        df = pd.read_csv(SIGNALS_CSV, dtype=str)
        dup = ((df["ticket_id"] == event.ticket_id) &
               (df["action"] == event.action)).any()
        if dup:
            return False
    _append(SIGNALS_CSV, SIGNAL_COLS, {
        "ticket_id": event.ticket_id, "strategy_id": event.strategy_id,
        "action": event.action, "date": f"{event.date:%Y-%m-%d}",
        "instrument": event.instrument, "direction": event.direction,
        "status": event.status, "instruction": event.instruction,
        "logged_at": f"{pd.Timestamp.now():%Y-%m-%d %H:%M}",
    })
    return True


def record_fill(ticket_id: str, side: str, price: float, qty: float,
                date: str | None, note: str) -> None:
    strategy_id = re.sub(r"-\d{8}$", "", ticket_id)
    _append(FILLS_CSV, FILL_COLS, {
        "ticket_id": ticket_id, "strategy_id": strategy_id, "side": side,
        "date": date or f"{pd.Timestamp.today():%Y-%m-%d}",
        "price": price, "qty": qty, "note": note,
    })
    print(f"[ledger] Fill geloggt: {ticket_id} {side} @ {price} x{qty}")


def report() -> None:
    if not FILLS_CSV.exists():
        print("Keine Fills geloggt.")
        return
    from engine import load_calendar

    cal = {c["id"]: c for c in load_calendar()}
    fills = pd.read_csv(FILLS_CSV)
    rows = []
    for tid, grp in fills.groupby("ticket_id"):
        entry = grp[grp["side"] == "entry"]
        exit_ = grp[grp["side"] == "exit"]
        if entry.empty:
            continue
        sid = entry.iloc[0]["strategy_id"]
        direction = cal.get(sid, {}).get("direction", "long")
        ret = None
        if not exit_.empty and entry.iloc[0]["price"] > 0:
            ret = exit_.iloc[0]["price"] / entry.iloc[0]["price"] - 1
            if direction == "short":
                ret = -ret
        rows.append({"ticket_id": tid, "strategy_id": sid,
                     "entry_date": entry.iloc[0]["date"],
                     "exit_date": exit_.iloc[0]["date"] if not exit_.empty else "",
                     "realized_ret": ret})
    df = pd.DataFrame(rows)
    if df.empty:
        print("Keine auswertbaren Tickets.")
        return

    print("# Live-vs-Backtest-Report\n")
    for sid, grp in df.groupby("strategy_id"):
        closed = grp.dropna(subset=["realized_ret"])
        exp = cal.get(sid, {}).get("expectancy", "?")
        mean = f"{closed['realized_ret'].mean():+.2%}" if len(closed) else "—"
        print(f"## {sid}\n  Tickets: {len(grp)} ({len(closed)} geschlossen, "
              f"{len(grp) - len(closed)} offen)")
        print(f"  Realisiert (Mittel): {mean}   |   Backtest: {exp}")
        for _, r in grp.iterrows():
            rr = f"{r['realized_ret']:+.2%}" if pd.notna(r["realized_ret"]) else "offen"
            print(f"    {r['ticket_id']:32s} {r['entry_date']} -> "
                  f"{r['exit_date'] or '...':10s} {rr}")
        print()

    n_signals = 0
    if SIGNALS_CSV.exists():
        sig = pd.read_csv(SIGNALS_CSV)
        n_signals = len(sig[sig["action"] == "entry"])
    n_filled = df["ticket_id"].nunique()
    print(f"Signal-Abdeckung: {n_filled} von {n_signals} Entry-Signalen gefüllt.")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fill", help="record a real fill")
    f.add_argument("ticket_id")
    f.add_argument("--side", choices=["entry", "exit"], required=True)
    f.add_argument("--price", type=float, required=True)
    f.add_argument("--qty", type=float, default=1)
    f.add_argument("--date", default=None)
    f.add_argument("--note", default="")
    sub.add_parser("report", help="live vs backtest comparison")
    args = ap.parse_args()

    if args.cmd == "fill":
        record_fill(args.ticket_id, args.side, args.price, args.qty,
                    args.date, args.note)
    else:
        report()


if __name__ == "__main__":
    main()
