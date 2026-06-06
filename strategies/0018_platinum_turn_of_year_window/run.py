"""Strategy 0018 — Platinum turn-of-year window (Seasonax lead).

Third Seasonax-sourced seasonal lead (after 0016/Charter, 0017/Nasdaq), the first
on a *commodity future*. The user found platinum strong from **18 December to
17 January** — a window that wraps the year boundary. Same honesty harness as
0016/0017, with three differences appropriate to a future:

  * Cost model = IBKR_FUTURES (commission folded into a few bps, slippage-dominated).
  * Non-positive-price guard (CL=F printed negative in 2020; platinum should not,
    but continuous front-month series have their own roll artifacts — fail loud).
  * The window spans Dec->Jan, so the signal builder handles the year wrap and the
    IS/OOS split is cut in mid-summer (1 July) to never bisect a winter trade.

Unlike the two equities, platinum has a *real* macro candidate (see report): a
seasonal demand pull from jewelry fabrication ahead of Chinese New Year (late
Jan/Feb) and year-start auto/industrial restocking. That earns it a genuine test
rather than instant data-mining suspicion — but the permutation test (0017's
lesson: the filter that separates true timing from mere drift) still decides.

Run:
    .venv/Scripts/python.exe strategies/0018_platinum_turn_of_year_window/run.py
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

TICKER = "PL=F"
NAME = "Platin (Platin-Futures)"
START_MD = (12, 18)        # 18 December — pre-committed from the Seasonax trial
END_MD = (1, 17)           # 17 January (next year)
COST_MODEL = IBKR_FUTURES


def date_window_signal(index, start_md=START_MD, end_md=END_MD,
                       start_shift=0, end_shift=0, name="platinum_toy") -> pd.Series:
    """Long (1.0) over the turn-of-year window each winter, else flat.

    The window runs from (start_md of year y) to (end_md of year y+1), i.e. it
    wraps the calendar boundary. Decision-time signal; the engine applies the T+1
    execution shift, so no look-ahead. ``start_shift``/``end_shift`` move the
    window edges by N calendar days for robustness probing.
    """
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    # Iterate over the START year of each winter; include one year before the
    # first sample year so a window already open at the data start is captured.
    for y in range(int(idx.year.min()) - 1, int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *start_md) + pd.Timedelta(days=start_shift)
        end = pd.Timestamp(y + 1, *end_md) + pd.Timedelta(days=end_shift)
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
    print(f"Strategy 0018 — {NAME} turn-of-year window "
          f"({START_MD[1]}/{START_MD[0]}..{END_MD[1]}/{END_MD[0]}, {TICKER})")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    prices = get_prices(TICKER, start="2000-01-01")

    # Futures guard (CLAUDE lesson 0005): non-positive prints make pct_change nonsense.
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{TICKER}: non-positive close detected — abort (see CLAUDE.md 0005).")

    first_year = int(prices.index[0].year)
    last_year = int(prices.index[-1].year)
    mid_year = (first_year + last_year) // 2
    split_date = f"{mid_year}-07-01"   # mid-summer cut never bisects a Dec-Jan window
    print(f"  Data: {prices.index[0].date()} .. {prices.index[-1].date()} "
          f"({first_year}-{last_year}); IS< {split_date}, OOS>= {split_date}")

    is_prices = prices.loc[:split_date]
    oos_prices = prices.loc[split_date:]

    # --- Robustness grid (built on FULL sample) drives the search-width count --
    shifts = list(range(-10, 11, 2))   # +/- 10 calendar days, step 2
    n_trials = len(shifts) * len(shifts)
    exp_grid = np.full((len(shifts), len(shifts)), np.nan)   # expectancy/trade %
    shp_grid = np.full((len(shifts), len(shifts)), np.nan)   # annualized Sharpe
    for i, es in enumerate(shifts):          # rows = end shift
        for j, ss in enumerate(shifts):      # cols = start shift
            e = evaluate(prices, date_window_signal(prices.index,
                                                    start_shift=ss, end_shift=es))
            exp_grid[i, j] = e["trades"]["expectancy"] * 100.0
            shp_grid[i, j] = e["metrics"]["sharpe"]

    base_full = evaluate(prices, date_window_signal(prices.index), n_trials=n_trials)
    base_is = evaluate(is_prices, date_window_signal(is_prices.index), n_trials=n_trials)
    base_oos = evaluate(oos_prices, date_window_signal(oos_prices.index), n_trials=n_trials)

    # Buy & hold over the same full period, for context.
    bh_rets = prices["Close"].pct_change().fillna(0.0)
    bh_metrics = compute_metrics(bh_rets)

    # --- Significance on the FULL sample (this is the data Seasonax mined) ------
    full_rets = base_full["returns"]
    perm = permutation_test(full_rets, prices["Close"].pct_change().fillna(0.0),
                            base_full["res"]["position"], n_perm=2000)
    boot = bootstrap_ci(full_rets, statistic="sharpe", n_boot=2000)
    ttest = t_test_mean_return(full_rets)

    # --- Plots -----------------------------------------------------------------
    import matplotlib.pyplot as plt

    # Plot 1: seasonal-window equity vs buy & hold (full sample).
    plotting.savefig(
        plotting.plot_equity(
            base_full["res"]["equity"],
            benchmark=base_full["res"]["buy_hold"],
            title=f"0018 {NAME} — Jahreswechsel-Fenster 18.12.–17.1. vs. Buy & Hold (gesamt)",
            strategy_label="Fenster (long 18.12.–17.1., sonst flat)",
            benchmark_label=f"{NAME} Buy & Hold",
            caption=("Nur ~20 Handelstage/Winter long im Platin-Future, sonst flat, netto nach "
                     "IBKR-Futures-Kosten. Das Fenster wurde von Seasonax auf eben dieser "
                     "Historie als bestes gewählt — die Kurve ist daher in-sample geschönt. "
                     "Aussagekräftig sind Permutationstest, OOS-Hälfte und Robustheit.")),
        PLOTS / "equity_vs_bh.png")

    # Plot 2: per-winter trade returns.
    trades = base_full["res"]["trades"].copy()
    trades["year"] = pd.to_datetime(trades["entry_date"]).dt.year
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = ["#2a9d8f" if p > 0 else "#e76f51" for p in trades["pnl"]]
    ax.bar(trades["year"], trades["pnl"] * 100.0, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Netto-Rendite pro Winter-Trade (%)")
    win = (trades["pnl"] > 0).mean()
    ax.set_title(f"0018 {NAME} — Rendite je Winter-Trade (18.12.–17.1., netto)",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        f"Jeder Balken = ein Winter-Trade (~20 Tage long, Jahr = Einstiegsjahr im Dez.). "
        f"Grün = Gewinn. Trefferquote {win:.0%} über {len(trades)} Trades. "
        f"Ein Trade pro Winter — die niedrige Trade-Zahl bleibt die Hauptschwäche."))
    plotting.savefig(fig, PLOTS / "per_year_trades.png")

    # Plot 3: robustness heatmap — expectancy across window-edge shifts.
    fig, ax = plt.subplots(figsize=(9.5, 7.5))
    vmax = np.nanmax(np.abs(exp_grid))
    im = ax.imshow(exp_grid, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(shifts)))
    ax.set_xticklabels(shifts)
    ax.set_yticks(range(len(shifts)))
    ax.set_yticklabels(shifts)
    ax.set_xlabel("Verschiebung Startdatum (Kalendertage, 0 = 18. Dezember)")
    ax.set_ylabel("Verschiebung Enddatum (Kalendertage, 0 = 17. Januar)")
    for i in range(len(shifts)):
        for j in range(len(shifts)):
            ax.text(j, i, f"{exp_grid[i, j]:.1f}", ha="center", va="center",
                    fontsize=6.5, color="black")
    bj = shifts.index(0)
    ax.add_patch(plt.Rectangle((bj - 0.5, bj - 0.5), 1, 1, fill=False,
                               edgecolor="black", linewidth=2.5))
    fig.colorbar(im, ax=ax, label="Expectancy pro Trade (%)", shrink=0.85)
    ax.set_title(f"0018 {NAME} — Robustheit: Expectancy je Fenster-Verschiebung",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Erwartete Netto-Rendite pro Trade (%) wenn man Start- (Spalte) und Enddatum "
        "(Zeile) um N Kalendertage verschiebt; gesamte Historie. Schwarz umrandet = "
        "exaktes Seasonax-Fenster. Achtung: Bei driftarmem Future ist ein grünes Plateau "
        "aussagekräftiger als bei einer Trend-Aktie — aber der Permutationstest entscheidet."))
    plotting.savefig(fig, PLOTS / "robustness_heatmap.png")

    # --- Persist ---------------------------------------------------------------
    def slim(e):
        return {"metrics": e["metrics"], "trades": e["trades"],
                "exposure": e["exposure"], "psr": e["psr"]}
    summary = {
        "ticker": TICKER, "name": NAME,
        "window": {"start": list(START_MD), "end": list(END_MD), "wraps_year": True},
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
        "id": "0018", "label": f"{NAME} Jahreswechsel-Fenster 18.12.-17.1.",
        "cagr": fm["cagr"], "annual_volatility": fm["annual_volatility"],
        "sharpe": fm["sharpe"], "max_drawdown": fm["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    # --- Console ---------------------------------------------------------------
    print(f"\n  Rule: long {START_MD[1]}/{START_MD[0]}..{END_MD[1]}/{END_MD[0]} each winter, {TICKER}\n")
    print(fmt_block(f"FULL {first_year}-{last_year} (Seasonax view, in-sample)", base_full))
    print(fmt_block(f"IN-SAMPLE {first_year}-{mid_year}", base_is))
    print(fmt_block(f"OUT-OF-SAMPLE {mid_year}-{last_year}", base_oos))
    print(f"  Buy & Hold (full): CAGR {bh_metrics['cagr']:.2%}  Sharpe {bh_metrics['sharpe']:.2f}  "
          f"MaxDD {bh_metrics['max_drawdown']:.2%}")
    print("\n  Significance (full sample; window was mined on this data):")
    print(f"    Permutation p {perm['p_value']:.3f}   "
          f"Bootstrap Sharpe CI [{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]   "
          f"t-test p {ttest['p_value']:.3f}")
    print(f"    DSR charged n_trials={n_trials} (Seasonax search proxy): "
          f"PSR {base_full['psr']:.3f}  (E[max Sharpe|null]={base_full['expected_max_sharpe_null']:.3f})")
    pos_cells = int(np.sum(exp_grid > 0))
    print(f"\n  Robustness: {pos_cells}/{exp_grid.size} window-shift combos have "
          f"positive expectancy (full sample).")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
