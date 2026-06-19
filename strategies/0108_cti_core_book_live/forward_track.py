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


def compute():
    """Rebuild the frozen book, score the forward window, write NAV + targets log.
    Returns a stats dict (used by the daily runner for the alert summary)."""
    RESULTS.mkdir(exist_ok=True)
    book = eng.build_book()
    book.index = pd.to_datetime(book.index)
    insample = book[book.index < FREEZE]
    fwd = book[book.index >= FREEZE]

    stats = {"insample_days": int(len(insample)),
             "insample_sharpe": eng.ann_sharpe(insample),
             "fwd_days": int(len(fwd))}
    if len(fwd) >= 2:
        stats.update({
            "fwd_sharpe": eng.ann_sharpe(fwd),
            "fwd_cum": float((1.0 + fwd).prod() - 1.0),
            "fwd_ann": float((1.0 + fwd).prod() ** (252.0 / len(fwd)) - 1.0),
            "fwd_mdd": max_drawdown(fwd),
            "gate_pass": eng.ann_sharpe(fwd) >= GATE_SHARPE,
        })
        nav = pd.DataFrame({"date": fwd.index.date, "daily_ret": fwd.values})
        nav["cum_return"] = (1.0 + fwd).cumprod().values - 1.0
        nav.to_csv(NAV_CSV, index=False)

    pos, ctx = eng.compute_targets()
    log_targets(ctx["asof"], ctx, pos)
    stats["ctx"] = ctx
    stats["active_targets"] = {k: round(v * 100, 2) for k, v in pos.items() if abs(v) > 1e-5}
    return stats


def main():
    print("Rebuilding the frozen book from yfinance...")
    s = compute()
    print(f"\nIn-sample (...{FREEZE.date()}): {s['insample_days']}d | "
          f"Sharpe {s['insample_sharpe']:+.3f} (target ~1.21)")
    print(f"\n===== FORWARD TEST (from {FREEZE.date()}) =====")
    if s["fwd_days"] < 2:
        print(f"  {s['fwd_days']} forward day(s) so far -- nothing to score yet.")
        print("  Re-run daily after the US close; the window fills as new sessions arrive.")
    else:
        print(f"  days={s['fwd_days']}  Sharpe={s['fwd_sharpe']:+.3f}  "
              f"cumReturn={s['fwd_cum']*100:+.2f}%  annReturn={s['fwd_ann']*100:+.2f}%  "
              f"maxDD={s['fwd_mdd']*100:+.2f}%")
        print(f"  gate (Sharpe >= {GATE_SHARPE}): "
              f"{'ON TRACK' if s['gate_pass'] else 'below gate'}")
        if s["fwd_days"] < 40:
            print("  NOTE: <40 forward days -- Sharpe is still very noisy, not yet decisive.")
        print(f"  -> {NAV_CSV}")
    ctx = s["ctx"]
    print(f"\nToday (as-of {ctx['asof']}): month_end={ctx['month_end']} carry_on={ctx['carry_on']} "
          f"(VIX {ctx['vix']:.1f}) crypto_gate={ctx['crypto_gate']:.1f}")
    print(f"  active targets (% equity): {s['active_targets'] if s['active_targets'] else 'FLAT'}")
    print(f"  -> appended to {TARGETS_LOG}")


if __name__ == "__main__":
    main()
