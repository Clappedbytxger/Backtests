"""Test: short Bitcoin just before 10:00 UTC, vary the holding period.

Strategy: every day, enter SHORT at the open of the 10:00-UTC hourly bar
(the price at 10:00:00 UTC), then exit ``h`` hours later. We sweep the holding
period h = 1..24 hours and ask how the per-trade return behaves for each h.

Data: cached Binance BTC/USDT 1h (UTC, bar timestamp = bar start). Window:
last 5 years up to the cache end.

Notes / scrutiny (per project hard rules):
  - Decision-time execution: we enter and exit at the *open* of the relevant
    hourly bar, so no look-ahead (the 10:00 open is known at 10:00).
  - Costs modeled: crypto round-trip wall (CFD_CRYPTO ~20 bps RT) plus the
    lighter Binance-spot taker (~12 bps RT) for context. Gross shown too.
  - This is a single-market intraday DIRECTIONAL bet — historically the
    cost wall kills these (catalog 0012-0015/0039-0041). Treat as exploratory.
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

ENTRY_HOUR_UTC = 10
MAX_HOLD = 24
YEARS = 5

# Round-trip cost assumptions (basis points), modeled on the exit.
COST_CFD_RT_BPS = 20.0   # project crypto CFD wall (memory: CFD_CRYPTO 20 bps RT)
COST_SPOT_RT_BPS = 12.0  # Binance spot taker ~6 bps/side


def build_trades(open_px: pd.Series, hold: int) -> pd.Series:
    """Per-day SHORT return for a given holding period (in hours).

    Enter at the 10:00-UTC open, exit ``hold`` hours later at that bar's open.
    Short return = -(exit/entry - 1). Indexed by entry timestamp.
    """
    entries = open_px[open_px.index.hour == ENTRY_HOUR_UTC]
    exit_ts = entries.index + pd.Timedelta(hours=hold)
    exit_px = open_px.reindex(exit_ts)  # NaN where the exit bar is missing
    long_ret = exit_px.values / entries.values - 1.0
    short_ret = -long_ret
    s = pd.Series(short_ret, index=entries.index)
    return s.dropna()


def main() -> None:
    df = get_crypto_ohlcv("BTC/USDT", timeframe="1h")
    open_px = df["Open"]

    end = open_px.index[-1]
    start = end - pd.DateOffset(years=YEARS)
    open_px = open_px[open_px.index >= start]
    print(f"Window: {open_px.index[0]}  ->  {open_px.index[-1]}  "
          f"({len(open_px):,} hourly bars)")

    holds = list(range(1, MAX_HOLD + 1))
    rows = []
    curves: dict[int, pd.Series] = {}
    for h in holds:
        tr = build_trades(open_px, h)
        n = len(tr)
        mean = tr.mean()
        sem = tr.std(ddof=1) / np.sqrt(n)
        # net per-trade (subtract round-trip cost as a fraction)
        net_cfd = mean - COST_CFD_RT_BPS / 1e4
        net_spot = mean - COST_SPOT_RT_BPS / 1e4
        sharpe = mean / tr.std(ddof=1) * np.sqrt(365 * 24 / h)  # annualized, per-trade freq
        rows.append({
            "hold_h": h,
            "n_trades": n,
            "mean_bps": mean * 1e4,
            "ci95_bps": 1.96 * sem * 1e4,
            "t_stat": mean / sem,
            "win_rate": (tr > 0).mean(),
            "net_spot_bps": net_spot * 1e4,
            "net_cfd_bps": net_cfd * 1e4,
            "ann_sharpe_gross": sharpe,
            "total_gross_pct": ((1 + tr).prod() - 1) * 100,
            "total_net_cfd_pct": ((1 + tr - COST_CFD_RT_BPS / 1e4).prod() - 1) * 100,
        })
        curves[h] = (1 + tr).cumprod()

    table = pd.DataFrame(rows).set_index("hold_h")
    pd.set_option("display.width", 200)
    print("\n" + table.round(3).to_string())
    table.to_csv(OUT_DIR / "btc_short_10utc_table.csv")

    # ---- Figure 1: mean short return per trade vs holding period (with 95% CI)
    fig, ax = plt.subplots(figsize=(12, 6))
    m = table["mean_bps"].values
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in m]
    ax.bar(holds, m, yerr=table["ci95_bps"].values, color=colors,
           edgecolor="white", linewidth=0.6, capsize=3,
           error_kw={"elinewidth": 1.0, "ecolor": "#444"})
    ax.axhline(0, color="#333", linewidth=0.9)
    ax.set_xticks(holds)
    ax.set_xlabel("Haltedauer (Stunden)")
    ax.set_ylabel("Ø Short-Rendite pro Trade (Basispunkte, brutto)")
    ax.set_title(f"BTC Short ab 10:00 UTC — Ø-Rendite je Haltedauer "
                 f"({open_px.index[0].date()}–{open_px.index[-1].date()})")
    fig.subplots_adjust(bottom=0.24)
    fig.text(0.5, 0.02,
             "Balken = mittlere Short-Rendite pro Trade je Haltedauer in Basispunkten "
             "(1 bp = 0,01%), brutto. Grün positiv, rot negativ. Fehlerbalken = 95%-"
             "Konfidenzintervall (±1,96·SE): reicht er über die Null, ist der Effekt NICHT "
             "signifikant. Kosten (~12 bps Spot / 20 bps CFD pro Roundtrip) sind NICHT "
             "abgezogen — siehe Tabelle für netto.",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444", wrap=True)
    out1 = OUT_DIR / "btc_short_10utc_mean_per_hold.png"
    fig.savefig(out1, dpi=130)

    # ---- Figure 2: cumulative equity curves for a selection of holding periods
    fig, ax = plt.subplots(figsize=(12, 6))
    sel = [1, 2, 4, 6, 8, 12, 24]
    cmap = plt.cm.viridis(np.linspace(0, 0.92, len(sel)))
    for c, h in zip(cmap, sel):
        ax.plot(curves[h].index, curves[h].values, color=c, linewidth=1.3, label=f"{h}h")
    ax.axhline(1.0, color="#333", linewidth=0.8, linestyle="--")
    ax.set_ylabel("Kapitalkurve (Start = 1,0; brutto, ohne Kosten)")
    ax.set_xlabel("Datum")
    ax.set_title("BTC Short ab 10:00 UTC — Kapitalkurve je Haltedauer (brutto)")
    ax.legend(title="Haltedauer", ncol=4, fontsize=9)
    fig.subplots_adjust(bottom=0.18)
    fig.text(0.5, 0.02,
             "Jede Linie = kumulierte (verzinste) tägliche Short-Rendite für eine feste "
             "Haltedauer, brutto. 1 Trade/Tag. Werte über 1,0 = Gewinn, unter 1,0 = Verlust. "
             "Kosten würden jede Linie spürbar nach unten drücken (~1 Trade/Tag × Roundtrip).",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444", wrap=True)
    out2 = OUT_DIR / "btc_short_10utc_equity_curves.png"
    fig.savefig(out2, dpi=130)

    # ---- Figure 3: total return per holding period, gross vs net
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.array(holds)
    w = 0.4
    ax.bar(x - w / 2, table["total_gross_pct"].values, w, label="brutto", color="#1f77b4")
    ax.bar(x + w / 2, table["total_net_cfd_pct"].values, w, label="netto (20 bps RT)",
           color="#ff7f0e")
    ax.axhline(0, color="#333", linewidth=0.9)
    ax.set_xticks(holds)
    ax.set_xlabel("Haltedauer (Stunden)")
    ax.set_ylabel(f"Gesamtrendite über {YEARS} Jahre (%)")
    ax.set_title(f"BTC Short ab 10:00 UTC — Gesamtrendite je Haltedauer (brutto vs netto)")
    ax.legend()
    fig.subplots_adjust(bottom=0.16)
    fig.text(0.5, 0.02,
             "Blau = Brutto-Gesamtrendite (verzinst) über das 5-Jahres-Fenster je Haltedauer. "
             "Orange = nach 20 bps Roundtrip-Kosten je Trade (Krypto-CFD-Wand). Die Lücke ist "
             "der Kosten-Drag von ~1 Trade/Tag.",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444", wrap=True)
    out3 = OUT_DIR / "btc_short_10utc_total_return.png"
    fig.savefig(out3, dpi=130)

    print(f"\nsaved -> {out1}")
    print(f"saved -> {out2}")
    print(f"saved -> {out3}")

    best = table["mean_bps"].idxmax()
    worst = table["mean_bps"].idxmin()
    print(f"\nbest hold (gross mean):  {best}h  ({table.loc[best,'mean_bps']:+.2f} bps/trade, "
          f"t={table.loc[best,'t_stat']:+.2f})")
    print(f"worst hold (gross mean): {worst}h  ({table.loc[worst,'mean_bps']:+.2f} bps/trade, "
          f"t={table.loc[worst,'t_stat']:+.2f})")
    sig = table[table["mean_bps"].abs() > table["ci95_bps"]]
    print(f"holds with mean 95%-distinguishable from 0: "
          f"{list(sig.index) if len(sig) else 'NONE'}")


if __name__ == "__main__":
    main()
