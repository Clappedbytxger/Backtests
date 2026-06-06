"""Average Bitcoin volatility per hour of day (UTC).

Loads the cached Binance BTC/USDT 1h series and, for each of the 24 hours of the
day, measures how volatile that hour typically is. Two complementary measures:

  * return volatility  = std of hourly log returns within that hour bucket (%)
  * typical range      = mean of (High-Low)/Open within that hour bucket (%)

Both are intraday-seasonality views: they reveal which hours move most, which is
the foundation for any time-of-day intraday strategy.
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

    log_ret = np.log(df["Close"]).diff()
    hour = df.index.hour

    ret_vol = log_ret.groupby(hour).std() * 100.0          # % std of hourly returns
    rng = ((df["High"] - df["Low"]) / df["Open"]).groupby(hour).mean() * 100.0  # % range

    table = pd.DataFrame({"return_vol_pct": ret_vol, "range_pct": rng})
    table.index.name = "hour_utc"
    print(table.round(3).to_string())
    print(f"\n  busiest hour (return vol): {ret_vol.idxmax():02d}:00 UTC ({ret_vol.max():.3f}%)")
    print(f"  calmest hour (return vol): {ret_vol.idxmin():02d}:00 UTC ({ret_vol.min():.3f}%)")

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = plt.cm.viridis((ret_vol - ret_vol.min()) / (ret_vol.max() - ret_vol.min()))
    ax.bar(ret_vol.index, ret_vol.values, color=colors, edgecolor="white", linewidth=0.6)
    ax.plot(rng.index, rng.values, color="#d62728", marker="o", linewidth=1.6,
            label="Ø Spanne (High-Low)/Open")
    ax.set_xticks(range(24))
    ax.set_xlabel("Stunde des Tages (UTC)")
    ax.set_ylabel("Volatilität (%)")
    ax.set_title("Bitcoin — durchschnittliche Volatilität pro Stunde (1h, Binance "
                 f"{df.index[0].date()}–{df.index[-1].date()})")
    ax.legend(loc="upper left")
    fig.subplots_adjust(bottom=0.24)
    fig.text(0.5, 0.02,
             "Balken = Standardabweichung der stündlichen Log-Renditen je Tagesstunde (UTC). "
             "Rote Linie = mittlere prozentuale Kerzen-Spanne. Höhere Werte = bewegtere Stunde. "
             "US-Handelsstart (~13–15 UTC) und Asien-Open sind typische Aktivitäts-Cluster.",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444444", wrap=True)

    out = OUT_DIR / "btc_hourly_volatility.png"
    fig.savefig(out, dpi=130)
    print(f"\n  saved -> {out}")


if __name__ == "__main__":
    main()
