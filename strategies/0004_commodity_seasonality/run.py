"""Strategy 0004 — Commodity seasonal supply/demand windows (broad screen).

Moves beyond equity indices to assets with a *real, physical* seasonal driver,
where a fundamental supply/demand cause makes a seasonal edge more plausible
than on broad stock indices (0001-0003). Inspired by tools like Seasonax, but
with honest cost modeling, a permutation test and a Deflated Sharpe that
corrects for the whole battery of assets screened.

Method (bias-aware):
  * Each long window is a **pre-specified macro hypothesis** from the asset's
    supply/demand cycle — NOT chosen from the price — so there is no in-sample
    selection bias on the window itself.
  * Evaluation is **out-of-sample from 2016** (the early ETF years are context
    only), net of IBKR costs.
  * Significance: per-asset permutation test vs random timing, plus one Deflated
    Sharpe across all assets screened (multiple-testing correction).
  * Honest limitation: ~1 trade/asset/year → low power; commodity ETFs also
    carry roll/contango decay, which is exactly why we test net tradeable ETF
    returns rather than idealized futures.

Run:
    .venv/Scripts/python.exe strategies/0004_commodity_seasonality/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import (  # noqa: E402
    compute_metrics, trade_stats, run_backtest,
    bootstrap_ci, deflated_sharpe_ratio, permutation_test,
)
from quantlab.costs import IBKR_DEFAULT  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.metrics import sharpe_ratio  # noqa: E402
from quantlab import plotting, seasonal  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"
OOS_START = "2016-01-01"

# Pre-specified macro-seasonal long windows (months), one hypothesis per asset.
ASSETS = {
    "UNG":  {"name": "Erdgas",          "months": [9, 10, 11, 12],
             "driver": "Heizsaison: Nachfrage und Lagerabbau bauen sich in den Winter auf"},
    "USO":  {"name": "Rohöl (WTI)",     "months": [2, 3, 4, 5],
             "driver": "Vorlauf zur US-Sommer-Fahrsaison (Driving Season)"},
    "UGA":  {"name": "Benzin",          "months": [2, 3, 4, 5],
             "driver": "US-Sommer-Fahrsaison treibt Benzinnachfrage"},
    "BNO":  {"name": "Rohöl (Brent)",   "months": [2, 3, 4, 5],
             "driver": "Globale Sommer-Treibstoffnachfrage"},
    "GLD":  {"name": "Gold",            "months": [8, 9, 10, 11, 12],
             "driver": "Indische Hochzeits-/Diwali- und chin. Neujahrs-Nachfrage"},
    "SLV":  {"name": "Silber",          "months": [8, 9, 10, 11, 12],
             "driver": "Folgt Gold + industrielle Nachfrage"},
    "CORN": {"name": "Mais",            "months": [3, 4, 5, 6],
             "driver": "Wetter-/Aussaat-Risikoprämie im Frühjahr"},
    "WEAT": {"name": "Weizen",          "months": [3, 4, 5, 6],
             "driver": "Winterweizen-Wetterrisiko bis ins Frühjahr"},
    "SOYB": {"name": "Sojabohnen",      "months": [4, 5, 6, 7],
             "driver": "Aussaat-/Wetterprämie im Frühsommer"},
    "DBA":  {"name": "Agrar (breit)",   "months": [3, 4, 5, 6],
             "driver": "Frühjahrs-Aussaatsaison breit über Agrarrohstoffe"},
}


def screen() -> dict:
    rows = []
    strat_returns = {}
    deep = {}
    for ticker, spec in ASSETS.items():
        try:
            prices = get_prices(ticker, start="2004-01-01")
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {ticker}: {exc}")
            continue
        oos = prices.loc[OOS_START:]
        if len(oos) < 252:
            continue
        sig = seasonal.month_window_signal(oos.index, spec["months"], name=ticker)
        res = run_backtest(oos, sig, cost_model=IBKR_DEFAULT)
        rets = res["returns"]
        m = compute_metrics(rets)
        ts = trade_stats(res["trades"])
        bh = oos["Close"].pct_change().dropna()
        perm = permutation_test(rets, oos["Close"].pct_change().fillna(0.0),
                                res["position"], n_perm=2000)
        rows.append({
            "ticker": ticker, "name": spec["name"],
            "window": "-".join(str(x) for x in spec["months"]),
            "sharpe": round(m["sharpe"], 2),
            "buyhold_sharpe": round(sharpe_ratio(bh), 2),
            "cagr": round(m["cagr"], 4),
            "max_drawdown": round(m["max_drawdown"], 4),
            "exposure": round(float(res["position"].abs().mean()), 3),
            "n_trades": ts["n_trades"],
            "win_rate": round(ts["win_rate"], 3),
            "perm_p": round(perm["p_value"], 3),
        })
        strat_returns[ticker] = rets
        deep[ticker] = {"oos": oos, "res": res}
    return {"panel": pd.DataFrame(rows), "returns": strat_returns, "deep": deep}


def main() -> None:
    print("Strategy 0004 — Commodity seasonal supply/demand windows")
    RESULTS.mkdir(parents=True, exist_ok=True)
    s = screen()
    panel = s["panel"].sort_values("sharpe", ascending=False).reset_index(drop=True)
    panel.to_csv(RESULTS / "screen_panel.csv", index=False)
    n_trials = len(panel)

    # Equal-weight portfolio of all seasonal commodity strategies (the 0004
    # "strategy" for the global comparison): diversifies the single-asset noise.
    ret_df = pd.DataFrame(s["returns"]).sort_index()
    port_ret = ret_df.mean(axis=1).fillna(0.0)
    port_m = compute_metrics(port_ret)
    port_perm = permutation_test(port_ret,
                                 port_ret, (port_ret != 0).astype(float), n_perm=2000)
    port_boot = bootstrap_ci(port_ret, statistic="sharpe", n_boot=2000)
    sp = port_ret.mean() / port_ret.std(ddof=1) if port_ret.std(ddof=1) else 0.0
    port_dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(port_ret),
                                     n_trials=n_trials, returns=port_ret)

    # --- Plots --------------------------------------------------------------
    # Bar chart: per-asset OOS Sharpe vs buy & hold.
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = range(len(panel))
    ax.bar([i - 0.2 for i in x], panel["sharpe"], width=0.4,
           label="Saison-Strategie", color="#2a9d8f")
    ax.bar([i + 0.2 for i in x], panel["buyhold_sharpe"], width=0.4,
           label="Buy & Hold", color="#b0b0b0")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(panel["name"], rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("OOS Sharpe Ratio")
    ax.set_title("0004 Saisonale Rohstoff-Fenster — Sharpe je Asset (OOS ab 2016)",
                 fontsize=12, fontweight="bold")
    ax.legend()
    plotting._add_caption(fig, (
        "OOS-Sharpe jeder vorab makro-begründeten Saison-Strategie (grün) vs. "
        "Buy & Hold (grau) je Rohstoff. Über Buy & Hold UND über null ist das "
        "Ziel — hier schafft das nur eine Minderheit, und mit ~1 Trade/Jahr ist "
        "die Aussagekraft je Asset gering."))
    plotting.savefig(fig, PLOTS / "sharpe_by_asset.png")

    plotting.savefig(
        plotting.plot_equity(
            (1 + port_ret).cumprod(),
            title="0004 Rohstoff-Saison-Portfolio (gleichgewichtet) — Kapitalkurve (OOS)",
            strategy_label="Rohstoff-Saison-Portfolio",
            caption=("Gleichgewichtetes Portfolio aller saisonalen Rohstoff-Strategien, "
                     "netto nach Kosten. Diversifikation über viele unkorrelierte "
                     "Rohstoffe glättet das Einzel-Asset-Rauschen.")),
        PLOTS / "portfolio_equity.png")

    # --- Persist ------------------------------------------------------------
    summary = {
        "oos_start": OOS_START,
        "n_assets": n_trials,
        "screen_panel": panel.to_dict(orient="records"),
        "portfolio_metrics": port_m,
        "portfolio_significance": {
            "permutation": port_perm,
            "bootstrap_sharpe_ci": port_boot,
            "deflated_sharpe": port_dsr,
        },
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    (1 + port_ret).cumprod().rename("equity").to_csv(RESULTS / "equity.csv")
    card = {
        "id": "0004", "label": "Rohstoff-Saison-Portfolio (10 Assets)",
        "cagr": port_m["cagr"], "annual_volatility": port_m["annual_volatility"],
        "sharpe": port_m["sharpe"], "max_drawdown": port_m["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    # --- Console ------------------------------------------------------------
    print("\n[seasonal screen — OOS from 2016, net of costs]")
    with pd.option_context("display.width", 160, "display.max_columns", None):
        print(panel.to_string(index=False))
    print("\n===== EQUAL-WEIGHT COMMODITY-SEASONAL PORTFOLIO =====")
    print(f"  CAGR            {port_m['cagr']:.2%}")
    print(f"  Sharpe          {port_m['sharpe']:.2f}")
    print(f"  Ann. vol        {port_m['annual_volatility']:.2%}")
    print(f"  Max Drawdown    {port_m['max_drawdown']:.2%}")
    print(f"  Permutation p   {port_perm['p_value']:.3f}")
    print(f"  Bootstrap Sharpe CI [{port_boot['ci_low']:.2f}, {port_boot['ci_high']:.2f}]")
    print(f"  Deflated Sharpe {port_dsr['psr_deflated']:.3f}  (n_trials={n_trials})")
    survivors = panel[(panel["sharpe"] > panel["buyhold_sharpe"]) & (panel["perm_p"] < 0.10)]
    print(f"\n  Assets beating B&H with perm p<0.10: "
          f"{', '.join(survivors['name']) if len(survivors) else 'none'}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
