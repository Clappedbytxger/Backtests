"""Strategy 0019 — Platinum turn-of-year: roll-artifact check + earlier exit.

0018 found a strong, permutation-significant (p=0.001), macro-justified platinum
window 18 Dec -> 17 Jan. The open risk: yfinance ``PL=F`` is a *continuous* front
month. Platinum contracts are Jan/Apr/Jul/Oct; the volume roll from the January
into the April contract happens in mid-January — i.e. right at the base window's
exit. Part of the measured edge could be a stitching/roll gap rather than genuine
spot strength.

This script decides whether the edge is real by three independent angles:

  1. **Average seasonal path** — mean cumulative return across the window, aligned
     by trading-day offset from entry. If gains accrue smoothly through *late
     December* (well before any roll), the edge is pre-roll and genuine.
  2. **Per-calendar-day mean return** — does one day in mid-January dominate the
     PnL (roll-gap signature) or is the return spread across the window?
  3. **Earlier-exit variants** — hold from 18 Dec but exit on 17 Jan (base), 13 Jan,
     10 Jan, 5 Jan, 31 Dec, 28 Dec. Each is re-tested for expectancy, win rate and a
     permutation p-value. If the edge survives an exit *before* the mid-Jan roll, the
     roll-artifact hypothesis is rejected and the cleaner early exit is preferable.

Definitive contract-level confirmation needs single-contract data (Norgate/Barchart);
yfinance cannot supply reliable individual platinum contracts, so this is a strong
triangulation, not a contract-by-contract proof — stated honestly in the report.

Run:
    .venv/Scripts/python.exe strategies/0019_platinum_roll_check/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import (  # noqa: E402
    compute_metrics, trade_stats, run_backtest,
    bootstrap_ci, permutation_test,
)
from quantlab.significance import t_test_mean_return  # noqa: E402
from quantlab.costs import IBKR_FUTURES  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab import plotting  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

TICKER = "PL=F"
NAME = "Platin (Platin-Futures)"
START_MD = (12, 18)
COST_MODEL = IBKR_FUTURES

# Exit-date variants (month, day). Base is 17 Jan; the rest exit progressively
# earlier, the last two fully inside December (well before any mid-Jan roll).
EXITS = [(1, 17), (1, 13), (1, 10), (1, 5), (12, 31), (12, 28)]
BASE_EXIT = (1, 17)
# Mid-January is the suspected roll zone for the PL=F continuous series.
ROLL_ZONE_MD = ((1, 13), (1, 20))


def date_window_signal(index, start_md=START_MD, end_md=BASE_EXIT,
                       start_shift=0, end_shift=0, name="platinum_win") -> pd.Series:
    """Long (1.0) from start_md to end_md each winter, else flat.

    The exit year is the start year when (end_md > start_md) — e.g. a December
    exit — and the next year otherwise (a January exit wraps the boundary).
    Decision-time signal; the engine applies the T+1 shift, so no look-ahead.
    """
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    same_year = tuple(end_md) > tuple(start_md)
    for y in range(int(idx.year.min()) - 1, int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *start_md) + pd.Timedelta(days=start_shift)
        end_year = y if same_year else y + 1
        end = pd.Timestamp(end_year, *end_md) + pd.Timedelta(days=end_shift)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(prices: pd.DataFrame, signal: pd.Series) -> dict:
    res = run_backtest(prices, signal, cost_model=COST_MODEL)
    rets = res["returns"]
    return {"metrics": compute_metrics(rets), "trades": trade_stats(res["trades"]),
            "exposure": float(res["position"].abs().mean()),
            "returns": rets, "res": res}


def main() -> None:
    print(f"Strategy 0019 — {NAME} roll-artifact check + earlier exit ({TICKER})")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    prices = get_prices(TICKER, start="2000-01-01")
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{TICKER}: non-positive close — abort (CLAUDE.md 0005).")
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    first_year, last_year = int(prices.index[0].year), int(prices.index[-1].year)
    mid_year = (first_year + last_year) // 2
    split_date = f"{mid_year}-07-01"

    # === 1. Per-winter aligned return paths (base 18 Dec -> 17 Jan) ============
    base_pos = date_window_signal(prices.index, end_md=BASE_EXIT)
    held = base_pos.shift(1).fillna(0.0)          # actually-held (look-ahead safe)
    in_win = held > 0
    # Tag each held day with its winter (start-year) and trading-day offset.
    winter_paths = {}          # start_year -> list of daily net returns in window
    day_cal = {}               # start_year -> list of (month, day)
    cost_frac = COST_MODEL.cost_fraction_per_side(float(prices["Close"].mean()))
    prev = False
    cur_year = None
    for dt, flag in in_win.items():
        if flag:
            if not prev:                          # new winter starts
                cur_year = dt.year if dt.month >= 7 else dt.year - 1
                winter_paths[cur_year] = []
                day_cal[cur_year] = []
            winter_paths[cur_year].append(asset_ret.loc[dt])
            day_cal[cur_year].append((dt.month, dt.day))
        prev = flag

    max_len = max(len(v) for v in winter_paths.values())
    path_mat = np.full((len(winter_paths), max_len), np.nan)
    for i, (_, rets) in enumerate(sorted(winter_paths.items())):
        cum = np.cumprod(1.0 + np.array(rets)) - 1.0
        path_mat[i, :len(cum)] = cum
    mean_path = np.nanmean(path_mat, axis=0) * 100.0   # mean cumulative % by day offset

    # Per-calendar-day mean return (which dates carry the move?)
    cal_rows = []
    for yr, days in day_cal.items():
        for (m, d), r in zip(days, winter_paths[yr]):
            cal_rows.append({"md": f"{m:02d}-{d:02d}", "ret": r})
    cal_df = pd.DataFrame(cal_rows)
    cal_mean = cal_df.groupby("md")["ret"].mean() * 100.0
    cal_mean = cal_mean.sort_index()

    # Largest single-day move per winter — does it cluster in the roll zone?
    big_day_md = []
    for yr, rets in winter_paths.items():
        j = int(np.argmax(np.abs(rets)))
        big_day_md.append(day_cal[yr][j])
    rz_lo, rz_hi = ROLL_ZONE_MD
    in_roll = [(m, d) >= rz_lo and (m, d) <= rz_hi for (m, d) in big_day_md]
    big_in_roll = float(np.mean(in_roll))

    # === 2. Exit-date variants ================================================
    variant_rows = []
    for ex in EXITS:
        sig = date_window_signal(prices.index, end_md=ex)
        e = evaluate(prices, sig)
        rets = e["returns"]
        perm = permutation_test(rets, asset_ret, e["res"]["position"], n_perm=2000)
        boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
        # IS / OOS for this variant
        e_is = evaluate(prices.loc[:split_date], date_window_signal(
            prices.loc[:split_date].index, end_md=ex))
        e_oos = evaluate(prices.loc[split_date:], date_window_signal(
            prices.loc[split_date:].index, end_md=ex))
        variant_rows.append({
            "exit": f"{ex[1]:02d}.{ex[0]:02d}.",
            "n_trades": e["trades"]["n_trades"],
            "win_rate": e["trades"]["win_rate"],
            "expectancy_pct": e["trades"]["expectancy"] * 100.0,
            "avg_hold": e["trades"]["avg_holding_days"],
            "sharpe": e["metrics"]["sharpe"],
            "cagr": e["metrics"]["cagr"],
            "max_dd": e["metrics"]["max_drawdown"],
            "perm_p": perm["p_value"],
            "boot_ci": [boot["ci_low"], boot["ci_high"]],
            "sharpe_is": e_is["metrics"]["sharpe"],
            "sharpe_oos": e_oos["metrics"]["sharpe"],
            "exp_is_pct": e_is["trades"]["expectancy"] * 100.0,
            "exp_oos_pct": e_oos["trades"]["expectancy"] * 100.0,
        })
    var_df = pd.DataFrame(variant_rows)

    # === Plots ================================================================
    import matplotlib.pyplot as plt

    # Plot 1: average seasonal path (cumulative % by trading-day offset).
    fig, ax = plt.subplots(figsize=(11, 5.4))
    x = np.arange(max_len)
    ax.plot(x, mean_path, marker="o", linewidth=1.8, color="#264653")
    ax.axhline(0, color="black", linewidth=0.8)
    # Mark where January typically begins (~9-10 trading days after 18 Dec).
    ax.set_xlabel("Handelstag im Fenster (0 = Einstieg ~18. Dez.)")
    ax.set_ylabel("Ø kumulierte Rendite (%)")
    ax.set_title(f"0019 {NAME} — durchschnittlicher Saison-Pfad im Fenster",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Mittlere kumulierte Rendite über alle Winter, ausgerichtet am Einstiegstag "
        "(~18. Dez.). Steigt die Kurve schon in den ersten ~9 Tagen (= Dezember, VOR "
        "dem Mitte-Januar-Roll), ist der Edge echte Spot-Stärke, kein Roll-Gap. Ein "
        "flacher Verlauf mit spätem Sprung am rechten Rand wäre ein Roll-Artefakt-Verdacht."))
    plotting.savefig(fig, PLOTS / "avg_seasonal_path.png")

    # Plot 2: per-calendar-day mean return.
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = []
    for md in cal_mean.index:
        m, d = int(md[:2]), int(md[3:])
        colors.append("#e9c46a" if (rz_lo <= (m, d) <= rz_hi) else "#2a9d8f")
    ax.bar(range(len(cal_mean)), cal_mean.values, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(range(len(cal_mean)))
    ax.set_xticklabels(cal_mean.index, rotation=90, fontsize=7)
    ax.set_ylabel("Ø Tagesrendite (%)")
    ax.set_title(f"0019 {NAME} — mittlere Rendite je Kalendertag im Fenster",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Durchschnittliche Tagesrendite je Kalenderdatum über alle Winter. Gelb = "
        "vermutete Roll-Zone (13.–20. Jan.). Konzentriert sich der Gewinn auf wenige "
        "gelbe Tage = Roll-Verdacht; ist er über Dezember+Januar verteilt = echt."))
    plotting.savefig(fig, PLOTS / "per_calendar_day.png")

    # Plot 3: edge vs exit date (expectancy + permutation p).
    fig, ax1 = plt.subplots(figsize=(11, 5.4))
    xpos = range(len(var_df))
    bars = ax1.bar(xpos, var_df["expectancy_pct"], color="#2a9d8f", alpha=0.8,
                   label="Expectancy/Trade (%)")
    ax1.set_xticks(list(xpos))
    ax1.set_xticklabels(var_df["exit"])
    ax1.set_xlabel("Ausstiegsdatum (Einstieg konstant ~18. Dez.)")
    ax1.set_ylabel("Expectancy pro Trade (%)", color="#2a9d8f")
    ax1.axhline(0, color="black", linewidth=0.8)
    ax2 = ax1.twinx()
    ax2.plot(list(xpos), var_df["perm_p"], marker="o", color="#e76f51",
             linewidth=1.8, label="Permutation p")
    ax2.axhline(0.05, color="#e76f51", linestyle="--", linewidth=1.0)
    ax2.set_ylabel("Permutationstest p-Wert", color="#e76f51")
    ax2.set_ylim(0, max(0.1, var_df["perm_p"].max() * 1.2))
    ax1.set_title(f"0019 {NAME} — Edge je Ausstiegsdatum (übersteht er einen Exit vor dem Roll?)",
                  fontsize=12, fontweight="bold")
    for i, p in enumerate(var_df["perm_p"]):
        ax2.annotate(f"{p:.3f}", (i, p), textcoords="offset points", xytext=(0, 7),
                     ha="center", fontsize=7, color="#e76f51")
    plotting._add_caption(fig, (
        "Grüne Balken: Netto-Expectancy/Trade je Exit. Rote Linie: Permutations-p "
        "(gestrichelt = 5%). Die rechten zwei Exits (31.12./28.12.) liegen komplett VOR "
        "dem Roll. Bleiben Expectancy hoch und p<0,05 auch dort, ist der Edge kein "
        "Roll-Artefakt."))
    plotting.savefig(fig, PLOTS / "edge_vs_exit.png")

    # === Persist ==============================================================
    summary = {
        "ticker": TICKER, "start_md": list(START_MD),
        "roll_zone": [list(rz_lo), list(rz_hi)],
        "largest_day_in_roll_zone_share": big_in_roll,
        "n_winters": len(winter_paths),
        "avg_path_pct_by_dayoffset": mean_path.tolist(),
        "variants": var_df.to_dict(orient="records"),
        "sample": {"first_year": first_year, "last_year": last_year,
                   "split_date": split_date},
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    var_df.to_csv(RESULTS / "exit_variants.csv", index=False)
    cal_mean.rename("mean_ret_pct").to_csv(RESULTS / "per_calendar_day.csv")

    # === Console ==============================================================
    print(f"\n  Winters: {len(winter_paths)}  ({first_year}-{last_year})")
    print(f"  Roll zone (suspected): {rz_lo[1]:02d}.{rz_lo[0]:02d}. - {rz_hi[1]:02d}.{rz_hi[0]:02d}.")
    print(f"  Share of winters whose LARGEST move falls in the roll zone: {big_in_roll:.0%}")
    print(f"  Avg cumulative return by day ~9 (end of December): "
          f"{mean_path[min(8, max_len-1)]:.2f}%  | full window: {mean_path[-1]:.2f}%\n")
    print("  Exit-date variants (entry ~18 Dec; net after costs):")
    print(f"    {'exit':>7} {'n':>3} {'win':>5} {'exp%':>7} {'hold':>5} "
          f"{'Sharpe':>7} {'perm_p':>7} {'expIS%':>7} {'expOOS%':>8}")
    for _, r in var_df.iterrows():
        flag = "  <-- pre-roll" if r["exit"] in ("31.12.", "28.12.") else ""
        print(f"    {r['exit']:>7} {int(r['n_trades']):>3} {r['win_rate']:>5.0%} "
              f"{r['expectancy_pct']:>7.2f} {r['avg_hold']:>5.1f} {r['sharpe']:>7.2f} "
              f"{r['perm_p']:>7.3f} {r['exp_is_pct']:>7.2f} {r['exp_oos_pct']:>8.2f}{flag}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
