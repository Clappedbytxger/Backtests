"""Strategy 0040 — Intraday time-of-day effects (ES 1-minute, NQ 1h cross-check).

Prop-Edge-Framework.md hypothesis #3: structural, recurring intraday flow
patterns — last-hour / close-auction drift, lunch reversion, morning->afternoon
continuation. Time-defined and therefore testable like the seasonal windows, but
daily instead of yearly.

Data: ES 1-minute (Databento GLBX.MDP3, 2010-2026, ~3,900-4,046 RTH sessions),
NQ 1h as an independent cross-instrument check. ES intraday returns == MES, so
the MES_INTRADAY cost model (3 bps round-trip) applies.

Result: REJECTED. Three findings, all against the hypothesis:
  1. The popular "last-hour drift" is ABSENT — the last 60/30/15 min carry no
     positive drift (the last 15 min are slightly negative). Intraday equity gains
     are front-loaded, not concentrated into the close.
  2. The only window with real Sharpe (full RTH, 0.55) is pure long beta
     (always long the session) and nets ~0 after a single round-trip cost.
  3. Conditional structure is empty: corr(morning, afternoon)=+0.02,
     corr(morning, lunch)=-0.06 — lunch-reversion and morning->afternoon both
     coin-flips that fail the cost gate (same as BTC 0015).
No time-of-day window is a tradable edge net of cost.

Run:
    .venv/Scripts/python.exe strategies/0040_intraday_time_of_day/run.py
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

FUT = ROOT / "data" / "cache" / "futures"
ES_1M = FUT / "ES_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet"
NQ_1H = FUT / "NQ_c_0_ohlcv-1h_2010-06-06_2026-06-06.parquet"
RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
RT_COST = 0.0003
ANN = np.sqrt(252)


def load_es_rth() -> pd.DataFrame:
    df = pd.read_parquet(ES_1M).tz_convert("US/Eastern")
    t = df.index.time
    rth = (t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())
    df = df[rth].copy()
    df["date"] = df.index.normalize()
    df["m"] = (df.index.hour - 9) * 60 + (df.index.minute - 30)  # 0..389
    return df


def window_ret(g: pd.DataFrame, a: int, b: int) -> float:
    """Return from the open of minute ``a`` to the close of minute ``b``."""
    sa = g.loc[g.m == a, "Open"]
    sb = g.loc[g.m == b, "Close"]
    if sa.empty or sb.empty:
        return np.nan
    return sb.iloc[0] / sa.iloc[0] - 1.0


def stat(s: pd.Series) -> dict:
    s = s.dropna()
    return {"n": int(len(s)), "mean_bps": float(s.mean() * 1e4),
            "sharpe": float(s.mean() / s.std() * ANN) if s.std() else float("nan"),
            "win": float((s > 0).mean()), "net_bps": float((s.mean() - RT_COST) * 1e4)}


def main() -> None:
    df = load_es_rth()
    g = df.groupby("date")
    out = {"cost_rt": RT_COST, "windows": {}, "conditional": {}, "nq_cross": {}}

    windows = {
        "first 30m (9:30-10:00)": (0, 29),
        "morning (9:30-11:00)": (0, 89),
        "lunch (12:00-13:00)": (150, 209),
        "last 60m (15:00-16:00)": (330, 389),
        "last 30m (15:30-16:00)": (360, 389),
        "last 15m (15:45-16:00)": (375, 389),
        "full RTH (9:30-16:00)": (0, 389),
    }
    print("ES time-of-day window returns (one round-trip/day, net = -3 bps):\n")
    print(f"{'window':24} {'n':>5} {'mean_bps':>9} {'Sharpe':>7} {'win%':>6} {'net_bps':>8}")
    for name, (a, b) in windows.items():
        s = g.apply(lambda x: window_ret(x, a, b))
        st = stat(s)
        out["windows"][name] = st
        print(f"{name:24} {st['n']:5d} {st['mean_bps']:9.2f} {st['sharpe']:7.2f} "
              f"{st['win']*100:6.1f} {st['net_bps']:8.2f}")

    # conditional structure
    morning = g.apply(lambda x: window_ret(x, 0, 149)).rename("morning")
    lunch = g.apply(lambda x: window_ret(x, 150, 209)).rename("lunch")
    aft = g.apply(lambda x: window_ret(x, 210, 389)).rename("aft")
    d = pd.concat([morning, lunch, aft], axis=1).dropna()
    c_ml = float(d["morning"].corr(d["lunch"]))
    c_ma = float(d["morning"].corr(d["aft"]))
    print(f"\ncorr(morning, lunch)     = {c_ml:+.3f}")
    print(f"corr(morning, afternoon) = {c_ma:+.3f}")
    for nm, sign in [("lunch fade morning", -np.sign(d["morning"]) * d["lunch"]),
                     ("afternoon fade morning", -np.sign(d["morning"]) * d["aft"]),
                     ("afternoon follow morning", np.sign(d["morning"]) * d["aft"])]:
        st = stat(sign)
        out["conditional"][nm] = st
        print(f"  {nm:26}: net={st['net_bps']:6.2f}bps Sharpe={st['sharpe']:5.2f} "
              f"win={st['win']*100:4.1f}%")
    out["conditional"]["corr_morning_lunch"] = c_ml
    out["conditional"]["corr_morning_afternoon"] = c_ma

    # NQ 1h independent cross-check: is the last RTH hour special?
    nq = pd.read_parquet(NQ_1H).tz_convert("US/Eastern")
    nq_ret = nq["Close"].pct_change()
    nq_h = pd.DataFrame({"ret": nq_ret, "hour": nq.index.hour})
    rth_hours = nq_h[(nq_h.hour >= 10) & (nq_h.hour <= 15)]
    by_hour = rth_hours.groupby("hour")["ret"].agg(["mean", "std", "count"])
    by_hour["mean_bps"] = by_hour["mean"] * 1e4
    by_hour["sharpe"] = by_hour["mean"] / by_hour["std"] * ANN
    print("\nNQ 1h close-to-close by ET hour (cross-check; is 15:00 'last hour' special?):")
    for h, row in by_hour.iterrows():
        print(f"  ET {h:02d}:00  mean={row['mean_bps']:6.2f}bps Sharpe={row['sharpe']:5.2f} n={int(row['count'])}")
        out["nq_cross"][f"ET{h}"] = {"mean_bps": float(row["mean_bps"]),
                                     "sharpe": float(row["sharpe"])}

    # ---- money-shot plot: average cumulative intraday drift by minute ----
    piv = df.pivot_table(index="m", columns="date", values="Close", aggfunc="last")
    opens = df[df.m == 0].set_index("date")["Open"]
    cum = piv.divide(opens, axis=1) - 1.0           # cumulative return from open
    avg_cum = cum.mean(axis=1) * 1e4                 # average across days, in bps
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    ax[0].plot(avg_cum.index, avg_cum.values, color="steelblue")
    ax[0].axhline(0, color="k", lw=0.8)
    ax[0].set_xlabel("minute of RTH session (0 = 09:30 ET)")
    ax[0].set_ylabel("avg cumulative return from open (bps)")
    ax[0].set_title("ES average intraday drift, 2010-2026\n(gains are front/mid-loaded — NOT in the last hour)")
    ax[0].grid(alpha=0.3)
    for x, lab in [(150, "12:00"), (330, "15:00"), (389, "16:00")]:
        ax[0].axvline(x, color="grey", ls="--", lw=0.7)
        ax[0].text(x, ax[0].get_ylim()[0], lab, fontsize=7, rotation=90, va="bottom")
    names = list(windows.keys())
    nets = [out["windows"][n]["net_bps"] for n in names]
    colors = ["seagreen" if v > 0 else "indianred" for v in nets]
    ax[1].barh(range(len(names)), nets, color=colors)
    ax[1].set_yticks(range(len(names)))
    ax[1].set_yticklabels(names, fontsize=8)
    ax[1].axvline(0, color="k", lw=0.8)
    ax[1].set_xlabel("net bps/trade (after 3 bps RT)")
    ax[1].set_title("Every time-of-day window is net-negative")
    ax[1].grid(alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(RESULTS / "time_of_day.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2))
    print("\nVerdict: REJECTED. No intraday time window has a directional edge "
          "clearing the 3 bps cost; the last-hour drift is absent, the full-RTH "
          "Sharpe is pure beta (net ~0), and intraday autocorrelation is ~0.")


if __name__ == "__main__":
    main()
