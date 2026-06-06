"""Strategy 0032 — Corn WASDE core 8–18 Dec (pre-registered refinement of 0030).

0030 showed the corn December edge (perm p=0.000, no roll stitch) but found ~60%
of it concentrated in 11-16 Dec, collapsing to p=0.093 once those days are removed.
The natural question: is that cluster a *nameable* event effect or just noise that
happened to win? This script pre-registers a **tight, event-driven** window around
the **December WASDE report** (USDA World Agricultural Supply & Demand Estimates,
released ~9-12 Dec — the year's last major US crop reckoning) plus a few digestion
days: **8 to 18 December**. The window is fixed *before* this run from the event
calendar, not re-mined from ZC=F's daily returns (the 15-Dec spike merely motivated
looking; the WASDE date defines the window).

Two independent validations decide whether this is a real ag-complex turn-of-year
effect or a corn-only fluke — both apply the *frozen* 8-18 Dec window with NO
re-fitting (the 0021 cross-instrument method):

  1. **CORN** — Teucrium corn ETF (2010+). A basket/fund, not a single front-month
     future → independent of any continuous-stitch concern.
  2. **ZW=F wheat, ZS=F soybeans** — sibling CBOT grains sharing the same WASDE
     driver. If the window works across the complex, it is a real event seasonal.

Guards: non-positive close (0005) + frozen-feed (<50 distinct/yr, 0025).

Run:
    .venv/Scripts/python.exe strategies/0032_corn_wasde_core/run.py
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

PRIMARY = ("ZC=F", "Mais (Corn-Future)")
CROSS = [("CORN", "Mais-ETF (Teucrium)"), ("ZW=F", "Weizen (Wheat)"), ("ZS=F", "Sojabohnen (Soybeans)")]
START_MD = (12, 8)          # pre-registered: WASDE (~9-12 Dec) + digestion
END_MD = (12, 18)
COST_MODEL = IBKR_FUTURES


def date_window_signal(index, start_shift=0, end_shift=0, name="corn_wasde") -> pd.Series:
    idx = pd.DatetimeIndex(index)
    pos = np.zeros(len(idx))
    for y in range(int(idx.year.min()), int(idx.year.max()) + 1):
        start = pd.Timestamp(y, *START_MD) + pd.Timedelta(days=start_shift)
        end = pd.Timestamp(y, *END_MD) + pd.Timedelta(days=end_shift)
        mask = (idx >= start) & (idx <= end)
        pos[np.asarray(mask)] = 1.0
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


def full_eval(ticker, n_trials=1, split_frac=0.5):
    prices = get_prices(ticker, start="2000-01-01")
    if (prices["Close"] <= 0).any():
        raise SystemExit(f"{ticker}: non-positive close (0005).")
    if int(prices["Close"].groupby(prices.index.year).nunique().min()) < 50:
        raise SystemExit(f"{ticker}: frozen feed (0025).")
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    yrs = prices.index.year
    mid = int((yrs.min() + yrs.max()) // 2)
    split = f"{mid}-01-01"
    e = evaluate(prices, date_window_signal(prices.index), n_trials=n_trials)
    e_is = evaluate(prices.loc[:split], date_window_signal(prices.loc[:split].index))
    e_oos = evaluate(prices.loc[split:], date_window_signal(prices.loc[split:].index))
    perm = permutation_test(e["returns"], asset_ret, e["res"]["position"], n_perm=2000)
    boot = bootstrap_ci(e["returns"], statistic="sharpe", n_boot=2000)
    tt = t_test_mean_return(e["returns"])
    bh = compute_metrics(asset_ret)
    return {"prices": prices, "e": e, "e_is": e_is, "e_oos": e_oos, "perm": perm,
            "boot": boot, "tt": tt, "bh": bh, "split": split,
            "first": int(yrs.min()), "last": int(yrs.max())}


def main() -> None:
    print(f"Strategy 0032 — Corn WASDE core ({START_MD[1]}.{START_MD[0]}..{END_MD[1]}.{END_MD[0]})")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    # --- Primary: ZC=F with robustness grid (short window -> +/-6 step 2) -------
    tk, nm = PRIMARY
    prices = get_prices(tk, start="2000-01-01")
    shifts = list(range(-6, 7, 2))     # 7 -> 49 trials
    n_trials = len(shifts) ** 2
    exp_grid = np.full((len(shifts), len(shifts)), np.nan)
    for i, es in enumerate(shifts):
        for j, ss in enumerate(shifts):
            ee = evaluate(prices, date_window_signal(prices.index, start_shift=ss, end_shift=es))
            exp_grid[i, j] = ee["trades"]["expectancy"] * 100
    P = full_eval(tk, n_trials=n_trials)

    # --- Cross-instruments: frozen window, NO refit ----------------------------
    cross_results = {}
    for ctk, cnm in CROSS:
        try:
            cross_results[ctk] = {"name": cnm, **full_eval(ctk)}
        except SystemExit as ex:
            cross_results[ctk] = {"name": cnm, "error": str(ex)}

    # --- Console ---------------------------------------------------------------
    def line(tag, R):
        e, ts = R["e"], R["e"]["trades"]
        return (f"  {tag:28s} p={R['perm']['p_value']:.3f}  exp/trade {ts['expectancy']*100:+6.2f}%  "
                f"win {ts['win_rate']:.0%}  Sharpe {e['metrics']['sharpe']:.2f}  "
                f"bootCI[{R['boot']['ci_low']:.2f},{R['boot']['ci_high']:.2f}]  "
                f"n={ts['n_trades']} ({R['first']}-{R['last']})")
    print(f"\n  PRE-REGISTERED window {START_MD[1]}.{START_MD[0]}.-{END_MD[1]}.{END_MD[0]}. (WASDE event), frozen across all\n")
    print("  PRIMARY:")
    print(line(f"{tk} {nm}", P))
    print(f"    IS exp {P['e_is']['trades']['expectancy']*100:+.2f}%  OOS exp {P['e_oos']['trades']['expectancy']*100:+.2f}%  "
          f"| B&H Sharpe {P['bh']['sharpe']:.2f}  DSR-PSR {P['e']['psr']:.3f} (n_trials={n_trials})")
    print(f"    Robustness: {int(np.sum(exp_grid>0))}/{exp_grid.size} shifts positive")
    print("\n  CROSS-INSTRUMENT (frozen window, NO refit):")
    for ctk, R in cross_results.items():
        if "error" in R:
            print(f"  {ctk:28s} ERROR {R['error']}")
        else:
            print(line(f"{ctk} {R['name']}", R))

    # --- Plots -----------------------------------------------------------------
    import matplotlib.pyplot as plt
    plotting.savefig(
        plotting.plot_equity(
            P["e"]["res"]["equity"], benchmark=P["e"]["res"]["buy_hold"],
            title=f"0032 {nm} — WASDE-Kern 8.–18.12. vs. Buy & Hold (gesamt)",
            strategy_label="Fenster (long 8.–18.12., sonst flat)", benchmark_label=f"{nm} Buy & Hold",
            caption=("Enges, vorab auf den Dezember-WASDE-Bericht (~9.–12. Dez.) fixiertes Fenster, "
                     "~8 Handelstage/Jahr long, netto. Validierung über CORN-ETF + Weizen/Soja mit "
                     "demselben eingefrorenen Fenster ohne Re-Fitting (siehe Konsole/metrics.json).")),
        PLOTS / "equity_vs_bh.png")

    # Cross-instrument significance bars.
    labels, ps, exps = [], [], []
    for ctk, R in [(tk, {"name": nm, **P})] + list(cross_results.items()):
        if "error" in R:
            continue
        labels.append(ctk)
        ps.append(R["perm"]["p_value"])
        exps.append(R["e"]["trades"]["expectancy"] * 100)
    fig, ax1 = plt.subplots(figsize=(9, 5))
    xs = range(len(labels))
    ax1.bar(xs, exps, color="#2a9d8f", alpha=0.85)
    ax1.set_xticks(list(xs)); ax1.set_xticklabels(labels)
    ax1.set_ylabel("Expectancy/Trade (%)", color="#2a9d8f"); ax1.axhline(0, color="black", lw=0.8)
    ax2 = ax1.twinx()
    ax2.plot(list(xs), ps, "o-", color="#e76f51", lw=1.8)
    ax2.axhline(0.05, color="#e76f51", ls="--", lw=1.0); ax2.set_ylabel("Permutation p", color="#e76f51")
    ax2.set_ylim(0, max(0.2, max(ps) * 1.2))
    for i, p in enumerate(ps):
        ax2.annotate(f"{p:.3f}", (i, p), textcoords="offset points", xytext=(0, 7), ha="center",
                     fontsize=8, color="#e76f51")
    ax1.set_title("0032 Mais-WASDE-Kern — selbe eingefrorene Regel über die Ag-Komplex-Geschwister",
                  fontsize=11, fontweight="bold")
    plotting._add_caption(fig, "Grün: Netto-Expectancy/Trade. Rot: Permutation-p (gestrichelt = 5%). "
                               "Eingefrorenes Fenster 8.–18.12. ohne Re-Fitting. Hält es über CORN-ETF + "
                               "Weizen + Soja, ist es ein echter Ag-Komplex-WASDE-Effekt, kein Mais-Zufall.")
    plotting.savefig(fig, PLOTS / "cross_instrument.png")

    # --- Persist ---------------------------------------------------------------
    def slim(R):
        return {"perm_p": R["perm"]["p_value"], "boot_ci": [R["boot"]["ci_low"], R["boot"]["ci_high"]],
                "t_p": R["tt"]["p_value"], "expectancy_pct": R["e"]["trades"]["expectancy"] * 100,
                "win_rate": R["e"]["trades"]["win_rate"], "sharpe": R["e"]["metrics"]["sharpe"],
                "n_trades": R["e"]["trades"]["n_trades"], "bh_sharpe": R["bh"]["sharpe"],
                "exp_is": R["e_is"]["trades"]["expectancy"] * 100, "exp_oos": R["e_oos"]["trades"]["expectancy"] * 100,
                "years": [R["first"], R["last"]]}
    summary = {
        "window": {"start": list(START_MD), "end": list(END_MD)},
        "rationale": "pre-registered around December WASDE report (~9-12 Dec) + digestion",
        "n_trials_charged_primary": n_trials,
        "primary": {"ticker": tk, "name": nm, **slim(P), "psr": P["e"]["psr"],
                    "robustness_positive": int(np.sum(exp_grid > 0)), "robustness_total": int(exp_grid.size)},
        "cross_instrument": {ctk: ({"name": R["name"], "error": R["error"]} if "error" in R
                                   else {"name": R["name"], **slim(R)})
                             for ctk, R in cross_results.items()},
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
