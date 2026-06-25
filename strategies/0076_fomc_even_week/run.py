"""Strategy 0076 — FOMC-Cycle "Even-Week" Drift (Cieslak/Morse/Vissing-Jorgensen).

Idea I0008 from the `D:\\Backtest Ideas` handoff (source #s02, JF 2019). Claim:
since 1994 the entire equity risk premium is earned in the EVEN weeks (0, 2, 4, 6)
of FOMC cycle time — i.e. the fortnight pattern anchored to each FOMC meeting —
while odd weeks are ~flat. Cause: a liquidity cycle in the fed-funds market plus
informal Fed communication; generalises the pre-FOMC drift (confirmed here as 0052).

This is the natural test of whether 0052's pre-FOMC overnight pulse is the tip of
a broader biweekly structure. Low-frequency (~half the days, week-level), so cost
is not binding. Tradable instrument: SPY / MES.

FOMC cycle time: for each trading day, days_since = trading days since the most
recent scheduled FOMC announcement (announcement day = 0). cycle_week =
days_since // 5 -> week 0 = days 0-4, week 1 = 5-9, etc. EVEN weeks {0,2,4,6...}
-> long; odd -> flat. (Phase robustness: we also scan a ±2-day anchor shift.)

THE key test is the drift-trap permutation (lesson 0016/0017/0050): being long
~50% of the days in a secular equity bull is itself positive. The permutation
shuffles the held days to random same-count timing -> it asks whether the
EVEN-WEEK timing carries, not merely being long half the time. We also do a
direct difference-in-means (even-week days vs odd-week days).

Data: SPY (1993+, but FOMC list starts 2000 -> sample 2000+). Cross-market:
Nasdaq-100 (^NDX) and DAX (^GDAXI) — FOMC drives global equities, so these are
correlated cross-market robustness, not independent OOS. Decay split 2000-2014 vs
2015-2026 (Cieslak published 2019).

Run:
    .venv/Scripts/python.exe strategies/0076_fomc_even_week/run.py
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
from quantlab.metrics import compute_metrics, trade_stats  # noqa: E402
from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

ANN = np.sqrt(252)
OOS_START = "2013-01-01"   # IS 2000-2012 / OOS 2013-2026

# FOMC scheduled-meeting announcement dates (last day of each meeting), 2000-2026.
# Verified list reused from strategy 0052 (Fed-confirmed 2021-2026; emergency
# meetings excluded — they have no normal cycle phase).
FOMC = [
    "2000-02-02", "2000-03-21", "2000-05-16", "2000-06-28", "2000-08-22", "2000-10-03", "2000-11-15", "2000-12-19",
    "2001-01-31", "2001-03-20", "2001-05-15", "2001-06-27", "2001-08-21", "2001-10-02", "2001-11-06", "2001-12-11",
    "2002-01-30", "2002-03-19", "2002-05-07", "2002-06-26", "2002-08-13", "2002-09-24", "2002-11-06", "2002-12-10",
    "2003-01-29", "2003-03-18", "2003-05-06", "2003-06-25", "2003-08-12", "2003-09-16", "2003-10-28", "2003-12-09",
    "2004-01-28", "2004-03-16", "2004-05-04", "2004-06-30", "2004-08-10", "2004-09-21", "2004-11-10", "2004-12-14",
    "2005-02-02", "2005-03-22", "2005-05-03", "2005-06-30", "2005-08-09", "2005-09-20", "2005-11-01", "2005-12-13",
    "2006-01-31", "2006-03-28", "2006-05-10", "2006-06-29", "2006-08-08", "2006-09-20", "2006-10-25", "2006-12-12",
    "2007-01-31", "2007-03-21", "2007-05-09", "2007-06-28", "2007-08-07", "2007-09-18", "2007-10-31", "2007-12-11",
    "2008-01-30", "2008-03-18", "2008-04-30", "2008-06-25", "2008-08-05", "2008-09-16", "2008-10-29", "2008-12-16",
    "2009-01-28", "2009-03-18", "2009-04-29", "2009-06-24", "2009-08-12", "2009-09-23", "2009-11-04", "2009-12-16",
    "2010-01-27", "2010-03-16", "2010-04-28", "2010-06-23", "2010-08-10", "2010-09-21", "2010-11-03", "2010-12-14",
    "2011-01-26", "2011-03-15", "2011-04-27", "2011-06-22", "2011-08-09", "2011-09-21", "2011-11-02", "2011-12-13",
    "2012-01-25", "2012-03-13", "2012-04-25", "2012-06-20", "2012-08-01", "2012-09-13", "2012-10-24", "2012-12-12",
    "2013-01-30", "2013-03-20", "2013-05-01", "2013-06-19", "2013-07-31", "2013-09-18", "2013-10-30", "2013-12-18",
    "2014-01-29", "2014-03-19", "2014-04-30", "2014-06-18", "2014-07-30", "2014-09-17", "2014-10-29", "2014-12-17",
    "2015-01-28", "2015-03-18", "2015-04-29", "2015-06-17", "2015-07-29", "2015-09-17", "2015-10-28", "2015-12-16",
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27", "2016-09-21", "2016-11-02", "2016-12-14",
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26", "2017-09-20", "2017-11-01", "2017-12-13",
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01", "2018-09-26", "2018-11-08", "2018-12-19",
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
    "2020-01-29", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29",
]


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def fomc_cycle_week(index: pd.DatetimeIndex, phase_shift: int = 0) -> np.ndarray:
    """Trading-day cycle week since the most recent FOMC meeting (week = days//5).

    ``phase_shift`` shifts the day count (robustness to the exact anchor). Returns
    -1 before the first meeting in-sample.
    """
    idx = pd.DatetimeIndex(index)
    fomc = pd.to_datetime(FOMC)
    pos = sorted({idx.searchsorted(d) for d in fomc if idx.searchsorted(d) < len(idx)})
    pos_arr = np.array(pos)
    i = np.arange(len(idx))
    j = np.searchsorted(pos_arr, i, side="right") - 1
    days_since = np.full(len(idx), -1)
    valid = j >= 0
    days_since[valid] = i[valid] - pos_arr[j[valid]]
    week = np.where(days_since >= 0, (days_since + phase_shift) // 5, -1)
    return week


def even_week_signal(index: pd.DatetimeIndex, phase_shift: int = 0) -> pd.Series:
    week = fomc_cycle_week(index, phase_shift)
    even = (week >= 0) & (week % 2 == 0)
    return pd.Series(even.astype(float), index=index, name="fomc_even_week")


def run_phase(prices: pd.DataFrame, phase_shift: int = 0, cost=MES_INTRADAY) -> dict:
    sig = even_week_signal(prices.index, phase_shift)
    return run_backtest(prices, sig, cost_model=cost)


def main() -> None:
    out: dict = {"idea_id": "I0008", "oos_start": OOS_START}

    spy = get_prices("SPY", start="1999-06-01")
    spy = spy[spy.index >= "2000-01-01"]
    print(f"SPY {spy.index.min().date()}..{spy.index.max().date()} ({len(spy)} days)\n")

    bt = run_phase(spy, 0)
    pos = bt["position"]
    asset_ret = spy["Close"].pct_change().fillna(0.0)
    gross, net = bt["gross_returns"], bt["returns"]
    m_gross, m_net, bh = compute_metrics(gross), compute_metrics(net), compute_metrics(asset_ret)
    ts = trade_stats(bt["trades"])
    days_in = float((pos > 0).mean())

    print(f"=== SPY even-week ({days_in*100:.1f}% of days long) ===")
    print(f"{'':16}{'Sharpe':>8}{'CAGR':>9}{'MaxDD':>9}")
    print(f"{'gross':16}{m_gross['sharpe']:8.2f}{m_gross['cagr']*100:8.1f}%{m_gross['max_drawdown']*100:8.1f}%")
    print(f"{'net (MES)':16}{m_net['sharpe']:8.2f}{m_net['cagr']*100:8.1f}%{m_net['max_drawdown']*100:8.1f}%")
    print(f"{'buy & hold':16}{bh['sharpe']:8.2f}{bh['cagr']*100:8.1f}%{bh['max_drawdown']*100:8.1f}%")
    print(f"trades: {ts['n_trades']}, win {ts['win_rate']*100:.1f}%, avg hold {ts['avg_holding_days']:.1f}d")
    out["spy_headline"] = {"days_long_frac": days_in, "gross": m_gross, "net": m_net,
                           "buy_hold": bh, "trades": ts}

    # diagnostic: even-week vs odd-week daily mean
    week = fomc_cycle_week(spy.index, 0)
    even_mask = (week >= 0) & (week % 2 == 0)
    odd_mask = (week >= 0) & (week % 2 == 1)
    even_ret, odd_ret = asset_ret[even_mask], asset_ret[odd_mask]
    even_tot = (1 + even_ret).prod() - 1
    odd_tot = (1 + odd_ret).prod() - 1
    diag = {"even_day_mean_bps": float(even_ret.mean() * 1e4),
            "odd_day_mean_bps": float(odd_ret.mean() * 1e4),
            "even_days": int(even_mask.sum()), "odd_days": int(odd_mask.sum()),
            "even_total_pct": float(even_tot * 100), "odd_total_pct": float(odd_tot * 100),
            "share_of_gain_even_pct": float(even_tot / (even_tot + odd_tot) * 100)}
    print(f"\neven-week mean {diag['even_day_mean_bps']:+.2f}bps vs odd-week {diag['odd_day_mean_bps']:+.2f}bps "
          f"({diag['even_days']} vs {diag['odd_days']} days)")
    print(f"compounded: even +{diag['even_total_pct']:.0f}% vs odd +{diag['odd_total_pct']:.0f}% "
          f"-> {diag['share_of_gain_even_pct']:.0f}% of the gain in even weeks")
    out["diagnostic"] = diag

    # per-cycle-week mean (the biweekly fingerprint)
    wk_mean = {int(w): float(asset_ret[(week == w)].mean() * 1e4) for w in range(0, 8)}
    print("per-cycle-week mean (bps): " + "  ".join(f"w{w}={v:+.1f}" for w, v in wk_mean.items()))
    out["per_week_mean_bps"] = wk_mean

    # IS/OOS/decay
    splits = {"IS 2000-2012": net[net.index < OOS_START],
              "OOS 2013-2026": net[net.index >= OOS_START],
              "post-publ 2019-2026": net[net.index >= "2019-01-01"]}
    print("\nIS/OOS (net, Sharpe):")
    out["is_oos_net"] = {}
    for name, r in splits.items():
        s = {"net_sharpe": net_sharpe(r), "gross_sharpe": net_sharpe(gross[r.index]),
             "net_cagr_pct": float(compute_metrics(r)["cagr"] * 100)}
        out["is_oos_net"][name] = s
        print(f"  {name:20}: net {s['net_sharpe']:+.2f}  gross {s['gross_sharpe']:+.2f}  CAGR {s['net_cagr_pct']:+.1f}%")

    # significance: permutation (drift-trap), t-test diff-in-means, bootstrap, DSR
    n_trials = 5  # phase-shift robustness scan below
    perm = permutation_test(gross, asset_ret, pos, n_perm=5000, metric="sharpe")
    # difference-in-means even minus odd via t-test on (even_ret) and (odd_ret)
    diff = pd.Series(even_ret.values).mean() - pd.Series(odd_ret.values).mean()
    tt_even = t_test_mean_return(pd.Series(even_ret.values))
    boot = bootstrap_ci(even_ret, statistic="mean", n_boot=5000)
    pp_sharpe = float(gross.mean() / gross.std()) if gross.std() else float("nan")
    dsr = deflated_sharpe_ratio(observed_sharpe=pp_sharpe, n_obs=len(gross),
                                n_trials=n_trials, returns=gross)
    print(f"\npermutation (gross Sharpe vs random same-count timing, n=5000): p = {perm['p_value']:.4f}")
    print(f"even-minus-odd daily mean diff: {diff*1e4:+.2f} bps")
    print(f"t-test even-week mean > 0: t={tt_even['t_stat']:+.2f} p={tt_even['p_value']:.4f}")
    print(f"bootstrap even-week mean 95% CI: [{boot['ci_low']*1e4:+.2f}, {boot['ci_high']*1e4:+.2f}] bps")
    print(f"deflated Sharpe (n_trials={n_trials}): PSR_deflated = {dsr['psr_deflated']:.3f}")
    out["significance"] = {"permutation": perm, "even_minus_odd_bps": float(diff * 1e4),
                           "t_test_even": tt_even, "bootstrap_even_mean": boot,
                           "deflated_sharpe": dsr, "n_trials": n_trials}

    # phase robustness (is it knife-edge on the exact anchor?)
    print("\nPhase robustness — net Sharpe by anchor shift:")
    phase = {}
    for ps in (-2, -1, 0, 1, 2):
        sh = net_sharpe(run_phase(spy, ps)["returns"])
        phase[ps] = float(sh)
        print(f"  shift {ps:+d}: net Sharpe {sh:+.2f}")
    out["phase_robustness"] = phase

    # cross-market (correlated robustness, FOMC drives global equities)
    print("\nCross-market (same even-week rule):")
    cm = {}
    for tk, label in [("^NDX", "Nasdaq-100"), ("^GDAXI", "DAX")]:
        try:
            p = get_prices(tk, start="2000-01-01")
            b = run_phase(p, 0)
            ar = p["Close"].pct_change().fillna(0.0)
            pm = permutation_test(b["gross_returns"], ar, b["position"], n_perm=5000, metric="sharpe")
            wk = fomc_cycle_week(p.index, 0)
            em = ar[(wk >= 0) & (wk % 2 == 0)]
            cm[tk] = {"label": label, "net_sharpe": net_sharpe(b["returns"]),
                      "bh_sharpe": net_sharpe(ar), "even_mean_bps": float(em.mean() * 1e4),
                      "permutation_p": pm["p_value"]}
            print(f"  {label:12}: even {cm[tk]['even_mean_bps']:+.2f}bps, net Sharpe {cm[tk]['net_sharpe']:+.2f} "
                  f"vs B&H {cm[tk]['bh_sharpe']:+.2f}, perm p={pm['p_value']:.4f}")
        except Exception as e:  # noqa: BLE001
            cm[tk] = {"error": str(e)}
            print(f"  {label}: skipped ({e})")
    out["cross_market"] = cm

    # plots
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    eq = (1 + net).cumprod()
    ax[0].plot(eq.index, eq.values, color="darkred", label="even-week (net)")
    ax[0].plot(spy.index, (1 + asset_ret).cumprod().values, color="grey", alpha=0.8, label="SPY B&H")
    ax[0].set_title(f"SPY: FOMC even-week net vs buy&hold\n({days_in*100:.0f}% invested)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)
    ws = list(range(8))
    ax[1].bar(ws, [wk_mean[w] for w in ws],
              color=["darkred" if w % 2 == 0 else "lightgrey" for w in ws], edgecolor="k")
    ax[1].axhline(0, color="k", lw=0.8); ax[1].set_xlabel("FOMC cycle week")
    ax[1].set_ylabel("mean daily return (bps)")
    ax[1].set_title("Biweekly fingerprint: even weeks (red) > odd (grey)?")
    ax[1].grid(alpha=0.3, axis="y")
    ax[2].bar([str(k) for k in phase.keys()], list(phase.values()), color="steelblue", edgecolor="k")
    ax[2].axhline(0, color="k", lw=0.8); ax[2].set_xlabel("anchor phase shift (days)")
    ax[2].set_ylabel("net Sharpe"); ax[2].set_title("Phase robustness (knife-edge?)")
    ax[2].grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(RESULTS / "fomc_even_week.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    bt["trades"].to_csv(RESULTS / "trades.csv", index=False)

    passes = (perm["p_value"] < 0.05 and boot["ci_low"] > 0 and diff > 0
              and out["is_oos_net"]["OOS 2013-2026"]["net_sharpe"] > 0)
    print("\nVerdict:", "LEAD/testing — even-week timing survives the drift-trap permutation."
          if passes else "see REPORT — battery mixed, judge per criterion.")


if __name__ == "__main__":
    main()
