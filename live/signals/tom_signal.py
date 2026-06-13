"""Print the next Turn-of-the-Month ticket (0050).

Usage:
    .venv/Scripts/python.exe live/signals/tom_signal.py [--date YYYY-MM-DD]
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
    print(next_ticket("turn_of_month", args.date))


if __name__ == "__main__":
    main()
