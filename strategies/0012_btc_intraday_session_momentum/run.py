"""Strategy 0012 — BTC intraday session momentum (US active window).

Hypothesis (derived from analysis/btc_hourly_volatility.py):
    Bitcoin volatility clusters in the US session 13-16 UTC (peak 14:00 UTC),
    driven by institutional flow and US macro releases. A directional impulse
    that forms going *into* that window tends to CONTINUE through it (momentum).
    The dead hours (03-06 UTC) are thin-liquidity noise and are avoided.

Rule (parametrized; long/short to strip out the crypto buy-and-hold drift):
    At the close of hour `e` (entry), take the sign of the return over the prior
    `L` hours. Hold that direction for `H` hours (the active window), flat
    otherwise. One round-trip per day.

Discipline:
    * IS 2017-08..2022-12 picks the best of a small 3x3x3 grid (n_trials = 27).
    * OOS 2023-01.. judges the locked rule only.
    * Realistic crypto cost (Binance taker ~10bps + 2bps slippage = 12bps/side).
    * Hourly engine (look-ahead safe via .shift(1)); metrics on the daily series.
    * Permutation, bootstrap CI, Deflated Sharpe (charged the full grid width).

Run:
    .venv/Scripts/python.exe strategies/0012_btc_intraday_session_momentum/run.py
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
DPY = 365  # crypto trades every calendar day

# Crypto cost: Binance spot taker fee 0.10% (=10bps) folded into slippage_bps,
# plus 2bps execution slippage. commission_per_share/min set to 0 so the cost is
# a flat fraction of notional regardless of price -> 12bps per side, 24bps RT.
CRYPTO_COST = CostModel(
    commission_per_share=0.0, min_commission=0.0, slippage_bps=12.0, regulatory_bps=0.0
)

# Small, pre-declared grid. Entry hours straddle the US-session ramp; lookbacks
# and holds are short (the move forms and plays out within the active window).
ENTRY_HOURS = [12, 13, 14]
LOOKBACKS = [1, 2, 3]
HOLDS = [2, 3, 4]
N_TRIALS = len(ENTRY_HOURS) * len(LOOKBACKS) * len(HOLDS)


def build_signal(close: pd.Series, e: int, L: int, H: int) -> pd.Series:
    """Decision-time target position for the session-momentum rule.

    Signal is non-zero on hours [e, e+H-1] carrying the sign of the prior-L-hour
    return measured at hour e. The engine shifts by one bar, so the position is
    actually held over hours [e+1, e+H]. No wrap-around (e+H-1 <= 23 by grid).
    """
    idx = close.index
    hour = idx.hour
    day = idx.normalize()
    ret_L = close / close.shift(L) - 1.0
    trig_e = np.sign(ret_L)
    day_trig = pd.Series(np.where(hour == e, trig_e, np.nan), index=idx)
    day_trig = day_trig.groupby(day).ffill()
    in_window = (hour >= e) & (hour < e + H)
    return day_trig.where(in_window, 0.0).fillna(0.0)


def daily_returns(net_hourly: pd.Series) -> pd.Series:
    """Compound the net hourly returns into one value per calendar day (UTC)."""
    d = (1.0 + net_hourly).groupby(net_hourly.index.normalize()).prod() - 1.0
    d.index = pd.to_datetime(d.index)
    return d


def evaluate(prices: pd.DataFrame, e: int, L: int, H: int) -> dict:
    """Run the hourly backtest and return engine result + daily return series."""
    signal = build_signal(prices["Close"], e, L, H)
    res = run_backtest(prices, signal, cost_model=CRYPTO_COST)
    res["daily"] = daily_returns(res["returns"])
    res["daily_gross"] = daily_returns(res["gross_returns"])
    return res


def is_sharpe(prices: pd.DataFrame, e: int, L: int, H: int) -> float:
    d = evaluate(prices, e, L, H)["daily"]
    return compute_metrics(d, periods_per_year=DPY)["sharpe"]


def main() -> None:
    px = get_crypto_ohlcv("BTC/USDT", timeframe="1h")
    px = px[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    is_px = px.loc[:IS_END]
    oos_px = px.loc[OOS_START:]

    # --- In-sample grid search -------------------------------------------------
    grid = list(itertools.product(ENTRY_HOURS, LOOKBACKS, HOLDS))
    is_scores = {combo: is_sharpe(is_px, *combo) for combo in grid}
    best = max(is_scores, key=is_scores.get)
    e, L, H = best
    print(f"IS best combo: entry={e}h lookback={L}h hold={H}h  "
          f"IS daily Sharpe={is_scores[best]:.3f}  (of {N_TRIALS} trials)")

    # --- Out-of-sample evaluation of the LOCKED rule ---------------------------
    oos = evaluate(oos_px, e, L, H)
    daily = oos["daily"]
    daily_gross = oos["daily_gross"]
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

    pp_sharpe = float(daily.mean() / daily.std(ddof=1))  # per-period (daily) Sharpe
    dsr = deflated_sharpe_ratio(
        observed_sharpe=pp_sharpe, n_obs=int(daily.shape[0]),
        n_trials=N_TRIALS, returns=daily,
    )

    # --- OOS robustness across the whole grid (plateau vs spike?) --------------
    oos_grid = {combo: compute_metrics(evaluate(oos_px, *combo)["daily"],
                                       periods_per_year=DPY)["sharpe"]
                for combo in grid}
    n_pos = sum(v > 0 for v in oos_grid.values())

    # --- Report to console -----------------------------------------------------
    print("\n=== OOS (2023-01 .. now), net of 12bps/side ===")
    print(f"  CAGR {m['cagr']:.1%}  Sharpe {m['sharpe']:.2f}  MaxDD {m['max_drawdown']:.1%}"
          f"  | gross Sharpe {m_gross['sharpe']:.2f}")
    print(f"  Buy&Hold: CAGR {bh_m['cagr']:.1%}  Sharpe {bh_m['sharpe']:.2f}")
    print(f"  Trades {ts['n_trades']}  WinRate {ts['win_rate']:.1%}  "
          f"PF {ts['profit_factor']:.2f}")
    print(f"  Permutation p={perm['p_value']:.4f}  "
          f"Bootstrap Sharpe 95% CI [{boot['ci_low']:.2f}; {boot['ci_high']:.2f}]")
    print(f"  Deflated Sharpe (PSR, n_trials={N_TRIALS}): {dsr['psr_deflated']:.3f}")
    print(f"  OOS grid: {n_pos}/{N_TRIALS} combos have positive Sharpe")

    # --- Persist artefacts -----------------------------------------------------
    metrics = {
        "locked_combo": {"entry_hour": e, "lookback_h": L, "hold_h": H},
        "is_sharpe": is_scores[best],
        "n_trials": N_TRIALS,
        "oos_net": m, "oos_gross": m_gross, "buy_hold": bh_m,
        "trade_stats": ts, "permutation": perm, "bootstrap": boot,
        "deflated_sharpe": dsr,
        "oos_grid_positive": f"{n_pos}/{N_TRIALS}",
    }
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    oos["equity"].to_csv(RESULTS / "equity.csv")
    oos["trades"].to_csv(RESULTS / "trades.csv", index=False)
    pd.Series({f"e{a}_L{b}_H{c}": v for (a, b, c), v in oos_grid.items()}).to_csv(
        RESULTS / "oos_grid_sharpe.csv")

    # --- Plots -----------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 6))
    strat_eq = (1.0 + daily).cumprod()
    bh_eq = (1.0 + bh_daily).cumprod()
    ax.plot(strat_eq.index, strat_eq.values, label="Session-Momentum (net)", lw=1.6)
    ax.plot(bh_eq.index, bh_eq.values, label="Buy & Hold BTC", lw=1.2, color="#888")
    ax.set_yscale("log")
    ax.set_title(f"0012 BTC Session-Momentum OOS — entry {e}h, lookback {L}h, hold {H}h")
    ax.set_ylabel("Equity (log, Start=1)")
    ax.legend()
    fig.subplots_adjust(bottom=0.2)
    fig.text(0.5, 0.02,
             "OOS-Kapitalkurve (log) der long/short Session-Momentum-Regel netto nach "
             "12bps/Seite vs. Buy & Hold. Long/short entfernt den Aufwaertsdrift -> reines Timing.",
             ha="center", fontsize=8.5, style="italic", color="#444")
    fig.savefig(PLOTS / "oos_equity.png", dpi=130)

    # robustness heatmap: rows=entry hour, cols=(L,H)
    piv = pd.DataFrame(
        [[oos_grid[(eh, L_, H_)] for L_ in LOOKBACKS for H_ in HOLDS]
         for eh in ENTRY_HOURS],
        index=[f"{eh}h" for eh in ENTRY_HOURS],
        columns=[f"L{L_}H{H_}" for L_ in LOOKBACKS for H_ in HOLDS],
    )
    fig2, ax2 = plt.subplots(figsize=(11, 4))
    im = ax2.imshow(piv.values, cmap="RdYlGn", aspect="auto",
                    vmin=-abs(piv.values).max(), vmax=abs(piv.values).max())
    ax2.set_xticks(range(len(piv.columns)), piv.columns)
    ax2.set_yticks(range(len(piv.index)), piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax2.text(j, i, f"{piv.values[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax2.set_title("OOS daily Sharpe across the grid (green = positive)")
    fig2.colorbar(im, ax=ax2, shrink=0.8)
    fig2.subplots_adjust(bottom=0.18)
    fig2.text(0.5, 0.02,
              "Out-of-sample Sharpe je Parameter-Kombination. Ein zusammenhaengendes "
              "gruenes Plateau = robust; ein einzelner gruener Fleck = Overfit.",
              ha="center", fontsize=8.5, style="italic", color="#444")
    fig2.savefig(PLOTS / "oos_robustness.png", dpi=130)

    card = {
        "id": "0012", "name": "BTC Intraday Session-Momentum",
        "category": "momentum / intraday",
        "oos_sharpe": m["sharpe"], "oos_cagr": m["cagr"],
        "perm_p": perm["p_value"], "dsr": dsr["psr_deflated"],
        "n_trades": ts["n_trades"],
    }
    (RESULTS / "card.json").write_text(json.dumps(card, indent=2, default=float))
    print(f"\nSaved artefacts -> {RESULTS}")


if __name__ == "__main__":
    main()
