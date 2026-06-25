"""Test the "Jane Street 10am dump" claim: short BTC at 10:00 US-Eastern, 2026 YTD.

Narrative (researched 2026-06): traders alleged Jane Street sold spot BTC at the
US market open (~10:00 AM ET) to slam the price daily, running ~Nov 2025 to late
Feb 2026, then "disappearing" after the Feb 2026 lawsuit headlines. Analysts
(e.g. Alex Kruger) dispute any consistent 10am effect.

So the correct entry is 10:00 *Eastern Time* (DST-aware: 14:00 UTC in summer,
15:00 UTC in winter), NOT 10:00 UTC. We test "this year" = 2026 YTD and split it
into the alleged-active window (Jan-Feb) vs the faded window (Mar-Jun).

Data: cached Binance BTC/USDT 1h (UTC). Decision-time execution at bar opens.
Costs noted but the headline plots are gross (small sample, exploratory).
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

ENTRY_HOUR_ET = 10
MAX_HOLD = 24
COST_RT_BPS = 12.0  # Binance spot taker ~6 bps/side round trip


def build_short_trades(open_et: pd.Series, hold: int) -> pd.Series:
    """Per-day SHORT return entering at 10:00 ET, exiting `hold` hours later."""
    entries = open_et[open_et.index.hour == ENTRY_HOUR_ET]
    exit_ts = entries.index + pd.Timedelta(hours=hold)
    exit_px = open_et.reindex(exit_ts)
    short_ret = -(exit_px.values / entries.values - 1.0)
    return pd.Series(short_ret, index=entries.index).dropna()


def summarize(open_et: pd.Series, label: str) -> pd.DataFrame:
    rows = []
    for h in range(1, MAX_HOLD + 1):
        tr = build_short_trades(open_et, h)
        n = len(tr)
        if n < 5:
            continue
        mean = tr.mean()
        sem = tr.std(ddof=1) / np.sqrt(n)
        rows.append({
            "hold_h": h, "n": n,
            "mean_bps": mean * 1e4,
            "ci95_bps": 1.96 * sem * 1e4,
            "t_stat": mean / sem,
            "win_rate": (tr > 0).mean(),
            "net_bps": (mean - COST_RT_BPS / 1e4) * 1e4,
            "total_gross_pct": ((1 + tr).prod() - 1) * 100,
        })
    df = pd.DataFrame(rows).set_index("hold_h")
    print(f"\n=== {label} (n={df['n'].iloc[0]} trades/hold) ===")
    print(df.round(3).to_string())
    return df


def main() -> None:
    df = get_crypto_ohlcv("BTC/USDT", timeframe="1h")
    open_et = df["Open"].copy()
    open_et.index = open_et.index.tz_convert("US/Eastern")  # DST-aware ET

    end = df.index[-1]  # 2026-06-03 in UTC
    ytd = open_et[open_et.index >= pd.Timestamp("2026-01-01", tz="US/Eastern")]
    print(f"2026 YTD window: {ytd.index[0]}  ->  {ytd.index[-1]}  ({len(ytd):,} bars)")

    # Sub-periods of the narrative
    active = ytd[ytd.index < pd.Timestamp("2026-03-01", tz="US/Eastern")]   # Jan-Feb
    faded = ytd[ytd.index >= pd.Timestamp("2026-03-01", tz="US/Eastern")]   # Mar-Jun

    t_ytd = summarize(ytd, "2026 YTD — short 10:00 ET")
    t_active = summarize(active, "Jan-Feb 2026 (alleged ACTIVE)")
    t_faded = summarize(faded, "Mar-Jun 2026 (alleged FADED)")
    t_ytd.to_csv(OUT_DIR / "btc_short_10et_2026_table.csv")

    # ---- Figure 1: mean short return per holding period, 2026 YTD, with CI
    fig, ax = plt.subplots(figsize=(12, 6))
    m, ci = t_ytd["mean_bps"].values, t_ytd["ci95_bps"].values
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in m]
    ax.bar(t_ytd.index, m, yerr=ci, color=colors, edgecolor="white", linewidth=0.6,
           capsize=3, error_kw={"elinewidth": 1.0, "ecolor": "#444"})
    ax.axhline(0, color="#333", linewidth=0.9)
    ax.set_xticks(list(t_ytd.index))
    ax.set_xlabel("Haltedauer (Stunden)")
    ax.set_ylabel("Ø Short-Rendite pro Trade (Basispunkte, brutto)")
    ax.set_title("BTC Short ab 10:00 ET (US-Open) — Ø-Rendite je Haltedauer, 2026 YTD")
    fig.subplots_adjust(bottom=0.22)
    fig.text(0.5, 0.02,
             "Test der „Jane-Street-10-Uhr-Dump\"-These: Short zum US-Börsenopen (10:00 "
             "Ostküstenzeit, DST-korrekt). Positiv = der Dump existiert (Short verdient). "
             "Fehlerbalken = 95%-KI: über der Null = NICHT signifikant. n≈106 Trades (5 Monate). "
             "Brutto, ohne Kosten.",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444", wrap=True)
    out1 = OUT_DIR / "btc_short_10et_2026_mean_per_hold.png"
    fig.savefig(out1, dpi=130)

    # ---- Figure 2: Jan-Feb (active) vs Mar-Jun (faded), mean per hold
    fig, ax = plt.subplots(figsize=(12, 6))
    idx = t_active.index
    w = 0.4
    ax.bar(np.array(idx) - w / 2, t_active["mean_bps"].values, w,
           label="Jan–Feb (angeblich aktiv)", color="#d62728")
    ax.bar(np.array(t_faded.index) + w / 2, t_faded["mean_bps"].values, w,
           label="Mär–Jun (angeblich verschwunden)", color="#7f7f7f")
    ax.axhline(0, color="#333", linewidth=0.9)
    ax.set_xticks(list(idx))
    ax.set_xlabel("Haltedauer (Stunden)")
    ax.set_ylabel("Ø Short-Rendite pro Trade (Basispunkte, brutto)")
    ax.set_title("BTC Short ab 10:00 ET — angeblich aktive vs. verschwundene Phase 2026")
    ax.legend()
    fig.subplots_adjust(bottom=0.18)
    fig.text(0.5, 0.02,
             "Die These behauptet: Jan–Feb war der Dump aktiv (rot sollte positiv sein), nach "
             "den Klage-Schlagzeilen Ende Feb verschwunden (grau ~null). Je ~40 bzw. ~66 Trades "
             "je Balken — kleine Stichprobe.",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444", wrap=True)
    out2 = OUT_DIR / "btc_short_10et_2026_active_vs_faded.png"
    fig.savefig(out2, dpi=130)

    # ---- Figure 3: average BTC hourly return by hour-of-day (ET), 2026 YTD
    ret = (df["Close"].pct_change() * 1e4)
    ret_et = ret.copy()
    ret_et.index = ret.index.tz_convert("US/Eastern")
    ret_et = ret_et[ret_et.index >= pd.Timestamp("2026-01-01", tz="US/Eastern")]
    by_hour = ret_et.groupby(ret_et.index.hour)
    mean_h = by_hour.mean()
    ci_h = 1.96 * by_hour.std(ddof=1) / np.sqrt(by_hour.count())
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#2ca02c" if v >= 0 else "#d62728" for v in mean_h.values]
    ax.bar(mean_h.index, mean_h.values, yerr=ci_h.values, color=colors,
           edgecolor="white", linewidth=0.6, capsize=3,
           error_kw={"elinewidth": 1.0, "ecolor": "#444"})
    ax.axhline(0, color="#333", linewidth=0.9)
    ax.axvspan(9.5, 10.5, color="#ffd700", alpha=0.25, zorder=0)  # highlight 10 ET
    ax.set_xticks(range(24))
    ax.set_xlabel("Stunde des Tages (US-Ostküstenzeit, ET)")
    ax.set_ylabel("Ø stündliche Rendite (Basispunkte)")
    ax.set_title("BTC — Ø Rendite je Tagesstunde (ET), 2026 YTD  [gelb = 10:00-Stunde]")
    fig.subplots_adjust(bottom=0.2)
    fig.text(0.5, 0.02,
             "Zeigt direkt, ob die 10:00-ET-Stunde (gelb) einen abnormalen Abverkauf hat. "
             "Stark negativer gelber Balken mit Fehlerbalken unter null = Beleg für den „10-Uhr-"
             "Dump\". Brutto.",
             ha="center", va="bottom", fontsize=8.5, style="italic", color="#444", wrap=True)
    out3 = OUT_DIR / "btc_hourly_return_et_2026.png"
    fig.savefig(out3, dpi=130)

    print(f"\nsaved -> {out1}\nsaved -> {out2}\nsaved -> {out3}")
    print(f"\n10:00-ET hour mean (2026): {mean_h.get(10, float('nan')):+.2f} bps "
          f"(CI ±{ci_h.get(10, float('nan')):.2f})")
    print(f"worst hour ET: {mean_h.idxmin():02d}:00 ({mean_h.min():+.2f} bps), "
          f"best hour ET: {mean_h.idxmax():02d}:00 ({mean_h.max():+.2f} bps)")


if __name__ == "__main__":
    main()
