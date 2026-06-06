"""Strategy 0031 — Palladium turn-of-year window 6 Dec–25 Jan (Seasonax lead).

Full honesty harness (0028) PLUS the mandatory roll-day check (0029), on the NYMEX
palladium front-month future `PA=F`. User-supplied Seasonax window: **6 Dec to 25
Jan** (wraps the year boundary; ~35 trading days). IS/OOS split at 1 July (never
bisects a Dec->Jan window).

Roll relevance is real here (unlike corn 0030): palladium delivery months are
Mar/Jun/Sep/Dec; the December contract's last trading day is ~late December, so a
Dec->Mar roll falls *inside* the window — the same structure platinum's 0019 had to
clear. The roll-zone exclusion test (late Dec) is therefore decisive.

Macro rationale: palladium is the PGM sister to platinum (0018/0021). Same turn-of-
year drivers — auto-catalyst restocking at the year start + jewelry/industrial
demand into Chinese New Year. NOTE: this shares its driver with 0018/0021/0023, so
it is *correlated*, not independent, evidence; palladium already passed as the
cross-asset OOS leg in 0021 (platinum window on PA=F: 93% win, p=0.004).

Guards: non-positive close (0005) + frozen-feed check (<50 distinct closes/yr, 0025).

Run:
    .venv/Scripts/python.exe strategies/0031_palladium_turn_of_year/run.py
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

TICKER = "PA=F"
NAME = "Palladium (Palladium-Future)"
START_MD = (12, 6)          # 6 December — pre-committed from Seasonax
END_MD = (1, 25)            # 25 January (next year — window wraps)
COST_MODEL = IBKR_FUTURES

# Suspected roll/expiry zone inside the window: Dec contract LTD ~ late December.
ROLL_ZONES = [((12, 24), (12, 31))]


def in_roll_zone(m: int, d: int) -> bool:
    return any(lo <= (m, d) <= hi for (lo, hi) in ROLL_ZONES)


def date_window_signal(index, start_md=START_MD, end_md=END_MD,
                       start_shift=0, end_shift=0, exclude_roll=False,
                       name="palladium_toy") -> pd.Series:
    """Long (1.0) from 6 Dec -> 25 Jan each winter, else flat (wrap-aware)."""
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    same_year = tuple(end_md) > tuple(start_md)
    for y in range(int(idx.year.min()) - 1, int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *start_md) + pd.Timedelta(days=start_shift)
        end_year = y if same_year else y + 1
        end = pd.Timestamp(end_year, *end_md) + pd.Timedelta(days=end_shift)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
    if exclude_roll:
        roll_mask = np.array([in_roll_zone(t.month, t.day) for t in idx])
        pos[roll_mask] = 0.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(prices: pd.DataFrame, signal: pd.Series, n_trials: int = 1) -> dict:
    res = run_backtest(prices, signal, cost_model=COST_MODEL)
    rets = res["returns"]
    m = compute_metrics(rets)
    ts = trade_stats(res["trades"])
    sp = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) else 0.0
    dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(rets),
                                n_trials=max(1, n_trials), returns=rets)
    return {"metrics": m, "trades": ts, "exposure": float(res["position"].abs().mean()),
            "psr": dsr["psr_deflated"],
            "expected_max_sharpe_null": dsr["expected_max_sharpe_under_null"],
            "returns": rets, "res": res}


def fmt_block(label: str, e: dict) -> str:
    m, ts = e["metrics"], e["trades"]
    pnl = e["res"]["trades"]["pnl"]
    median = float(pnl.median()) if len(pnl) else float("nan")
    return (
        f"  [{label}]\n"
        f"    CAGR {m['cagr']:.2%}   Sharpe {m['sharpe']:.2f}   Sortino {m['sortino']:.2f}"
        f"   MaxDD {m['max_drawdown']:.2%}\n"
        f"    Trades {ts['n_trades']}   Win {ts['win_rate']:.0%}   PF {ts['profit_factor']:.2f}"
        f"   Expectancy/Trade {ts['expectancy']:.2%}   Median/Trade {median:.2%}   "
        f"AvgHold {ts['avg_holding_days']:.1f}d   Exposure {e['exposure']:.1%}\n"
    )


def roll_check(prices: pd.DataFrame, asset_ret: pd.Series, split_date: str) -> dict:
    """0029-style: does the edge survive removing the in-window roll/expiry zone?"""
    def bundle(exclude_roll: bool) -> dict:
        sig = date_window_signal(prices.index, exclude_roll=exclude_roll)
        e = evaluate(prices, sig)
        perm = permutation_test(e["returns"], asset_ret, e["res"]["position"], n_perm=2000)
        boot = bootstrap_ci(e["returns"], statistic="sharpe", n_boot=2000)
        e_is = evaluate(prices.loc[:split_date],
                        date_window_signal(prices.loc[:split_date].index, exclude_roll=exclude_roll))
        e_oos = evaluate(prices.loc[split_date:],
                         date_window_signal(prices.loc[split_date:].index, exclude_roll=exclude_roll))
        return {"exp": e["trades"]["expectancy"] * 100, "win": e["trades"]["win_rate"],
                "sharpe": e["metrics"]["sharpe"], "perm_p": perm["p_value"],
                "boot_lo": boot["ci_low"], "exp_is": e_is["trades"]["expectancy"] * 100,
                "exp_oos": e_oos["trades"]["expectancy"] * 100}

    base, cleaned = bundle(False), bundle(True)

    held = date_window_signal(prices.index).shift(1).fillna(0.0) > 0
    winters, days = {}, {}
    prev, cy = False, None
    for dt, fl in held.items():
        if fl:
            if not prev:
                cy = dt.year if dt.month >= 7 else dt.year - 1
                winters[cy], days[cy] = [], []
            winters[cy].append(asset_ret.loc[dt]); days[cy].append((dt.month, dt.day))
        prev = fl
    full_m, roll_m = [], []
    for yr in winters:
        rs = np.array(winters[yr]); isr = np.array([in_roll_zone(m, d) for (m, d) in days[yr]])
        full_m.append(np.prod(1 + rs) - 1)
        roll_m.append((np.prod(1 + rs[isr]) - 1) if isr.any() else 0.0)
    share = float(np.mean(roll_m) / np.mean(full_m)) if np.mean(full_m) else float("nan")
    return {"base": base, "cleaned": cleaned, "share_on_roll": share}


def main() -> None:
    print(f"Strategy 0031 — {NAME} turn-of-year window (6.12..25.1, {TICKER})")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    prices = get_prices(TICKER, start="2000-01-01")
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{TICKER}: non-positive close — abort (0005).")
    if int(prices["Close"].groupby(prices.index.year).nunique().min()) < 50:
        raise SystemExit(f"{TICKER}: frozen-feed suspect (<50 distinct/yr) — abort (0025).")

    asset_ret = prices["Close"].pct_change().fillna(0.0)
    first_year, last_year = int(prices.index[0].year), int(prices.index[-1].year)
    mid_year = (first_year + last_year) // 2
    split_date = f"{mid_year}-07-01"   # mid-year cut never bisects a Dec->Jan window
    print(f"  Data: {prices.index[0].date()}..{prices.index[-1].date()}; IS<{split_date}, OOS>=")

    is_p, oos_p = prices.loc[:split_date], prices.loc[split_date:]

    shifts = list(range(-10, 11, 2))
    n_trials = len(shifts) ** 2
    exp_grid = np.full((len(shifts), len(shifts)), np.nan)
    for i, es in enumerate(shifts):
        for j, ss in enumerate(shifts):
            e = evaluate(prices, date_window_signal(prices.index, start_shift=ss, end_shift=es))
            exp_grid[i, j] = e["trades"]["expectancy"] * 100

    base_full = evaluate(prices, date_window_signal(prices.index), n_trials=n_trials)
    base_is = evaluate(is_p, date_window_signal(is_p.index), n_trials=n_trials)
    base_oos = evaluate(oos_p, date_window_signal(oos_p.index), n_trials=n_trials)
    bh = compute_metrics(asset_ret)

    perm = permutation_test(base_full["returns"], asset_ret, base_full["res"]["position"], n_perm=2000)
    boot = bootstrap_ci(base_full["returns"], statistic="sharpe", n_boot=2000)
    ttest = t_test_mean_return(base_full["returns"])
    rc = roll_check(prices, asset_ret, split_date)

    # --- Plots ---
    import matplotlib.pyplot as plt
    plotting.savefig(
        plotting.plot_equity(
            base_full["res"]["equity"], benchmark=base_full["res"]["buy_hold"],
            title=f"0031 {NAME} — Jahreswechsel 6.12.–25.1. vs. Buy & Hold (gesamt)",
            strategy_label="Fenster (long 6.12.–25.1., sonst flat)",
            benchmark_label=f"{NAME} Buy & Hold",
            caption=("Nur ~35 Handelstage/Jahr long im NYMEX-Palladium-Future, sonst flat, netto nach "
                     "IBKR-Futures-Kosten. Fenster von Seasonax gewählt → in-sample geschönt. "
                     "Aussagekräftig: Permutation, OOS-Hälfte, Robustheit, Roll-Tag-Check (Dez-Roll im "
                     "Fenster). Treiber = PGM-Schwester zu Platin (0018/0021): Jahresstart-Restocking + CNY.")),
        PLOTS / "equity_vs_bh.png")

    trades = base_full["res"]["trades"].copy()
    trades["year"] = pd.to_datetime(trades["entry_date"]).dt.year
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(trades["year"], trades["pnl"] * 100,
           color=["#2a9d8f" if p > 0 else "#e76f51" for p in trades["pnl"]])
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Netto-Rendite pro Trade (%)")
    ax.set_title(f"0031 {NAME} — Rendite je Jahreswechsel-Trade (netto)", fontsize=12, fontweight="bold")
    plotting._add_caption(fig, f"Jeder Balken = ein Trade (~35 Tage, Einstieg im Dez.). Trefferquote "
                               f"{(trades['pnl'] > 0).mean():.0%} über {len(trades)} Trades.")
    plotting.savefig(fig, PLOTS / "per_year_trades.png")

    fig, ax = plt.subplots(figsize=(9.5, 7.5))
    vmax = np.nanmax(np.abs(exp_grid))
    im = ax.imshow(exp_grid, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(shifts))); ax.set_xticklabels(shifts)
    ax.set_yticks(range(len(shifts))); ax.set_yticklabels(shifts)
    ax.set_xlabel("Verschiebung Start (Tage, 0 = 6. Dez.)")
    ax.set_ylabel("Verschiebung Ende (Tage, 0 = 25. Jan.)")
    for i in range(len(shifts)):
        for j in range(len(shifts)):
            ax.text(j, i, f"{exp_grid[i, j]:.1f}", ha="center", va="center", fontsize=6.5)
    ax.add_patch(plt.Rectangle((shifts.index(0) - 0.5, shifts.index(0) - 0.5), 1, 1,
                               fill=False, edgecolor="black", linewidth=2.5))
    fig.colorbar(im, ax=ax, label="Expectancy/Trade (%)", shrink=0.85)
    ax.set_title(f"0031 {NAME} — Robustheit je Fenster-Verschiebung", fontsize=12, fontweight="bold")
    plotting._add_caption(fig, "Netto-Expectancy/Trade (%) bei Verschiebung Start (Spalte)/Ende (Zeile). "
                               "Schwarz = Seasonax-Fenster. Driftarmes PGM → Plateau aussagekräftig; "
                               "Permutation + Roll-Check entscheiden.")
    plotting.savefig(fig, PLOTS / "robustness_heatmap.png")

    # --- Persist ---
    def slim(e):
        return {"metrics": e["metrics"], "trades": e["trades"], "exposure": e["exposure"], "psr": e["psr"]}
    summary = {
        "ticker": TICKER, "name": NAME,
        "window": {"start": list(START_MD), "end": list(END_MD), "wraps_year": True},
        "sample": {"first_year": first_year, "last_year": last_year, "mid_year": mid_year,
                   "split_date": split_date},
        "n_trials_charged": n_trials,
        "full_sample": slim(base_full), "in_sample": slim(base_is), "out_of_sample": slim(base_oos),
        "buy_hold_full": bh,
        "significance_full": {"permutation": perm, "bootstrap_sharpe_ci": boot, "t_test": ttest,
                              "psr_deflated": base_full["psr"],
                              "expected_max_sharpe_null": base_full["expected_max_sharpe_null"]},
        "robustness": {"shifts": shifts, "expectancy_pct": exp_grid.tolist(),
                       "positive_cells": int(np.sum(exp_grid > 0)), "total_cells": int(exp_grid.size)},
        "roll_check": {"roll_zones": [[list(a), list(b)] for (a, b) in ROLL_ZONES], **rc},
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    base_full["res"]["trades"].to_csv(RESULTS / "trades.csv", index=False)
    base_full["res"]["equity"].rename("equity").to_csv(RESULTS / "equity.csv")
    fm = base_full["metrics"]
    with open(RESULTS / "card.json", "w") as fh:
        json.dump({"id": "0031", "label": f"{NAME} Jahreswechsel 6.12.-25.1.",
                   "cagr": fm["cagr"], "annual_volatility": fm["annual_volatility"],
                   "sharpe": fm["sharpe"], "max_drawdown": fm["max_drawdown"], "is_strategy": True}, fh, indent=2)

    # --- Console ---
    print(f"\n  Rule: long 6.12..25.1 each winter, {TICKER}\n")
    print(fmt_block(f"FULL {first_year}-{last_year} (Seasonax view, in-sample)", base_full))
    print(fmt_block(f"IN-SAMPLE -{mid_year}", base_is))
    print(fmt_block(f"OUT-OF-SAMPLE {mid_year}-", base_oos))
    print(f"  Buy & Hold (full): CAGR {bh['cagr']:.2%}  Sharpe {bh['sharpe']:.2f}  MaxDD {bh['max_drawdown']:.2%}")
    print("\n  Significance (full sample):")
    print(f"    Permutation p {perm['p_value']:.3f}   Bootstrap Sharpe CI [{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]   t-test p {ttest['p_value']:.3f}")
    print(f"    DSR charged n_trials={n_trials}: PSR {base_full['psr']:.3f}")
    print(f"    Robustness: {int(np.sum(exp_grid > 0))}/{exp_grid.size} shifts positive")
    print("\n  ROLL-DAY CHECK (mandatory, lesson 0029) — roll zone 24.-31.12.:")
    print(f"    Share of mean trade PnL on roll days: {rc['share_on_roll']:.0%}")
    b, c = rc["base"], rc["cleaned"]
    print(f"    {'variant':>16} {'exp%':>7} {'win':>5} {'sharpe':>7} {'perm_p':>7} {'expIS%':>7} {'expOOS%':>8}")
    print(f"    {'BASE (all days)':>16} {b['exp']:>7.2f} {b['win']:>5.0%} {b['sharpe']:>7.2f} {b['perm_p']:>7.3f} {b['exp_is']:>7.2f} {b['exp_oos']:>8.2f}")
    print(f"    {'roll EXCLUDED':>16} {c['exp']:>7.2f} {c['win']:>5.0%} {c['sharpe']:>7.2f} {c['perm_p']:>7.3f} {c['exp_is']:>7.2f} {c['exp_oos']:>8.2f}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
