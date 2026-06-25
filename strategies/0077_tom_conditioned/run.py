"""Strategy 0077 — Turn-of-Month conditioned (rebalancing-strength).

Idea I0028 from the `D:\\Backtest Ideas` handoff (source #s10 + confirmed lead
0050). 0050 (Turn-of-the-Month) is a confirmed testing-lead. #s10 (Goldman/NBER
month-end pension-rebalancing flows) reports the turn-of-month premium is LARGER
at quarter-/half-year ends (12.2 / 22.2 bps vs 5.2 bps) and scales with the
rebalancing flow. Hypothesis: condition / overweight the TOM trade at quarter-ends
and by prior-month equity strength.

This SHARPENS an already-confirmed lead — the question is whether the conditioning
adds value over the equal-weight 0050. The honest decision metric: does a
quarter-weighted or flow-conditioned TOM beat plain 0050 on active-day Sharpe?
If not, 0050 stays as-is.

Pre-registered window = the 0050 canonical Lakonishok-Smidt window (last 1 + first
3 trading days), NOT re-optimised. We test conditioning ON TOP of that fixed window.

Tests:
  * Per-turn return: quarter-end turns vs ordinary turns (t-test + permutation that
    randomly re-labels which months are quarter-ends, same count).
  * Conditioning on prior-month equity return (#s10 predicts funds SELL equities
    after a strong month -> the equity-TOM sign under conditioning is empirical).
  * Strategy comparison: equal-weight 0050 vs quarter-only vs quarter-doubled vs
    prior-month-conditioned — active-day Sharpe, net of MES cost.

Data: SPY (1993+, tradable), ^GSPC (1927+, power for the quarter-vs-normal test).

Run:
    .venv/Scripts/python.exe strategies/0077_tom_conditioned/run.py
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

from quantlab.costs import MES_INTRADAY  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics  # noqa: E402
from quantlab.seasonal import add_calendar_features, turn_of_month_signal  # noqa: E402
from quantlab.significance import bootstrap_ci, t_test_mean_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

BEFORE, AFTER = 1, 3   # 0050 canonical window (pre-registered, NOT re-fit)
ANN = np.sqrt(252)
rng = np.random.default_rng(42)


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def turn_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Per-turn TOM trade returns, tagged by the driving month-end.

    A 'turn' = one contiguous held block (last day of M + first days of M+1). We
    tag it by the month whose END drives it (the calendar month before the held
    block's start). quarter_end = driving month in {3,6,9,12}.
    """
    sig = turn_of_month_signal(prices.index, BEFORE, AFTER)
    bt = run_backtest(prices, sig, cost_model=MES_INTRADAY)
    pos = bt["position"]
    asset_ret = prices["Close"].pct_change().fillna(0.0)
    held = (pos > 0).values
    dates = prices.index
    rows = []
    i = 0
    n = len(held)
    while i < n:
        if held[i]:
            j = i
            while j < n and held[j]:
                j += 1
            block = asset_ret.iloc[i:j]
            start = dates[i]
            # driving month-end = the month before the block start month
            driving = (start.to_period("M") - 1)
            dm = driving.month
            rows.append({"start": start, "driving_month": dm,
                         "ret": float((1 + block).prod() - 1),
                         "quarter_end": dm in (3, 6, 9, 12),
                         "halfyear_end": dm in (6, 12)})
            i = j
        else:
            i += 1
    return pd.DataFrame(rows)


def conditioned_signal(prices: pd.DataFrame, mode: str) -> pd.Series:
    """Build a (possibly weighted) TOM signal.

    mode: 'all' (=0050), 'quarter_only', 'quarter_double', 'prior_up'
    (long only when prior calendar month return > 0).
    """
    base = turn_of_month_signal(prices.index, BEFORE, AFTER)
    feats = add_calendar_features(prices.index)
    driving = (prices.index.to_period("M") - 1)
    dm = pd.Series(driving.month, index=prices.index)
    if mode == "all":
        return base
    if mode == "quarter_only":
        return base * dm.isin([3, 6, 9, 12]).astype(float)
    if mode == "quarter_double":
        w = base * (1.0 + dm.isin([3, 6, 9, 12]).astype(float))  # 2x at quarter-ends
        return w
    if mode == "prior_up":
        # prior calendar month total return, known at month start
        m_ret = prices["Close"].resample("ME").last().pct_change()
        prior = m_ret.shift(1)  # previous month's return, available now
        prior_by_period = prior.copy()
        prior_by_period.index = prior_by_period.index.to_period("M")
        lookup = pd.Series(prices.index.to_period("M").map(prior_by_period), index=prices.index)
        cond = (lookup > 0).astype(float)  # NaN > 0 -> False -> 0.0
        return base * cond
    raise ValueError(mode)


def main() -> None:
    out: dict = {"idea_id": "I0028", "window": [BEFORE, AFTER]}

    spy = get_prices("SPY", start="1993-01-01")
    gspc = get_prices("^GSPC", start="1927-01-01")
    print(f"SPY  {spy.index.min().date()}..{spy.index.max().date()}")
    print(f"GSPC {gspc.index.min().date()}..{gspc.index.max().date()}\n")

    # ---- per-turn: quarter-end vs ordinary (long history ^GSPC) ----
    tr = turn_returns(gspc)
    qe = tr[tr["quarter_end"]]["ret"]
    no = tr[~tr["quarter_end"]]["ret"]
    hy = tr[tr["halfyear_end"]]["ret"]
    diff_q = qe.mean() - no.mean()
    # permutation: randomly relabel quarter-ends (same count), is the gap special?
    n_qe = len(qe)
    allret = tr["ret"].values
    obs = diff_q
    perm_gaps = []
    for _ in range(5000):
        idx = rng.permutation(len(allret))
        g = allret[idx[:n_qe]].mean() - allret[idx[n_qe:]].mean()
        perm_gaps.append(g)
    perm_gaps = np.array(perm_gaps)
    p_perm = float((perm_gaps >= obs).mean())
    # two-sample difference via bootstrap of the difference
    boot_diff = []
    qv, nv = qe.values, no.values
    for _ in range(5000):
        boot_diff.append(rng.choice(qv, len(qv)).mean() - rng.choice(nv, len(nv)).mean())
    boot_diff = np.array(boot_diff)
    ci_diff = (float(np.percentile(boot_diff, 2.5)), float(np.percentile(boot_diff, 97.5)))

    print("=== ^GSPC per-turn (1927+) ===")
    print(f"quarter-end turns: n={len(qe)}, mean {qe.mean()*100:+.3f}%  (median {qe.median()*100:+.3f}%)")
    print(f"ordinary turns   : n={len(no)}, mean {no.mean()*100:+.3f}%")
    print(f"half-year turns  : n={len(hy)}, mean {hy.mean()*100:+.3f}%")
    print(f"quarter-minus-ordinary gap: {diff_q*100:+.3f}%  perm p={p_perm:.4f}  "
          f"bootstrap 95% CI [{ci_diff[0]*100:+.3f}%, {ci_diff[1]*100:+.3f}%]")
    out["per_turn_gspc"] = {
        "qe_mean_pct": float(qe.mean()*100), "qe_median_pct": float(qe.median()*100), "qe_n": len(qe),
        "ordinary_mean_pct": float(no.mean()*100), "ordinary_n": len(no),
        "halfyear_mean_pct": float(hy.mean()*100), "halfyear_n": len(hy),
        "gap_pct": float(diff_q*100), "perm_p": p_perm,
        "boot_gap_ci_pct": [ci_diff[0]*100, ci_diff[1]*100]}

    # ---- conditioning on prior-month return (#s10) ----
    tr["prior_month_ret"] = np.nan
    m_ret = gspc["Close"].resample("ME").last().pct_change()
    m_by = m_ret.copy(); m_by.index = m_by.index.to_period("M")
    # driving month return = the month that just ended
    tr["prior_month_ret"] = tr["start"].apply(
        lambda d: m_by.get((d.to_period("M") - 1), np.nan))
    up = tr[tr["prior_month_ret"] > 0]["ret"]
    dn = tr[tr["prior_month_ret"] <= 0]["ret"]
    print(f"\nConditioning on prior-month equity return:")
    print(f"  after UP month  : n={len(up)}, TOM mean {up.mean()*100:+.3f}%")
    print(f"  after DOWN month: n={len(dn)}, TOM mean {dn.mean()*100:+.3f}%")
    out["prior_month_conditioning"] = {"after_up_mean_pct": float(up.mean()*100), "after_up_n": len(up),
                                       "after_down_mean_pct": float(dn.mean()*100), "after_down_n": len(dn)}

    # ---- strategy comparison on SPY (active-day Sharpe, net MES) ----
    print("\n=== SPY strategy comparison (net MES) ===")
    comp = {}
    for mode in ("all", "quarter_only", "quarter_double", "prior_up"):
        sig = conditioned_signal(spy, mode)
        bt = run_backtest(spy, sig, cost_model=MES_INTRADAY)
        net = bt["returns"]
        active = net[bt["position"] > 0]
        m = compute_metrics(net)
        comp[mode] = {"full_sharpe": m["sharpe"], "active_sharpe": net_sharpe(active),
                      "cagr_pct": float(m["cagr"]*100), "days_long_frac": float((bt["position"]>0).mean()),
                      "net_raw_sharpe": net_sharpe(net)}
        print(f"  {mode:15}: active-day Sharpe {comp[mode]['active_sharpe']:+.2f}  "
              f"net-raw {comp[mode]['net_raw_sharpe']:+.2f}  CAGR {comp[mode]['cagr_pct']:+.1f}%  "
              f"({comp[mode]['days_long_frac']*100:.0f}% invested)")
    out["strategy_comparison_spy"] = comp

    # ---- plots ----
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    ax[0].bar(["quarter-end", "ordinary", "half-year"],
              [qe.mean()*100, no.mean()*100, hy.mean()*100],
              color=["darkgreen", "lightgrey", "teal"], edgecolor="k")
    ax[0].axhline(0, color="k", lw=0.8); ax[0].set_ylabel("mean TOM-turn return (%)")
    ax[0].set_title(f"^GSPC: quarter-end TOM stronger?\n(gap {diff_q*100:+.3f}%, perm p={p_perm:.3f})")
    ax[0].grid(alpha=0.3, axis="y")
    modes = list(comp.keys())
    ax[1].bar(modes, [comp[m]["active_sharpe"] for m in modes], color="steelblue", edgecolor="k")
    ax[1].axhline(comp["all"]["active_sharpe"], color="red", ls="--", lw=1, label="0050 baseline")
    ax[1].set_ylabel("active-day Sharpe (net MES)"); ax[1].legend(fontsize=8)
    ax[1].set_title("Does conditioning beat equal-weight 0050?")
    ax[1].grid(alpha=0.3, axis="y"); plt.setp(ax[1].get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(RESULTS / "tom_conditioned.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    base_sh = comp["all"]["active_sharpe"]
    best_cond = max(comp["quarter_only"]["active_sharpe"], comp["quarter_double"]["active_sharpe"],
                    comp["prior_up"]["active_sharpe"])
    passes = (p_perm < 0.05 and ci_diff[0] > 0 and best_cond > base_sh + 0.05)
    print("\nVerdict:", "conditioning ADDS value over 0050 — keep conditioned variant."
          if passes else "conditioning does NOT clearly beat equal-weight 0050 — keep 0050 as-is.")


if __name__ == "__main__":
    main()
