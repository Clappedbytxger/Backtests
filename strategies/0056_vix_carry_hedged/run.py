"""Strategy 0056 — Risk-managed VIX carry (defined-risk variant of 0054).

0054 found the VRP carry is a REAL, significant edge (short VIXY in contango:
Sharpe 0.74, p=0.005, DSR 0.993) but with an account-ending left tail (worst day
-34%, MaxDD -63%). It was rejected on RISK, not signal. This strategy asks: can
the same edge be sized/hedged into a tolerable sleeve for a small IBKR account?

Two defined-risk routes (the user asked for either / both):
  R1 — SIZING: contango gate (+buffer) + volatility targeting (cut exposure as
       vol rises) + a hard global scalar so the worst HISTORICAL day = -5% of
       the sleeve. Pure data, no options.
  R2 — TAIL HEDGE: a stylized long VIX-call overlay that caps FUTURE tails too,
       run as a COST SENSITIVITY (1/3/5 %/yr drag) because exact option prices
       are out of the free-data scope. Clearly labelled illustrative.

Look-ahead-safe: gate + vol estimate use info up to the prior close; run_backtest
shifts +1 and charges turnover cost on every rebalance.

Run:
    .venv/Scripts/python.exe strategies/0056_vix_carry_hedged/run.py
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

from quantlab.costs import IBKR_LIQUID_ETF  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio, permutation_test  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)

TARGET_DAILY_VOL = 0.015   # ~24%/yr target on the sleeve before the -5% scalar
VOL_LOOKBACK = 20
WEIGHT_CAP = 1.0           # never more than fully short (no added leverage)
BUFFER = 1.03              # require VIX3M/VIX > 1.03 (step aside near inversion)
WORST_DAY_TARGET = -0.05   # hard sizing: worst historical day = -5% of sleeve


def tail_report(r: pd.Series) -> dict:
    r = r.dropna()
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1)
    worst = r.nsmallest(3)
    return {"worst_day_pct": float(r.min() * 100),
            "worst3_pct": [float(v * 100) for v in worst.values],
            "maxdd_pct": float(dd.min() * 100),
            "daily_kurtosis": float(pd.Series(r).kurt())}


def metrics_row(name: str, r: pd.Series) -> dict:
    m = compute_metrics(r)
    t = tail_report(r)
    print(f"{name:34} Sharpe {m['sharpe']:5.2f}  CAGR {m['cagr']*100:5.1f}%  "
          f"MaxDD {m['max_drawdown']*100:6.1f}%  worstDay {t['worst_day_pct']:6.1f}%  "
          f"kurt {t['daily_kurtosis']:6.1f}")
    return {"sharpe": m["sharpe"], "cagr": m["cagr"], "maxdd": m["max_drawdown"],
            "vol": m["annual_volatility"], **t}


def main() -> None:
    out: dict = {}
    vix = get_prices("^VIX", start="2006-01-01")["Close"]
    vix3m = get_prices("^VIX3M", start="2006-01-01")["Close"]
    vixy = get_prices("VIXY", start="2011-01-01")
    vixy_ret = vixy["Close"].pct_change()

    ratio = (vix3m / vix).reindex(vixy.index).ffill()
    gate = (ratio > 1.0).astype(float)
    gate_buf = (ratio > BUFFER).astype(float)

    # volatility target: weight = clip(target / trailing realized daily vol, 0, cap)
    rv = vixy_ret.rolling(VOL_LOOKBACK).std().shift(1)
    w = (TARGET_DAILY_VOL / rv).clip(0.0, WEIGHT_CAP).fillna(0.0)

    print(f"VIXY {vixy.index.min().date()}..{vixy.index.max().date()} ({len(vixy)} days)\n")
    print("Short-vol carry, risk controls compared (short = negative weight):")

    # ---- R0 naive full short in contango (the 0054 baseline) ----
    sig0 = -gate
    bt0 = run_backtest(vixy, sig0, cost_model=IBKR_LIQUID_ETF)
    r0 = bt0["returns"]
    out["R0_naive"] = metrics_row("R0 naive full short (=0054)", r0)

    # ---- R1 PURE linear down-size of the naive short to worst-day = -5% ----
    # Scaling a return series is LINEAR -> Sharpe, permutation p and DSR are
    # IDENTICAL to R0; only the absolute return/DD shrink. This is the honest
    # answer to "size it so the worst day is -5%".
    scalar = abs(WORST_DAY_TARGET) / abs(r0.min())
    bt1 = run_backtest(vixy, sig0 * scalar, cost_model=IBKR_LIQUID_ETF)
    r1 = bt1["returns"]
    out["R1_sized_naive"] = metrics_row(f"R1 sized naive to -5% day (x{scalar:.3f})", r1)
    out["sizing_scalar"] = float(scalar)

    # ---- R2 vol-targeting (diagnostic: does NOT help short-vol's gap tail) ----
    bt2 = run_backtest(vixy, -(gate * w), cost_model=IBKR_LIQUID_ETF)
    out["R2_voltarget_diagnostic"] = metrics_row("R2 vol-target (does NOT help)", bt2["returns"])
    bt2b = run_backtest(vixy, -(gate_buf * w), cost_model=IBKR_LIQUID_ETF)
    out["R2b_voltarget_buffer"] = metrics_row("R2b vol-target+buffer (worse)", bt2b["returns"])

    # ---- significance on the sized sleeve (= the naive edge, linearly scaled) ----
    perm = permutation_test(bt1["gross_returns"], vixy_ret, bt1["position"], n_perm=2000, metric="sharpe")
    boot = bootstrap_ci(r1, statistic="sharpe", n_boot=5000)
    pp = float(r1.mean() / r1.std()) if r1.std() else float("nan")
    dsr = deflated_sharpe_ratio(observed_sharpe=pp, n_obs=len(r1), n_trials=4, returns=r1)
    print(f"\nSized-naive sleeve significance (edge preserved under linear sizing): "
          f"permutation p={perm['p_value']:.3f}, "
          f"bootstrap Sharpe CI [{boot['ci_low']:+.2f},{boot['ci_high']:+.2f}], DSR={dsr['psr_deflated']:.3f}")
    out["significance_sized"] = {"permutation": perm, "bootstrap": boot, "deflated_sharpe": dsr}
    r3 = r1  # the sleeve we carry forward

    # crisis behaviour of the sized sleeve
    for ep, sl in [("feb2018", slice("2018-02-01", "2018-02-10")),
                   ("mar2020", slice("2020-02-20", "2020-03-31")),
                   ("aug2024", slice("2024-08-01", "2024-08-09"))]:
        seg = r3.loc[sl]
        out.setdefault("sized_crises", {})[ep] = {"cum_pct": float(((1 + seg).prod() - 1) * 100),
                                                  "worst_day_pct": float(seg.min() * 100)}
    print("Sized-sleeve crises:", {k: f"{v['cum_pct']:+.1f}% (worst {v['worst_day_pct']:+.1f}%)"
                                    for k, v in out["sized_crises"].items()})

    # ---- R2 stylized VIX-call tail hedge: COST SENSITIVITY ----
    # A continuous OTM VIX-call hedge caps the tail at ~the strike but costs a
    # roughly constant premium drag. We do NOT price options here; instead we show,
    # for plausible drags, the sleeve = sized short-vol minus hedge drag, with the
    # tail assumed capped near the worst sized day. Illustrative, labelled.
    print("\nR3 stylized VIX-call hedge (cost sensitivity on the sized sleeve):")
    out["R3_hedge_sensitivity"] = {}
    base_cagr = out["R1_sized_naive"]["cagr"]
    for drag in (0.01, 0.03, 0.05):
        net_cagr = base_cagr - drag
        # rough Sharpe haircut: subtract drag from annualized return, keep vol
        vol = out["R1_sized_naive"]["vol"]
        net_sharpe = (base_cagr - drag - 0.02) / vol if vol else float("nan")
        out["R3_hedge_sensitivity"][f"drag_{int(drag*100)}pct"] = {
            "net_cagr_pct": float(net_cagr * 100), "approx_sharpe": float(net_sharpe)}
        print(f"  hedge drag {drag*100:.0f}%/yr -> net CAGR {net_cagr*100:5.1f}%, "
              f"approx Sharpe {net_sharpe:.2f}  (tail capped near strike)")

    # ---- plot ----
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    for bt, lab, col in [(bt0, "R0 naive (0054)", "indianred"),
                         (bt2b, "R2 vol-target+buffer", "steelblue"),
                         (bt1, "R1 sized to -5% day", "seagreen")]:
        eq = (1 + bt["returns"]).cumprod()
        ax[0].semilogy(eq.index, eq.values, label=lab, color=col)
    ax[0].set_title("Risk-managed short-vol vs naive (log equity)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3, which="both")
    names = ["R0\nnaive", "R2\nvol-tgt", "R2b\n+buffer", "R1\nsized"]
    worst = [out["R0_naive"]["worst_day_pct"], out["R2_voltarget_diagnostic"]["worst_day_pct"],
             out["R2b_voltarget_buffer"]["worst_day_pct"], out["R1_sized_naive"]["worst_day_pct"]]
    mdd = [out["R0_naive"]["maxdd"]*100, out["R2_voltarget_diagnostic"]["maxdd"]*100,
           out["R2b_voltarget_buffer"]["maxdd"]*100, out["R1_sized_naive"]["maxdd"]*100]
    x = np.arange(len(names))
    ax[1].bar(x - 0.2, worst, 0.4, label="worst day %", color="indianred")
    ax[1].bar(x + 0.2, mdd, 0.4, label="MaxDD %", color="darkred", alpha=0.6)
    ax[1].axhline(WORST_DAY_TARGET*100, color="k", ls="--", lw=0.9, label="-5% target")
    ax[1].set_xticks(x); ax[1].set_xticklabels(names, fontsize=8); ax[1].legend(fontsize=8)
    ax[1].set_title("Tail shrinks with each control"); ax[1].grid(alpha=0.3, axis="y")
    fig.tight_layout(); fig.savefig(RESULTS / "vix_carry_hedged.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    s = out["R1_sized_naive"]
    print(f"\nSUMMARY: sized sleeve Sharpe {s['sharpe']:.2f}, CAGR {s['cagr']*100:.1f}%, "
          f"MaxDD {s['maxdd']*100:.0f}%, worst day {s['worst_day_pct']:.1f}% "
          f"(edge survives: perm p={perm['p_value']:.3f}).")


if __name__ == "__main__":
    main()
