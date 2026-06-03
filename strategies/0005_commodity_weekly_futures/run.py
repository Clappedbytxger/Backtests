"""Strategy 0005 — Short seasonal futures windows (in-sample scan, OOS validation).

Follows directly from 0004. There the commodity *ETFs* held a macro-seasonal
window for several months and bled from contango/roll decay (natural gas was the
worst trade despite the strongest fundamental story). Roll decay scales with
holding length, so this strategy isolates the *price* effect from the *carry*:

  * Trade the **front-month futures** (NG=F, CL=F, ...), not decay-prone ETFs.
  * Hold only a **short** window (1-3 ISO weeks, ~5-15 trading days), so a trade
    barely touches a roll date.
  * **Avoid data-mining honestly:** scan average weekly returns ONLY on the
    in-sample years (2000-2015) to pick each asset's best short window, then
    LOCK it and judge it purely out-of-sample (2016+). The Deflated Sharpe is
    charged the full multiple-testing burden of the scan (52 starts x 3 lengths
    = 156 windows per asset).

Caveat kept explicit: a yearly window is still ~1 trade/asset/year, so power
stays low; the short hold cleans each trade, it does not add trades.

Run:
    .venv/Scripts/python.exe strategies/0005_commodity_weekly_futures/run.py
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
from quantlab.metrics import sharpe_ratio  # noqa: E402
from quantlab import plotting, seasonal  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"
IS_END = "2015-12-31"
OOS_START = "2016-01-01"
K_RANGE = (1, 2, 3)             # candidate window lengths in ISO weeks
N_TRIALS = 52 * len(K_RANGE)    # multiple-testing burden of the per-asset scan

# Front-month continuous futures (yfinance), one per commodity.
ASSETS = {
    "NG=F": "Erdgas",
    "CL=F": "Rohöl (WTI)",
    "BZ=F": "Rohöl (Brent)",
    "RB=F": "Benzin",
    "GC=F": "Gold",
    "SI=F": "Silber",
    "ZC=F": "Mais",
    "ZW=F": "Weizen",
    "ZS=F": "Sojabohnen",
}


def weeks_for(start: int, k: int) -> list[int]:
    """Contiguous run of ``k`` ISO weeks starting at ``start`` (wraps 52->1)."""
    return [((start - 1 + j) % 52) + 1 for j in range(k)]


def active_sharpe(net_ret: pd.Series, position: pd.Series) -> float:
    """Annualized Sharpe of the held-day returns only (exposure-neutral score).

    Scoring on in-window days makes windows of different length comparable: a
    longer window is not rewarded merely for being invested more often.
    """
    active = net_ret[position > 0]
    if len(active) < 20 or active.std(ddof=1) == 0:
        return -np.inf
    return float(active.mean() / active.std(ddof=1) * np.sqrt(252))


def pick_window(is_prices: pd.DataFrame) -> tuple[int, int, float]:
    """Scan all (start, length) windows in-sample; return the best (start,k,score)."""
    best = (1, 1, -np.inf)
    idx = is_prices.index
    for k in K_RANGE:
        for start in range(1, 53):
            wk = weeks_for(start, k)
            sig = seasonal.week_window_signal(idx, wk)
            res = run_backtest(is_prices, sig, cost_model=IBKR_FUTURES)
            score = active_sharpe(res["returns"], res["position"])
            if score > best[2]:
                best = (start, k, score)
    return best


def screen() -> dict:
    rows, strat_returns, weekly_is = [], {}, {}
    for ticker, name in ASSETS.items():
        try:
            prices = get_prices(ticker, start="2000-01-01")
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {ticker}: {exc}")
            continue
        is_p = prices.loc[:IS_END]
        oos = prices.loc[OOS_START:]
        if len(is_p) < 252 * 5 or len(oos) < 252:
            print(f"  SKIP {ticker}: insufficient history")
            continue
        # Continuous front-month futures can print a non-positive settlement
        # (WTI hit -$37.63 on 2020-04-20). Simple pct-change returns are
        # undefined across a zero crossing, so such a series cannot be tested
        # honestly here — skip it rather than report a meaningless return.
        if (prices["Close"] <= 0).any():
            print(f"  SKIP {ticker}: non-positive price in series "
                  f"(min={prices['Close'].min():.2f}) — undefined simple returns")
            continue

        # In-sample average daily return per ISO week (the "Wochenrenditen" plot).
        is_ret = is_p["Close"].pct_change().dropna()
        wk_is = is_ret.groupby(seasonal.add_calendar_features(is_ret.index)["week"]
                               ).mean().reindex(range(1, 53))
        weekly_is[ticker] = wk_is

        start, k, is_score = pick_window(is_p)
        wk = weeks_for(start, k)

        # Lock the window; judge OOS only.
        sig = seasonal.week_window_signal(oos.index, wk, name=ticker)
        res = run_backtest(oos, sig, cost_model=IBKR_FUTURES)
        rets = res["returns"]
        m = compute_metrics(rets)
        ts = trade_stats(res["trades"])
        bh = oos["Close"].pct_change().dropna()
        perm = permutation_test(rets, oos["Close"].pct_change().fillna(0.0),
                                res["position"], n_perm=2000)
        sp = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) else 0.0
        dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(rets),
                                    n_trials=N_TRIALS, returns=rets)
        rows.append({
            "ticker": ticker, "name": name,
            "weeks": f"{min(wk)}-{max(wk)}" if k > 1 else f"{wk[0]}",
            "k_weeks": k,
            "is_sharpe": round(is_score, 2),
            "oos_sharpe": round(m["sharpe"], 2),
            "buyhold_sharpe": round(sharpe_ratio(bh), 2),
            "cagr": round(m["cagr"], 4),
            "max_drawdown": round(m["max_drawdown"], 4),
            "n_trades": ts["n_trades"],
            "win_rate": round(ts["win_rate"], 3),
            "perm_p": round(perm["p_value"], 3),
            "dsr": round(dsr["psr_deflated"], 3),
        })
        strat_returns[ticker] = rets
    return {"panel": pd.DataFrame(rows), "returns": strat_returns,
            "weekly_is": pd.DataFrame(weekly_is)}


def main() -> None:
    print("Strategy 0005 — Short seasonal futures windows (IS scan / OOS test)")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)
    s = screen()
    panel = s["panel"].sort_values("oos_sharpe", ascending=False).reset_index(drop=True)
    panel.to_csv(RESULTS / "screen_panel.csv", index=False)

    # Equal-weight portfolio of the OOS short-window strategies.
    ret_df = pd.DataFrame(s["returns"]).sort_index()
    port_ret = ret_df.mean(axis=1).fillna(0.0)
    port_m = compute_metrics(port_ret)
    port_perm = permutation_test(port_ret, port_ret,
                                 (port_ret != 0).astype(float), n_perm=2000)
    port_boot = bootstrap_ci(port_ret, statistic="sharpe", n_boot=2000)
    sp = port_ret.mean() / port_ret.std(ddof=1) if port_ret.std(ddof=1) else 0.0
    port_dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(port_ret),
                                     n_trials=N_TRIALS, returns=port_ret)

    # --- Plots --------------------------------------------------------------
    import matplotlib.pyplot as plt

    # Heatmap: in-sample average daily return per ISO week, per asset, with the
    # locked window outlined. This is the "plot the weekly returns first" step —
    # deliberately on IS data only, so it cannot peek at the OOS test.
    sel = {r["ticker"]: r for _, r in panel.iterrows()}
    available = [t for t in ASSETS if t in s["weekly_is"].columns and t in sel]
    wk = s["weekly_is"][available]
    names = [ASSETS[t] for t in wk.columns]
    mat = wk.T.values * 100.0  # rows=assets, cols=weeks 1..52, in %
    fig, ax = plt.subplots(figsize=(13, 5.5))
    vmax = np.nanpercentile(np.abs(mat), 95)
    im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(0, 52, 4))
    ax.set_xticklabels(range(1, 53, 4), fontsize=8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("ISO-Kalenderwoche")
    for row, t in enumerate(wk.columns):
        k = int(sel[t]["k_weeks"])
        start = int(sel[t]["weeks"].split("-")[0])
        for w in weeks_for(start, k):
            ax.add_patch(plt.Rectangle((w - 1.5, row - 0.5), 1, 1, fill=False,
                                       edgecolor="black", linewidth=1.6))
    fig.colorbar(im, ax=ax, label="Ø Tagesrendite in der Woche (%)", shrink=0.8)
    ax.set_title("0005 In-Sample-Wochenrenditen je Rohstoff (2000–2015) — gewähltes Fenster umrandet",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Durchschnittliche Tagesrendite je ISO-Woche, NUR aus den In-Sample-Jahren "
        "(2000–2015). Grün = im Schnitt positive Woche. Das schwarz umrandete Fenster "
        "je Zeile ist das in-sample stärkste kurze Fenster — es wird fixiert und "
        "anschließend ausschließlich out-of-sample (ab 2016) getestet."))
    plotting.savefig(fig, PLOTS / "weekly_returns_is.png")

    plotting.savefig(
        plotting.plot_equity(
            (1 + port_ret).cumprod(),
            title="0005 Kurzfristige Futures-Saison-Fenster — Portfolio-Kapitalkurve (OOS)",
            strategy_label="Futures-Saison-Portfolio",
            caption=("Gleichgewichtetes Portfolio der neun out-of-sample getesteten "
                     "Kurzfrist-Fenster (Futures, netto nach Kosten). Die Fenster wurden "
                     "rein in-sample gewählt; dies ist die ehrliche OOS-Auszahlung.")),
        PLOTS / "portfolio_equity.png")

    # --- Persist ------------------------------------------------------------
    summary = {
        "is_end": IS_END, "oos_start": OOS_START, "n_assets": len(panel),
        "n_trials_per_asset": N_TRIALS,
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
        "id": "0005", "label": f"Futures-Saison-Fenster kurzfristig ({len(panel)} Assets)",
        "cagr": port_m["cagr"], "annual_volatility": port_m["annual_volatility"],
        "sharpe": port_m["sharpe"], "max_drawdown": port_m["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    # --- Console ------------------------------------------------------------
    print("\n[short-window futures screen — window picked IS 2000-2015, judged OOS 2016+]")
    with pd.option_context("display.width", 180, "display.max_columns", None):
        print(panel.to_string(index=False))
    print("\n===== EQUAL-WEIGHT SHORT-WINDOW FUTURES PORTFOLIO (OOS) =====")
    print(f"  CAGR            {port_m['cagr']:.2%}")
    print(f"  Sharpe          {port_m['sharpe']:.2f}")
    print(f"  Ann. vol        {port_m['annual_volatility']:.2%}")
    print(f"  Max Drawdown    {port_m['max_drawdown']:.2%}")
    print(f"  Permutation p   {port_perm['p_value']:.3f}")
    print(f"  Bootstrap Sharpe CI [{port_boot['ci_low']:.2f}, {port_boot['ci_high']:.2f}]")
    print(f"  Deflated Sharpe {port_dsr['psr_deflated']:.3f}  (n_trials/asset={N_TRIALS})")
    survivors = panel[(panel["oos_sharpe"] > panel["buyhold_sharpe"])
                      & (panel["perm_p"] < 0.10) & (panel["dsr"] > 0.5)]
    print(f"\n  Assets beating B&H, perm p<0.10 AND DSR>0.5: "
          f"{', '.join(survivors['name']) if len(survivors) else 'none'}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
