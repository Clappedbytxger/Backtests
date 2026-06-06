"""Strategy 0011 — Extended seasonal futures screen (3rd pass, IS scan / OOS test).

Same machinery as 0005/0008, applied to every remaining distinct, IBKR-tradeable
future that yfinance can actually supply with 2000-2015 history (see probe.py).

The funnel is the point of this strategy as much as the result:
  50 hand-picked candidates  ->  24 with usable history  ->  19 DISTINCT new markets
The binding constraint is NOT IBKR (almost all are tradeable) but the data source:
crypto and micro contracts are too young, several symbols (canola, MGEX wheat,
ICE dollar index) have no yfinance series, and the rest of yfinance's =F universe
are pure duplicates of underlyings already screened (QC=copper, QG=natgas,
QO/QI=gold/silver) — same underlying, same seasonality, so excluded.

Of the 19 distinct new markets only THREE are commodities with a physical
supply/demand seasonal driver (rough rice, milk, lumber). The other 16 are
financial futures (rates / FX / equity indices) and act as a large NOISE CONTROL,
exactly like the 4 controls in 0008: if the method manufactures "significant"
seasonal windows on rates and FX — where no physical seasonality should exist —
that is direct evidence it is fitting noise.

Multiple-testing accounting is now cumulative: this is the 3rd 156-window scan.
Distinct underlyings scanned across 0005+0008+0011 = 8 + 20 + 19 = 47, i.e.
~7,300 windows. Per-asset Deflated Sharpe is charged the full 156; on top, any
commodity "lead" is held to a Bonferroni bar over the 3 new commodities and read
against that growing family. Two earlier survivors (gasoline 0006, feeder cattle
0009) earned their status by also passing an independent forward test — that, not
the screen, is what separates a lead from luck.

Run:
    .venv/Scripts/python.exe strategies/0011_extended_futures_screen/run.py
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
K_RANGE = (1, 2, 3)
N_TRIALS = 52 * len(K_RANGE)    # 156 windows per asset

# 19 distinct, IBKR-tradeable futures with usable yfinance history (probe.py),
# none overlapping 0005/0008. Only the first three have a physical seasonal
# driver; the rest are financial NOISE CONTROLS.
ASSETS = {
    # --- Commodities with real physical seasonality (the only edge candidates) ---
    "ZR=F": "Rough Rice",
    "DC=F": "Milch (Class III)",
    "LBS=F": "Bauholz (Lumber)",
    # --- Financial controls: equity indices ---
    "YM=F": "Dow Jones",
    "NKD=F": "Nikkei 225",
    # --- Financial controls: interest rates ---
    "ZN=F": "10Y T-Note",
    "ZF=F": "5Y T-Note",
    "ZT=F": "2Y T-Note",
    "UB=F": "Ultra T-Bond",
    "ZQ=F": "30D Fed Funds",
    "GE=F": "Eurodollar",
    # --- Financial controls: FX ---
    "6B=F": "Britisches Pfund",
    "6J=F": "Japanischer Yen",
    "6C=F": "Kanadischer Dollar",
    "6A=F": "Australischer Dollar",
    "6S=F": "Schweizer Franken",
    "6N=F": "Neuseeland-Dollar",
    "6M=F": "Mexikanischer Peso",
    "6L=F": "Brasilianischer Real",
}

# Markets with a genuine physical supply/demand seasonal driver. Everything else
# is a financial control used only to detect noise-fitting.
COMMODITY_TICKERS = {"ZR=F", "DC=F", "LBS=F"}


def weeks_for(start: int, k: int) -> list[int]:
    """Contiguous run of ``k`` ISO weeks starting at ``start`` (wraps 52->1)."""
    return [((start - 1 + j) % 52) + 1 for j in range(k)]


def active_sharpe(net_ret: pd.Series, position: pd.Series) -> float:
    """Annualized Sharpe of the held-day returns only (exposure-neutral score)."""
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
            print(f"  SKIP {ticker} ({name}): insufficient history "
                  f"(IS={len(is_p)}, OOS={len(oos)})")
            continue
        if (prices["Close"] <= 0).any():
            print(f"  SKIP {ticker} ({name}): non-positive price "
                  f"(min={prices['Close'].min():.2f}) — undefined simple returns")
            continue

        is_ret = is_p["Close"].pct_change().dropna()
        wk_is = is_ret.groupby(seasonal.add_calendar_features(is_ret.index)["week"]
                               ).mean().reindex(range(1, 53))
        weekly_is[ticker] = wk_is

        start, k, is_score = pick_window(is_p)
        wk = weeks_for(start, k)

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
            "commodity": ticker in COMMODITY_TICKERS,
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
        kind = "COMMODITY" if ticker in COMMODITY_TICKERS else "control"
        print(f"  OK   {ticker:6s} ({name}) [{kind}]: KW{rows[-1]['weeks']}, "
              f"IS {is_score:.2f} -> OOS {m['sharpe']:.2f}, perm-p {perm['p_value']:.3f}")
    return {"panel": pd.DataFrame(rows), "returns": strat_returns,
            "weekly_is": pd.DataFrame(weekly_is)}


def main() -> None:
    print("Strategy 0011 — Extended seasonal futures screen (IS scan / OOS test)")
    RESULTS.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)
    s = screen()
    if s["panel"].empty:
        print("  No assets passed the data filters — nothing to report.")
        return
    panel = s["panel"].sort_values("oos_sharpe", ascending=False).reset_index(drop=True)
    panel.to_csv(RESULTS / "screen_panel.csv", index=False)

    # Equal-weight portfolio of the COMMODITY short-window strategies only.
    comm = [t for t in s["returns"] if t in COMMODITY_TICKERS]
    ret_df = pd.DataFrame({t: s["returns"][t] for t in comm}).sort_index()
    port_ret = ret_df.mean(axis=1).fillna(0.0)
    port_m = compute_metrics(port_ret)
    port_boot = bootstrap_ci(port_ret, statistic="sharpe", n_boot=2000)
    sp = port_ret.mean() / port_ret.std(ddof=1) if port_ret.std(ddof=1) else 0.0
    port_dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(port_ret),
                                     n_trials=N_TRIALS, returns=port_ret)

    # --- Plots --------------------------------------------------------------
    import matplotlib.pyplot as plt

    sel = {r["ticker"]: r for _, r in panel.iterrows()}
    available = [t for t in ASSETS if t in s["weekly_is"].columns and t in sel]
    wk = s["weekly_is"][available]
    names = [ASSETS[t] + ("" if t in COMMODITY_TICKERS else "  (Kontrolle)")
             for t in wk.columns]
    mat = wk.T.values * 100.0
    fig, ax = plt.subplots(figsize=(13, max(5.5, 0.42 * len(names))))
    vmax = np.nanpercentile(np.abs(mat), 95)
    im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(0, 52, 4))
    ax.set_xticklabels(range(1, 53, 4), fontsize=8)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("ISO-Kalenderwoche")
    for row, t in enumerate(wk.columns):
        k = int(sel[t]["k_weeks"])
        start = int(str(sel[t]["weeks"]).split("-")[0])
        for w in weeks_for(start, k):
            ax.add_patch(plt.Rectangle((w - 1.5, row - 0.5), 1, 1, fill=False,
                                       edgecolor="black", linewidth=1.6))
    fig.colorbar(im, ax=ax, label="Ø Tagesrendite in der Woche (%)", shrink=0.8)
    ax.set_title("0011 In-Sample-Wochenrenditen je Future (2000–2015) — gewähltes Fenster umrandet",
                 fontsize=12, fontweight="bold")
    plotting._add_caption(fig, (
        "Durchschnittliche Tagesrendite je ISO-Woche, NUR aus den In-Sample-Jahren. "
        "Die 3 obersten Zeilen sind Rohstoffe (echte Saisonalität), der Rest sind "
        "Finanz-Kontrollen (Zinsen/FX/Aktien) ohne physische Saison. Das umrandete "
        "Fenster wird fixiert und ausschließlich out-of-sample (ab 2016) getestet."))
    plotting.savefig(fig, PLOTS / "weekly_returns_is.png")

    if len(comm):
        plotting.savefig(
            plotting.plot_equity(
                (1 + port_ret).cumprod(),
                title="0011 Erweiterter Screen — Rohstoff-Portfolio Kapitalkurve (OOS)",
                strategy_label="Rohstoff-Saison-Portfolio (Reis/Milch/Holz)",
                caption=("Gleichgewichtetes OOS-Portfolio der drei neuen Rohstoff-Fenster "
                         "(Reis, Milch, Bauholz), netto nach Kosten. Fenster rein in-sample "
                         "gewählt — die ehrliche Out-of-Sample-Auszahlung.")),
            PLOTS / "portfolio_equity.png")

    # --- Persist ------------------------------------------------------------
    summary = {
        "is_end": IS_END, "oos_start": OOS_START, "n_assets": len(panel),
        "n_trials_per_asset": N_TRIALS,
        "cumulative_distinct_assets_scanned": 8 + 20 + len(panel),
        "screen_panel": panel.to_dict(orient="records"),
        "commodity_portfolio_metrics": port_m,
        "commodity_portfolio_significance": {
            "bootstrap_sharpe_ci": port_boot, "deflated_sharpe": port_dsr,
        },
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    if len(comm):
        (1 + port_ret).cumprod().rename("equity").to_csv(RESULTS / "equity.csv")
    card = {
        "id": "0011", "label": f"Erweiterter Futures-Screen ({len(panel)} Märkte, {len(comm)} Rohstoffe)",
        "cagr": port_m["cagr"], "annual_volatility": port_m["annual_volatility"],
        "sharpe": port_m["sharpe"], "max_drawdown": port_m["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    # --- Console ------------------------------------------------------------
    print("\n[extended screen — window picked IS 2000-2015, judged OOS 2016+]")
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(panel.to_string(index=False))

    # Commodity leads: stricter Bonferroni bar over the 3 new commodities.
    n_comm = int(panel["commodity"].sum())
    bonf = 0.10 / max(1, n_comm)
    comm_leads = panel[(panel["commodity"])
                       & (panel["oos_sharpe"] > panel["buyhold_sharpe"])
                       & (panel["perm_p"] < bonf)]
    ctrl_hits = panel[(~panel["commodity"]) & (panel["perm_p"] < 0.10)]
    n_ctrl = int((~panel["commodity"]).sum())

    print(f"\n  Commodity leads (OOS>B&H, perm-p < Bonferroni {bonf:.3f} over "
          f"{n_comm} commodities): {', '.join(comm_leads['name']) if len(comm_leads) else 'none'}")
    print(f"  Control futures with perm-p < 0.10: "
          f"{', '.join(ctrl_hits['name']) if len(ctrl_hits) else 'none'} "
          f"({len(ctrl_hits)}/{n_ctrl}; ~{0.10*n_ctrl:.1f} expected by chance)")
    if len(comm):
        print(f"\n  Commodity portfolio OOS: CAGR {port_m['cagr']:.2%}, "
              f"Sharpe {port_m['sharpe']:.2f}, "
              f"Bootstrap Sharpe CI [{port_boot['ci_low']:.2f}, {port_boot['ci_high']:.2f}], "
              f"DSR {port_dsr['psr_deflated']:.3f}")
    print(f"\n  Cumulative distinct underlyings scanned (0005+0008+0011): "
          f"{8 + 20 + len(panel)}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
