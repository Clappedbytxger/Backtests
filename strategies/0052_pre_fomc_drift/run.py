"""Strategy 0052 — Pre-FOMC Announcement Drift (Lucca & Moench 2015, J. Finance).

Paper-edge #3. Claim: equities earn abnormal POSITIVE returns in the ~24h before
a scheduled FOMC policy announcement. Cause: compression of the uncertainty
premium ahead of a pre-scheduled information release; institutional de-risking
into the event then unwinds.

Data: SPY daily (1993+). FOMC announcement dates are HARD-CODED (the FRED
"FOMC Press Release" release-dates feed returns every business day, not meeting
days, so it is useless here; web extraction mis-stated 2023). The list below is
the last day of each *scheduled* meeting, 2000-2026; the 2021-2026 portion is
cross-checked against federalreserve.gov, the 2023 web-extraction glitch
corrected. Emergency / unscheduled inter-meeting actions are excluded (a weekend
emergency cut has no normal "pre-announcement drift day"). 2020's cancelled March
meeting is dropped. Verification: the script asserts ~8 meetings per year and
prints the list for eyeballing.

Test: is the return on the trading day *before* the announcement (and the
announcement day itself) abnormally positive vs ordinary days? 8 events/year,
1-day holds -> cost negligible. The permutation test (is the pre-FOMC day special
vs random same-count days?) is the key filter.

Run:
    .venv/Scripts/python.exe strategies/0052_pre_fomc_drift/run.py
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
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio, t_test_mean_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)
RT_COST = 0.0003

# FOMC scheduled-meeting announcement dates (last day of each meeting), 2000-2026.
FOMC = [
    # 2000
    "2000-02-02", "2000-03-21", "2000-05-16", "2000-06-28", "2000-08-22", "2000-10-03", "2000-11-15", "2000-12-19",
    # 2001 (excl. emergency 01-03, 04-18, 09-17)
    "2001-01-31", "2001-03-20", "2001-05-15", "2001-06-27", "2001-08-21", "2001-10-02", "2001-11-06", "2001-12-11",
    # 2002
    "2002-01-30", "2002-03-19", "2002-05-07", "2002-06-26", "2002-08-13", "2002-09-24", "2002-11-06", "2002-12-10",
    # 2003
    "2003-01-29", "2003-03-18", "2003-05-06", "2003-06-25", "2003-08-12", "2003-09-16", "2003-10-28", "2003-12-09",
    # 2004
    "2004-01-28", "2004-03-16", "2004-05-04", "2004-06-30", "2004-08-10", "2004-09-21", "2004-11-10", "2004-12-14",
    # 2005
    "2005-02-02", "2005-03-22", "2005-05-03", "2005-06-30", "2005-08-09", "2005-09-20", "2005-11-01", "2005-12-13",
    # 2006
    "2006-01-31", "2006-03-28", "2006-05-10", "2006-06-29", "2006-08-08", "2006-09-20", "2006-10-25", "2006-12-12",
    # 2007
    "2007-01-31", "2007-03-21", "2007-05-09", "2007-06-28", "2007-08-07", "2007-09-18", "2007-10-31", "2007-12-11",
    # 2008 (excl. emergency 01-22, 10-08)
    "2008-01-30", "2008-03-18", "2008-04-30", "2008-06-25", "2008-08-05", "2008-09-16", "2008-10-29", "2008-12-16",
    # 2009
    "2009-01-28", "2009-03-18", "2009-04-29", "2009-06-24", "2009-08-12", "2009-09-23", "2009-11-04", "2009-12-16",
    # 2010
    "2010-01-27", "2010-03-16", "2010-04-28", "2010-06-23", "2010-08-10", "2010-09-21", "2010-11-03", "2010-12-14",
    # 2011
    "2011-01-26", "2011-03-15", "2011-04-27", "2011-06-22", "2011-08-09", "2011-09-21", "2011-11-02", "2011-12-13",
    # 2012
    "2012-01-25", "2012-03-13", "2012-04-25", "2012-06-20", "2012-08-01", "2012-09-13", "2012-10-24", "2012-12-12",
    # 2013
    "2013-01-30", "2013-03-20", "2013-05-01", "2013-06-19", "2013-07-31", "2013-09-18", "2013-10-30", "2013-12-18",
    # 2014
    "2014-01-29", "2014-03-19", "2014-04-30", "2014-06-18", "2014-07-30", "2014-09-17", "2014-10-29", "2014-12-17",
    # 2015
    "2015-01-28", "2015-03-18", "2015-04-29", "2015-06-17", "2015-07-29", "2015-09-17", "2015-10-28", "2015-12-16",
    # 2016
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27", "2016-09-21", "2016-11-02", "2016-12-14",
    # 2017
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26", "2017-09-20", "2017-11-01", "2017-12-13",
    # 2018
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01", "2018-09-26", "2018-11-08", "2018-12-19",
    # 2019
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
    # 2020 (March scheduled meeting cancelled -> emergency 03-15; dropped here)
    "2020-01-29", "2020-04-29", "2020-06-10", "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    # 2021 (Fed-confirmed)
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    # 2022 (Fed-confirmed)
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    # 2023 (Fed-confirmed; web glitch '2023-10-01' corrected to 09-20)
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    # 2024 (Fed-confirmed)
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025 (Fed-confirmed)
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026 (past portion, Fed-confirmed)
    "2026-01-28", "2026-03-18", "2026-04-29",
]


def main() -> None:
    out: dict = {}
    fomc = pd.to_datetime(FOMC)
    # sanity: meetings per year
    per_year = pd.Series(1, index=fomc).groupby(fomc.year).sum()
    print("FOMC meetings per year:", dict(per_year))
    assert per_year.loc[2000:2019].min() == 8, "expected 8 scheduled meetings/year 2000-2019"

    spy = get_prices("SPY", start="1999-06-01")
    close = spy["Close"]
    ret = close.pct_change()
    idx = close.index
    # map each announcement to the trading-day position
    pos_of = {d: i for i, d in enumerate(idx)}

    def nearest_loc(d):
        # announcement day's trading-day index (or the next trading day if holiday)
        loc = idx.searchsorted(d)
        return int(loc) if loc < len(idx) else None

    rec = []
    for d in fomc:
        a = nearest_loc(d)
        if a is None or a < 2 or a >= len(idx):
            continue
        rec.append({
            "ann_date": idx[a],
            "pre_day_ret": float(ret.iloc[a - 1]),     # close[A-2]->close[A-1] : the "day before"
            "overnight_into": float(spy["Open"].iloc[a] / close.iloc[a - 1] - 1),  # close[A-1]->open[A] (tradable, pre-2pm)
            "ann_day_ret": float(ret.iloc[a]),          # close[A-1]->close[A]   : announcement day
            "two_day_ret": float((close.iloc[a] / close.iloc[a - 2] - 1)),  # A-1 & A combined
        })
    ev = pd.DataFrame(rec).set_index("ann_date")
    ev = ev[ev.index <= idx[-1]]
    print(f"\nUsable events: {len(ev)}  ({ev.index.min().date()}..{ev.index.max().date()})")

    # baseline: all non-event day returns
    event_days = set(ev.index)
    pre_days = set(idx[idx.searchsorted(ev.index) - 1])
    base = ret[~ret.index.isin(event_days | pre_days)].dropna()
    base_mean = float(base.mean() * 1e4)

    print(f"\nBaseline ordinary-day mean: {base_mean:+.2f} bps  (n={len(base)})")
    print(f"{'window':14}{'n':>5}{'mean_bps':>10}{'t':>7}{'p':>9}{'win%':>7}{'ann_Sharpe':>11}")
    out["windows"] = {}
    for nm, col in [("pre-FOMC day", "pre_day_ret"),
                    ("overnight->FOMC", "overnight_into"),
                    ("FOMC day", "ann_day_ret"),
                    ("both days", "two_day_ret")]:
        s = ev[col].dropna()
        tt = t_test_mean_return(s)
        # per-day Sharpe for 1-day windows; two-day annualized differently but keep ANN proxy
        shp = float(s.mean() / s.std() * ANN) if s.std() else float("nan")
        out["windows"][nm] = {"n": int(len(s)), "mean_bps": float(s.mean() * 1e4),
                              "t": tt["t_stat"], "p": tt["p_value"],
                              "win": float((s > 0).mean()), "ann_sharpe": shp,
                              "net_bps": float((s.mean() - RT_COST) * 1e4)}
        print(f"{nm:14}{len(s):5d}{s.mean()*1e4:10.2f}{tt['t_stat']:7.2f}{tt['p_value']:9.4f}"
              f"{(s>0).mean()*100:7.1f}{shp:11.2f}")
    out["baseline_mean_bps"] = base_mean

    # --- headline = overnight INTO the announcement (tradable, pre-2pm) ---
    # the a-priori-correct Lucca-Moench window: buy MOC the day before, sell MOO
    # on announcement morning. Permutation controls for the baseline overnight
    # drift (0051) by drawing random OVERNIGHT returns, not close-to-close.
    s = ev["overnight_into"].dropna()
    obs_mean = float(s.mean())
    all_overnight = (spy["Open"] / spy["Close"].shift(1) - 1).dropna().values
    rng = np.random.default_rng(42)
    n = len(s)
    null = np.array([rng.choice(all_overnight, size=n, replace=False).mean() for _ in range(5000)])
    p_perm = float((np.sum(null >= obs_mean) + 1) / 5001)
    boot = bootstrap_ci(s, statistic="sharpe", n_boot=5000)
    pp_sharpe = float(s.mean() / s.std())
    dsr = deflated_sharpe_ratio(observed_sharpe=pp_sharpe, n_obs=n, n_trials=4, returns=s)
    print(f"\nHeadline = overnight->FOMC. permutation vs random {n} OVERNIGHTS "
          f"(controls for baseline overnight drift): p = {p_perm:.4f}")
    print(f"  (baseline overnight mean = {np.mean(all_overnight)*1e4:+.2f} bps)")
    print(f"bootstrap overnight->FOMC Sharpe 95% CI: [{boot['ci_low']:+.2f}, {boot['ci_high']:+.2f}]")
    print(f"deflated Sharpe (n_trials=4 windows): PSR = {dsr['psr_deflated']:.3f}")
    out["headline_overnight_into"] = {"permutation_p_vs_overnight": p_perm, "bootstrap": boot,
                                      "deflated_sharpe": dsr, "mean_bps": obs_mean * 1e4,
                                      "baseline_overnight_bps": float(np.mean(all_overnight) * 1e4)}

    # --- decay split: 2000-2014 vs 2015-2026 (Lucca-Moench published 2015) ---
    print("\nDecay check (overnight->FOMC mean bps):")
    out["decay"] = {}
    for nm, mask in [("2000-2014", ev.index.year <= 2014), ("2015-2026", ev.index.year >= 2015)]:
        seg = ev.loc[mask, "overnight_into"]
        tt = t_test_mean_return(seg)
        out["decay"][nm] = {"n": int(len(seg)), "mean_bps": float(seg.mean() * 1e4),
                            "t": tt["t_stat"], "p": tt["p_value"]}
        print(f"  {nm}: {seg.mean()*1e4:+.2f} bps (n={len(seg)}, t={tt['t_stat']:+.2f}, p={tt['p_value']:.3f})")

    # --- plot ---
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    cats = ["overnight\n->FOMC", "pre-FOMC\nday", "FOMC\nday", "ordinary\nday"]
    vals = [out["windows"]["overnight->FOMC"]["mean_bps"], out["windows"]["pre-FOMC day"]["mean_bps"],
            out["windows"]["FOMC day"]["mean_bps"], base_mean]
    ax[0].bar(cats, vals, color=["seagreen", "darkseagreen", "steelblue", "lightgrey"], edgecolor="k")
    ax[0].axhline(0, color="k", lw=0.8); ax[0].set_ylabel("mean return (bps)")
    ax[0].set_title("Pre-FOMC drift sits in the OVERNIGHT into\nthe announcement (SPY 2000-2026)")
    ax[0].grid(alpha=0.3, axis="y")
    cum = (1 + s).cumprod()
    ax[1].plot(cum.index, (cum.values - 1) * 100, color="seagreen", marker=".", ms=3)
    ax[1].axhline(0, color="k", lw=0.8); ax[1].set_ylabel("cumulative return (%)")
    ax[1].set_title("Compounding only the overnight->FOMC\nwindows (8 nights/year)")
    ax[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS / "pre_fomc_drift.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSUMMARY: overnight->FOMC mean {obs_mean*1e4:+.2f} bps vs "
          f"{out['headline_overnight_into']['baseline_overnight_bps']:+.2f} ordinary overnight; "
          f"permutation p={p_perm:.3f}, win {(s>0).mean()*100:.0f}%.")


if __name__ == "__main__":
    main()
