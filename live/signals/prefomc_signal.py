"""Print the next Pre-FOMC overnight ticket (0052).

Usage:
    .venv/Scripts/python.exe live/signals/prefomc_signal.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from overlay_signal import next_ticket  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    args = ap.parse_args()
    print(next_ticket("pre_fomc", args.date))


if __name__ == "__main__":
    main()
