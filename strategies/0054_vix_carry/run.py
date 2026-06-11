"""Strategy 0054 — Variance Risk Premium / VIX-term-structure carry (Simon & Campasano).

Paper-edge #7. Claim: VIX futures trade in contango most of the time (buyers of
crash insurance systematically overpay), so SHORTING front-month vol harvests the
roll-down. Refinement: only short when the term structure is in contango
(VIX3M > VIX), step aside in backwardation (the regime of the vol spikes).

Cause: insurance premium — a structural, persistent risk premium. Caveat (the
whole point of Tier-2): brutal tail risk (Feb 2018 "Volmageddon", Mar 2020).

Data: ^VIX (2004+), ^VIX3M (2006+) for the term-structure signal; VIXY (iPath
short-term VIX futures ETF, 2011+) as the tradable P&L proxy — shorting VIXY ==
harvesting the contango. IBKR ETF cost.

Signal: short VIXY (position -1) when VIX3M > VIX (contango), flat otherwise.
Look-ahead-safe (term structure known at close, engine shifts +1).

Run:
    .venv/Scripts/python.exe strategies/0054_vix_carry/run.py
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
from quantlab.metrics import compute_metrics, trade_stats  # noqa: E402
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio, permutation_test  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)


def main() -> None:
    out: dict = {}
    vix = get_prices("^VIX", start="2006-01-01")["Close"]
    vix3m = get_prices("^VIX3M", start="2006-01-01")["Close"]
    vixy = get_prices("VIXY", start="2011-01-01")

    # term structure: contango when VIX3M > VIX
    contango = (vix3m / vix).reindex(vixy.index).ffill()
    in_contango = (contango > 1.0)
    print(f"VIXY {vixy.index.min().date()}..{vixy.index.max().date()} ({len(vixy)} days)")
    print(f"contango fraction of days: {in_contango.mean()*100:.1f}%")

    # ---- does contango predict next-day VIXY decline? (is the carry real) ----
    vixy_ret = vixy["Close"].pct_change()
    nxt = vixy_ret.shift(-1)  # next-day return
    c_on = nxt[in_contango.values].dropna()
    c_off = nxt[~in_contango.values].dropna()
    print(f"\nNext-day VIXY return: in contango {c_on.mean()*1e4:+.1f}bps (n={len(c_on)}) "
          f"vs backwardation {c_off.mean()*1e4:+.1f}bps (n={len(c_off)})")
    out["carry_signal"] = {"contango_frac": float(in_contango.mean()),
                           "nextday_vixy_contango_bps": float(c_on.mean() * 1e4),
                           "nextday_vixy_backwardation_bps": float(c_off.mean() * 1e4)}

    # ---- strategy: short VIXY when contango, flat otherwise ----
    sig = pd.Series(np.where(in_contango, -1.0, 0.0), index=vixy.index)
    bt = run_backtest(vixy, sig, cost_model=IBKR_LIQUID_ETF)
    net = bt["returns"]
    m = compute_metrics(net)
    ts = trade_stats(bt["trades"])
    # always-short benchmark (no gate)
    bt_always = run_backtest(vixy, pd.Series(-1.0, index=vixy.index), cost_model=IBKR_LIQUID_ETF)
    m_always = compute_metrics(bt_always["returns"])

    print(f"\nShort-VIXY-in-contango: Sharpe {m['sharpe']:.2f}, CAGR {m['cagr']*100:.1f}%, "
          f"MaxDD {m['max_drawdown']*100:.1f}%, trades {ts['n_trades']}")
    print(f"Always-short-VIXY:      Sharpe {m_always['sharpe']:.2f}, CAGR {m_always['cagr']*100:.1f}%, "
          f"MaxDD {m_always['max_drawdown']*100:.1f}%")

    # ---- TAIL RISK: worst days and the famous episodes ----
    worst = net.nsmallest(5)
    feb2018 = net.loc["2018-02-01":"2018-02-10"]
    mar2020 = net.loc["2020-02-20":"2020-03-31"]
    print("\nTAIL RISK (net daily returns of the gated strategy):")
    print("  5 worst days: " + ", ".join(f"{d.date()} {v*100:.1f}%" for d, v in worst.items()))
    print(f"  Feb 2018 'Volmageddon' (1-10 Feb): cum {((1+feb2018).prod()-1)*100:+.1f}%, "
          f"worst day {feb2018.min()*100:.1f}%")
    print(f"  Mar 2020 COVID (20 Feb-31 Mar):    cum {((1+mar2020).prod()-1)*100:+.1f}%, "
          f"worst day {mar2020.min()*100:.1f}%")
    out["tail_risk"] = {
        "worst_days": {str(d.date()): float(v) for d, v in worst.items()},
        "feb2018_cum_pct": float(((1 + feb2018).prod() - 1) * 100),
        "feb2018_worst_day_pct": float(feb2018.min() * 100),
        "mar2020_cum_pct": float(((1 + mar2020).prod() - 1) * 100),
        "mar2020_worst_day_pct": float(mar2020.min() * 100),
    }
    out["metrics_gated"] = m
    out["metrics_always"] = m_always
    out["trades_gated"] = ts

    # ---- significance ----
    pos = bt["position"]
    perm = permutation_test(bt["gross_returns"], vixy_ret, pos, n_perm=2000, metric="sharpe")
    boot = bootstrap_ci(net, statistic="sharpe", n_boot=5000)
    pp = float(net.mean() / net.std()) if net.std() else float("nan")
    dsr = deflated_sharpe_ratio(observed_sharpe=pp, n_obs=len(net), n_trials=2, returns=net)
    print(f"\npermutation p={perm['p_value']:.3f}, bootstrap Sharpe 95% CI "
          f"[{boot['ci_low']:+.2f},{boot['ci_high']:+.2f}], DSR={dsr['psr_deflated']:.3f}")
    out["significance"] = {"permutation": perm, "bootstrap": boot, "deflated_sharpe": dsr}

    # ---- plot ----
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    eq = (1 + net).cumprod()
    eqa = (1 + bt_always["returns"]).cumprod()
    ax[0].semilogy(eq.index, eq.values, color="seagreen", label="short VIXY in contango")
    ax[0].semilogy(eqa.index, eqa.values, color="indianred", alpha=0.7, label="always short VIXY")
    ax[0].set_title(f"Short-vol carry net of cost (Sharpe {m['sharpe']:.2f})\n"
                    f"MaxDD {m['max_drawdown']*100:.0f}% — the tail is the story")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3, which="both")
    dd = (eq / eq.cummax() - 1) * 100
    ax[1].fill_between(dd.index, dd.values, 0, color="indianred", alpha=0.6)
    ax[1].set_title("Drawdown of the gated short-vol strategy\n(Feb 2018 / Mar 2020 craters)")
    ax[1].set_ylabel("drawdown (%)"); ax[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS / "vix_carry.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSUMMARY: carry real (contango next-day VIXY {c_on.mean()*1e4:+.0f}bps), gated Sharpe "
          f"{m['sharpe']:.2f} but MaxDD {m['max_drawdown']*100:.0f}% / worst day {worst.iloc[0]*100:.0f}%.")


if __name__ == "__main__":
    main()
