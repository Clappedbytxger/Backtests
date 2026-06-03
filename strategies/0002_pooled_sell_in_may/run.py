"""Strategy 0002 — Pooled cross-market sell-in-May (Halloween) overlay.

Motivation (follows directly from strategy 0001):
    0001 showed the sell-in-May effect is *positive and consistent across all
    five equity markets*, but only ~16 trades per market — too few to reject
    luck individually (per-market permutation p-values were weak). The honest
    next step is **pooling**: trade the effect simultaneously in all five
    markets as one equal-weight portfolio. This multiplies the trade count
    (~80 trades), diversifies idiosyncratic country risk, and finally gives the
    permutation test and Deflated Sharpe real statistical power.

What we test:
    An equal-weight portfolio that is long all five indices during the winter
    half-year (Nov-Apr) and flat in summer (May-Oct), rebalanced daily, net of
    IBKR costs, out-of-sample 2011-2026. Benchmark: an equal-weight buy & hold
    of the same five indices (always invested).

The hypothesis (pooled sell-in-May) was *pre-specified* from 0001's panel, so
this is a confirmation test, not a fresh search.

Run:
    .venv/Scripts/python.exe strategies/0002_pooled_sell_in_may/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import (  # noqa: E402
    compute_metrics,
    trade_stats,
    run_backtest,
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)
from quantlab.costs import IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.metrics import sharpe_ratio, compute_metrics as _cm  # noqa: E402
from quantlab import plotting, seasonal  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

# Full display names (used in the German report — no raw tickers there).
UNIVERSE = {
    "SPY": "S&P 500 (USA)",
    "QQQ": "Nasdaq 100 (USA)",
    "^GDAXI": "DAX (Deutschland)",
    "^FTSE": "FTSE 100 (UK)",
    "^N225": "Nikkei 225 (Japan)",
}

OOS_START = "2011-01-01"
# The effect was pre-specified from 0001's three macro-justified calendar
# effects; we carry that selection burden into the Deflated Sharpe.
N_TRIALS = 3


def load_universe() -> dict[str, pd.DataFrame]:
    data = {}
    for ticker in UNIVERSE:
        try:
            df = get_prices(ticker, start="1990-01-01")
            data[ticker] = df
            print(f"  loaded {ticker:8s} {df.index.min().date()} -> "
                  f"{df.index.max().date()} ({len(df)} rows)")
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {ticker}: {exc}")
    return data


def per_market_backtests(data: dict[str, pd.DataFrame]) -> dict[str, dict]:
    """Run the sell-in-May backtest on each market, out-of-sample."""
    out = {}
    for ticker, prices in data.items():
        oos = prices.loc[OOS_START:]
        if len(oos) < 252:
            continue
        sig = seasonal.sell_in_may_signal(oos.index)
        res = run_backtest(oos, sig, cost_model=IBKR_LIQUID_ETF)
        out[ticker] = {"oos": oos, "res": res}
    return out


def build_pooled_portfolio(bts: dict[str, dict]) -> dict:
    """Equal-weight daily-rebalanced portfolio of the per-market strategies.

    The portfolio return on each day is the simple average of the available
    markets' net strategy returns. The benchmark is the equal-weight average of
    the markets' buy & hold returns over the same dates.
    """
    strat_rets = pd.DataFrame(
        {t: b["res"]["returns"] for t, b in bts.items()}
    ).sort_index()
    bh_rets = pd.DataFrame(
        {t: b["oos"]["Close"].pct_change() for t, b in bts.items()}
    ).sort_index()

    # Equal weight across whatever markets have data that day.
    port_ret = strat_rets.mean(axis=1).fillna(0.0)
    bh_port_ret = bh_rets.mean(axis=1).fillna(0.0)

    equity = (1.0 + port_ret).cumprod()
    bh_equity = (1.0 + bh_port_ret).cumprod()

    # Pool every market's trades for trade-level statistics (real power).
    pooled_trades = pd.concat(
        [b["res"]["trades"].assign(market=t) for t, b in bts.items()],
        ignore_index=True,
    )
    return {
        "returns": port_ret,
        "bh_returns": bh_port_ret,
        "equity": equity,
        "bh_equity": bh_equity,
        "trades": pooled_trades,
        "strat_rets": strat_rets,
    }


def evaluate(port: dict) -> dict:
    rets = port["returns"]
    m = compute_metrics(rets)
    bh_m = compute_metrics(port["bh_returns"])
    ts = trade_stats(port["trades"])

    # Permutation test: pooled portfolio position vs its own blended asset return.
    # Reconstruct an "effective position" so random timing is well defined: the
    # share of markets invested each day (0..1), tested against the equal-weight
    # buy & hold return stream.
    invested_share = (port["strat_rets"].notna() &
                      (port["strat_rets"] != 0)).mean(axis=1).reindex(rets.index).fillna(0.0)
    perm = permutation_test(rets, port["bh_returns"], invested_share, n_perm=2000)
    boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
    tt = t_test_mean_return(rets)

    sharpe_pp = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) else 0.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=float(sharpe_pp), n_obs=len(rets),
        n_trials=N_TRIALS, returns=rets,
    )
    return {
        "portfolio_metrics": m,
        "benchmark_metrics": bh_m,
        "trade_stats": ts,
        "significance": {
            "permutation": perm,
            "bootstrap_sharpe_ci": boot,
            "t_test": tt,
            "deflated_sharpe": dsr,
        },
    }


def per_market_panel(bts: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for ticker, b in bts.items():
        res = b["res"]
        rets = res["returns"]
        bh = b["oos"]["Close"].pct_change().dropna()
        ts = trade_stats(res["trades"])
        rows.append({
            "ticker": ticker,
            "name": UNIVERSE[ticker],
            "sharpe": round(sharpe_ratio(rets), 2),
            "buyhold_sharpe": round(sharpe_ratio(bh), 2),
            "cagr": round(compute_metrics(rets)["cagr"], 4),
            "max_drawdown": round(compute_metrics(rets)["max_drawdown"], 4),
            "exposure": round(float(res["position"].abs().mean()), 3),
            "n_trades": ts["n_trades"],
            "win_rate": round(ts["win_rate"], 3),
            "profit_factor": round(ts["profit_factor"], 2),
        })
    return pd.DataFrame(rows)


def main() -> None:
    print("Strategy 0002 — Pooled cross-market sell-in-May")
    data = load_universe()
    if not data:
        raise SystemExit("No data loaded — check network / yfinance.")

    RESULTS.mkdir(parents=True, exist_ok=True)
    bts = per_market_backtests(data)
    port = build_pooled_portfolio(bts)
    summary = evaluate(port)
    panel = per_market_panel(bts)
    panel.to_csv(RESULTS / "per_market_panel.csv", index=False)

    # --- Plots (German captions explaining exactly what is shown) -----------
    plotting.savefig(
        plotting.plot_equity(
            port["equity"], port["bh_equity"],
            title="0002 Gepooltes Sell-in-May — Portfolio vs. Buy & Hold (OOS 2011-2026)",
            strategy_label="Sell-in-May Portfolio (5 Märkte, gleichgewichtet)",
            benchmark_label="Buy & Hold Portfolio (5 Märkte, immer investiert)",
            caption=("Kapitalkurve (log) eines gleichgewichteten Portfolios aus fünf "
                     "Aktienindizes, das nur im Winterhalbjahr (Nov-Apr) investiert ist "
                     "(flache Abschnitte = Sommer in Cash). Es endet klar UNTER dem stets "
                     "investierten Buy-&-Hold, läuft dafür aber ruhiger und mit nur ~50% "
                     "Marktzeit — ein Risiko-, kein Rendite-Vorteil."),
        ),
        PLOTS / "equity.png")
    plotting.savefig(
        plotting.plot_drawdown(
            port["returns"],
            title="0002 Drawdown des gepoolten Sell-in-May Portfolios",
            caption=("Rückgang vom jeweiligen Höchststand in %. Da die Strategie den "
                     "Sommer (Mai-Okt) in Cash sitzt, fängt sie typische Sommer-/"
                     "Herbst-Korrekturen nicht voll ab — der maximale Drawdown ist "
                     "kleiner als bei Buy & Hold."),
        ),
        PLOTS / "drawdown.png")
    plotting.savefig(
        plotting.plot_monthly_heatmap(
            port["returns"],
            title="0002 Monatsrenditen des Portfolios (%) pro Jahr",
            caption=("Jede Zelle ist die Portfolio-Rendite eines Kalendermonats. Die "
                     "Sommermonate (Mai-Okt) sind per Konstruktion ~0% (Cash); die "
                     "Wertentwicklung kommt fast ausschließlich aus dem Winterhalbjahr."),
        ),
        PLOTS / "monthly_heatmap.png")

    # Pooled winter daily returns -> bucket by month to show the seasonal shape.
    pooled_daily = pd.concat(
        [b["oos"]["Close"].pct_change().dropna() for b in bts.values()]
    )
    buckets = seasonal.bucket_return_analysis(pooled_daily, by="month")
    plotting.savefig(
        plotting.plot_bucket_returns(
            buckets,
            title="0002 Mittlere Tagesrendite je Monat (alle 5 Märkte gepoolt)",
            caption=("Durchschnittliche Tagesrendite pro Kalendermonat, über alle fünf "
                     "Märkte gepoolt. Grün = statistisch signifikant (p<0.05). Die "
                     "Sommermonate sind im Schnitt schwächer — die makroökonomische "
                     "Grundlage des Sell-in-May-Effekts."),
        ),
        PLOTS / "bucket_month.png")

    # --- Persist results -----------------------------------------------------
    port["trades"].to_csv(RESULTS / "trades.csv", index=False)
    port["equity"].rename("equity").to_csv(RESULTS / "equity.csv")

    m = summary["portfolio_metrics"]
    card = {
        "id": "0002",
        "label": "Sell-in-May Portfolio (gepoolt, 5 Märkte)",
        "cagr": m["cagr"],
        "annual_volatility": m["annual_volatility"],
        "sharpe": m["sharpe"],
        "max_drawdown": m["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)

    summary["per_market_panel"] = panel.to_dict(orient="records")
    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    ts = summary["trade_stats"]
    sig = summary["significance"]
    bh = summary["benchmark_metrics"]
    print("\n[per-market OOS panel]")
    with pd.option_context("display.width", 140, "display.max_columns", None):
        print(panel.to_string(index=False))
    print("\n===== POOLED PORTFOLIO (net of costs, OOS 2011-2026) =====")
    print(f"  CAGR            {m['cagr']:.2%}   (buy&hold {bh['cagr']:.2%})")
    print(f"  Sharpe          {m['sharpe']:.2f}   (buy&hold {bh['sharpe']:.2f})")
    print(f"  Sortino         {m['sortino']:.2f}")
    print(f"  Ann. vol        {m['annual_volatility']:.2%}  (buy&hold {bh['annual_volatility']:.2%})")
    print(f"  Max Drawdown    {m['max_drawdown']:.2%}  (buy&hold {bh['max_drawdown']:.2%})")
    print(f"  Calmar          {m['calmar']:.2f}")
    print(f"  Win rate        {ts['win_rate']:.2%}")
    print(f"  Profit factor   {ts['profit_factor']:.2f}")
    print(f"  Avg holding     {ts['avg_holding_days']:.1f} days")
    print(f"  # Trades        {ts['n_trades']}  (pooled across 5 markets)")
    print(f"  Permutation p   {sig['permutation']['p_value']:.4f}")
    print(f"  Bootstrap Sharpe CI [{sig['bootstrap_sharpe_ci']['ci_low']:.2f}, "
          f"{sig['bootstrap_sharpe_ci']['ci_high']:.2f}]")
    print(f"  Deflated Sharpe {sig['deflated_sharpe']['psr_deflated']:.3f}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
