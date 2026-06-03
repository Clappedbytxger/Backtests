"""Strategy 0006 — Gasoline spring window: a proper FORWARD TEST of the 0005 lead.

0005 scanned 156 short windows per commodity in-sample (2000-2015) and found ONE
that also held out-of-sample: gasoline futures (RB=F) long in ISO week 9 (~early
March). Because it was the best of many windows, it could be the lucky 1-of-8
false positive. The honest next step is a **forward test**: take the rule fixed on
old data and run it on data that played NO role in choosing it.

Splits used here:
  * **Discovery** 2000-2015 — the only data that picked "week 9". (Context.)
  * **Forward**   2016-2026 — unseen by the window choice; the forward test.
  * **Recent holdout** last 5 years — the purest forward slice (also never used
    to pick gasoline among the 8 assets).

Because a forward test evaluates ONE pre-committed rule, there is no search
burden: the Deflated Sharpe uses n_trials=1 (≈ probabilistic Sharpe).

We also probe robustness — a real edge should survive small changes to the entry
day within the week, the holding length and thus the exit day; a knife-edge that
only works on one exact configuration is noise.

Run:
    .venv/Scripts/python.exe strategies/0006_gasoline_forward_test/run.py
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
from quantlab.costs import IBKR_FUTURES  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.seasonal import add_calendar_features  # noqa: E402
from quantlab import plotting  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

TICKER = "RB=F"
NAME = "Benzin (RBOB-Futures)"
ISO_WEEK = 9              # pre-committed from 0005 in-sample scan
BASE_OFFSET = 0          # entry on the first trading day of week 9
BASE_HOLD = 5            # hold ~one trading week
DISCOVERY_END = "2015-12-31"
FORWARD_START = "2016-01-01"
RECENT_YEARS = 5


def event_signal(index, iso_week=ISO_WEEK, entry_offset=0, hold_days=BASE_HOLD,
                 name="rb_event") -> pd.Series:
    """One trade per year: long for ``hold_days`` trading days starting at the
    first trading day of ``iso_week`` (shifted by ``entry_offset`` days).

    Decision-time signal; the engine applies the T+1 execution shift, so no
    look-ahead. ``entry_offset`` < 0 enters earlier (late week 8), > 0 later.
    """
    idx = pd.DatetimeIndex(index)
    feats = add_calendar_features(idx)
    weeks = feats["week"].values
    years = idx.year.values
    pos = np.zeros(len(idx))
    for y in np.unique(years):
        locs = np.where((years == y) & (weeks == iso_week))[0]
        if len(locs) == 0:
            continue
        start = max(0, locs[0] + entry_offset)
        end = min(len(idx), start + hold_days)
        pos[start:end] = 1.0
    return pd.Series(pos, index=idx, name=name)


def evaluate(prices: pd.DataFrame, signal: pd.Series, n_trials: int = 1) -> dict:
    """Full metric bundle for one (prices, signal) pair."""
    res = run_backtest(prices, signal, cost_model=IBKR_FUTURES)
    rets = res["returns"]
    m = compute_metrics(rets)
    ts = trade_stats(res["trades"])
    sp = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) else 0.0
    dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(rets),
                                n_trials=n_trials, returns=rets)
    return {
        "metrics": m, "trades": ts,
        "exposure": float(res["position"].abs().mean()),
        "psr": dsr["psr_deflated"],
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
    print(f"Strategy 0006 — Gasoline week-{ISO_WEEK} forward test ({TICKER})")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    prices = get_prices(TICKER, start="2000-01-01")
    disc = prices.loc[:DISCOVERY_END]
    fwd = prices.loc[FORWARD_START:]
    recent_start = f"{prices.index[-1].year - RECENT_YEARS + 1}-01-01"
    recent = prices.loc[recent_start:]

    base_disc = evaluate(disc, event_signal(disc.index))
    base_fwd = evaluate(fwd, event_signal(fwd.index))
    base_recent = evaluate(recent, event_signal(recent.index))

    # Forward significance: one pre-committed rule, so no search burden.
    fwd_rets = base_fwd["returns"]
    perm = permutation_test(fwd_rets, fwd["Close"].pct_change().fillna(0.0),
                            base_fwd["res"]["position"], n_perm=2000)
    boot = bootstrap_ci(fwd_rets, statistic="sharpe", n_boot=2000)

    # --- Robustness grid over (entry_offset, hold_days) on the FORWARD period --
    offsets = list(range(-3, 6))          # buy earlier/later within the week
    holds = [2, 3, 5, 8, 10, 13]          # holding length (=> exit point)
    exp_grid = np.full((len(holds), len(offsets)), np.nan)   # expectancy/trade %
    shp_grid = np.full((len(holds), len(offsets)), np.nan)   # annualized Sharpe
    for i, h in enumerate(holds):
        for j, off in enumerate(offsets):
            e = evaluate(fwd, event_signal(fwd.index, entry_offset=off, hold_days=h))
            exp_grid[i, j] = e["trades"]["expectancy"] * 100.0
            shp_grid[i, j] = e["metrics"]["sharpe"]

    import matplotlib.pyplot as plt

    # Plot 1: equity curve of THIS strategy only (forward period).
    plotting.savefig(
        plotting.plot_equity(
            (1 + fwd_rets).cumprod(),
            title=f"0006 Benzin Saison-Fenster KW{ISO_WEEK} — Forward-Test Kapitalkurve (ab 2016)",
            strategy_label=f"Benzin KW{ISO_WEEK} (long, ~1 Woche/Jahr)",
            caption=("Nur diese Strategie: jedes Jahr ~5 Handelstage ab Anfang ISO-Woche 9 "
                     "long im Benzin-Future, sonst flat, netto nach Kosten. Die Regel wurde "
                     "2000–2015 fixiert; gezeigt ist die Auszahlung auf den danach folgenden, "
                     "bei der Fenster-Wahl ungesehenen Jahren (echter Forward-Test).")),
        PLOTS / "forward_equity.png")

    # Plot 2: per-year trade returns (forward) — the intuitive "how often it works".
    trades = base_fwd["res"]["trades"].copy()
    trades["year"] = pd.to_datetime(trades["entry_date"]).dt.year
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = ["#2a9d8f" if p > 0 else "#e76f51" for p in trades["pnl"]]
    ax.bar(trades["year"], trades["pnl"] * 100.0, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Netto-Rendite pro Jahres-Trade (%)")
    ax.set_title(f"0006 Benzin KW{ISO_WEEK} — Rendite je Jahres-Trade (Forward, netto)",
                 fontsize=12, fontweight="bold")
    win = (trades["pnl"] > 0).mean()
    plotting._add_caption(fig, (
        f"Jeder Balken = ein Jahres-Trade (~5 Tage long Anfang März). Grün = Gewinn. "
        f"Trefferquote {win:.0%} über {len(trades)} Forward-Trades. Wenige, aber "
        f"überwiegend positive Trades — die niedrige Trade-Zahl bleibt die Hauptschwäche."))
    plotting.savefig(fig, PLOTS / "per_year_trades.png")

    # Plot 3: robustness heatmap — expectancy per trade across entry/hold.
    fig, ax = plt.subplots(figsize=(11, 5))
    vmax = np.nanmax(np.abs(exp_grid))
    im = ax.imshow(exp_grid, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(offsets)))
    ax.set_xticklabels(offsets)
    ax.set_yticks(range(len(holds)))
    ax.set_yticklabels(holds)
    ax.set_xlabel("Einstiegs-Offset (Handelstage relativ zum Start von KW9)")
    ax.set_ylabel("Haltedauer (Handelstage)")
    for i in range(len(holds)):
        for j in range(len(offsets)):
            ax.text(j, i, f"{exp_grid[i, j]:.1f}", ha="center", va="center",
                    fontsize=7, color="black")
    bj, bi = offsets.index(BASE_OFFSET), holds.index(BASE_HOLD)
    ax.add_patch(plt.Rectangle((bj - 0.5, bi - 0.5), 1, 1, fill=False,
                               edgecolor="black", linewidth=2.5))
    fig.colorbar(im, ax=ax, label="Expectancy pro Trade (%)", shrink=0.85)
    ax.set_title(f"0006 Benzin KW{ISO_WEEK} — Robustheit: Expectancy je Einstieg/Haltedauer (Forward)",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Erwartete Netto-Rendite pro Trade (%) für jede Kombination aus Einstiegstag "
        "(Spalte) und Haltedauer (Zeile), auf den Forward-Jahren. Schwarz umrandet = "
        "vorab fixierte Basis-Regel. Ein zusammenhängendes grünes Feld = robuster Effekt; "
        "ein einzelner grüner Fleck = fragiler Zufall."))
    plotting.savefig(fig, PLOTS / "robustness_heatmap.png")

    # --- Persist ------------------------------------------------------------
    def slim(e):
        return {"metrics": e["metrics"], "trades": e["trades"], "exposure": e["exposure"],
                "psr": e["psr"]}
    summary = {
        "ticker": TICKER, "iso_week": ISO_WEEK,
        "base_rule": {"entry_offset": BASE_OFFSET, "hold_days": BASE_HOLD},
        "discovery": slim(base_disc),
        "forward": slim(base_fwd),
        "recent_holdout": {"start": recent_start, **slim(base_recent)},
        "forward_significance": {"permutation": perm, "bootstrap_sharpe_ci": boot,
                                 "psr_n_trials_1": base_fwd["psr"]},
        "robustness": {
            "offsets": offsets, "holds": holds,
            "expectancy_pct": exp_grid.tolist(), "sharpe": shp_grid.tolist(),
        },
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    (1 + fwd_rets).cumprod().rename("equity").to_csv(RESULTS / "equity.csv")
    base_fwd["res"]["trades"].to_csv(RESULTS / "trades.csv", index=False)
    fm = base_fwd["metrics"]
    card = {
        "id": "0006", "label": f"Benzin Saison KW{ISO_WEEK} (Forward-Test)",
        "cagr": fm["cagr"], "annual_volatility": fm["annual_volatility"],
        "sharpe": fm["sharpe"], "max_drawdown": fm["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    # --- Console ------------------------------------------------------------
    print(f"\n  Rule: long ISO week {ISO_WEEK}, hold {BASE_HOLD} trading days, {TICKER}\n")
    print(fmt_block("DISCOVERY 2000-2015 (chose the window)", base_disc))
    print(fmt_block("FORWARD 2016-2026 (unseen by window choice)", base_fwd))
    print(fmt_block(f"RECENT HOLDOUT {recent_start[:4]}-2026 (purest)", base_recent))
    print("  Forward significance (single pre-committed rule, n_trials=1):")
    print(f"    Permutation p {perm['p_value']:.3f}   "
          f"Bootstrap Sharpe CI [{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]   "
          f"PSR {base_fwd['psr']:.3f}")
    pos_cells = int(np.sum(exp_grid > 0))
    print(f"\n  Robustness: {pos_cells}/{exp_grid.size} entry/hold combos have "
          f"positive expectancy (forward).")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
