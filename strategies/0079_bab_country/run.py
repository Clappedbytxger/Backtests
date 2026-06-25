"""Strategy 0079 — Betting-Against-Beta on country equity ETFs (Frazzini/Pedersen).

Idea I0024 from the `D:\\Backtest Ideas` handoff (source #s08; Quantpedia
Country-BAB). Leverage-constrained investors overbid high-beta -> low-beta assets
deliver higher risk-adjusted returns. Long low-beta countries / short high-beta,
beta-neutral. Tradable at the country level (ETFs), no single-stock universe.

Exact rule (#s18 deepread): beta of each country ETF vs the US market, 1-year
rolling; rank ascending -> two portfolios (low/high beta); long low / short high;
EACH leg rescaled to beta = 1 at formation (so the spread is beta-neutral, the
defining FP feature); monthly rebalance.

This is the key point: a NAIVE rank L/S (equal-weight low minus equal-weight high)
is net SHORT beta (~-0.6), so in a bull market it loses for the wrong reason. The
FP construction rescales each leg to beta 1 -> a clean zero-beta BAB spread. We
report BOTH: (a) the naive rank L/S + its permutation (via the tested cross_sectional
engine), and (b) the proper FP beta-rescaled BAB with its realized beta + bootstrap.

Decision gate (brief): the BAB hedge-return Bootstrap-CI excludes 0.

Data: 21 iShares MSCI country ETFs (1996/2000+), market = SPY. yfinance, free.

Run:
    .venv/Scripts/python.exe strategies/0079_bab_country/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.data import get_prices  # noqa: E402
from quantlab.cross_sectional import run_cross_sectional, cross_sectional_permutation_test  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import bootstrap_ci  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

ANN = np.sqrt(252)
BETA_LB = 252
ETFS = ["EWG", "EWJ", "EWU", "EWZ", "EWA", "EWC", "EWH", "EWW", "EWS", "EWP",
        "EWQ", "EWL", "EWI", "EWD", "EWN", "EWK", "EWO", "EWY", "EWT", "EWM", "EZA"]
OOS_START = "2013-01-01"
rng = np.random.default_rng(7)


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def main() -> None:
    out: dict = {"idea_id": "I0024", "beta_lookback": BETA_LB}

    panel = {}
    for t in ETFS:
        try:
            panel[t] = get_prices(t, start="1996-01-01")["Close"]
        except Exception:  # noqa: BLE001
            pass
    prices = pd.DataFrame(panel).sort_index()
    spy = get_prices("SPY", start="1996-01-01")["Close"]
    mkt_ret = spy.pct_change()
    rets = prices.pct_change()
    print(f"universe: {len(prices.columns)} country ETFs, {prices.index.min().date()}..{prices.index.max().date()}\n")

    # ---- rolling beta of each ETF vs SPY (decision-time) ----
    mkt = mkt_ret.reindex(rets.index)
    var_m = mkt.rolling(BETA_LB).var()
    beta = pd.DataFrame(index=rets.index, columns=rets.columns, dtype=float)
    for c in rets.columns:
        cov = rets[c].rolling(BETA_LB).cov(mkt)
        beta[c] = cov / var_m
    beta = beta.where(rets.notna())

    # ---- (a) naive rank L/S via tested engine: signal = -beta (low beta = long) ----
    signal = -beta
    res = run_cross_sectional(prices, signal, rebalance="ME", quantile=0.33,
                              long_short=True, cost_bps_per_side=2.0, min_names=9)
    net = res["returns"]
    # realized beta of the naive spread
    aligned = pd.concat([net, mkt_ret], axis=1).dropna()
    naive_beta = float(np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1] / np.var(aligned.iloc[:, 1]))
    perm = cross_sectional_permutation_test(prices, signal, n_perm=2000, metric="sharpe",
                                            rebalance="ME", quantile=0.33, long_short=True,
                                            cost_bps_per_side=2.0, min_names=9)
    m_naive = compute_metrics(net)
    print(f"=== (a) naive rank L/S (low-minus-high beta tercile) ===")
    print(f"  net Sharpe {m_naive['sharpe']:+.2f}, CAGR {m_naive['cagr']*100:+.1f}%, realized beta {naive_beta:+.2f}, perm p={perm['p_value']:.3f}")
    out["naive_ls"] = {"sharpe": m_naive["sharpe"], "cagr_pct": float(m_naive["cagr"]*100),
                       "realized_beta": naive_beta, "perm_p": perm["p_value"]}

    # ---- (b) beta-NEUTRAL BAB: hedge the naive L/S with the market (stable) ----
    # The FP 1/beta leg-rescaling blows up when a leg's avg beta is small (extreme
    # leverage). The robust, standard alternative that tests the SAME question
    # ("does low-beta beat high-beta on a beta-adjusted basis?") is to neutralise
    # the naive spread's market exposure: BAB = naive_LS - beta_hat * mkt, with a
    # ROLLING beta_hat (decision-time). The regression alpha is the beta-adjusted edge.
    roll_beta = net.rolling(252).cov(mkt_ret) / mkt_ret.rolling(252).var()
    roll_beta = roll_beta.shift(1)  # decision-time hedge ratio
    net_bab = (net - roll_beta * mkt_ret).dropna()
    al = pd.concat([net_bab, mkt_ret], axis=1).dropna()
    bab_beta = float(np.cov(al.iloc[:, 0], al.iloc[:, 1])[0, 1] / np.var(al.iloc[:, 1]))
    m_bab = compute_metrics(net_bab)
    # full-sample OLS alpha (annualised) + t-stat
    x = al.iloc[:, 1].values; y = al.iloc[:, 0].values
    bcoef, acoef = np.polyfit(x, y, 1)
    resid = y - (bcoef * x + acoef)
    se_a = float(np.std(resid, ddof=2) / np.sqrt(len(x)))
    t_alpha = float(acoef / se_a) if se_a else float("nan")
    monthly = (1 + net_bab).resample("ME").prod() - 1
    boot = bootstrap_ci(monthly[monthly != 0], statistic="mean", n_boot=5000)
    print(f"\n=== (b) beta-NEUTRAL BAB (naive L/S hedged with market, rolling beta) ===")
    print(f"  net Sharpe {m_bab['sharpe']:+.2f}, CAGR {m_bab['cagr']*100:+.1f}%, residual beta {bab_beta:+.2f}")
    print(f"  daily alpha {acoef*1e4:+.3f} bps/day (annualised {acoef*252*100:+.2f}%), t_alpha={t_alpha:+.2f}")
    print(f"  monthly hedge-return bootstrap mean 95% CI: [{boot['ci_low']*100:+.3f}%, {boot['ci_high']*100:+.3f}%]")
    out["fp_bab"] = {"sharpe": m_bab["sharpe"], "cagr_pct": float(m_bab["cagr"]*100),
                     "residual_beta": bab_beta, "max_dd_pct": float(m_bab["max_drawdown"]*100),
                     "alpha_ann_pct": float(acoef*252*100), "t_alpha": t_alpha,
                     "monthly_hedge_ci_pct": [boot["ci_low"]*100, boot["ci_high"]*100]}
    beta_L_series, beta_H_series = {}, {}  # not used in robust version

    # ---- long-only low-beta vs equal-weight universe ----
    lo_res = run_cross_sectional(prices, signal, rebalance="ME", quantile=0.33,
                                 long_short=False, cost_bps_per_side=2.0, min_names=9)
    bench_ret = rets.mean(axis=1)
    out["long_only_low_beta"] = {"sharpe": net_sharpe(lo_res["returns"]),
                                 "benchmark_ew_sharpe": net_sharpe(bench_ret)}
    print(f"\nlong-only low-beta Sharpe {net_sharpe(lo_res['returns']):+.2f} vs equal-weight universe {net_sharpe(bench_ret):+.2f}")

    # ---- IS/OOS for FP BAB ----
    print("\nIS/OOS (FP BAB net Sharpe):")
    out["is_oos_bab"] = {}
    for nm, msk in [("IS 1997-2012", net_bab.index < OOS_START), ("OOS 2013-2026", net_bab.index >= OOS_START)]:
        s = net_sharpe(net_bab[msk])
        out["is_oos_bab"][nm] = s
        print(f"  {nm:16}: {s:+.2f}")

    # ---- plot ----
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    ax[0].plot((1 + net_bab).cumprod(), color="purple", label=f"FP BAB (beta {bab_beta:+.2f})")
    ax[0].plot((1 + net).cumprod(), color="orange", alpha=0.7, label=f"naive L/S (beta {naive_beta:+.2f})")
    ax[0].set_yscale("log"); ax[0].set_title("Country BAB: equity curves"); ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3, which="both")
    if beta_L_series:
        bl = pd.Series(beta_L_series); bh = pd.Series(beta_H_series)
        ax[1].plot(bl.index, bl.values, color="green", label="low-beta leg avg β")
        ax[1].plot(bh.index, bh.values, color="red", label="high-beta leg avg β")
        ax[1].axhline(1, color="k", lw=0.6, ls="--")
        ax[1].set_title("Leg betas (rescaled to 1 in the trade)"); ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS / "bab_country.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    passes = (boot["ci_low"] > 0 and m_bab["sharpe"] > 0 and out["is_oos_bab"]["OOS 2013-2026"] > 0)
    print("\nVerdict:", "LEAD/testing — beta-neutral BAB hedge-return CI excludes 0."
          if passes else "see REPORT — BAB hedge-return CI touches 0 / weak.")


if __name__ == "__main__":
    main()
