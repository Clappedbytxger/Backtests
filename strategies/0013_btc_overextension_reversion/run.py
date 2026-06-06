"""Strategy 0013 — BTC intraday over-extension mean-reversion.

Hypothesis (directional mechanism, low turnover — answer to 0012's lesson):
    After an EXTREME hourly move (return beyond +/-k sigma, sigma = rolling 7-day
    std of hourly returns), the market over-reacts and partially reverts over the
    next H hours. So we FADE the spike: a sharp up-hour -> short, a sharp down-hour
    -> long, held H hours, flat otherwise. Only extreme bars trade -> far fewer
    round-trips than 0012 -> friendlier to the 24bps round-trip crypto cost.

Discipline:
    * IS 2017-08..2022-12 picks the best of a small 3x3 grid (n_trials = 9).
    * OOS 2023-01.. judges the locked rule only.
    * sigma window fixed at 168h (7 days) -> not a searched parameter.
    * Realistic crypto cost (Binance taker 10bps + 2bps slippage = 12bps/side).
    * Hourly engine (look-ahead safe via .shift(1)); metrics on the daily series.
    * Permutation, bootstrap CI, Deflated Sharpe (charged the full grid width).

Run:
    .venv/Scripts/python.exe strategies/0013_btc_overextension_reversion/run.py
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.costs import CostModel  # noqa: E402
from quantlab.crypto_data import get_crypto_ohlcv  # noqa: E402
from quantlab.metrics import compute_metrics, trade_stats  # noqa: E402
from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
)

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
PLOTS = RESULTS / "plots"
PLOTS.mkdir(parents=True, exist_ok=True)

IS_END = "2022-12-31"
OOS_START = "2023-01-01"
DPY = 365
VOL_WINDOW = 168  # 7 days of hourly bars; fixed, NOT searched

CRYPTO_COST = CostModel(
    commission_per_share=0.0, min_commission=0.0, slippage_bps=12.0, regulatory_bps=0.0
)

# Pre-declared grid: fade threshold in sigmas x holding hours = 9 trials.
SIGMAS = [2.0, 2.5, 3.0]
HOLDS = [1, 3, 6]
N_TRIALS = len(SIGMAS) * len(HOLDS)


def build_signal(close: pd.Series, k: float, H: int) -> pd.Series:
    """Decision-time target position for the over-extension fade.

    z_t = ret_t / std(ret over the *previous* VOL_WINDOW bars). The normalizer is
    shifted by one bar so the current return never contaminates its own sigma.
    When |z_t| >= k, fade: position = -sign(z_t), carried for H bars (held over
    [t+1, t+H] after the engine's .shift(1)). A newer trigger overrides an older
    one still in its holding window.
    """
    ret = close.pct_change()
    vol = ret.rolling(VOL_WINDOW).std().shift(1)
    z = ret / vol
    trig = pd.Series(np.nan, index=close.index)
    fade = -np.sign(z)
    trig[z >= k] = fade[z >= k]
    trig[z <= -k] = fade[z <= -k]
    # Hold the trigger for H bars (trigger bar + H-1 forward), newest wins.
    signal = trig.ffill(limit=H - 1) if H > 1 else trig
    return signal.fillna(0.0)


def daily_returns(net_hourly: pd.Series) -> pd.Series:
    d = (1.0 + net_hourly).groupby(net_hourly.index.normalize()).prod() - 1.0
    d.index = pd.to_datetime(d.index)
    return d


def evaluate(prices: pd.DataFrame, k: float, H: int) -> dict:
    signal = build_signal(prices["Close"], k, H)
    res = run_backtest(prices, signal, cost_model=CRYPTO_COST)
    res["daily"] = daily_returns(res["returns"])
    res["daily_gross"] = daily_returns(res["gross_returns"])
    return res


def is_sharpe(prices: pd.DataFrame, k: float, H: int) -> float:
    d = evaluate(prices, k, H)["daily"]
    return compute_metrics(d, periods_per_year=DPY)["sharpe"]


def main() -> None:
    px = get_crypto_ohlcv("BTC/USDT", timeframe="1h")
    px = px[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    is_px = px.loc[:IS_END]
    oos_px = px.loc[OOS_START:]

    grid = list(itertools.product(SIGMAS, HOLDS))
    is_scores = {c: is_sharpe(is_px, *c) for c in grid}
    best = max(is_scores, key=is_scores.get)
    k, H = best
    print(f"IS best combo: sigma={k} hold={H}h  IS daily Sharpe={is_scores[best]:.3f}"
          f"  (of {N_TRIALS} trials)")

    oos = evaluate(oos_px, k, H)
    daily, daily_gross = oos["daily"], oos["daily_gross"]
    m = compute_metrics(daily, periods_per_year=DPY)
    m_gross = compute_metrics(daily_gross, periods_per_year=DPY)
    ts = trade_stats(oos["trades"])
    bh_daily = daily_returns(oos["buy_hold"].pct_change().fillna(0.0))
    bh_m = compute_metrics(bh_daily, periods_per_year=DPY)

    perm = permutation_test(
        oos["returns"], oos_px["Close"].pct_change().fillna(0.0),
        oos["position"], n_perm=2000, metric="sharpe",
    )
    boot = bootstrap_ci(daily, statistic="sharpe", n_boot=2000)
    pp_sharpe = float(daily.mean() / daily.std(ddof=1))
    dsr = deflated_sharpe_ratio(
        observed_sharpe=pp_sharpe, n_obs=int(daily.shape[0]),
        n_trials=N_TRIALS, returns=daily,
    )

    oos_grid = {c: compute_metrics(evaluate(oos_px, *c)["daily"],
                                   periods_per_year=DPY)["sharpe"] for c in grid}
    n_pos = sum(v > 0 for v in oos_grid.values())

    print("\n=== OOS (2023-01 .. now), net of 12bps/side ===")
    print(f"  CAGR {m['cagr']:.1%}  Sharpe {m['sharpe']:.2f}  MaxDD {m['max_drawdown']:.1%}"
          f"  | gross Sharpe {m_gross['sharpe']:.2f}")
    print(f"  Buy&Hold: CAGR {bh_m['cagr']:.1%}  Sharpe {bh_m['sharpe']:.2f}")
    print(f"  Trades {ts['n_trades']}  WinRate {ts['win_rate']:.1%}  PF {ts['profit_factor']:.2f}"
          f"  avgHold {ts['avg_holding_days']:.1f} bars")
    print(f"  Permutation p={perm['p_value']:.4f}  "
          f"Bootstrap Sharpe 95% CI [{boot['ci_low']:.2f}; {boot['ci_high']:.2f}]")
    print(f"  Deflated Sharpe (PSR, n_trials={N_TRIALS}): {dsr['psr_deflated']:.3f}")
    print(f"  OOS grid: {n_pos}/{N_TRIALS} combos positive  ->",
          {f"s{c[0]}H{c[1]}": round(v, 2) for c, v in oos_grid.items()})

    metrics = {
        "locked_combo": {"sigma": k, "hold_h": H, "vol_window_h": VOL_WINDOW},
        "is_sharpe": is_scores[best], "n_trials": N_TRIALS,
        "oos_net": m, "oos_gross": m_gross, "buy_hold": bh_m,
        "trade_stats": ts, "permutation": perm, "bootstrap": boot,
        "deflated_sharpe": dsr, "oos_grid_positive": f"{n_pos}/{N_TRIALS}",
    }
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    oos["equity"].to_csv(RESULTS / "equity.csv")
    oos["trades"].to_csv(RESULTS / "trades.csv", index=False)
    pd.Series({f"s{a}_H{b}": v for (a, b), v in oos_grid.items()}).to_csv(
        RESULTS / "oos_grid_sharpe.csv")

    fig, ax = plt.subplots(figsize=(12, 6))
    strat_eq = (1.0 + daily).cumprod()
    bh_eq = (1.0 + bh_daily).cumprod()
    ax.plot(strat_eq.index, strat_eq.values, label="Over-Extension Fade (net)", lw=1.6)
    ax.plot(bh_eq.index, bh_eq.values, label="Buy & Hold BTC", lw=1.2, color="#888")
    ax.set_title(f"0013 BTC Over-Extension Reversion OOS — sigma {k}, hold {H}h")
    ax.set_ylabel("Equity (Start=1)")
    ax.legend()
    fig.subplots_adjust(bottom=0.2)
    fig.text(0.5, 0.02,
             "OOS-Kapitalkurve der long/short Over-Extension-Fade-Regel netto nach "
             "12bps/Seite vs. Buy & Hold. Handelt nur auf +/-k-sigma-Extrembars.",
             ha="center", fontsize=8.5, style="italic", color="#444")
    fig.savefig(PLOTS / "oos_equity.png", dpi=130)

    piv = pd.DataFrame(
        [[oos_grid[(s, h)] for h in HOLDS] for s in SIGMAS],
        index=[f"{s}σ" for s in SIGMAS], columns=[f"H{h}" for h in HOLDS])
    fig2, ax2 = plt.subplots(figsize=(7, 4))
    im = ax2.imshow(piv.values, cmap="RdYlGn", aspect="auto",
                    vmin=-abs(piv.values).max(), vmax=abs(piv.values).max())
    ax2.set_xticks(range(len(piv.columns)), piv.columns)
    ax2.set_yticks(range(len(piv.index)), piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax2.text(j, i, f"{piv.values[i, j]:.2f}", ha="center", va="center", fontsize=9)
    ax2.set_title("OOS daily Sharpe across the grid")
    fig2.colorbar(im, ax=ax2, shrink=0.8)
    fig2.subplots_adjust(bottom=0.16)
    fig2.text(0.5, 0.02, "OOS-Sharpe je (sigma, hold). Zusammenhaengendes gruenes "
              "Plateau = robust; einzelner Fleck = Overfit.",
              ha="center", fontsize=8.5, style="italic", color="#444")
    fig2.savefig(PLOTS / "oos_robustness.png", dpi=130)

    card = {
        "id": "0013", "name": "BTC Over-Extension Reversion",
        "category": "mean-reversion / intraday",
        "oos_sharpe": m["sharpe"], "oos_cagr": m["cagr"],
        "perm_p": perm["p_value"], "dsr": dsr["psr_deflated"], "n_trades": ts["n_trades"],
    }
    (RESULTS / "card.json").write_text(json.dumps(card, indent=2, default=float))
    print(f"\nSaved artefacts -> {RESULTS}")


if __name__ == "__main__":
    main()
