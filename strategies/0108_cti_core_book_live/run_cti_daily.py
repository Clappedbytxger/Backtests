"""Daily orchestrator for the 0108 CORE-book bot -- the single entry point the VPS
scheduler calls once per day after the US close.

It does two independent jobs, each isolated so one failing never blocks the other:
  A) forward tracking (always, free, no broker): rebuild the frozen book, score the
     live forward Sharpe, write NAV + targets log.
  B) IBKR execution (optional): place the day's FX targets on the paper account
     (--arm). Index-CFD/crypto fills need a market-data subscription (see HANDOFF);
     until then this leg trades FX only and the tracker carries the full-book score.

Everything is mirrored to results/daily_logs/YYYY-MM-DD.log and a short summary is
pushed via live/notify.py (Telegram/WhatsApp, if a *.key is present).

Run (tracker only, safe):       .venv/Scripts/python.exe strategies/0108_cti_core_book_live/run_cti_daily.py
Run (also place FX, dry-run):   ... run_cti_daily.py --ibkr
Run (also place FX, ARMED):     ... run_cti_daily.py --ibkr --arm
"""
from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "live"))   # reuse the live notifier

import forward_track  # noqa: E402

LOG_DIR = HERE / "results" / "daily_logs"


class Tee:
    """Mirror stdout/stderr to a log file and the console."""
    def __init__(self, stream, fh):
        self.stream, self.fh = stream, fh

    def write(self, s):
        self.stream.write(s); self.fh.write(s)

    def flush(self):
        self.stream.flush(); self.fh.flush()


def notify(text):
    try:
        from notify import send  # live/notify.py
        send(text)
    except Exception as e:  # noqa: BLE001
        print(f"[notify] unavailable: {e}")


def forward_leg(lines):
    s = forward_track.compute()
    ctx = s["ctx"]
    head = f"as-of {ctx['asof']} | inSample Sh {s['insample_sharpe']:+.2f}"
    if s["fwd_days"] >= 2:
        gate = "ON TRACK" if s["gate_pass"] else "below gate"
        head += (f" | FWD {s['fwd_days']}d Sh {s['fwd_sharpe']:+.2f} "
                 f"({gate}) cum {s['fwd_cum']*100:+.1f}% mDD {s['fwd_mdd']*100:+.1f}%")
    else:
        head += f" | FWD {s['fwd_days']}d (no score yet)"
    lines.append(head)
    tg = s["active_targets"]
    lines.append(f"targets: {tg if tg else 'FLAT'} | "
                 f"month_end={ctx['month_end']} carry={ctx['carry_on']} "
                 f"VIX {ctx['vix']:.1f} crypto_gate={ctx['crypto_gate']:.1f}")
    return s


def ibkr_leg(lines, arm):
    import ib_adapter
    ib_adapter.main(arm=arm)
    # report today's fills from the ledger tail
    led = HERE / "results" / "fills_ledger.csv"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fills = [ln for ln in led.read_text().splitlines()[1:] if ln.startswith(today)] if led.exists() else []
    lines.append(f"IBKR: {'ARMED' if arm else 'dry-run'} | {len(fills)} order(s) today")


def main(do_ibkr=False, arm=False):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logpath = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    fh = logpath.open("a", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, fh)
    sys.stderr = Tee(sys.__stderr__, fh)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"\n========== CTI daily run {stamp} (ibkr={do_ibkr} arm={arm}) ==========")

    lines = [f"CTI bot {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    failed = False

    try:
        forward_leg(lines)
    except Exception:  # noqa: BLE001
        failed = True
        lines.append("forward tracker FAILED (see log)")
        traceback.print_exc()

    if do_ibkr:
        try:
            ibkr_leg(lines, arm)
        except Exception as e:  # noqa: BLE001
            failed = True
            lines.append(f"IBKR leg FAILED: {type(e).__name__}")
            traceback.print_exc()

    if failed:
        lines.insert(1, "!! RUN HAD FAILURES -- check the VPS log")
    summary = "\n".join(lines)
    print("\n--- summary ---\n" + summary)
    notify(summary)
    sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__  # restore before closing the log
    fh.flush(); fh.close()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main(do_ibkr="--ibkr" in sys.argv, arm="--arm" in sys.argv)
