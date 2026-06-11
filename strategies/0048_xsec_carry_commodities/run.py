"""0048 — Cross-Sectional Commodity Carry (term structure).

Second strategy in the cross-sectional paradigm, and the one 0047 pointed to.
Carry ranks commodities by their roll yield (front vs second contract): long the
backwardated markets (front > second, a long earns the roll up the curve), short
the contangoed ones. Dollar-neutral, monthly rebalance.

Macro rationale: commodity carry is one of the most persistent documented factors
(Koijen/Moskowitz/Pedersen/Vrugt 2018, "Carry"; Gorton/Rouwenhorst). Unlike
momentum it is STRUCTURAL, not behavioural: backwardation reflects scarce
inventory / convenience yield (consumers pay up for prompt delivery), so the
premium is an inventory-risk compensation that is not arbitraged away.

Data: Databento GLBX.MDP3 continuous front (.c.0) and second (.c.1) contracts,
daily, 2010-2026, 16 CME/NYMEX/COMEX/CBOT commodities (no ICE softs). Carry is
annualized per market by nominal contract spacing (energy ~1mo .. PGM ~3mo).

No look-ahead: carry is the month-end front/second log spread; the engine
forward-fills the target weights and shifts them (held from the next day).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import plotting
from quantlab.cross_sectional import cross_sectional_permutation_test, run_cross_sectional
from quantlab.futures_curve import (
    CURVE_UNIVERSE,
    carry_signal,
    get_carry_panel,
    roll_adjusted_front_panel,
)
from quantlab.metrics import compute_metrics
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio, t_test_mean_return

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)

SPLIT = "2018-06-01"       # GLBX starts 2010-06 -> ~8y IS / ~8y OOS
QUANTILE = 0.25
COST_BPS_SIDE = 6.0
# Robustness grid: quantile {0.25,0.33} x rebalance {ME,QE} x annualize {T,F} = 8.
N_TRIALS = 8


def report_block(returns: pd.Series, label: str) -> dict:
    m = compute_metrics(returns)
    sp_pp = returns.mean() / returns.std(ddof=1) if returns.std(ddof=1) else 0.0
    print(f"[{label}]  n={len(returns)}  net Sharpe(ann)={m['sharpe']:.2f}  "
          f"CAGR={m['cagr']*100:.1f}%  MaxDD={m['max_drawdown']*100:.1f}%")
    return {"metrics": m, "sharpe_pp": float(sp_pp)}


def main() -> None:
    print("Loading term structure (front + second) ...")
    curves = get_carry_panel()
    signal = carry_signal(curves, annualize=True)
    # Returns come from the ROLL-ADJUSTED front series (stitch gap removed via the
    # instrument_id roll dates); the naive front pct_change is a roll artifact
    # (lesson 0028/0029), confirmed losing -39 bps on every roll day.
    prices = roll_adjusted_front_panel().reindex(columns=list(curves))
    print(f"  {prices.shape[1]} commodities, {prices.shape[0]} days "
          f"({prices.index[0].date()}..{prices.index[-1].date()})")

    res = run_cross_sectional(
        prices, signal, rebalance="ME", quantile=QUANTILE,
        long_short=True, leg_weight=1.0, cost_bps_per_side=COST_BPS_SIDE,
    )
    full_ret = res["returns"]
    is_ret = full_ret[full_ret.index < SPLIT]
    oos_ret = full_ret[full_ret.index >= SPLIT]

    print("\n=== Cross-Sectional Commodity Carry (L/S quartiles) ===")
    full_stats = report_block(full_ret, "FULL")
    is_stats = report_block(is_ret, "IN-SAMPLE  <2018-06")
    oos_stats = report_block(oos_ret, "OUT-OF-SAMPLE >=2018-06")

    bench_ret = prices.pct_change().mean(axis=1)
    bench_oos = compute_metrics(bench_ret[bench_ret.index >= SPLIT].dropna())
    print(f"[benchmark EW long-only OOS] Sharpe(ann)={bench_oos['sharpe']:.2f}")

    print("\n=== Significance (OOS, net) ===")
    perm = cross_sectional_permutation_test(
        prices[prices.index >= SPLIT], signal[signal.index >= SPLIT],
        n_perm=500, rebalance="ME", quantile=QUANTILE, cost_bps_per_side=COST_BPS_SIDE,
    )
    print(f"  Permutation (rank-shuffle) p = {perm['p_value']:.3f}  "
          f"(obs Sharpe {perm['observed']:.2f} vs null {perm['null_mean']:.2f})")
    boot = bootstrap_ci(oos_ret, statistic="sharpe", n_boot=2000)
    print(f"  Bootstrap Sharpe 95% CI = [{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]")
    dsr = deflated_sharpe_ratio(observed_sharpe=oos_stats["sharpe_pp"],
                                n_obs=len(oos_ret), n_trials=N_TRIALS, returns=oos_ret)
    print(f"  Deflated Sharpe (N={N_TRIALS}) = {dsr['psr_deflated']:.3f}  "
          f"(SR*={dsr['expected_max_sharpe_under_null']:.3f} per-period)")
    tt = t_test_mean_return(oos_ret)
    print(f"  t-test mean daily return: t={tt['t_stat']:.2f}, p={tt['p_value']:.3f}")

    print("\n=== Robustness grid (OOS net annualized Sharpe) ===")
    grid = {}
    for q in (0.25, 0.33):
        for freq in ("ME", "QE"):
            for ann in (True, False):
                sig = carry_signal(curves, annualize=ann)
                r = run_cross_sectional(prices, sig, rebalance=freq, quantile=q,
                                        cost_bps_per_side=COST_BPS_SIDE)["returns"]
                r = r[r.index >= SPLIT]
                key = f"q{q}_{freq}_{'ann' if ann else 'raw'}"
                grid[key] = compute_metrics(r)["sharpe"]
    for k, v in grid.items():
        print(f"  {k:18s} Sharpe {v:+.2f}")

    # Per-commodity mean annualized carry (which markets sit long vs short).
    mean_carry = signal.mean().sort_values(ascending=False)
    print("\n=== Mean annualized carry by commodity (backwardation > 0) ===")
    for root, val in mean_carry.items():
        print(f"  {root:3s} {CURVE_UNIVERSE[root]:14s} {val*100:+.1f}%/yr")

    # Plots
    eq = (1 + full_ret).cumprod()
    bench_eq = (1 + bench_ret.fillna(0)).cumprod()
    fig = plotting.plot_equity(
        eq, benchmark=bench_eq, strategy_label="L/S Carry",
        benchmark_label="Equal-Weight Long-Only",
        title="0048 — Cross-Sectional Commodity Carry",
        caption="Dollar-neutrale Long-Backwardation/Short-Contango-Quartile, monatlich, "
                f"netto nach {COST_BPS_SIDE:.0f} bps/Seite. Senkrechte = IS/OOS-Split.",
    )
    fig.axes[0].axvline(pd.Timestamp(SPLIT), color="gray", linestyle="--", linewidth=1)
    plotting.savefig(fig, RESULTS / "equity.png")
    plotting.savefig(plotting.plot_drawdown(full_ret), RESULTS / "drawdown.png")

    out = {
        "universe_n": int(prices.shape[1]),
        "period": [str(prices.index[0].date()), str(prices.index[-1].date())],
        "config": {"quantile": QUANTILE, "rebalance": "ME",
                   "cost_bps_per_side": COST_BPS_SIDE, "annualized_carry": True},
        "full": full_stats["metrics"], "is": is_stats["metrics"],
        "oos": oos_stats["metrics"], "benchmark_oos": bench_oos,
        "significance": {
            "permutation_p": perm["p_value"],
            "bootstrap_sharpe_ci": [boot["ci_low"], boot["ci_high"]],
            "deflated_sharpe": dsr["psr_deflated"],
            "ttest_p": tt["p_value"],
        },
        "robustness_grid": grid,
        "mean_carry_pct_yr": {k: float(v * 100) for k, v in mean_carry.items()},
    }
    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=float))
    full_ret.to_frame("net_return").to_csv(RESULTS / "returns.csv")
    print(f"\nSaved -> {RESULTS}")


if __name__ == "__main__":
    main()
