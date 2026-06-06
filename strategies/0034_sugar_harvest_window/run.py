"""Strategy 0034 — Sugar harvest window 8 Jun–3 Jul (Seasonax lead).

Full honesty harness (0028) + mandatory roll-day check (0029), on ICE Sugar #11
front-month future `SB=F`. User-supplied Seasonax window: **8 Jun to 3 Jul** (single
calendar year, ~18 trading days). IS/OOS split at 1 Jan.

Macro rationale: Brazil Center-South dominates world sugar exports; its crush/harvest
runs ~Apr-Nov. The June strength fits an early-harvest **weather/cane-frost risk
premium** (Brazilian winter Jun-Jul can bring frost to cane regions) plus crush-pace
uncertainty. Sugar is drift-light (mean-reverting soft) → a positive window is more
meaningful than on a drift asset, and the permutation test is decisive.

ROLL RISK (lesson 0029): Sugar #11 contracts are Mar/May/Jul/Oct; the July contract's
last trading day is ~end of June, so the continuous series rolls Jul->Oct right at the
window's tail (the 1-Jul daily std is ~6% — a roll signature). The roll-day exclusion
test (29 Jun - 2 Jul) is therefore run regardless.

Guards: non-positive close (0005) + frozen-feed (<50 distinct/yr, 0025).

Run:
    .venv/Scripts/python.exe strategies/0034_sugar_harvest_window/run.py
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

TICKER = "SB=F"
NAME = "Zucker (Sugar #11-Future)"
START_MD = (6, 8)           # 8 June — pre-committed from Seasonax
END_MD = (7, 3)             # 3 July (same year)
COST_MODEL = IBKR_FUTURES
ROLL_ZONES = [((6, 29), (7, 2))]     # Jul contract LTD ~end June -> Jul->Oct roll


def in_roll_zone(m, d):
    return any(lo <= (m, d) <= hi for (lo, hi) in ROLL_ZONES)


def date_window_signal(index, start_shift=0, end_shift=0, exclude_roll=False, name="sugar") -> pd.Series:
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    for y in range(int(idx.year.min()), int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *START_MD) + pd.Timedelta(days=start_shift)
        end = pd.Timestamp(y, *END_MD) + pd.Timedelta(days=end_shift)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    if exclude_roll:
        pos[np.array([in_roll_zone(t.month, t.day) for t in idx])] = 0.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(prices, signal, n_trials=1) -> dict:
    res = run_backtest(prices, signal, cost_model=COST_MODEL)
    rets = res["returns"]
    m, ts = compute_metrics(rets), trade_stats(res["trades"])
    sp = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) else 0.0
    dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(rets),
                                n_trials=max(1, n_trials), returns=rets)
    return {"metrics": m, "trades": ts, "exposure": float(res["position"].abs().mean()),
            "psr": dsr["psr_deflated"], "returns": rets, "res": res}


def fmt_block(label, e):
    m, ts = e["metrics"], e["trades"]
    pnl = e["res"]["trades"]["pnl"]
    median = float(pnl.median()) if len(pnl) else float("nan")
    return (f"  [{label}]\n"
            f"    CAGR {m['cagr']:.2%}  Sharpe {m['sharpe']:.2f}  Sortino {m['sortino']:.2f}  MaxDD {m['max_drawdown']:.2%}\n"
            f"    Trades {ts['n_trades']}  Win {ts['win_rate']:.0%}  PF {ts['profit_factor']:.2f}  "
            f"Exp/Trade {ts['expectancy']:.2%}  Median {median:.2%}  Exposure {e['exposure']:.1%}\n")


def roll_check(prices, asset_ret, split_date):
    def bundle(exclude_roll):
        sig = date_window_signal(prices.index, exclude_roll=exclude_roll)
        e = evaluate(prices, sig)
        perm = permutation_test(e["returns"], asset_ret, e["res"]["position"], n_perm=2000)
        e_is = evaluate(prices.loc[:split_date], date_window_signal(prices.loc[:split_date].index, exclude_roll=exclude_roll))
        e_oos = evaluate(prices.loc[split_date:], date_window_signal(prices.loc[split_date:].index, exclude_roll=exclude_roll))
        return {"exp": e["trades"]["expectancy"] * 100, "win": e["trades"]["win_rate"],
                "sharpe": e["metrics"]["sharpe"], "perm_p": perm["p_value"],
                "exp_is": e_is["trades"]["expectancy"] * 100, "exp_oos": e_oos["trades"]["expectancy"] * 100}
    base, cleaned = bundle(False), bundle(True)
    held = date_window_signal(prices.index).shift(1).fillna(0.0) > 0
    winters, days = {}, {}
    prev, cy = False, None
    for dt, fl in held.items():
        if fl:
            if not prev:
                cy = dt.year; winters[cy], days[cy] = [], []
            winters[cy].append(asset_ret.loc[dt]); days[cy].append((dt.month, dt.day))
        prev = fl
    full_m, roll_m = [], []
    for yr in winters:
        rs = np.array(winters[yr]); isr = np.array([in_roll_zone(m, d) for (m, d) in days[yr]])
        full_m.append(np.prod(1 + rs) - 1)
        roll_m.append((np.prod(1 + rs[isr]) - 1) if isr.any() else 0.0)
    share = float(np.mean(roll_m) / np.mean(full_m)) if np.mean(full_m) else float("nan")
    return {"base": base, "cleaned": cleaned, "share_on_roll": share}


def main():
    print(f"Strategy 0034 — {NAME} window ({START_MD[1]}.{START_MD[0]}..{END_MD[1]}.{END_MD[0]}, {TICKER})")
    RESULTS.mkdir(parents=True, exist_ok=True); PLOTS.mkdir(parents=True, exist_ok=True)

    prices = get_prices(TICKER, start="2000-01-01")
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{TICKER}: non-positive close (0005).")
    if int(prices["Close"].groupby(prices.index.year).nunique().min()) < 50:
        raise SystemExit(f"{TICKER}: frozen feed (0025).")
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    first_year, last_year = int(prices.index[0].year), int(prices.index[-1].year)
    mid_year = (first_year + last_year) // 2
    split_date = f"{mid_year}-01-01"
    print(f"  Data: {prices.index[0].date()}..{prices.index[-1].date()}; IS<{split_date}")
    is_p, oos_p = prices.loc[:split_date], prices.loc[split_date:]

    shifts = list(range(-10, 11, 2)); n_trials = len(shifts) ** 2
    exp_grid = np.full((len(shifts), len(shifts)), np.nan)
    for i, es in enumerate(shifts):
        for j, ss in enumerate(shifts):
            exp_grid[i, j] = evaluate(prices, date_window_signal(prices.index, start_shift=ss, end_shift=es))["trades"]["expectancy"] * 100

    base_full = evaluate(prices, date_window_signal(prices.index), n_trials=n_trials)
    base_is = evaluate(is_p, date_window_signal(is_p.index), n_trials=n_trials)
    base_oos = evaluate(oos_p, date_window_signal(oos_p.index), n_trials=n_trials)
    bh = compute_metrics(asset_ret)
    perm = permutation_test(base_full["returns"], asset_ret, base_full["res"]["position"], n_perm=2000)
    boot = bootstrap_ci(base_full["returns"], statistic="sharpe", n_boot=2000)
    ttest = t_test_mean_return(base_full["returns"])
    rc = roll_check(prices, asset_ret, split_date)

    import matplotlib.pyplot as plt
    plotting.savefig(plotting.plot_equity(
        base_full["res"]["equity"], benchmark=base_full["res"]["buy_hold"],
        title=f"0034 {NAME} — Fenster 8.6.–3.7. vs. Buy & Hold (gesamt)",
        strategy_label="Fenster (long 8.6.–3.7., sonst flat)", benchmark_label=f"{NAME} Buy & Hold",
        caption=("~18 Handelstage/Jahr long im ICE-Sugar-#11-Future, sonst flat, netto. Fenster Seasonax-"
                 "gemined → in-sample geschönt. Aussagekräftig: Permutation, OOS, Robustheit, Roll-Tag-Check "
                 "(Juli-Roll am Fensterende). Treiber-These: brasilianische Ernte-/Cane-Frost-Risikoprämie Jun–Jul.")),
        PLOTS / "equity_vs_bh.png")
    trades = base_full["res"]["trades"].copy(); trades["year"] = pd.to_datetime(trades["entry_date"]).dt.year
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(trades["year"], trades["pnl"] * 100, color=["#2a9d8f" if p > 0 else "#e76f51" for p in trades["pnl"]])
    ax.axhline(0, color="black", lw=0.8); ax.set_ylabel("Netto-Rendite pro Trade (%)")
    ax.set_title(f"0034 {NAME} — Rendite je Sommer-Trade (netto)", fontsize=12, fontweight="bold")
    plotting._add_caption(fig, f"Jeder Balken = ein Trade (~18 Tage). Trefferquote {(trades['pnl']>0).mean():.0%} über {len(trades)} Trades.")
    plotting.savefig(fig, PLOTS / "per_year_trades.png")
    fig, ax = plt.subplots(figsize=(9.5, 7.5)); vmax = np.nanmax(np.abs(exp_grid))
    im = ax.imshow(exp_grid, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(shifts))); ax.set_xticklabels(shifts); ax.set_yticks(range(len(shifts))); ax.set_yticklabels(shifts)
    ax.set_xlabel("Verschiebung Start (Tage, 0 = 8.6.)"); ax.set_ylabel("Verschiebung Ende (Tage, 0 = 3.7.)")
    for i in range(len(shifts)):
        for j in range(len(shifts)):
            ax.text(j, i, f"{exp_grid[i, j]:.1f}", ha="center", va="center", fontsize=6.5)
    ax.add_patch(plt.Rectangle((shifts.index(0) - 0.5, shifts.index(0) - 0.5), 1, 1, fill=False, edgecolor="black", lw=2.5))
    fig.colorbar(im, ax=ax, label="Expectancy/Trade (%)", shrink=0.85)
    ax.set_title(f"0034 {NAME} — Robustheit je Fenster-Verschiebung", fontsize=12, fontweight="bold")
    plotting._add_caption(fig, "Netto-Expectancy/Trade (%) bei Start-(Spalte)/Ende-(Zeile)-Verschiebung. Schwarz = Seasonax-Fenster. Permutation + Roll-Check entscheiden.")
    plotting.savefig(fig, PLOTS / "robustness_heatmap.png")

    def slim(e): return {"metrics": e["metrics"], "trades": e["trades"], "exposure": e["exposure"], "psr": e["psr"]}
    summary = {"ticker": TICKER, "name": NAME, "window": {"start": list(START_MD), "end": list(END_MD), "wraps_year": False},
               "sample": {"first_year": first_year, "last_year": last_year, "mid_year": mid_year, "split_date": split_date},
               "n_trials_charged": n_trials, "full_sample": slim(base_full), "in_sample": slim(base_is), "out_of_sample": slim(base_oos),
               "buy_hold_full": bh,
               "significance_full": {"permutation": perm, "bootstrap_sharpe_ci": boot, "t_test": ttest, "psr_deflated": base_full["psr"]},
               "robustness": {"shifts": shifts, "expectancy_pct": exp_grid.tolist(), "positive_cells": int(np.sum(exp_grid > 0)), "total_cells": int(exp_grid.size)},
               "roll_check": {"roll_zones": [[list(a), list(b)] for (a, b) in ROLL_ZONES], **rc}}
    with open(RESULTS / "metrics.json", "w") as fh: json.dump(summary, fh, indent=2, default=str)
    base_full["res"]["trades"].to_csv(RESULTS / "trades.csv", index=False)
    fm = base_full["metrics"]
    with open(RESULTS / "card.json", "w") as fh:
        json.dump({"id": "0034", "label": f"{NAME} Fenster 8.6.-3.7.", "cagr": fm["cagr"],
                   "annual_volatility": fm["annual_volatility"], "sharpe": fm["sharpe"], "max_drawdown": fm["max_drawdown"], "is_strategy": True}, fh, indent=2)

    print(f"\n  Rule: long 8.6..3.7 each year, {TICKER}\n")
    print(fmt_block(f"FULL {first_year}-{last_year}", base_full))
    print(fmt_block(f"IN-SAMPLE -{mid_year}", base_is))
    print(fmt_block(f"OUT-OF-SAMPLE {mid_year}-", base_oos))
    print(f"  Buy & Hold: CAGR {bh['cagr']:.2%}  Sharpe {bh['sharpe']:.2f}  MaxDD {bh['max_drawdown']:.2%}")
    print(f"\n  Significance: Permutation p {perm['p_value']:.3f}  Bootstrap Sharpe CI [{boot['ci_low']:.2f},{boot['ci_high']:.2f}]  t-test p {ttest['p_value']:.3f}")
    print(f"    DSR-PSR {base_full['psr']:.3f} (n_trials={n_trials})  Robustness {int(np.sum(exp_grid>0))}/{exp_grid.size}")
    print(f"\n  ROLL-DAY CHECK (mandatory 0029) — roll zone 29.6.-2.7.:")
    print(f"    Share of mean trade PnL on roll days: {rc['share_on_roll']:.0%}")
    b, c = rc["base"], rc["cleaned"]
    print(f"    {'variant':>16} {'exp%':>7} {'win':>5} {'sharpe':>7} {'perm_p':>7} {'expIS%':>7} {'expOOS%':>8}")
    print(f"    {'BASE (all days)':>16} {b['exp']:>7.2f} {b['win']:>5.0%} {b['sharpe']:>7.2f} {b['perm_p']:>7.3f} {b['exp_is']:>7.2f} {b['exp_oos']:>8.2f}")
    print(f"    {'roll EXCLUDED':>16} {c['exp']:>7.2f} {c['win']:>5.0%} {c['sharpe']:>7.2f} {c['perm_p']:>7.3f} {c['exp_is']:>7.2f} {c['exp_oos']:>8.2f}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
