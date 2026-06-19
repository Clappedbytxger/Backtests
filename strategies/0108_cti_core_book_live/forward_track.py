"""Free forward-test tracker for the frozen CORE book (0108) -- no broker fills needed.

The book is a pure end-of-day strategy on daily closes, so the "fill" is effectively the
next close, which the engine already reconstructs from yfinance. This tracker therefore
computes the genuine out-of-sample performance by rebuilding the FROZEN book each run and
slicing it from the freeze date forward -- the live-combined Sharpe that the success gate
(>= ~0.9) is measured against. No market-data subscription, no paper fills required.

It writes results/forward_nav.csv (deterministic from data, regenerated each run) and the
current target weights to results/forward_targets_log.csv (append-only audit trail, so we
can prove the emitted positions even if yfinance later revises a print).

Run: .venv/Scripts/python.exe strategies/0108_cti_core_book_live/forward_track.py
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import signal_engine as eng  # noqa: E402

FREEZE = pd.Timestamp("2026-06-19")   # OOS window starts here (freeze commit date)
GATE_SHARPE = 0.9
RESULTS = Path(__file__).resolve().parent / "results"
NAV_CSV = RESULTS / "forward_nav.csv"
TARGETS_LOG = RESULTS / "forward_targets_log.csv"
ANN = np.sqrt(252)


def max_drawdown(returns):
    cum = (1.0 + returns).cumprod()
    return float((cum / cum.cummax() - 1.0).min()) if len(returns) else 0.0


def log_targets(asof, ctx, pos):
    RESULTS.mkdir(exist_ok=True)
    new = not TARGETS_LOG.exists()
    active = {k: round(v, 5) for k, v in pos.items() if abs(v) > 1e-5}
    with TARGETS_LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_ts_utc", "asof", "month_end", "carry_on", "vix",
                        "crypto_gate", "gross", "active_targets"])
        gross = sum(abs(v) for v in pos.values())
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), asof,
                    ctx["month_end"], ctx["carry_on"], round(ctx["vix"], 1),
                    ctx["crypto_gate"], round(gross, 4), active])


def main():
    RESULTS.mkdir(exist_ok=True)
    print("Rebuilding the frozen book from yfinance...")
    book = eng.build_book()
    book.index = pd.to_datetime(book.index)

    insample = book[book.index < FREEZE]
    fwd = book[book.index >= FREEZE]

    print(f"\nIn-sample (...{FREEZE.date()}): {len(insample)}d | "
          f"Sharpe {eng.ann_sharpe(insample):+.3f} (target ~1.21)")

    print(f"\n===== FORWARD TEST (from {FREEZE.date()}) =====")
    if len(fwd) < 2:
        print(f"  {len(fwd)} forward day(s) so far -- nothing to score yet.")
        print("  Re-run daily after the US close; the window fills as new sessions arrive.")
    else:
        sharpe = eng.ann_sharpe(fwd)
        cum = float((1.0 + fwd).prod() - 1.0)
        mdd = max_drawdown(fwd)
        ann_ret = (1.0 + fwd).prod() ** (252.0 / len(fwd)) - 1.0
        print(f"  days={len(fwd)}  Sharpe={sharpe:+.3f}  cumReturn={cum*100:+.2f}%  "
              f"annReturn={ann_ret*100:+.2f}%  maxDD={mdd*100:+.2f}%")
        status = "ON TRACK" if sharpe >= GATE_SHARPE else "below gate"
        print(f"  gate (Sharpe >= {GATE_SHARPE}): {status}")
        if len(fwd) < 40:
            print("  NOTE: <40 forward days -- Sharpe is still very noisy, not yet decisive.")

        # deterministic NAV table (regenerated each run from data)
        nav = pd.DataFrame({"date": fwd.index.date, "daily_ret": fwd.values})
        nav["cum_return"] = (1.0 + fwd).cumprod().values - 1.0
        nav.to_csv(NAV_CSV, index=False)
        print(f"  -> {NAV_CSV}")

    # today's targets (audit trail)
    pos, ctx = eng.compute_targets()
    log_targets(ctx["asof"], ctx, pos)
    active = {k: round(v * 100, 2) for k, v in pos.items() if abs(v) > 1e-5}
    print(f"\nToday (as-of {ctx['asof']}): month_end={ctx['month_end']} carry_on={ctx['carry_on']} "
          f"(VIX {ctx['vix']:.1f}) crypto_gate={ctx['crypto_gate']:.1f}")
    print(f"  active targets (% equity): {active if active else 'FLAT'}")
    print(f"  -> appended to {TARGETS_LOG}")


if __name__ == "__main__":
    main()
