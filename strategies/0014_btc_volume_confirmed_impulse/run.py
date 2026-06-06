"""Strategy 0014 — BTC volume-confirmed impulse continuation (orderflow).

Hypothesis (orderflow mechanism, low turnover):
    0012 taught "vola != direction" and 0013 taught that extreme hourly moves
    *continue* (momentum), they do not revert — but the raw continuation was too
    weak to clear 24bps round-trip cost. The missing ingredient is a DIRECTIONAL
    CONVICTION FILTER. Order flow provides it.

    A large hourly bar (|ret| >= k*sigma) that is BOTH
      (a) backed by abnormally high volume (relvol = vol / median(vol) >= V), and
      (b) closes near its extreme in the move direction (close-location value CLV
          has the same sign as the return -> aggressive takers carried price into
          the close, it was not a rejected wick),
    reflects genuine one-sided aggression: information arrival, stop runs, or
    forced-liquidation cascades on the perp. In a fragmented, 24/7, retail-heavy,
    momentum-capital-dominated market this repricing diffuses slowly, so the move
    CONTINUES over the next H hours. We RIDE it (long on up-impulse, short on
    down-impulse), held H hours, flat otherwise.

    The triple gate fires only on rare conviction bars -> very low turnover, the
    binding constraint identified in 0012/0013.

Discipline:
    * IS 2017-08..2022-12 picks the best of a pre-declared 3x3 grid (n_trials=9).
    * OOS 2023-01.. judges the locked rule only.
    * Fixed (NOT searched): VOL_WINDOW=168h (7d), extremity k=1.5 sigma, CLV
      sign-confirmation required.
    * Searched: volume multiple V in {1.5, 2.0, 3.0} x holding H in {3, 6, 12}h.
    * Realistic Bitget perp cost: taker 6bps + 2bps slippage = 8bps/side. A
      stress run at 12bps/side checks robustness to the (binding) cost assumption.
    * Hourly engine (look-ahead safe via .shift(1)); metrics on the daily series.
    * Permutation, bootstrap CI, Deflated Sharpe (charged the full grid width).

Run:
    .venv/Scripts/python.exe strategies/0014_btc_volume_confirmed_impulse/run.py
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
from quantlab.costs import BITGET_PERP_TAKER, CostModel  # noqa: E402
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

# Fixed structural parameters — NOT part of the search.
VOL_WINDOW = 168  # 7 days of hourly bars: volume-baseline + return-sigma window
K_SIGMA = 1.5  # a bar counts as an "impulse" when |ret| >= K_SIGMA * sigma

# Bitget perp taker cost (base case) and a cost-stress model.
COST_BASE = BITGET_PERP_TAKER  # 8 bps/side, 16 bps round-trip
COST_STRESS = CostModel(
    commission_per_share=0.0, min_commission=0.0, slippage_bps=4.0, regulatory_bps=8.0
)  # 12 bps/side, 24 bps round-trip (the old Binance-spot-equivalent assumption)

# Pre-declared grid: volume multiple x holding hours = 9 trials.
VOLMULTS = [1.5, 2.0, 3.0]
HOLDS = [3, 6, 12]
N_TRIALS = len(VOLMULTS) * len(HOLDS)


def build_signal(prices: pd.DataFrame, V: float, H: int) -> pd.Series:
    """Decision-time target position for the volume-confirmed impulse.

    All normalizers use only *past* bars (``.shift(1)``) so the current bar can
    never contaminate its own baseline. The triggering bar's own return, volume
    and close-location are known at decision time t (the bar has closed); the
    engine then holds the position from t+1 onward.
    """
    close = prices["Close"]
    high = prices["High"]
    low = prices["Low"]
    volume = prices["Volume"]

    ret = close.pct_change()
    sigma = ret.rolling(VOL_WINDOW).std().shift(1)
    z = ret / sigma

    vol_base = volume.rolling(VOL_WINDOW).median().shift(1)
    relvol = volume / vol_base

    rng = (high - low).replace(0.0, np.nan)
    clv = ((close - low) - (high - close)) / rng  # in [-1, 1]

    up = (z >= K_SIGMA) & (relvol >= V) & (clv > 0)
    down = (z <= -K_SIGMA) & (relvol >= V) & (clv < 0)

    trig = pd.Series(np.nan, index=close.index)
    trig[up] = 1.0
    trig[down] = -1.0
    # Ride the impulse for H bars (trigger bar + H-1 forward); newest trigger wins.
    signal = trig.ffill(limit=H - 1) if H > 1 else trig
    return signal.fillna(0.0)


def daily_returns(net_hourly: pd.Series) -> pd.Series:
    d = (1.0 + net_hourly).groupby(net_hourly.index.normalize()).prod() - 1.0
    d.index = pd.to_datetime(d.index)
    return d


def evaluate(prices: pd.DataFrame, V: float, H: int, cost: CostModel) -> dict:
    signal = build_signal(prices, V, H)
    res = run_backtest(prices, signal, cost_model=cost)
    res["daily"] = daily_returns(res["returns"])
    res["daily_gross"] = daily_returns(res["gross_returns"])
    return res


def is_sharpe(prices: pd.DataFrame, V: float, H: int) -> float:
    d = evaluate(prices, V, H, COST_BASE)["daily"]
    return compute_metrics(d, periods_per_year=DPY)["sharpe"]


def main() -> None:
    px = get_crypto_ohlcv("BTC/USDT", timeframe="1h")
    px = px[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    is_px = px.loc[:IS_END]
    oos_px = px.loc[OOS_START:]

    rt_base = 2.0 * COST_BASE.cost_fraction_per_side(float(px["Close"].mean()))
    rt_stress = 2.0 * COST_STRESS.cost_fraction_per_side(float(px["Close"].mean()))
    print(f"Bitget perp cost: {rt_base*1e4:.1f} bps round-trip (taker 6 + slip 2 /side)."
          f"  Stress: {rt_stress*1e4:.1f} bps RT.")
    print(f"  Example: on a 10,000 USDT position one round-trip costs "
          f"{rt_base*10_000:.2f} USDT (base) / {rt_stress*10_000:.2f} USDT (stress).")

    grid = list(itertools.product(VOLMULTS, HOLDS))
    is_scores = {c: is_sharpe(is_px, *c) for c in grid}
    best = max(is_scores, key=is_scores.get)
    V, H = best
    print(f"\nIS best combo: V={V}x vol, hold={H}h  IS daily Sharpe={is_scores[best]:.3f}"
          f"  (of {N_TRIALS} trials)")

    oos = evaluate(oos_px, V, H, COST_BASE)
    daily, daily_gross = oos["daily"], oos["daily_gross"]
    m = compute_metrics(daily, periods_per_year=DPY)
    m_gross = compute_metrics(daily_gross, periods_per_year=DPY)
    ts = trade_stats(oos["trades"])
    bh_daily = daily_returns(oos["buy_hold"].pct_change().fillna(0.0))
    bh_m = compute_metrics(bh_daily, periods_per_year=DPY)

    # Cost-stress OOS (same locked rule, heavier cost).
    oos_stress = evaluate(oos_px, V, H, COST_STRESS)
    m_stress = compute_metrics(oos_stress["daily"], periods_per_year=DPY)

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

    oos_grid = {c: compute_metrics(evaluate(oos_px, *c, COST_BASE)["daily"],
                                   periods_per_year=DPY)["sharpe"] for c in grid}
    n_pos = sum(v > 0 for v in oos_grid.values())

    print("\n=== OOS (2023-01 .. now), net of Bitget 8bps/side ===")
    print(f"  CAGR {m['cagr']:.1%}  Sharpe {m['sharpe']:.2f}  MaxDD {m['max_drawdown']:.1%}"
          f"  | gross Sharpe {m_gross['sharpe']:.2f}")
    print(f"  Cost-stress (12bps/side): Sharpe {m_stress['sharpe']:.2f}  CAGR {m_stress['cagr']:.1%}")
    print(f"  Buy&Hold: CAGR {bh_m['cagr']:.1%}  Sharpe {bh_m['sharpe']:.2f}")
    print(f"  Trades {ts['n_trades']}  WinRate {ts['win_rate']:.1%}  PF {ts['profit_factor']:.2f}"
          f"  avgHold {ts['avg_holding_days']:.1f} bars")
    print(f"  Permutation p={perm['p_value']:.4f}  "
          f"Bootstrap Sharpe 95% CI [{boot['ci_low']:.2f}; {boot['ci_high']:.2f}]")
    print(f"  Deflated Sharpe (PSR, n_trials={N_TRIALS}): {dsr['psr_deflated']:.3f}")
    print(f"  OOS grid: {n_pos}/{N_TRIALS} combos positive  ->",
          {f"V{c[0]}H{c[1]}": round(v, 2) for c, v in oos_grid.items()})

    metrics = {
        "locked_combo": {"vol_mult": V, "hold_h": H, "vol_window_h": VOL_WINDOW,
                         "k_sigma": K_SIGMA},
        "cost_round_trip_bps": {"base": rt_base * 1e4, "stress": rt_stress * 1e4},
        "is_sharpe": is_scores[best], "n_trials": N_TRIALS,
        "oos_net": m, "oos_gross": m_gross, "oos_cost_stress": m_stress,
        "buy_hold": bh_m, "trade_stats": ts, "permutation": perm,
        "bootstrap": boot, "deflated_sharpe": dsr,
        "oos_grid_positive": f"{n_pos}/{N_TRIALS}",
    }
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    oos["equity"].to_csv(RESULTS / "equity.csv")
    oos["trades"].to_csv(RESULTS / "trades.csv", index=False)
    pd.Series({f"V{a}_H{b}": v for (a, b), v in oos_grid.items()}).to_csv(
        RESULTS / "oos_grid_sharpe.csv")

    fig, ax = plt.subplots(figsize=(12, 6))
    strat_eq = (1.0 + daily).cumprod()
    bh_eq = (1.0 + bh_daily).cumprod()
    ax.plot(strat_eq.index, strat_eq.values, label="Volume-Confirmed Impulse (net)", lw=1.6)
    ax.plot(bh_eq.index, bh_eq.values, label="Buy & Hold BTC", lw=1.2, color="#888")
    ax.set_title(f"0014 BTC Volume-Confirmed Impulse OOS — V {V}x, hold {H}h")
    ax.set_ylabel("Equity (Start=1)")
    ax.legend()
    fig.subplots_adjust(bottom=0.2)
    fig.text(0.5, 0.02,
             "OOS-Kapitalkurve der long/short Impuls-Continuation-Regel netto nach "
             "8bps/Seite (Bitget Taker) vs. Buy & Hold. Handelt nur auf seltenen "
             "Hochvolumen-Impulsbars mit Orderflow-Bestaetigung.",
             ha="center", fontsize=8.5, style="italic", color="#444")
    fig.savefig(PLOTS / "oos_equity.png", dpi=130)

    piv = pd.DataFrame(
        [[oos_grid[(v, h)] for h in HOLDS] for v in VOLMULTS],
        index=[f"{v}x" for v in VOLMULTS], columns=[f"H{h}" for h in HOLDS])
    fig2, ax2 = plt.subplots(figsize=(7, 4))
    im = ax2.imshow(piv.values, cmap="RdYlGn", aspect="auto",
                    vmin=-abs(piv.values).max(), vmax=abs(piv.values).max())
    ax2.set_xticks(range(len(piv.columns)), piv.columns)
    ax2.set_yticks(range(len(piv.index)), piv.index)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax2.text(j, i, f"{piv.values[i, j]:.2f}", ha="center", va="center", fontsize=9)
    ax2.set_title("OOS daily Sharpe across the grid")
    ax2.set_xlabel("hold (h)"); ax2.set_ylabel("volume multiple")
    fig2.colorbar(im, ax=ax2, shrink=0.8)
    fig2.subplots_adjust(bottom=0.16)
    fig2.text(0.5, 0.02, "OOS-Sharpe je (Volumen-Vielfaches, Haltedauer). "
              "Zusammenhaengendes gruenes Plateau = robust; einzelner Fleck = Overfit.",
              ha="center", fontsize=8.5, style="italic", color="#444")
    fig2.savefig(PLOTS / "oos_robustness.png", dpi=130)

    card = {
        "id": "0014", "name": "BTC Volume-Confirmed Impulse Continuation",
        "category": "momentum / orderflow / intraday",
        "oos_sharpe": m["sharpe"], "oos_cagr": m["cagr"],
        "perm_p": perm["p_value"], "dsr": dsr["psr_deflated"], "n_trades": ts["n_trades"],
    }
    (RESULTS / "card.json").write_text(json.dumps(card, indent=2, default=float))
    print(f"\nSaved artefacts -> {RESULTS}")


if __name__ == "__main__":
    main()
