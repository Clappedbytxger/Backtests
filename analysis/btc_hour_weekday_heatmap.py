"""Bitcoin average return heatmap: hour of day (UTC) x weekday.

Loads the cached Binance BTC/USDT 1h series and builds a 7x24 grid of the mean
close-to-close return (in basis points) for each (weekday, hour) cell. A diverging
colormap centered at zero shows up-drift (green) vs down-drift (red) cells.

Caveat: with ~76,977 bars spread over 168 cells there are only ~460 observations
per cell, so individual cells are noisy. The accompanying ``_significant`` grid
marks cells whose mean is 95%-distinguishable from zero (|mean| > 1.96*SE); expect
very few. This is exploratory intraday-seasonality, gross of costs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantlab.crypto_data import get_crypto_ohlcv  # noqa: E402

OUT_DIR = ROOT / "analysis" / "plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def main() -> None:
    df = get_crypto_ohlcv("BTC/USDT", timeframe="1h")

    ret = (df["Close"].pct_change() * 1e4).rename("bps")  # basis points
    g = pd.DataFrame({"bps": ret, "wd": df.index.weekday, "hr": df.index.hour}).dropna()

    mean = g.groupby(["wd", "hr"])["bps"].mean().unstack("hr")
    std = g.groupby(["wd", "hr"])["bps"].std(ddof=1).unstack("hr")
    n = g.groupby(["wd", "hr"])["bps"].count().unstack("hr")
    sem = std / np.sqrt(n)
    significant = mean.abs() > 1.96 * sem

    mean = mean.reindex(range(7)); significant = significant.reindex(range(7))

    print(f"sample: {df.index[0].date()} .. {df.index[-1].date()}  ({len(df):,} bars, "
          f"~{int(n.values.mean())} obs/cell)")
    print(f"hottest cell: {DAYS[int(np.unravel_index(mean.values.argmax(), mean.shape)[0])]} "
          f"{mean.values.argmax() % 24:02d} UTC  ({mean.values.max():+.2f} bps)")
    print(f"coldest cell: {DAYS[int(np.unravel_index(mean.values.argmin(), mean.shape)[0])]} "
          f"{mean.values.argmin() % 24:02d} UTC  ({mean.values.min():+.2f} bps)")
    print(f"95%-significant cells: {int(significant.values.sum())} of 168")

    vmax = float(np.nanpercentile(np.abs(mean.values), 98))  # robust symmetric scale
    fig, ax = plt.subplots(figsize=(15, 5.5))
    im = ax.imshow(mean.values, cmap="RdYlGn", aspect="auto", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(24), [f"{h:02d}" for h in range(24)])
    ax.set_yticks(range(7), DAYS)
    ax.set_xlabel("Stunde des Tages (UTC)")
    ax.set_ylabel("Wochentag")
    ax.set_title("Bitcoin — Ø Rendite (bps) je Stunde × Wochentag (1h, Binance "
                 f"{df.index[0].date()}–{df.index[-1].date()})")
    # Mark statistically significant cells with a dot.
    ys, xs = np.where(significant.fillna(False).values)
    ax.scatter(xs, ys, s=18, c="black", marker="o", linewidths=0)
    cbar = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.01)
    cbar.set_label("Ø Rendite (Basispunkte)")
    fig.subplots_adjust(bottom=0.26)
    fig.text(0.5, 0.03,
             "Jede Zelle = mittlere stündliche Close-to-Close-Rendite für diese "
             "Stunde an diesem Wochentag (UTC), in Basispunkten. Grün = Aufwärts-, "
             "rot = Abwärts-Drift. Schwarze Punkte = Zelle 95%-signifikant von null "
             "verschieden (sehr wenige → meiste Zellen sind Rauschen). Brutto, ohne Kosten.",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444", wrap=True)

    out = OUT_DIR / "btc_hour_weekday_heatmap.png"
    fig.savefig(out, dpi=130)
    mean.round(3).to_csv(OUT_DIR / "btc_hour_weekday_mean_bps.csv")
    print(f"\n  saved -> {out}")


if __name__ == "__main__":
    main()
