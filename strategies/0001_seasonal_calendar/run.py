"""Strategy 0001 — Seasonal calendar effects on equity indices.

Tests three macro-justifiable calendar windows (turn-of-month, turn-of-year,
sell-in-May) on broad equity indices. Methodology:

  * In-sample (<= 2010) is used only to *select* the most promising effect.
  * Out-of-sample (> 2010) is the honest test: costs on, full metrics,
    permutation test, bootstrap CI and Deflated Sharpe (corrected for the
    number of variants tried).

Run:
    .venv/Scripts/python.exe strategies/0001_seasonal_calendar/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# Make `quantlab` importable when run as a plain script.
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
from quantlab.metrics import sharpe_ratio  # noqa: E402
from quantlab import plotting, seasonal  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
PLOTS = RESULTS / "plots"

# Broad indices via long-history ETFs / index symbols.
UNIVERSE = {
    "SPY": "S&P 500 (US)",
    "QQQ": "Nasdaq 100 (US)",
    "^GDAXI": "DAX (Germany)",
    "^FTSE": "FTSE 100 (UK)",
    "^N225": "Nikkei 225 (Japan)",
}

IS_END = "2010-12-31"      # in-sample cutoff (selection only)
OOS_START = "2011-01-01"   # out-of-sample (honest evaluation)

# The candidate effects we try (this count feeds the Deflated Sharpe).
SIGNAL_BUILDERS = {
    "turn_of_month": seasonal.turn_of_month_signal,
    "turn_of_year": seasonal.turn_of_year_signal,
    "sell_in_may": seasonal.sell_in_may_signal,
}
N_TRIALS = len(SIGNAL_BUILDERS) * len(UNIVERSE)


def load_universe() -> dict[str, pd.DataFrame]:
    data = {}
    for ticker in UNIVERSE:
        try:
            data[ticker] = get_prices(ticker, start="1990-01-01")
            print(f"  loaded {ticker:8s} {data[ticker].index.min().date()} "
                  f"-> {data[ticker].index.max().date()} ({len(data[ticker])} rows)")
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {ticker}: {exc}")
    return data


def insample_select(data: dict[str, pd.DataFrame]) -> tuple[str, str]:
    """Pick the (effect, ticker) with the best in-sample Sharpe."""
    print("\n[in-sample selection <= 2010]")
    best = (None, None, -1e9)
    for ticker, prices in data.items():
        is_prices = prices.loc[:IS_END]
        if len(is_prices) < 252 * 3:
            continue
        for name, builder in SIGNAL_BUILDERS.items():
            sig = builder(is_prices.index)
            res = run_backtest(is_prices, sig, cost_model=IBKR_LIQUID_ETF)
            sr = sharpe_ratio(res["returns"])
            print(f"  {ticker:8s} {name:14s} IS Sharpe={sr:6.2f}")
            if sr > best[2]:
                best = (name, ticker, sr)
    print(f"  -> selected effect='{best[0]}' on '{best[1]}' (IS Sharpe {best[2]:.2f})")
    return best[0], best[1]


def oos_panel(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Evaluate every effect on every ticker out-of-sample (transparency panel).

    Reporting the full panel — not just the in-sample winner — avoids the
    illusion of an edge created by cherry-picking. ``exposure`` is the fraction
    of time invested: a part-time effect that nearly matches buy & hold while
    invested only a fraction of the time has a real per-exposure advantage.
    """
    print("\n[out-of-sample panel > 2010]")
    rows = []
    for ticker, prices in data.items():
        oos = prices.loc[OOS_START:]
        if len(oos) < 252:
            continue
        bh_sharpe = sharpe_ratio(oos["Close"].pct_change().dropna())
        for name, builder in SIGNAL_BUILDERS.items():
            sig = builder(oos.index)
            res = run_backtest(oos, sig, cost_model=IBKR_LIQUID_ETF)
            ts = trade_stats(res["trades"])
            rows.append({
                "ticker": ticker,
                "effect": name,
                "oos_sharpe": round(sharpe_ratio(res["returns"]), 2),
                "buyhold_sharpe": round(bh_sharpe, 2),
                "cagr": round(compute_metrics(res["returns"])["cagr"], 4),
                "exposure": round(float(res["position"].abs().mean()), 3),
                "n_trades": ts["n_trades"],
                "win_rate": round(ts["win_rate"], 3),
                "profit_factor": round(ts["profit_factor"], 2),
            })
    panel = pd.DataFrame(rows)
    panel.to_csv(RESULTS / "oos_panel.csv", index=False)
    with pd.option_context("display.width", 120, "display.max_columns", None):
        print(panel.to_string(index=False))
    return panel


def evaluate_oos(prices: pd.DataFrame, effect: str, ticker: str) -> dict:
    """Full out-of-sample evaluation of the selected effect."""
    print(f"\n[out-of-sample evaluation > 2010] effect='{effect}' ticker='{ticker}'")
    oos = prices.loc[OOS_START:]
    builder = SIGNAL_BUILDERS[effect]
    signal = builder(oos.index)
    res = run_backtest(oos, signal, cost_model=IBKR_LIQUID_ETF)

    rets = res["returns"]
    m = compute_metrics(rets)
    ts = trade_stats(res["trades"])

    # Significance.
    perm = permutation_test(rets, oos["Close"].pct_change().fillna(0.0),
                            res["position"], n_perm=2000)
    boot = bootstrap_ci(rets, statistic="sharpe", n_boot=2000)
    tt = t_test_mean_return(rets)
    # Per-period (non-annualized) Sharpe for the DSR, on the same time base.
    sharpe_per_period = rets.mean() / rets.std(ddof=1) if rets.std(ddof=1) else 0.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=float(sharpe_per_period),
        n_obs=len(rets),
        n_trials=N_TRIALS,
        returns=rets,
    )

    summary = {
        "effect": effect,
        "ticker": ticker,
        "oos_start": OOS_START,
        "n_trials_tried": N_TRIALS,
        "portfolio_metrics": m,
        "trade_stats": ts,
        "significance": {
            "permutation": perm,
            "bootstrap_sharpe_ci": boot,
            "t_test": tt,
            "deflated_sharpe": dsr,
        },
        "buy_hold_sharpe": float(sharpe_ratio(oos["Close"].pct_change().dropna())),
    }

    # Plots.
    plotting.savefig(
        plotting.plot_equity(res["equity"], res["buy_hold"],
                             title=f"0001 {effect} on {ticker} (OOS)"),
        PLOTS / "equity.png")
    plotting.savefig(plotting.plot_drawdown(rets, title=f"{effect} drawdown (OOS)"),
                     PLOTS / "drawdown.png")
    plotting.savefig(plotting.plot_monthly_heatmap(rets), PLOTS / "monthly_heatmap.png")
    buckets = seasonal.bucket_return_analysis(
        oos["Close"].pct_change().dropna(), by="tdom_from_end")
    plotting.savefig(
        plotting.plot_bucket_returns(buckets, title="Return by trading-days-from-month-end"),
        PLOTS / "bucket_tdom_from_end.png")

    res["trades"].to_csv(RESULTS / "trades.csv", index=False)

    # Standardized artifacts for the cross-strategy comparison (reports/).
    res["equity"].rename("equity").to_csv(RESULTS / "equity.csv")
    card = {
        "id": "0001",
        "label": f"Sell-in-May ({ticker})",
        "cagr": m["cagr"],
        "annual_volatility": m["annual_volatility"],
        "sharpe": m["sharpe"],
        "max_drawdown": m["max_drawdown"],
        "is_strategy": True,
    }
    with open(RESULTS / "card.json", "w") as fh:
        json.dump(card, fh, indent=2)
    return summary


def main() -> None:
    print("Strategy 0001 — Seasonal calendar effects")
    data = load_universe()
    if not data:
        raise SystemExit("No data loaded — check network / yfinance.")

    RESULTS.mkdir(parents=True, exist_ok=True)
    effect, ticker = insample_select(data)
    panel = oos_panel(data)
    summary = evaluate_oos(data[ticker], effect, ticker)
    summary["oos_panel"] = panel.to_dict(orient="records")

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)

    m = summary["portfolio_metrics"]
    ts = summary["trade_stats"]
    sig = summary["significance"]
    print("\n===== OUT-OF-SAMPLE SUMMARY (net of costs) =====")
    print(f"  CAGR            {m['cagr']:.2%}")
    print(f"  Sharpe          {m['sharpe']:.2f}   (buy&hold {summary['buy_hold_sharpe']:.2f})")
    print(f"  Sortino         {m['sortino']:.2f}")
    print(f"  Max Drawdown    {m['max_drawdown']:.2%}")
    print(f"  Win rate        {ts['win_rate']:.2%}")
    print(f"  Profit factor   {ts['profit_factor']:.2f}")
    print(f"  Avg holding     {ts['avg_holding_days']:.1f} days")
    print(f"  # Trades        {ts['n_trades']}")
    print(f"  Permutation p   {sig['permutation']['p_value']:.4f}")
    print(f"  Deflated Sharpe {sig['deflated_sharpe']['psr_deflated']:.3f}")
    print(f"\n  results -> {RESULTS}")


if __name__ == "__main__":
    main()
