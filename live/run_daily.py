"""Daily orchestrator of the live trading system (NEXT-STRATEGIES Teil 3).

Checks ``calendar.yaml`` for due triggers, runs the daily gates, builds a
human-readable order-ticket report, logs due signals to the ledger and sends
an alert (Telegram via notify.py) when something is actionable today.

Usage:
    .venv/Scripts/python.exe live/run_daily.py                 # today
    .venv/Scripts/python.exe live/run_daily.py --date 2026-06-16
    .venv/Scripts/python.exe live/run_daily.py --week          # 7-day plan
    .venv/Scripts/python.exe live/run_daily.py --no-notify --no-gates

The report is always written to ``live/outbox/YYYY-MM-DD.md`` (versioned —
the outbox doubles as the signal audit trail). Execution stays
human-in-the-loop: this system never places orders.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

import pandas as pd

LIVE = Path(__file__).resolve().parent
sys.path.insert(0, str(LIVE))

from engine import Event, events_in_range, is_trading_day, load_calendar  # noqa: E402
from ledger import log_signal  # noqa: E402

OUTBOX = LIVE / "outbox"
PREVIEW_DAYS = 4  # calendar days of heads-up beyond today


def _fmt_event(e: Event, due: bool) -> str:
    head = "HEUTE FÄLLIG" if due else f"Vorschau {e.date:%a %d.%m.}"
    lines = [f"### [{head}] {e.name} — {e.action.upper()} ({e.status})",
             f"- **Ticket:** `{e.ticket_id}`",
             f"- **Anweisung:** {e.instruction}"]
    if e.expectancy:
        lines.append(f"- **Backtest-Erwartung:** {e.expectancy}")
    if e.size_hint:
        lines.append(f"- **Size:** {e.size_hint}")
    if e.notes:
        lines.append(f"- **Notiz:** {e.notes}")
    return "\n".join(lines)


def _run_gates(today: pd.Timestamp) -> tuple[list[str], bool]:
    """Run daily_gate strategies; returns (report blocks, any actionable flip)."""
    blocks, actionable = [], False
    gates = [c for c in load_calendar() if c["trigger"]["type"] == "daily_gate"]
    if gates and not is_trading_day(today):
        return [], False
    for cfg in gates:
        try:
            module = __import__(f"signals.{cfg['trigger']['module']}",
                                fromlist=["check"])
            res = module.check()
            flip = " **(GATE-FLIP — handeln!)**" if res["flipped"] else ""
            blocks.append(f"### Gate {cfg['name']}\n- {res['message']}{flip}")
            actionable = actionable or res["flipped"]
        except Exception:
            blocks.append(f"### Gate {cfg['name']}\n- FEHLER beim Check:\n"
                          f"```\n{traceback.format_exc(limit=3)}```")
    return blocks, actionable


def build_report(today: pd.Timestamp, horizon_days: int,
                 run_gates: bool = True) -> tuple[str, bool]:
    """Returns (markdown report, anything_actionable_today)."""
    events = events_in_range(today, today + pd.Timedelta(days=horizon_days))
    due = [e for e in events if e.date == today]
    upcoming = [e for e in events if e.date > today]

    parts = [f"# Trading-Desk {today:%A, %d.%m.%Y}",
             "" if is_trading_day(today)
             else "> Heute ist KEIN US-Handelstag.", ""]
    if due:
        parts.append("## Heute fällig\n")
        parts += [_fmt_event(e, True) + "\n" for e in due]
    else:
        parts.append("## Heute fällig\n\n_Keine Trades fällig._\n")
    if upcoming:
        parts.append(f"## Vorschau (nächste {horizon_days} Tage)\n")
        parts += [_fmt_event(e, False) + "\n" for e in upcoming]

    gate_actionable = False
    if run_gates:
        gate_blocks, gate_actionable = _run_gates(today)
        if gate_blocks:
            parts.append("## Tägliche Gates\n")
            parts += [b + "\n" for b in gate_blocks]

    parts.append("---\n_Ausführung human-in-the-loop: Fills mit "
                 "`live/ledger.py fill <ticket>` protokollieren._")
    report = "\n".join(p for p in parts if p is not None)

    # Audit trail: log today's due trade signals (idempotent on ticket+action).
    for e in due:
        if e.action in ("entry", "exit"):
            log_signal(e)
    return report, bool(due) or gate_actionable


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="override today (YYYY-MM-DD)")
    ap.add_argument("--week", action="store_true", help="7-day weekly plan")
    ap.add_argument("--days", type=int, default=None, help="preview horizon")
    ap.add_argument("--no-notify", action="store_true")
    ap.add_argument("--no-gates", action="store_true",
                    help="skip daily gates (no network needed)")
    args = ap.parse_args()

    today = pd.Timestamp(args.date or pd.Timestamp.today()).normalize()
    horizon = args.days or (7 if args.week else PREVIEW_DAYS)
    report, actionable = build_report(today, horizon, run_gates=not args.no_gates)

    OUTBOX.mkdir(parents=True, exist_ok=True)
    out_file = OUTBOX / f"{today:%Y-%m-%d}.md"
    out_file.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[run_daily] Report -> {out_file}")

    if actionable and not args.no_notify:
        from notify import send
        send(report)
    elif not actionable:
        print("[run_daily] Nichts fällig — kein Alert.")


if __name__ == "__main__":
    main()
