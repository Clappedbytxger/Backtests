"""Strategy 0023 — Gold around Asian gold-buying festivals (dual study).

Where 0022 (gold around Western Easter) failed for lack of any macro cause, this
tests the *real* seasonal gold-demand events and compares them head to head:

  * **Akshaya Tritiya** (India) — the second-biggest gold-buying day of the Indian
    year (after Dhanteras/Diwali). Considered the most auspicious day to buy gold;
    jewellers stock up and households buy in the run-up. India is the #2 gold
    consumer. Date floats (Shukla Paksha Tritiya of Vaishakha) in late Apr/early May.
  * **Chinese New Year** (China) — Spring-Festival jewellery demand and gold
    gifting; Chinese retailers restock and consumers buy ahead of the holiday.
    China is the #1 gold consumer. Date floats (lunisolar) in late Jan/early Feb.

Both dates are lunisolar and cannot be computed by a simple formula, so they are
hard-coded from verified tables (Western Easter in 0022 used the computus instead).

Mechanism = **demand pull BEFORE the festival**, so the rule is: long gold from
``DAYS_BEFORE`` calendar days before the festival until ``DAYS_AFTER`` after it,
else flat. The window (15 before / 2 after) is *pre-specified from the macro
story*, not scanned from price; the robustness grid (window-edge shifts) drives
the DSR search-width charge, and the **permutation test** (0017's lesson; the
filter that killed 0022) decides whether the timing beats random spring/winter
timing in a rising gold market.

Three views are produced and compared: Akshaya alone, CNY alone, and the **pooled
"Asian gold season"** (union of both windows) — pooling roughly doubles the trade
count for more statistical power, mirroring 0002's pooling logic.

Cross-instrument robustness: each base window is re-run on the physical-backed
ETF (GLD) to check the futures result is not a roll/contract artifact.

Run:
    .venv/Scripts/python.exe strategies/0023_gold_asian_festivals/run.py
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
    bootstrap_ci, deflated_sharpe_ratio, permutation_test,
)
from quantlab.significance import t_test_mean_return  # noqa: E402
from quantlab.costs import IBKR_FUTURES, IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab import plotting  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"

TICKER = "GC=F"
NAME = "Gold (Gold-Futures)"
ETF_TICKER = "GLD"
ETF_NAME = "Gold (SPDR Gold Shares, physisch)"
DAYS_BEFORE = 15           # enter 15 calendar days before the festival — pre-spec
DAYS_AFTER = 2             # exit 2 calendar days after the festival — pre-spec

# --- Verified festival date tables (Gregorian), 2000-2026 --------------------
# Akshaya Tritiya (Shukla Paksha Tritiya, Vaishakha). Sources: drikpanchang/Wikipedia.
AKSHAYA_TRITIYA = {
    2000: (5, 6), 2001: (4, 26), 2002: (5, 15), 2003: (5, 4), 2004: (4, 22),
    2005: (5, 11), 2006: (4, 30), 2007: (4, 19), 2008: (5, 7), 2009: (4, 27),
    2010: (5, 16), 2011: (5, 6), 2012: (4, 24), 2013: (5, 13), 2014: (5, 2),
    2015: (4, 21), 2016: (5, 9), 2017: (4, 28), 2018: (4, 18), 2019: (5, 7),
    2020: (4, 26), 2021: (5, 14), 2022: (5, 3), 2023: (4, 22), 2024: (5, 10),
    2025: (4, 30), 2026: (4, 19),
}
# Chinese New Year (first day of the Spring Festival).
CHINESE_NEW_YEAR = {
    2000: (2, 5), 2001: (1, 24), 2002: (2, 12), 2003: (2, 1), 2004: (1, 22),
    2005: (2, 9), 2006: (1, 29), 2007: (2, 18), 2008: (2, 7), 2009: (1, 26),
    2010: (2, 14), 2011: (2, 3), 2012: (1, 23), 2013: (2, 10), 2014: (1, 31),
    2015: (2, 19), 2016: (2, 8), 2017: (1, 28), 2018: (2, 16), 2019: (2, 5),
    2020: (1, 25), 2021: (2, 12), 2022: (2, 1), 2023: (1, 22), 2024: (2, 10),
    2025: (1, 29), 2026: (2, 17),
}

FESTIVALS = {
    "akshaya_tritiya": {"table": AKSHAYA_TRITIYA, "label": "Akshaya Tritiya (Indien)"},
    "chinese_new_year": {"table": CHINESE_NEW_YEAR, "label": "Chinesisches Neujahr (China)"},
}


def festival_window_signal(index, tables, days_before=DAYS_BEFORE, days_after=DAYS_AFTER,
                           start_shift=0, end_shift=0, name="festival") -> pd.Series:
    """Long (1.0) over each festival's pre-event window, else flat.

    ``tables`` is a list of {year: (month, day)} dicts; the position is long if
    the date falls inside ANY festival window (so passing both tables yields the
    pooled "Asian gold season"). Decision-time signal; the engine applies the T+1
    execution shift, so no look-ahead. ``start_shift``/``end_shift`` move the
    window edges by N calendar days for robustness probing (positive = later).
    """
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    for table in tables:
        for y, (mo, da) in table.items():
            event = pd.Timestamp(y, mo, da)
            start = event - pd.Timedelta(days=days_before) + pd.Timedelta(days=start_shift)
            end = event + pd.Timedelta(days=days_after) + pd.Timedelta(days=end_shift)
            mask = (idx >= start) & (idx <= end)
            pos[np.asarray(mask)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(prices, signal, cost_model, n_trials=1) -> dict:
    """Full metric bundle for one (prices, signal) pair."""
    res = run_backtest(prices, signal, cost_model=cost_model)
    rets = res["returns"]
    m = compute_metrics(rets)
    ts = trade_stats(res["trades"])
    sp = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) else 0.0
    dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(rets),
                                n_trials=max(1, n_trials), returns=rets)
    return {
        "metrics": m, "trades": ts,
        "exposure": float(res["position"].abs().mean()),
        "psr": dsr["psr_deflated"],
        "expected_max_sharpe_null": dsr["expected_max_sharpe_under_null"],
        "returns": rets, "res": res,
    }


def fmt_block(label: str, e: dict) -> str:
    m, ts = e["metrics"], e["trades"]
    return (
        f"  [{label}]\n"
        f"    CAGR {m['cagr']:.2%}   Sharpe {m['sharpe']:.2f}   Sortino {m['sortino']:.2f}"
        f"   Calmar {m['calmar']:.2f}   MaxDD {m['max_drawdown']:.2%}\n"
        f"    Trades {ts['n_trades']}   Win {ts['win_rate']:.0%}   "
        f"PF {ts['profit_factor']:.2f}   Payoff {ts['payoff_ratio']:.2f}\n"
        f"    Expectancy/Trade {ts['expectancy']:.2%}   AvgWin {ts['avg_win']:.2%}   "
        f"AvgLoss {ts['avg_loss']:.2%}   AvgHold {ts['avg_holding_days']:.1f}d   "
        f"Exposure {e['exposure']:.1%}\n"
    )


def slim(e):
    return {"metrics": e["metrics"], "trades": e["trades"],
            "exposure": e["exposure"], "psr": e["psr"]}


def run_one(key, tables, label, prices, split_date, bh_rets, out_dir):
    """Full honest harness for one window family (single festival or pooled)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    plots = out_dir / "plots"
    plots.mkdir(parents=True, exist_ok=True)

    is_prices = prices.loc[:split_date]
    oos_prices = prices.loc[split_date:]

    # Robustness grid (full sample) -> DSR search-width charge.
    shifts = list(range(-6, 7, 2))     # +/- 6 calendar days, step 2
    n_trials = len(shifts) * len(shifts)
    exp_grid = np.full((len(shifts), len(shifts)), np.nan)
    shp_grid = np.full((len(shifts), len(shifts)), np.nan)
    for i, es in enumerate(shifts):          # rows = end shift
        for j, ss in enumerate(shifts):      # cols = start shift
            e = evaluate(prices, festival_window_signal(prices.index, tables,
                                                        start_shift=ss, end_shift=es),
                         IBKR_FUTURES)
            exp_grid[i, j] = e["trades"]["expectancy"] * 100.0
            shp_grid[i, j] = e["metrics"]["sharpe"]

    base_full = evaluate(prices, festival_window_signal(prices.index, tables),
                         IBKR_FUTURES, n_trials=n_trials)
    base_is = evaluate(is_prices, festival_window_signal(is_prices.index, tables),
                       IBKR_FUTURES, n_trials=n_trials)
    base_oos = evaluate(oos_prices, festival_window_signal(oos_prices.index, tables),
                        IBKR_FUTURES, n_trials=n_trials)

    full_rets = base_full["returns"]
    perm = permutation_test(full_rets, bh_rets, base_full["res"]["position"], n_perm=2000)
    boot = bootstrap_ci(full_rets, statistic="sharpe", n_boot=2000)
    ttest = t_test_mean_return(full_rets)

    # --- Plots ---
    import matplotlib.pyplot as plt

    plotting.savefig(
        plotting.plot_equity(
            base_full["res"]["equity"],
            benchmark=base_full["res"]["buy_hold"],
            title=f"0023 {label} — Gold-Vorfest-Fenster (-{DAYS_BEFORE}d/+{DAYS_AFTER}d) vs. Buy & Hold",
            strategy_label=f"Fenster (long {DAYS_BEFORE}T vor bis {DAYS_AFTER}T nach Fest)",
            benchmark_label=f"{NAME} Buy & Hold",
            caption=(f"Long Gold-Future nur im Vorlauf des Festes ({label}), sonst flat, netto nach "
                     f"IBKR-Futures-Kosten. Makro: Nachfragesog durch physischen Schmuck-/Anlagekauf "
                     f"vor dem Fest. Aussagekräftig sind Permutationstest, OOS-Hälfte und Robustheit — "
                     f"nicht die schiere Kurve (Gold driftete stark nach oben).")),
        plots / "equity_vs_bh.png")

    trades = base_full["res"]["trades"].copy()
    trades["year"] = pd.to_datetime(trades["entry_date"]).dt.year
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = ["#2a9d8f" if p > 0 else "#e76f51" for p in trades["pnl"]]
    ax.bar(trades["year"], trades["pnl"] * 100.0, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Netto-Rendite pro Vorfest-Trade (%)")
    win = (trades["pnl"] > 0).mean()
    ax.set_title(f"0023 {label} — Rendite je Vorfest-Trade (netto)", fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        f"Jeder Balken = ein Trade im Vorlauf des Festes. Grün = Gewinn. "
        f"Trefferquote {win:.0%} über {len(trades)} Trades."))
    plotting.savefig(fig, plots / "per_year_trades.png")

    fig, ax = plt.subplots(figsize=(9.5, 7.5))
    vmax = np.nanmax(np.abs(exp_grid)) or 1.0
    im = ax.imshow(exp_grid, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(shifts)))
    ax.set_xticklabels(shifts)
    ax.set_yticks(range(len(shifts)))
    ax.set_yticklabels(shifts)
    ax.set_xlabel(f"Verschiebung Startdatum (Kalendertage, 0 = {DAYS_BEFORE}T vor Fest)")
    ax.set_ylabel(f"Verschiebung Enddatum (Kalendertage, 0 = {DAYS_AFTER}T nach Fest)")
    for i in range(len(shifts)):
        for j in range(len(shifts)):
            ax.text(j, i, f"{exp_grid[i, j]:.1f}", ha="center", va="center",
                    fontsize=6.5, color="black")
    bj = shifts.index(0)
    ax.add_patch(plt.Rectangle((bj - 0.5, bj - 0.5), 1, 1, fill=False,
                               edgecolor="black", linewidth=2.5))
    fig.colorbar(im, ax=ax, label="Expectancy pro Trade (%)", shrink=0.85)
    ax.set_title(f"0023 {label} — Robustheit: Expectancy je Fenster-Verschiebung",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Netto-Expectancy/Trade (%) bei Verschiebung von Start- (Spalte) und Enddatum (Zeile) um "
        "N Kalendertage; gesamte Historie. Schwarz = pre-spec Fenster. Drift-Warnung (0017/0022): "
        "In steigendem Gold ist ein grünes Plateau allein kein Beweis — der Permutationstest entscheidet."))
    plotting.savefig(fig, plots / "robustness_heatmap.png")

    base_full["res"]["trades"].to_csv(out_dir / "trades.csv", index=False)

    return {
        "key": key, "label": label,
        "n_trials_charged": n_trials,
        "full_sample": slim(base_full),
        "in_sample": slim(base_is),
        "out_of_sample": slim(base_oos),
        "significance_full": {
            "permutation": perm, "bootstrap_sharpe_ci": boot, "t_test": ttest,
            "psr_deflated": base_full["psr"],
            "expected_max_sharpe_null": base_full["expected_max_sharpe_null"],
        },
        "robustness": {
            "shifts": shifts, "expectancy_pct": exp_grid.tolist(),
            "sharpe": shp_grid.tolist(),
            "positive_cells": int(np.sum(exp_grid > 0)), "total_cells": int(exp_grid.size),
        },
        "_base_full": base_full, "_perm": perm, "_boot": boot, "_ttest": ttest,
    }


def main() -> None:
    print(f"Strategy 0023 — {NAME} Asian gold festivals "
          f"(-{DAYS_BEFORE}d .. +{DAYS_AFTER}d, {TICKER})")
    RESULTS.mkdir(parents=True, exist_ok=True)

    prices = get_prices(TICKER, start="2000-01-01")
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{TICKER}: non-positive close detected — abort (see CLAUDE.md 0005).")

    first_year = int(prices.index[0].year)
    last_year = int(prices.index[-1].year)
    mid_year = (first_year + last_year) // 2
    split_date = f"{mid_year}-07-01"   # mid-summer cut never bisects a Jan-May window
    print(f"  Data: {prices.index[0].date()} .. {prices.index[-1].date()} "
          f"({first_year}-{last_year}); IS< {split_date}, OOS>= {split_date}")
    bh_rets = prices["Close"].pct_change().fillna(0.0)
    bh_metrics = compute_metrics(bh_rets)

    # --- Three views: Akshaya, CNY, pooled ---
    runs = {}
    runs["akshaya_tritiya"] = run_one(
        "akshaya_tritiya", [AKSHAYA_TRITIYA], FESTIVALS["akshaya_tritiya"]["label"],
        prices, split_date, bh_rets, RESULTS / "akshaya_tritiya")
    runs["chinese_new_year"] = run_one(
        "chinese_new_year", [CHINESE_NEW_YEAR], FESTIVALS["chinese_new_year"]["label"],
        prices, split_date, bh_rets, RESULTS / "chinese_new_year")
    runs["pooled"] = run_one(
        "pooled", [AKSHAYA_TRITIYA, CHINESE_NEW_YEAR], "Asiatische Gold-Saison (gepoolt)",
        prices, split_date, bh_rets, RESULTS / "pooled")

    # --- Cross-instrument robustness: base window on physical GLD ETF ---
    etf_checks = {}
    try:
        etf = get_prices(ETF_TICKER, start="2004-11-01")
        for key, tables in [("akshaya_tritiya", [AKSHAYA_TRITIYA]),
                            ("chinese_new_year", [CHINESE_NEW_YEAR]),
                            ("pooled", [AKSHAYA_TRITIYA, CHINESE_NEW_YEAR])]:
            e = evaluate(etf, festival_window_signal(etf.index, tables), IBKR_LIQUID_ETF)
            er = e["returns"]
            ep = permutation_test(er, etf["Close"].pct_change().fillna(0.0),
                                  e["res"]["position"], n_perm=2000)
            etf_checks[key] = {"metrics": e["metrics"], "trades": e["trades"],
                               "permutation": ep}
    except Exception as exc:  # pragma: no cover - ETF availability guard
        etf_checks = {"error": str(exc)}

    # --- Persist top-level summary + headline card (pooled) ---
    summary = {
        "tickers": {"futures": TICKER, "etf": ETF_TICKER},
        "name": NAME,
        "window": {"days_before": DAYS_BEFORE, "days_after": DAYS_AFTER,
                   "logic": "pre_festival_demand_pull"},
        "sample": {"first_year": first_year, "last_year": last_year,
                   "mid_year": mid_year, "split_date": split_date},
        "buy_hold_full": bh_metrics,
        "views": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
                  for k, v in runs.items()},
        "etf_cross_check": etf_checks,
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    # Headline = the surviving view (CNY), not the pooled one that Akshaya dilutes.
    cny_m = runs["chinese_new_year"]["_base_full"]["metrics"]
    card = {
        "id": "0023",
        "label": "Gold Vorfest-Fenster Chinesisches Neujahr (-15d/+2d)",
        "cagr": cny_m["cagr"], "annual_volatility": cny_m["annual_volatility"],
        "sharpe": cny_m["sharpe"], "max_drawdown": cny_m["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    # --- Console ---
    print(f"\n  Rule: long {DAYS_BEFORE}d before .. {DAYS_AFTER}d after each festival, {TICKER}")
    print(f"  Buy & Hold (full): CAGR {bh_metrics['cagr']:.2%}  Sharpe {bh_metrics['sharpe']:.2f}  "
          f"MaxDD {bh_metrics['max_drawdown']:.2%}\n")
    for key in ("akshaya_tritiya", "chinese_new_year", "pooled"):
        r = runs[key]
        print(f"=== {r['label']} ===")
        print(fmt_block(f"FULL {first_year}-{last_year}", r["_base_full"]))
        bf, perm, boot, tt = r["_base_full"], r["_perm"], r["_boot"], r["_ttest"]
        print(f"    Permutation p {perm['p_value']:.3f}   "
              f"Bootstrap Sharpe CI [{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]   "
              f"t-test p {tt['p_value']:.3f}   PSR {bf['psr']:.3f} "
              f"(n_trials={r['n_trials_charged']})")
        pos = r["robustness"]["positive_cells"]
        tot = r["robustness"]["total_cells"]
        print(f"    Robustness: {pos}/{tot} window-shift combos positive\n")

    if "error" not in etf_checks:
        print("  Cross-instrument (physical GLD ETF, base window):")
        for key in ("akshaya_tritiya", "chinese_new_year", "pooled"):
            c = etf_checks[key]
            print(f"    {key:18s} Expectancy {c['trades']['expectancy']:.2%}/Trade  "
                  f"Win {c['trades']['win_rate']:.0%}  Perm p {c['permutation']['p_value']:.3f}  "
                  f"({c['trades']['n_trades']} trades)")

    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
