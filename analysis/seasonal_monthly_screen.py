"""Average monthly return screen across the open seasonal-candidate universe.

Pre-strategy reconnaissance (no backtest yet): for each candidate future from the
seasonal-candidate queue, screen data quality (lessons 0005 non-positive close /
0025 frozen feed), then compute the *average calendar-month return* and its hit
rate. Output a heatmap so a window hypothesis can be grounded in the data before
the user supplies the exact Seasonax window.

Focus per project decision: drift-light commodity futures with a hard supply/
demand story (the only class that has passed the permutation test so far).

Run:
    .venv/Scripts/python.exe analysis/seasonal_monthly_screen.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.data import get_prices  # noqa: E402

PLOTS = Path(__file__).resolve().parent / "plots"
START = "2000-01-01"

# Candidate universe from the seasonal-candidate queue (drift-light + supply story).
CANDIDATES = {
    "SB=F": "Zucker (Sugar #11)",
    "NG=F": "Erdgas (Natural Gas)",
    "CT=F": "Baumwolle (Cotton)",
    "ZC=F": "Mais (Corn)",
    "ZS=F": "Sojabohnen (Soybeans)",
    "ZW=F": "Weizen (Wheat)",
    "LE=F": "Lebendrind (Live Cattle)",
    "HE=F": "Magerschwein (Lean Hogs)",
    "PA=F": "Palladium",
    "SI=F": "Silber (Silver)",
    "HO=F": "Heizöl (Heating Oil)",
}

MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
          "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def screen_quality(ticker: str, close: pd.Series) -> tuple[bool, str]:
    """Apply the 0005 (non-positive) and 0025 (frozen feed) guards."""
    if (close <= 0).any():
        return False, "non-positive close (0005)"
    per_year = close.groupby(close.index.year).nunique()
    if int(per_year.min()) < 50:
        bad = per_year.idxmin()
        return False, f"frozen feed: {int(per_year.min())} distinct closes in {bad} (0025)"
    zero_frac = (close.pct_change() == 0).mean()
    if zero_frac > 0.25:
        return False, f"{zero_frac:.0%} zero-return days (stale feed, 0025)"
    return True, f"ok ({per_year.index.min()}-{per_year.index.max()}, {len(close)} days)"


def monthly_mean(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Average *calendar-month* total return and hit rate per month.

    Build month-end-to-month-end returns, then average across years per month.
    """
    monthly = close.resample("ME").last()
    mret = monthly.pct_change().dropna()
    by_month = mret.groupby(mret.index.month)
    mean_pct = by_month.mean() * 100.0
    hit = by_month.apply(lambda s: (s > 0).mean()) * 100.0
    return mean_pct.reindex(range(1, 13)), hit.reindex(range(1, 13))


def main() -> None:
    PLOTS.mkdir(parents=True, exist_ok=True)
    print("Seasonal monthly screen — open candidate universe\n")

    labels, mean_rows, hit_rows = [], [], []
    for ticker, name in CANDIDATES.items():
        try:
            close = get_prices(ticker, start=START)["Close"]
        except Exception as exc:  # noqa: BLE001
            print(f"  {ticker:6s} {name:28s} SKIP — no data ({exc})")
            continue
        ok, msg = screen_quality(ticker, close)
        flag = "OK  " if ok else "DROP"
        print(f"  [{flag}] {ticker:6s} {name:28s} {msg}")
        if not ok:
            continue
        mean_pct, hit = monthly_mean(close)
        labels.append(f"{name}\n{ticker}")
        mean_rows.append(mean_pct.values)
        hit_rows.append(hit.values)

    mean_mat = np.array(mean_rows, dtype=float)
    hit_mat = np.array(hit_rows, dtype=float)

    # --- Heatmap: average monthly return -----------------------------------
    fig, ax = plt.subplots(figsize=(13, 0.7 * len(labels) + 2.5))
    vmax = np.nanmax(np.abs(mean_mat))
    im = ax.imshow(mean_mat, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(12))
    ax.set_xticklabels(MONTHS)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    for i in range(len(labels)):
        for j in range(12):
            v = mean_mat[i, j]
            ax.text(j, i, f"{v:+.1f}", ha="center", va="center",
                    fontsize=7, color="black")
    fig.colorbar(im, ax=ax, label="Ø Monatsrendite (%)", shrink=0.8)
    ax.set_title("Ø Monatsrendite — saisonales Kandidaten-Universum "
                 f"(seit {START[:4]}, netto Monat→Monat)",
                 fontsize=13, fontweight="bold")
    fig.text(0.5, 0.01,
             "Durchschnittliche Kalendermonats-Gesamtrendite je Future (grün = positiv). "
             "Reine Rohdaten-Aufklärung, keine Kosten/kein Backtest — dient nur dazu, "
             "ein Fenster zu begründen, bevor der exakte Seasonax-Bereich getestet wird. "
             "Drift-Fallen-Vorsicht (Lehre 0017): bei Drift-Assets sind viele Monate grün.",
             ha="center", fontsize=8, style="italic", wrap=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = PLOTS / "seasonal_monthly_returns.png"
    fig.savefig(out, dpi=130)
    print(f"\n  heatmap -> {out}")

    # --- Console: top 2 months per asset -----------------------------------
    print("\n  Stärkste Monate je Asset (Ø-Rendite | Trefferquote):")
    for i, lab in enumerate(labels):
        name = lab.split("\n")[0]
        order = np.argsort(mean_mat[i])[::-1][:2]
        bits = [f"{MONTHS[j]} {mean_mat[i, j]:+.1f}% ({hit_mat[i, j]:.0f}%)" for j in order]
        print(f"    {name:28s} {'  ;  '.join(bits)}")


if __name__ == "__main__":
    main()
