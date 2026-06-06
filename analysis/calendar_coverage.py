"""Calendar-coverage report for the seasonal edge registry.

Reads ``strategies/seasonal_calendar.yaml`` and draws a year-long Gantt of every
edge's active window, coloured by status (confirmed / testing / rejected), so the
gaps in the calendar are obvious at a glance. Also prints a month-by-month
coverage table.

Run:
    .venv/Scripts/python.exe analysis/calendar_coverage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.seasonal import leg_signal  # noqa: E402

REGISTRY = ROOT / "strategies" / "seasonal_calendar.yaml"
OUT = Path(__file__).resolve().parent / "coverage.png"

# Representative non-leap year for projecting windows onto a calendar.
REF_YEAR = 2023
STATUS_COLOR = {"confirmed": "#2a9d8f", "testing": "#e9c46a", "rejected": "#bdbdbd"}
STATUS_ORDER = {"confirmed": 0, "testing": 1, "rejected": 2}
MONTH_STARTS = [pd.Timestamp(REF_YEAR, m, 1).dayofyear for m in range(1, 13)]
MONTH_LABELS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def load_edges() -> list[dict]:
    with open(REGISTRY, encoding="utf-8") as fh:
        return yaml.safe_load(fh)["edges"]


def active_doys(edge: dict) -> list[int]:
    """Day-of-year indices (1..365) this edge is active in the reference year."""
    idx = pd.date_range(f"{REF_YEAR}-01-01", f"{REF_YEAR}-12-31", freq="D")
    sig = leg_signal(idx, edge)
    return [d.dayofyear for d, v in zip(idx, sig.values) if v > 0]


def contiguous_runs(doys: list[int]) -> list[tuple[int, int]]:
    """Collapse sorted day-of-year list into (start, width) spans for broken_barh."""
    if not doys:
        return []
    doys = sorted(set(doys))
    runs, start, prev = [], doys[0], doys[0]
    for d in doys[1:]:
        if d == prev + 1:
            prev = d
            continue
        runs.append((start, prev - start + 1))
        start = prev = d
    runs.append((start, prev - start + 1))
    return runs


def main() -> None:
    edges = load_edges()
    edges.sort(key=lambda e: (STATUS_ORDER.get(e["status"], 9), e["id"]))

    fig, ax = plt.subplots(figsize=(13, 0.5 * len(edges) + 2))
    ylabels = []
    for row, edge in enumerate(edges):
        runs = contiguous_runs(active_doys(edge))
        color = STATUS_COLOR.get(edge["status"], "#999999")
        hatch = "//" if edge["kind"] == "cny" else None
        ax.broken_barh(runs, (row - 0.4, 0.8), facecolors=color, edgecolor="white",
                       hatch=hatch, linewidth=0.5)
        tradeable = "" if edge.get("overlay") else "  (nicht im Overlay)"
        ylabels.append(f"{edge['id']} {edge['name']} [{edge['ticker']}]{tradeable}")

    ax.set_yticks(range(len(edges)))
    ax.set_yticklabels(ylabels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xticks(MONTH_STARTS)
    ax.set_xticklabels(MONTH_LABELS)
    ax.set_xlim(1, 366)
    for ms in MONTH_STARTS:
        ax.axvline(ms, color="#eeeeee", linewidth=0.8, zorder=0)
    ax.set_title("Saisonaler Kalender — Abdeckung je Edge (Farbe = Status)",
                 fontsize=13, fontweight="bold")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in STATUS_COLOR.values()]
    ax.legend(handles, [f"{s}" for s in STATUS_COLOR], loc="lower right",
              ncol=3, fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(OUT, dpi=130)
    print(f"  coverage plot -> {OUT}")

    # --- Month coverage table -------------------------------------------------
    print("\n  Monatsabdeckung (nur tradeable: confirmed/testing mit overlay=true):")
    for m in range(1, 12 + 1):
        idx = pd.date_range(f"{REF_YEAR}-{m:02d}-01", periods=28, freq="D")
        confirmed, testing = [], []
        for edge in edges:
            if not edge.get("overlay"):
                continue
            doys = set(active_doys(edge))
            if any(d.dayofyear in doys for d in idx):
                (confirmed if edge["status"] == "confirmed" else
                 testing if edge["status"] == "testing" else []).append(edge["name"])
        tag = ", ".join(confirmed) or "—"
        ttag = (" | testing: " + ", ".join(testing)) if testing else ""
        print(f"    {MONTH_LABELS[m-1]}: {tag}{ttag}")


if __name__ == "__main__":
    main()
