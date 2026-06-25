"""Weekly seasonality scan + alpha-decay snapshot for the Seasonal Calendar.

Scans every symbol in :data:`quantlab.seasonality.SEASONAL_UNIVERSE`, validates
the strongest calendar windows (t-test, win rate, Sharpe) and re-scores each
over the most recent years for the alpha-decay verdict. Writes the snapshot the
``/api/seasonal/upcoming`` endpoint reads, so the request path stays fast.

Run (weekly is plenty — seasonal patterns move on a yearly cadence):

    .\\.venv\\Scripts\\python.exe scripts\\seasonal_scan.py
    .\\.venv\\Scripts\\python.exe scripts\\seasonal_scan.py --top 8 --refresh

Schedule on Windows via Task Scheduler (weekly, Mon 07:00), same pattern as the
"Backtests Trading Desk" daily job. The snapshot lands at
``data/seasonal/patterns.json`` (git-ignored data dir).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # make apps.api importable for the shared builder


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the seasonal-pattern snapshot.")
    ap.add_argument("--top", type=int, default=6,
                    help="patterns kept per asset (default 6)")
    ap.add_argument("--refresh", action="store_true",
                    help="force a fresh price download (ignore the in-process cache)")
    args = ap.parse_args()

    # Reuse the exact builder the API uses, so the snapshot format never drifts.
    from apps.api.seasonal import build_snapshot, _PRICE_CACHE

    if args.refresh:
        _PRICE_CACHE.clear()

    print(f"Scanning seasonal universe (top {args.top}/asset) ...")
    snap = build_snapshot(top_per_asset=args.top)
    actives = sum(1 for p in snap["patterns"] if p["status"] == "active")
    weak = sum(1 for p in snap["patterns"] if p["status"] == "weak")
    decayed = sum(1 for p in snap["patterns"] if p["status"] == "decayed")
    print(f"  built_at={snap['built_at']}  assets={snap['n_assets']}  "
          f"patterns={len(snap['patterns'])}")
    print(f"  status: active={actives}  weak={weak}  decayed={decayed}")
    print(f"  -> {ROOT / 'data' / 'seasonal' / 'patterns.json'}")


if __name__ == "__main__":
    main()
