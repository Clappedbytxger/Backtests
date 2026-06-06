"""Strategy 0022 — Gold around Western Easter (event-driven seasonal).

User-proposed pattern: go long gold **8 calendar days before Western (Gregorian)
Easter Sunday** and exit **2 calendar days after** it — a short (~10 calendar
day / ~6-7 trading day) window that floats with the moving feast each spring.

Unlike 0018 (platinum, fixed Dec/Jan dates) the window is *event-anchored*: Easter
shifts between 22 March and 25 April, so a fixed-date signal would not capture it.
We compute Western Easter per year with the Gregorian computus (Anonymous /
Meeus-Jones-Butcher algorithm — no extra dependency) and slide the window around it.

Macro honesty (CLAUDE.md hard rule): the well-documented gold-demand seasons are
**Indian** (Akshaya Tritiya, Diwali, wedding season) and **Chinese New Year**, NOT
Western Easter. Christian-culture countries are not big seasonal physical-gold
buyers. So a priori this window has *no clean economic cause* and is data-mining
suspect. We run the full honest harness anyway; the **permutation test** (0017's
lesson — the filter that separates real timing from drift/luck) decides whether it
is worth hunting for a mechanism (e.g. an Akshaya-Tritiya overlap in late years).

Same harness as 0018: IBKR_FUTURES costs, non-positive-price guard, mid-summer
IS/OOS cut (never bisects a spring window), robustness grid drives the DSR
search-width charge, significance on the full sample.

Run:
    .venv/Scripts/python.exe strategies/0022_gold_easter_window/run.py
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
from quantlab.costs import IBKR_FUTURES  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab import plotting  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

TICKER = "GC=F"
NAME = "Gold (Gold-Futures)"
DAYS_BEFORE = 8            # enter 8 calendar days before Easter — user pre-spec
DAYS_AFTER = 2             # exit 2 calendar days after Easter — user pre-spec
COST_MODEL = IBKR_FUTURES


def western_easter(year: int) -> pd.Timestamp:
    """Gregorian (Western) Easter Sunday for ``year`` via the computus.

    Anonymous / Meeus-Jones-Butcher algorithm. Dependency-free and exact for the
    Gregorian calendar (valid for all years we trade).
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    el = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * el) // 451
    month = (h + el - 7 * m + 114) // 31
    day = ((h + el - 7 * m + 114) % 31) + 1
    return pd.Timestamp(year, month, day)


def easter_window_signal(index, days_before=DAYS_BEFORE, days_after=DAYS_AFTER,
                         start_shift=0, end_shift=0, name="gold_easter") -> pd.Series:
    """Long (1.0) from (Easter - days_before) to (Easter + days_after) each year.

    Decision-time signal; the engine applies the T+1 execution shift, so no
    look-ahead. ``start_shift``/``end_shift`` move the window edges by N calendar
    days for robustness probing (positive = later).
    """
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    for y in range(int(idx.year.min()), int(idx.year.max()) + 1):
        easter = western_easter(y)
        start = easter - pd.Timedelta(days=days_before) + pd.Timedelta(days=start_shift)
        end = easter + pd.Timedelta(days=days_after) + pd.Timedelta(days=end_shift)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(prices: pd.DataFrame, signal: pd.Series, n_trials: int = 1) -> dict:
    """Full metric bundle for one (prices, signal) pair."""
    res = run_backtest(prices, signal, cost_model=COST_MODEL)
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


def main() -> None:
    print(f"Strategy 0022 — {NAME} Easter window "
          f"(-{DAYS_BEFORE}d .. +{DAYS_AFTER}d around Western Easter, {TICKER})")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    prices = get_prices(TICKER, start="2000-01-01")

    # Futures guard (CLAUDE lesson 0005): non-positive prints make pct_change nonsense.
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{TICKER}: non-positive close detected — abort (see CLAUDE.md 0005).")

    first_year = int(prices.index[0].year)
    last_year = int(prices.index[-1].year)
    mid_year = (first_year + last_year) // 2
    split_date = f"{mid_year}-07-01"   # mid-summer cut never bisects a spring window
    print(f"  Data: {prices.index[0].date()} .. {prices.index[-1].date()} "
          f"({first_year}-{last_year}); IS< {split_date}, OOS>= {split_date}")

    is_prices = prices.loc[:split_date]
    oos_prices = prices.loc[split_date:]

    # --- Robustness grid (built on FULL sample) drives the search-width count --
    shifts = list(range(-6, 7, 2))     # +/- 6 calendar days, step 2
    n_trials = len(shifts) * len(shifts)
    exp_grid = np.full((len(shifts), len(shifts)), np.nan)   # expectancy/trade %
    shp_grid = np.full((len(shifts), len(shifts)), np.nan)   # annualized Sharpe
    for i, es in enumerate(shifts):          # rows = end shift
        for j, ss in enumerate(shifts):      # cols = start shift
            e = evaluate(prices, easter_window_signal(prices.index,
                                                      start_shift=ss, end_shift=es))
            exp_grid[i, j] = e["trades"]["expectancy"] * 100.0
            shp_grid[i, j] = e["metrics"]["sharpe"]

    base_full = evaluate(prices, easter_window_signal(prices.index), n_trials=n_trials)
    base_is = evaluate(is_prices, easter_window_signal(is_prices.index), n_trials=n_trials)
    base_oos = evaluate(oos_prices, easter_window_signal(oos_prices.index), n_trials=n_trials)

    # Buy & hold over the same full period, for context.
    bh_rets = prices["Close"].pct_change().fillna(0.0)
    bh_metrics = compute_metrics(bh_rets)

    # --- Significance on the FULL sample ---------------------------------------
    full_rets = base_full["returns"]
    perm = permutation_test(full_rets, prices["Close"].pct_change().fillna(0.0),
                            base_full["res"]["position"], n_perm=2000)
    boot = bootstrap_ci(full_rets, statistic="sharpe", n_boot=2000)
    ttest = t_test_mean_return(full_rets)

    # --- Plots -----------------------------------------------------------------
    import matplotlib.pyplot as plt

    # Plot 1: Easter-window equity vs buy & hold (full sample).
    plotting.savefig(
        plotting.plot_equity(
            base_full["res"]["equity"],
            benchmark=base_full["res"]["buy_hold"],
            title=f"0022 {NAME} — Oster-Fenster (-{DAYS_BEFORE}d/+{DAYS_AFTER}d) vs. Buy & Hold (gesamt)",
            strategy_label=f"Fenster (long {DAYS_BEFORE}T vor bis {DAYS_AFTER}T nach Ostern)",
            benchmark_label=f"{NAME} Buy & Hold",
            caption=(f"Nur ~7 Handelstage/Jahr long im Gold-Future rund um das (bewegliche) "
                     f"Western-Easter-Datum, sonst flat, netto nach IBKR-Futures-Kosten. "
                     f"Das Fenster ist nutzer-vorgegeben, nicht aus diesen Daten gescannt — aber "
                     f"die Makro-Story ist schwach (Ostern ist kein bekannter Gold-Kauf-Anlass). "
                     f"Aussagekräftig sind Permutationstest, OOS-Hälfte und Robustheit.")),
        PLOTS / "equity_vs_bh.png")

    # Plot 2: per-year trade returns.
    trades = base_full["res"]["trades"].copy()
    trades["year"] = pd.to_datetime(trades["entry_date"]).dt.year
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = ["#2a9d8f" if p > 0 else "#e76f51" for p in trades["pnl"]]
    ax.bar(trades["year"], trades["pnl"] * 100.0, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Netto-Rendite pro Oster-Trade (%)")
    win = (trades["pnl"] > 0).mean()
    ax.set_title(f"0022 {NAME} — Rendite je Oster-Trade (netto)",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        f"Jeder Balken = ein Jahres-Trade (~7 Tage long um Ostern). "
        f"Grün = Gewinn. Trefferquote {win:.0%} über {len(trades)} Trades."))
    plotting.savefig(fig, PLOTS / "per_year_trades.png")

    # Plot 3: robustness heatmap — expectancy across window-edge shifts.
    fig, ax = plt.subplots(figsize=(9.5, 7.5))
    vmax = np.nanmax(np.abs(exp_grid))
    im = ax.imshow(exp_grid, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(shifts)))
    ax.set_xticklabels(shifts)
    ax.set_yticks(range(len(shifts)))
    ax.set_yticklabels(shifts)
    ax.set_xlabel(f"Verschiebung Startdatum (Kalendertage, 0 = {DAYS_BEFORE}T vor Ostern)")
    ax.set_ylabel(f"Verschiebung Enddatum (Kalendertage, 0 = {DAYS_AFTER}T nach Ostern)")
    for i in range(len(shifts)):
        for j in range(len(shifts)):
            ax.text(j, i, f"{exp_grid[i, j]:.1f}", ha="center", va="center",
                    fontsize=6.5, color="black")
    bj = shifts.index(0)
    ax.add_patch(plt.Rectangle((bj - 0.5, bj - 0.5), 1, 1, fill=False,
                               edgecolor="black", linewidth=2.5))
    fig.colorbar(im, ax=ax, label="Expectancy pro Trade (%)", shrink=0.85)
    ax.set_title(f"0022 {NAME} — Robustheit: Expectancy je Fenster-Verschiebung",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Erwartete Netto-Rendite pro Trade (%) wenn man Start- (Spalte) und Enddatum "
        "(Zeile) um N Kalendertage verschiebt; gesamte Historie. Schwarz umrandet = "
        "exaktes Nutzer-Fenster. Ein einzelner grüner Fleck ohne Plateau = Überanpassung."))
    plotting.savefig(fig, PLOTS / "robustness_heatmap.png")

    # --- Persist ---------------------------------------------------------------
    def slim(e):
        return {"metrics": e["metrics"], "trades": e["trades"],
                "exposure": e["exposure"], "psr": e["psr"]}
    summary = {
        "ticker": TICKER, "name": NAME,
        "window": {"days_before": DAYS_BEFORE, "days_after": DAYS_AFTER,
                   "anchor": "western_easter"},
        "sample": {"first_year": first_year, "last_year": last_year,
                   "mid_year": mid_year, "split_date": split_date},
        "n_trials_charged": n_trials,
        "full_sample": slim(base_full),
        "in_sample": slim(base_is),
        "out_of_sample": slim(base_oos),
        "buy_hold_full": bh_metrics,
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
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    base_full["res"]["equity"].rename("equity").to_csv(RESULTS / "equity.csv")
    base_full["res"]["trades"].to_csv(RESULTS / "trades.csv", index=False)
    fm = base_full["metrics"]
    card = {
        "id": "0022", "label": f"{NAME} Oster-Fenster -{DAYS_BEFORE}d/+{DAYS_AFTER}d",
        "cagr": fm["cagr"], "annual_volatility": fm["annual_volatility"],
        "sharpe": fm["sharpe"], "max_drawdown": fm["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    # --- Console ---------------------------------------------------------------
    # Show the actual Easter dates / windows traded, for the report.
    sample_years = sorted(set(pd.to_datetime(trades["entry_date"]).dt.year))
    print(f"\n  Rule: long {DAYS_BEFORE}d before .. {DAYS_AFTER}d after Western Easter, {TICKER}")
    print(f"  Easter dates traded ({sample_years[0]}..{sample_years[-1]}): " +
          ", ".join(f"{western_easter(y).strftime('%d.%m')}" for y in sample_years[:6]) + ", ...\n")
    print(fmt_block(f"FULL {first_year}-{last_year}", base_full))
    print(fmt_block(f"IN-SAMPLE {first_year}-{mid_year}", base_is))
    print(fmt_block(f"OUT-OF-SAMPLE {mid_year}-{last_year}", base_oos))
    print(f"  Buy & Hold (full): CAGR {bh_metrics['cagr']:.2%}  Sharpe {bh_metrics['sharpe']:.2f}  "
          f"MaxDD {bh_metrics['max_drawdown']:.2%}")
    print("\n  Significance (full sample):")
    print(f"    Permutation p {perm['p_value']:.3f}   "
          f"Bootstrap Sharpe CI [{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]   "
          f"t-test p {ttest['p_value']:.3f}")
    print(f"    DSR charged n_trials={n_trials} (window-search proxy): "
          f"PSR {base_full['psr']:.3f}  (E[max Sharpe|null]={base_full['expected_max_sharpe_null']:.3f})")
    pos_cells = int(np.sum(exp_grid > 0))
    print(f"\n  Robustness: {pos_cells}/{exp_grid.size} window-shift combos have "
          f"positive expectancy (full sample).")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
