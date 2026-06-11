"""0047 — Cross-Sectional Commodity Momentum (12-1).

First strategy in the cross-sectional / relative-value paradigm. Instead of
timing one market, we rank ~20 commodity futures every month by 12-1 momentum,
go long the top quartile and short the bottom, dollar-neutral. The bet is
RELATIVE (which commodity beats which), so observations scale with the universe
and the book is market-neutral.

Macro rationale: cross-sectional momentum is one of the most replicated factors
(Asness/Moskowitz/Pedersen 2013, "Value and Momentum Everywhere"). In commodities
it is driven by slow diffusion of supply/demand information and persistent
backwardation/contango regimes — structural, not a pure behavioural fad.

Data-quality guards (lessons 0005 / 0025): drop any series with a non-positive
print (CL=F went to -$37 in 2020-04) in its trailing window, and drop frozen
feeds (too few distinct closes per year).

No look-ahead: signal is the 12-1 momentum at each month-end close; the engine
forward-fills the target weights and shifts them, so they are held from the next
day onward.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import plotting
from quantlab.cross_sectional import (
    cross_sectional_permutation_test,
    momentum_signal,
    run_cross_sectional,
)
from quantlab.data import get_multiple_closes
from quantlab.metrics import compute_metrics
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio, t_test_mean_return

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)

# ── Universe: liquid commodity futures across sectors ───────────────────────
UNIVERSE = {
    "CL=F": "WTI Rohöl", "NG=F": "Erdgas", "RB=F": "Benzin", "HO=F": "Heizöl",
    "GC=F": "Gold", "SI=F": "Silber", "HG=F": "Kupfer", "PL=F": "Platin",
    "PA=F": "Palladium",
    "ZC=F": "Mais", "ZW=F": "Weizen", "ZS=F": "Sojabohnen", "ZL=F": "Sojaöl",
    "ZM=F": "Sojamehl",
    "SB=F": "Zucker", "KC=F": "Kaffee", "CC=F": "Kakao", "CT=F": "Baumwolle",
    "LE=F": "Lebendrind", "GF=F": "Mastrind", "HE=F": "Mageschwein",
}

START = "2007-01-01"
SPLIT = "2017-01-01"          # IS < SPLIT <= OOS
LOOKBACK, SKIP = 252, 21      # 12-1 month momentum (pre-committed headline)
QUANTILE = 0.25               # quartiles
COST_BPS_SIDE = 6.0           # blended liquid-futures cost, per side (12 bps RT)

# Multiple-testing burden for the Deflated Sharpe: lookbacks {63,126,189,252,
# 378,504} x rebalance {ME,QE} = 12 variants considered in robustness.
N_TRIALS = 12


def clean_panel(prices: pd.DataFrame) -> pd.DataFrame:
    """Drop frozen feeds and neutralize non-positive prints."""
    keep = {}
    for col in prices.columns:
        s = prices[col].dropna()
        if s.empty:
            continue
        # Frozen-feed guard: need >50 distinct closes per year on average.
        distinct_per_year = s.groupby(s.index.year).nunique().mean()
        if distinct_per_year < 50:
            print(f"  drop {col}: frozen feed ({distinct_per_year:.0f} distinct/yr)")
            continue
        keep[col] = prices[col]
    panel = pd.DataFrame(keep)
    # Non-positive prints (e.g. CL=F 2020-04-20) -> NaN so momentum excludes them.
    panel = panel.where(panel > 0)
    return panel


def report_block(returns: pd.Series, label: str) -> dict:
    m = compute_metrics(returns)
    sp_pp = returns.mean() / returns.std(ddof=1) if returns.std(ddof=1) else 0.0
    print(f"\n[{label}]  n={len(returns)}  net Sharpe(ann)={m['sharpe']:.2f}  "
          f"CAGR={m['cagr']*100:.1f}%  MaxDD={m['max_drawdown']*100:.1f}%")
    return {"metrics": m, "sharpe_pp": float(sp_pp)}


def main() -> None:
    print("Loading universe ...")
    prices = get_multiple_closes(list(UNIVERSE), start=START)
    prices = clean_panel(prices)
    print(f"  {prices.shape[1]} instruments, {prices.shape[0]} days "
          f"({prices.index[0].date()}..{prices.index[-1].date()})")

    signal = momentum_signal(prices, lookback=LOOKBACK, skip=SKIP)

    # ── Full-sample run ────────────────────────────────────────────────────
    res = run_cross_sectional(
        prices, signal, rebalance="ME", quantile=QUANTILE,
        long_short=True, leg_weight=1.0, cost_bps_per_side=COST_BPS_SIDE,
    )
    full_ret = res["returns"]

    # ── IS / OOS split ─────────────────────────────────────────────────────
    is_ret = full_ret[full_ret.index < SPLIT]
    oos_ret = full_ret[full_ret.index >= SPLIT]

    print("\n=== Cross-Sectional Commodity Momentum (12-1, L/S quartiles) ===")
    full_stats = report_block(full_ret, "FULL")
    is_stats = report_block(is_ret, "IN-SAMPLE  <2017")
    oos_stats = report_block(oos_ret, "OUT-OF-SAMPLE >=2017")

    bench_ret = prices.pct_change().mean(axis=1)
    bench_oos = bench_ret[bench_ret.index >= SPLIT]
    bench_m = compute_metrics(bench_oos.dropna())
    print(f"[benchmark EW long-only OOS] Sharpe(ann)={bench_m['sharpe']:.2f}")

    # ── Significance on OOS ────────────────────────────────────────────────
    print("\n=== Significance (OOS, net) ===")
    perm = cross_sectional_permutation_test(
        prices[prices.index >= SPLIT], signal[signal.index >= SPLIT],
        n_perm=500, rebalance="ME", quantile=QUANTILE,
        cost_bps_per_side=COST_BPS_SIDE,
    )
    print(f"  Permutation (rank-shuffle) p = {perm['p_value']:.3f}  "
          f"(obs Sharpe {perm['observed']:.2f} vs null {perm['null_mean']:.2f})")

    boot = bootstrap_ci(oos_ret, statistic="sharpe", n_boot=2000)
    print(f"  Bootstrap Sharpe 95% CI = [{boot['ci_low']:.2f}, {boot['ci_high']:.2f}]")

    dsr = deflated_sharpe_ratio(
        observed_sharpe=oos_stats["sharpe_pp"], n_obs=len(oos_ret),
        n_trials=N_TRIALS, returns=oos_ret,
    )
    print(f"  Deflated Sharpe (N={N_TRIALS}) = {dsr['psr_deflated']:.3f}  "
          f"(SR*={dsr['expected_max_sharpe_under_null']:.3f} per-period)")

    tt = t_test_mean_return(oos_ret)
    print(f"  t-test mean daily return: t={tt['t_stat']:.2f}, p={tt['p_value']:.3f}")

    # ── Robustness grid (lookback x rebalance) ─────────────────────────────
    print("\n=== Robustness grid (OOS net annualized Sharpe) ===")
    grid = {}
    for lb in (63, 126, 189, 252, 378, 504):
        for freq in ("ME", "QE"):
            sig = momentum_signal(prices, lookback=lb, skip=SKIP)
            r = run_cross_sectional(prices, sig, rebalance=freq, quantile=QUANTILE,
                                    cost_bps_per_side=COST_BPS_SIDE)["returns"]
            r = r[r.index >= SPLIT]
            grid[f"lb{lb}_{freq}"] = compute_metrics(r)["sharpe"]
    for k, v in grid.items():
        print(f"  {k:12s} Sharpe {v:+.2f}")

    # ── Plots ──────────────────────────────────────────────────────────────
    eq = (1 + full_ret).cumprod()
    bench_eq = (1 + bench_ret.fillna(0)).cumprod()
    fig = plotting.plot_equity(
        eq, benchmark=bench_eq, strategy_label="L/S 12-1 Momentum",
        benchmark_label="Equal-Weight Long-Only",
        title="0047 — Cross-Sectional Commodity Momentum",
        caption="Dollar-neutrale Long/Short-Quartile, monatliches Rebalancing, "
                f"netto nach {COST_BPS_SIDE:.0f} bps/Seite. Senkrechte = IS/OOS-Split 2017.",
    )
    fig.axes[0].axvline(pd.Timestamp(SPLIT), color="gray", linestyle="--", linewidth=1)
    plotting.savefig(fig, RESULTS / "equity.png")
    plotting.savefig(plotting.plot_drawdown(full_ret), RESULTS / "drawdown.png")

    # ── Persist ────────────────────────────────────────────────────────────
    out = {
        "universe_n": int(prices.shape[1]),
        "period": [str(prices.index[0].date()), str(prices.index[-1].date())],
        "config": {"lookback": LOOKBACK, "skip": SKIP, "quantile": QUANTILE,
                   "rebalance": "ME", "cost_bps_per_side": COST_BPS_SIDE},
        "full": full_stats["metrics"], "is": is_stats["metrics"],
        "oos": oos_stats["metrics"], "benchmark_oos": bench_m,
        "significance": {
            "permutation_p": perm["p_value"],
            "bootstrap_sharpe_ci": [boot["ci_low"], boot["ci_high"]],
            "deflated_sharpe": dsr["psr_deflated"],
            "dsr_expected_max": dsr["expected_max_sharpe_under_null"],
            "ttest_p": tt["p_value"],
        },
        "robustness_grid": grid,
    }
    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=float))
    full_ret.to_frame("net_return").to_csv(RESULTS / "returns.csv")
    print(f"\nSaved -> {RESULTS}")


if __name__ == "__main__":
    main()
