"""(Re)build the SQLite strategy registry from CATALOG.md + strategies/*/results.

Run: .venv/Scripts/python.exe scripts/build_registry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.registry import build_registry, bucket_counts  # noqa: E402


def main() -> None:
    s = build_registry()
    print("Registry built ->", s["db_path"])
    for key in ("strategies", "with_folder", "with_metrics", "metric_rows"):
        print(f"  {key:13s}: {s[key]}")
    print("  by lifecycle bucket:")
    for bucket, c in bucket_counts().items():
        print(f"    {bucket:12s}: {c}")


if __name__ == "__main__":
    main()
