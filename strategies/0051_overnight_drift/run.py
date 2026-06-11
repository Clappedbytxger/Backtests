"""Strategy 0051 — Overnight Drift (Boyarchenko/Larsen/Whelan; "night vs day").

Paper-edge #2. Claim: the equity premium is earned almost entirely OVERNIGHT
(prev close -> next open), while the intraday session (open -> close) contributes
~nothing; the NY-Fed refinement concentrates the drift in a narrow window around
the European open (~02:00-04:00 ET). Structural cause: inventory-risk transfer —
market makers offload inventory after the US close and pay liquidity providers in
the thin overnight session.

Tradability / cost: this is a HIGH-frequency edge — holding every night is one
round-trip PER DAY (~252/year). At 3 bps MES round-trip that is ~7.6%/year of
cost, so unlike the seasonal #5 (0050) the cost IS potentially binding here. The
honest question is whether the overnight premium survives 252 round-trips.

Data:
  * SPY (1993+, adjusted OHLC) — clean tradable open/close decomposition.
  * ^GSPC (index) from 1982 — longer cross-check (older index "Open" is unreliable).
  * ES.c.0 1h Globex (2010+) — locate WHEN the overnight drift accrues (by ET hour).

Look-ahead audit: overnight position is decided at the close (buy MOC) and exited
at the next open (sell MOO) — both are tradable instants; no future data.

Run:
    .venv/Scripts/python.exe strategies/0051_overnight_drift/run.py
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
from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

ES_1H = ROOT / "data" / "cache" / "futures" / "ES_c_0_ohlcv-1h_2010-06-06_2026-06-06.parquet"
RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

RT_COST = 0.0003          # MES round-trip, charged once per held night
ANN = np.sqrt(252)
OOS_START = "2010-01-01"


def decompose(df: pd.DataFrame) -> pd.DataFrame:
    """Split daily OHLC into overnight (Cprev->Open) and intraday (Open->Close)."""
    o, c = df["Open"], df["Close"]
    overnight = (o / c.shift(1) - 1.0).rename("overnight")
    intraday = (c / o - 1.0).rename("intraday")
    c2c = (c.pct_change()).rename("c2c")
    return pd.concat([overnight, intraday, c2c], axis=1).dropna()


def stat(r: pd.Series, cost: float = 0.0) -> dict:
    r = r.dropna()
    net = r - cost
    return {"n": int(len(r)), "mean_bps": float(r.mean() * 1e4),
            "ann_ret_pct": float(r.mean() * 252 * 100),
            "gross_sharpe": float(r.mean() / r.std() * ANN) if r.std() else float("nan"),
            "net_sharpe": float(net.mean() / net.std() * ANN) if net.std() else float("nan"),
            "net_ann_pct": float(net.mean() * 252 * 100), "win": float((r > 0).mean())}


def main() -> None:
    out: dict = {"cost_rt_bps": RT_COST * 1e4, "oos_start": OOS_START}

    spy = get_prices("SPY", start="1993-01-01")
    d = decompose(spy)
    print(f"SPY {d.index.min().date()}..{d.index.max().date()} ({len(d)} days)\n")

    # ---- core decomposition: overnight vs intraday vs buy&hold ----
    print("Component returns (one MOC->MOO round-trip/night = 3 bps for overnight):")
    print(f"{'':12}{'mean_bps':>9}{'annRet%':>9}{'grossSh':>8}{'netSh':>7}{'netAnn%':>8}{'win%':>6}")
    comp = {}
    for nm, col, cost in [("overnight", "overnight", RT_COST),
                          ("intraday", "intraday", RT_COST),
                          ("buy&hold(c2c)", "c2c", 0.0)]:
        s = stat(d[col], cost)
        comp[nm] = s
        print(f"{nm:12}{s['mean_bps']:9.2f}{s['ann_ret_pct']:9.1f}{s['gross_sharpe']:8.2f}"
              f"{s['net_sharpe']:7.2f}{s['net_ann_pct']:8.1f}{s['win']*100:6.1f}")
    out["components_spy"] = comp

    overnight = d["overnight"]
    # position is "long every night": pos=1 on all days, asset=overnight return
    pos = pd.Series(1.0, index=overnight.index)
    net_on = overnight - RT_COST

    # ---- IS/OOS/recent for the overnight leg (net) ----
    print("\nOvernight leg, net of 3 bps/night (Sharpe / ann.return):")
    out["is_oos_net"] = {}
    for nm, mask in [("IS 1993-2009", overnight.index < OOS_START),
                     ("OOS 2010-2026", overnight.index >= OOS_START),
                     ("recent 2015-2026", overnight.index >= "2015-01-01")]:
        seg = net_on[mask]
        s = {"net_sharpe": float(seg.mean() / seg.std() * ANN) if seg.std() else float("nan"),
             "net_ann_pct": float(seg.mean() * 252 * 100),
             "gross_sharpe": float(overnight[mask].mean() / overnight[mask].std() * ANN)}
        out["is_oos_net"][nm] = s
        print(f"  {nm:18}: net {s['net_sharpe']:+.2f} ({s['net_ann_pct']:+.1f}%/yr)  "
              f"gross {s['gross_sharpe']:+.2f}")

    # ---- significance on the GROSS overnight leg (does night beat day?) ----
    # permutation here = is overnight Sharpe special vs shuffling? With pos all-ones
    # that is trivial, so the meaningful test is the night-vs-day difference t-test
    # and the bootstrap CI of the net Sharpe.
    boot = bootstrap_ci(net_on, statistic="sharpe", n_boot=5000)
    tt = t_test_mean_return(overnight)
    tt_net = t_test_mean_return(net_on)
    # paired night-minus-day
    diff = (d["overnight"] - d["intraday"])
    tt_diff = t_test_mean_return(diff)
    pp_sharpe = float(overnight.mean() / overnight.std())
    dsr = deflated_sharpe_ratio(observed_sharpe=pp_sharpe, n_obs=len(overnight),
                                n_trials=1, returns=overnight)
    print(f"\nt-test overnight mean>0 (gross): t={tt['t_stat']:+.2f} p={tt['p_value']:.2e}")
    print(f"t-test overnight mean>0 (NET 3bps): t={tt_net['t_stat']:+.2f} p={tt_net['p_value']:.3f}")
    print(f"t-test (overnight - intraday)>0: t={tt_diff['t_stat']:+.2f} p={tt_diff['p_value']:.2e}")
    print(f"bootstrap NET overnight Sharpe 95% CI: [{boot['ci_low']:+.2f}, {boot['ci_high']:+.2f}]")
    print(f"deflated Sharpe (single pre-committed): PSR = {dsr['psr_deflated']:.3f}")
    out["significance"] = {"t_overnight_gross": tt, "t_overnight_net": tt_net,
                           "t_night_minus_day": tt_diff, "bootstrap_net": boot,
                           "deflated_sharpe": dsr}

    # ---- ES 1h Globex: WHERE does the overnight drift accrue (by ET hour)? ----
    es = pd.read_parquet(ES_1H).tz_convert("US/Eastern")
    es_ret = es["Close"].pct_change()
    by_hour = pd.DataFrame({"ret": es_ret, "hour": es.index.hour}).dropna()
    hourly = by_hour.groupby("hour")["ret"].agg(["mean", "std", "count"])
    hourly["mean_bps"] = hourly["mean"] * 1e4
    hourly["sharpe"] = hourly["mean"] / hourly["std"] * ANN
    # overnight = outside RTH 09:30-16:00 ET (hours 10..15 are RTH-ish)
    rth_hours = set(range(10, 16))
    on_hours = [h for h in hourly.index if h not in rth_hours]
    on_mean = float(by_hour[~by_hour["hour"].isin(rth_hours)]["ret"].mean() * 1e4)
    eu_window = by_hour[by_hour["hour"].isin([2, 3, 4])]["ret"]
    print("\nES 1h by ET hour (mean bps): overnight hours vs RTH")
    for h in sorted(hourly.index):
        tag = "RTH" if h in rth_hours else "ON "
        print(f"  ET {h:02d}:00 [{tag}] {hourly.loc[h,'mean_bps']:+6.2f}bps  Sharpe {hourly.loc[h,'sharpe']:+.2f}")
    print(f"  -> EU-open window 02-04 ET: {eu_window.mean()*1e4:+.2f}bps/h, "
          f"Sharpe {eu_window.mean()/eu_window.std()*ANN:+.2f} (n={len(eu_window)})")
    out["es_hourly"] = {str(h): {"mean_bps": float(hourly.loc[h, "mean_bps"]),
                                 "sharpe": float(hourly.loc[h, "sharpe"])} for h in hourly.index}
    out["es_hourly"]["overnight_mean_bps"] = on_mean
    out["es_hourly"]["eu_window_0204_mean_bps"] = float(eu_window.mean() * 1e4)

    # ---- plots ----
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    eq_on = (1 + (overnight - RT_COST)).cumprod()
    eq_id = (1 + (d["intraday"] - RT_COST)).cumprod()
    eq_bh = (1 + d["c2c"]).cumprod()
    ax[0].semilogy(eq_on.index, eq_on.values, color="navy", label="overnight (net)")
    ax[0].semilogy(eq_id.index, eq_id.values, color="indianred", label="intraday (net)")
    ax[0].semilogy(eq_bh.index, eq_bh.values, color="grey", alpha=0.8, label="buy&hold")
    ax[0].set_title("SPY: overnight vs intraday vs buy&hold\n(net of 3 bps/round-trip)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3, which="both")
    cats = ["overnight\n(gross)", "overnight\n(net 3bps)", "intraday\n(gross)", "buy&hold"]
    vals = [comp["overnight"]["ann_ret_pct"], comp["overnight"]["net_ann_pct"],
            comp["intraday"]["ann_ret_pct"], comp["buy&hold(c2c)"]["ann_ret_pct"]]
    ax[1].bar(cats, vals, color=["navy", "steelblue", "indianred", "grey"], edgecolor="k")
    ax[1].axhline(0, color="k", lw=0.8); ax[1].set_ylabel("annualized return (%)")
    ax[1].set_title("Equity premium is overnight —\nbut cost eats much of the net")
    ax[1].grid(alpha=0.3, axis="y")
    hrs = sorted(hourly.index)
    bar_c = ["indianred" if h in rth_hours else "navy" for h in hrs]
    ax[2].bar([f"{h:02d}" for h in hrs], [hourly.loc[h, "mean_bps"] for h in hrs], color=bar_c, edgecolor="k")
    ax[2].axhline(0, color="k", lw=0.8); ax[2].set_xlabel("ET hour (navy=overnight, red=RTH)")
    ax[2].set_ylabel("mean return (bps)")
    ax[2].set_title("ES 1h: drift accrues overnight,\nclustered around the EU open (02-04 ET)")
    ax[2].grid(alpha=0.3, axis="y"); ax[2].tick_params(axis="x", labelsize=7)
    fig.tight_layout()
    fig.savefig(RESULTS / "overnight_drift.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    on = comp["overnight"]
    print(f"\nSUMMARY: overnight gross Sharpe {on['gross_sharpe']:.2f} "
          f"({on['ann_ret_pct']:.1f}%/yr) vs intraday {comp['intraday']['gross_sharpe']:.2f}. "
          f"Net of 252 round-trips: Sharpe {on['net_sharpe']:.2f} ({on['net_ann_pct']:.1f}%/yr).")


if __name__ == "__main__":
    main()
