"""Strategy 0003 — Sell-in-May as a risk overlay: T-bill carry & partial de-risking.

Follows directly from 0002, which showed pooled sell-in-May does not beat buy &
hold on return but lowers volatility. Two concrete improvements are tested here,
both as equal-weight portfolios over the same five equity indices, OOS 2011-2026:

  1. **T-bill carry** — instead of sitting in *cash* during the summer (May-Oct),
     park the money in short-term treasuries (^IRX, 13-week T-bill yield). Does
     the carry close the CAGR gap to buy & hold?
  2. **De-risking overlay** — don't go fully flat in summer; stay 50% invested.
     Keeps half the summer upside while still cutting summer risk.

Compared portfolios (all equal-weight across the 5 markets, net of costs):
  * Buy & Hold              — always 100% invested (benchmark)
  * Sell-in-May (Cash)      — winter 100%, summer 0%        (= strategy 0002)
  * Sell-in-May (T-Bills)   — winter 100%, summer in ^IRX
  * De-Risking Overlay      — winter 100%, summer 50%

Run:
    .venv/Scripts/python.exe strategies/0003_seasonal_overlay/run.py
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
    bootstrap_ci, deflated_sharpe_ratio, permutation_test, t_test_mean_return,
)
from quantlab.costs import IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab import plotting, seasonal  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

UNIVERSE = {
    "SPY": "S&P 500 (USA)",
    "QQQ": "Nasdaq 100 (USA)",
    "^GDAXI": "DAX (Deutschland)",
    "^FTSE": "FTSE 100 (UK)",
    "^N225": "Nikkei 225 (Japan)",
}
OOS_START = "2011-01-01"
WINTER = [11, 12, 1, 2, 3, 4]
N_TRIALS = 3  # carried selection burden (3 macro-justified calendar effects)


def overlay_signal(index: pd.DatetimeIndex, summer_weight: float = 0.5) -> pd.Series:
    """Long 1.0 in winter (Nov-Apr), `summer_weight` in summer (de-risking)."""
    months = pd.DatetimeIndex(index).month
    w = pd.Series(summer_weight, index=index)
    w[months.isin(WINTER)] = 1.0
    return w.rename("overlay")


def build() -> dict:
    irx = get_prices("^IRX", start="2005-01-01")
    rf_annual = irx["Close"].astype(float) / 100.0  # yield in fraction

    cols = {"buyhold": {}, "cash": {}, "tbill": {}, "overlay": {}}
    panel = []
    for ticker in UNIVERSE:
        prices = get_prices(ticker, start="1990-01-01")
        oos = prices.loc[OOS_START:]
        if len(oos) < 252:
            continue
        idx = oos.index
        rf_daily = (rf_annual.reindex(idx).ffill().fillna(0.0)) / 252.0

        sim = seasonal.sell_in_may_signal(idx)
        res_cash = run_backtest(oos, sim, cost_model=IBKR_LIQUID_ETF)
        res_over = run_backtest(oos, overlay_signal(idx), cost_model=IBKR_LIQUID_ETF)

        cash_ret = res_cash["returns"]
        # On flat (summer) days the cash version earns 0; add T-bill carry there.
        is_flat = res_cash["position"].eq(0.0)
        tbill_ret = cash_ret + is_flat * rf_daily

        cols["buyhold"][ticker] = oos["Close"].pct_change()
        cols["cash"][ticker] = cash_ret
        cols["tbill"][ticker] = tbill_ret
        cols["overlay"][ticker] = res_over["returns"]

        ts = trade_stats(res_cash["trades"])
        m = compute_metrics(tbill_ret)
        panel.append({
            "ticker": ticker, "name": UNIVERSE[ticker],
            "tbill_sharpe": round(m["sharpe"], 2),
            "tbill_cagr": round(m["cagr"], 4),
            "n_trades": ts["n_trades"],
        })

    portfolios = {
        name: pd.DataFrame(d).sort_index().mean(axis=1).fillna(0.0)
        for name, d in cols.items()
    }
    return {"portfolios": portfolios, "panel": pd.DataFrame(panel)}


LABELS = {
    "buyhold": "Buy & Hold (immer investiert)",
    "cash": "Sell-in-May (Sommer Cash)",
    "tbill": "Sell-in-May (Sommer T-Bills)",
    "overlay": "De-Risking Overlay (Sommer 50%)",
}


def evaluate(port_ret: pd.Series, bh_ret: pd.Series, n_trials: int) -> dict:
    m = compute_metrics(port_ret)
    perm = permutation_test(port_ret, bh_ret,
                            (port_ret != 0).astype(float), n_perm=2000)
    boot = bootstrap_ci(port_ret, statistic="sharpe", n_boot=2000)
    tt = t_test_mean_return(port_ret)
    sp = port_ret.mean() / port_ret.std(ddof=1) if port_ret.std(ddof=1) else 0.0
    dsr = deflated_sharpe_ratio(observed_sharpe=float(sp), n_obs=len(port_ret),
                                n_trials=n_trials, returns=port_ret)
    return {"metrics": m, "permutation": perm, "bootstrap_sharpe_ci": boot,
            "t_test": tt, "deflated_sharpe": dsr}


def main() -> None:
    print("Strategy 0003 — Sell-in-May risk overlay (T-bill carry & de-risking)")
    RESULTS.mkdir(parents=True, exist_ok=True)
    b = build()
    ports = b["portfolios"]

    metrics = {name: compute_metrics(r) for name, r in ports.items()}
    bh = ports["buyhold"]
    # Significance is only meaningful for the cash variant: it is the pure
    # timing bet whose null (random timing vs flat) is well-defined, and it
    # keeps continuity with 0002. The T-bill/overlay variants are not new edges
    # but risk-engineering on top of that same (non-significant) timing, so a
    # permutation test against random timing is not informative for them.
    cash_eval = evaluate(ports["cash"], bh, N_TRIALS)

    # --- Plots --------------------------------------------------------------
    equities = {LABELS[n]: (1 + ports[n]).cumprod() for n in
                ("buyhold", "tbill", "overlay", "cash")}
    plotting.savefig(
        plotting.plot_strategy_comparison(
            equities,
            title="0003 Sell-in-May als Risiko-Overlay — Varianten im Vergleich (OOS)",
            caption=("Vier gleichgewichtete 5-Markt-Portfolios, auf 1 normiert (log). "
                     "Buy & Hold ist immer investiert; die Sell-in-May-Varianten sitzen "
                     "den Sommer in Cash, in T-Bills (Zins-Carry) bzw. zu 50% investiert. "
                     "Der T-Bill-Carry hebt die Sommer-Variante spürbar an."),
        ),
        PLOTS / "variants_equity.png")
    plotting.savefig(
        plotting.plot_drawdown(
            ports["overlay"],
            title="0003 Drawdown — De-Risking Overlay (Sommer 50% investiert)",
            caption=("Rückgang vom Höchststand des Overlay-Portfolios. Durch die "
                     "Halbierung der Sommer-Position werden Sommer-/Herbstkorrekturen "
                     "gedämpft, ohne den ganzen Sommer auf Rendite zu verzichten."),
        ),
        PLOTS / "drawdown_overlay.png")

    # --- Persist ------------------------------------------------------------
    summary = {
        "labels": LABELS,
        "portfolio_metrics": {n: metrics[n] for n in metrics},
        "cash_significance": cash_eval,
        "per_market_panel": b["panel"].to_dict(orient="records"),
    }
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    b["panel"].to_csv(RESULTS / "per_market_panel.csv", index=False)
    (1 + ports["overlay"]).cumprod().rename("equity").to_csv(RESULTS / "equity.csv")

    # Headline strategy for the global comparison = the de-risking overlay
    # (best risk-adjusted variant: closest Sharpe to buy & hold at lower vol).
    mt = metrics["overlay"]
    card = {
        "id": "0003", "label": "Sell-in-May De-Risking Overlay (gepoolt)",
        "cagr": mt["cagr"], "annual_volatility": mt["annual_volatility"],
        "sharpe": mt["sharpe"], "max_drawdown": mt["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    # --- Console summary ----------------------------------------------------
    print("\n[per-market panel — T-bill variant]")
    with pd.option_context("display.width", 120):
        print(b["panel"].to_string(index=False))
    print("\n===== PORTFOLIO VARIANTS (net of costs, OOS 2011-2026) =====")
    hdr = f"  {'Variant':<34}{'CAGR':>8}{'Sharpe':>8}{'Vol':>8}{'MaxDD':>9}{'Calmar':>8}"
    print(hdr)
    for n in ("buyhold", "tbill", "overlay", "cash"):
        m = metrics[n]
        print(f"  {LABELS[n]:<34}{m['cagr']*100:>7.1f}%{m['sharpe']:>8.2f}"
              f"{m['annual_volatility']*100:>7.1f}%{m['max_drawdown']*100:>8.1f}%"
              f"{m['calmar']:>8.2f}")
    print("\n  Significance of the underlying timing (cash variant, cf. 0002):")
    print(f"   permutation p={cash_eval['permutation']['p_value']:.3f}  "
          f"DSR={cash_eval['deflated_sharpe']['psr_deflated']:.3f}  "
          f"(not a significant standalone edge)")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
