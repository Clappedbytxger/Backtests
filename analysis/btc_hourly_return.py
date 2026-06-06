"""Average Bitcoin return per hour of day (UTC).

Loads the cached Binance BTC/USDT 1h series and, for each of the 24 hours of the
day, measures the *average* return of that hour (close-to-close), in basis points.

Unlike volatility (which hours MOVE most), this asks which hours DRIFT up or down
on average. A 95% confidence band (1.96 x standard error) shows which hours are
statistically distinguishable from zero — most are not; intraday drift is weak and
mostly noise, so the band is the important part of the picture.
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


def main() -> None:
    df = get_crypto_ohlcv("BTC/USDT", timeframe="1h")

    ret = df["Close"].pct_change() * 1e4  # hourly return in basis points
    hour = df.index.hour

    grp = ret.groupby(hour)
    mean_bps = grp.mean()
    sem_bps = grp.std(ddof=1) / np.sqrt(grp.count())  # standard error of the mean
    ci95 = 1.96 * sem_bps

    table = pd.DataFrame({
        "mean_return_bps": mean_bps,
        "std_bps": grp.std(ddof=1),
        "n": grp.count(),
        "ci95_bps": ci95,
        "significant": mean_bps.abs() > ci95,  # mean distinguishable from 0?
    })
    table.index.name = "hour_utc"
    print(table.round(3).to_string())
    sig = table[table["significant"]]
    print(f"\n  sample: {df.index[0].date()} .. {df.index[-1].date()}  "
          f"({len(df):,} hourly bars)")
    print(f"  best hour:  {mean_bps.idxmax():02d}:00 UTC ({mean_bps.max():+.3f} bps)")
    print(f"  worst hour: {mean_bps.idxmin():02d}:00 UTC ({mean_bps.min():+.3f} bps)")
    print(f"  hours whose mean is 95%-distinguishable from zero: "
          f"{list(sig.index) if len(sig) else 'NONE'}")
    print(f"  sum of all 24 hourly means: {mean_bps.sum():+.2f} bps "
          f"(= avg daily close-to-close drift)")

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in mean_bps.values]
    ax.bar(mean_bps.index, mean_bps.values, yerr=ci95.values, color=colors,
           edgecolor="white", linewidth=0.6, capsize=3,
           error_kw={"elinewidth": 1.0, "ecolor": "#444"})
    ax.axhline(0, color="#333", linewidth=0.9)
    ax.set_xticks(range(24))
    ax.set_xlabel("Stunde des Tages (UTC)")
    ax.set_ylabel("Ø Rendite (Basispunkte)")
    ax.set_title("Bitcoin — durchschnittliche Rendite pro Stunde (1h, Binance "
                 f"{df.index[0].date()}–{df.index[-1].date()})")
    fig.subplots_adjust(bottom=0.26)
    fig.text(0.5, 0.02,
             "Balken = mittlere stündliche Close-to-Close-Rendite je Tagesstunde (UTC) in "
             "Basispunkten (1 bp = 0,01%). Grün = positiv, rot = negativ. Fehlerbalken = "
             "95%-Konfidenzintervall (±1,96·Standardfehler): reicht er über die Nulllinie, "
             "ist die Stunde NICHT signifikant von null verschieden. Brutto, ohne Kosten.",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444444", wrap=True)

    out = OUT_DIR / "btc_hourly_return.png"
    fig.savefig(out, dpi=130)
    table.to_csv(OUT_DIR / "btc_hourly_return.csv")
    print(f"\n  saved -> {out}")


if __name__ == "__main__":
    main()
