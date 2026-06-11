"""Strategy 0049 — Market Intraday Momentum (Gao, Han, Li, Zhou 2018, JFE).

Paper-edge #1 from the prop research list. Claim: the return of the FIRST
half-hour of the session (optionally plus the overnight gap) predicts the return
of the LAST half-hour, with a structural cause (option-gamma hedging + leveraged-
ETF rebalancing force mechanical close-direction flow). Prop-perfect on paper:
one trade/day, held only the last 30 min, flat at the close.

Data: ES.c.0 1-minute (Databento GLBX.MDP3, 2010-06..2026-06, 3,919 RTH
sessions). ES intraday returns == MES, so the MES_INTRADAY cost (3 bps round-trip)
applies. RTH = 09:30-16:00 ET, 13 half-hour bins (0..389 min).

Decision-time / look-ahead audit:
  * first-30m signal (09:30-10:00) is fully known at 10:00 -> trade the last 30m
    (15:30-16:00). Signal precedes trade by >5h. Clean.
  * 12th-half-hour signal (15:00-15:30) is known at 15:30 -> trade 15:30-16:00.
    Clean.
The engine never uses the traded bar's own close in the signal.

Result: REJECTED. Two findings, both decisive:
  1. The canonical Gao et al. signal is EMPTY on ES: beta(first30 -> last30) =
     -0.01, corr -0.01, sign-strategy gross Sharpe -0.05. The predictive
     autocorrelation the paper rests on does not exist here — a direct
     confirmation of our own 0040/0041 result (ES intraday autocorr ~0).
  2. The only predictor with a real gross pulse is the 12th half-hour
     (near-term momentum into the close): gross Sharpe +0.34, +0.63 bps/trade —
     but that does NOT clear the 3 bps round-trip cost (net -2.4 bps). Magnitude
     conditioning does not rescue it; IS->OOS the pulse halves; permutation and
     deflated-Sharpe both fail. Same cost wall as 0012-0015 / 0038-0041.

Run:
    .venv/Scripts/python.exe strategies/0049_intraday_momentum/run.py
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

from quantlab.significance import (  # noqa: E402
    bootstrap_ci,
    deflated_sharpe_ratio,
    permutation_test,
    t_test_mean_return,
)

ES_1M = ROOT / "data" / "cache" / "futures" / "ES_c_0_ohlcv-1m_2010-06-06_2026-06-06.parquet"
RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

RT_COST = 0.0003          # MES_INTRADAY round-trip (3 bps), one trade/day
ANN = np.sqrt(252)
OOS_START = "2019-01-01"  # IS 2010-2018, OOS 2019-2026 (~60/40)


# ---------------------------------------------------------------------------
def load_es_rth() -> pd.DataFrame:
    df = pd.read_parquet(ES_1M).tz_convert("US/Eastern")
    t = df.index.time
    rth = (t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())
    df = df[rth].copy()
    df["date"] = df.index.normalize()
    df["m"] = (df.index.hour - 9) * 60 + (df.index.minute - 30)  # 0..389
    return df


def win(g: pd.DataFrame, a: int, b: int) -> float:
    """Return from open(minute a) to close(minute b) within one session."""
    sa = g.loc[g.m == a, "Open"]
    sb = g.loc[g.m == b, "Close"]
    if sa.empty or sb.empty:
        return np.nan
    return sb.iloc[0] / sa.iloc[0] - 1.0


def build_panel() -> pd.DataFrame:
    """One row per session: predictors known intraday + the last-30m target."""
    df = load_es_rth()
    g = df.groupby("date")
    first30 = g.apply(lambda x: win(x, 0, 29)).rename("first30")     # 09:30-10:00
    last30 = g.apply(lambda x: win(x, 360, 389)).rename("last30")    # 15:30-16:00 (TARGET)
    h12 = g.apply(lambda x: win(x, 330, 359)).rename("h12")          # 15:00-15:30
    open0930 = g.apply(
        lambda x: x.loc[x.m == 0, "Open"].iloc[0] if (x.m == 0).any() else np.nan
    ).rename("open0930")
    close1600 = g.apply(
        lambda x: x.loc[x.m == 389, "Close"].iloc[0] if (x.m == 389).any() else np.nan
    ).rename("close1600")
    d = pd.concat([first30, last30, h12, open0930, close1600], axis=1)
    d = d.dropna(subset=["first30", "last30", "h12"])
    d["overnight"] = d["open0930"] / d["close1600"].shift(1) - 1.0   # gap (prev close)
    d["gap_first30"] = (1 + d["overnight"]) * (1 + d["first30"]) - 1.0
    return d


# ---------------------------------------------------------------------------
def sign_strategy(sig: pd.Series, target: pd.Series) -> dict:
    """Position = sign(signal), held over the last-30m target window."""
    sub = pd.concat([sig.rename("s"), target.rename("t")], axis=1).dropna()
    pos = np.sign(sub["s"])
    gross = pos * sub["t"]
    net = gross - RT_COST * (pos != 0)
    beta = float(np.polyfit(sub["s"], sub["t"], 1)[0]) if len(sub) > 2 else float("nan")
    g_std = gross.std()
    return {
        "n": int(len(sub)),
        "beta": beta,
        "corr": float(sub["s"].corr(sub["t"])),
        "gross_bps": float(gross.mean() * 1e4),
        "net_bps": float(net.mean() * 1e4),
        "gross_sharpe": float(gross.mean() / g_std * ANN) if g_std else float("nan"),
        "net_sharpe": float(net.mean() / net.std() * ANN) if net.std() else float("nan"),
        "win": float((gross > 0).mean()),
        "_gross": gross, "_net": net, "_pos": pos, "_target": sub["t"],
    }


def fmt_row(name: str, r: dict) -> str:
    return (f"{name:22} n={r['n']:4d} beta={r['beta']:+6.3f} corr={r['corr']:+.3f} "
            f"gS={r['gross_sharpe']:+5.2f} gBps={r['gross_bps']:+5.2f} "
            f"nBps={r['net_bps']:+6.2f} win={r['win']*100:4.1f}%")


def main() -> None:
    d = build_panel()
    out: dict = {
        "data": {"sessions": int(len(d)),
                 "start": str(d.index.min().date()), "end": str(d.index.max().date()),
                 "last30_std_bps": float(d["last30"].std() * 1e4),
                 "last30_mean_bps": float(d["last30"].mean() * 1e4)},
        "cost_rt_bps": RT_COST * 1e4, "oos_start": OOS_START,
        "predictors": {}, "magnitude_conditioned": {}, "best_candidate": {},
    }
    print(f"ES RTH sessions: {len(d)}  ({d.index.min().date()}..{d.index.max().date()})")
    print(f"last-30m target: std={d['last30'].std()*1e4:.1f}bps "
          f"mean={d['last30'].mean()*1e4:+.2f}bps   cost RT=3.0bps\n")

    # --- 1) all predictors, full sample (the money table) ---
    predictors = ["first30", "overnight", "gap_first30", "h12"]
    print("PREDICTOR -> last-30m  (sign strategy, 1 trade/day, flat at close):")
    results = {}
    for p in predictors:
        r = sign_strategy(d[p], d["last30"])
        results[p] = r
        out["predictors"][p] = {k: v for k, v in r.items() if not k.startswith("_")}
        print("  " + fmt_row(p, r))

    # --- 2) magnitude conditioning: trade only top-tercile |signal| days ---
    # (the paper: predictability concentrates when the first-half-hour move is big)
    print("\nMagnitude conditioning (trade only top-tercile |signal| sessions):")
    for p in predictors:
        thr = d[p].abs().quantile(2 / 3)
        mask = d[p].abs() >= thr
        r = sign_strategy(d.loc[mask, p], d.loc[mask, "last30"])
        out["magnitude_conditioned"][p] = {k: v for k, v in r.items() if not k.startswith("_")}
        print("  " + fmt_row(p + " |top3|", r))

    # --- 3) full battery on the best GROSS candidate ---
    best = max(predictors, key=lambda p: results[p]["gross_sharpe"])
    r = results[best]
    gross, net, pos, target = r["_gross"], r["_net"], r["_pos"], r["_target"]
    print(f"\n=== Full significance battery on best gross candidate: '{best}' ===")
    print(f"full-sample: gross Sharpe {r['gross_sharpe']:+.2f} ({r['gross_bps']:+.2f}bps) "
          f"-> NET Sharpe {r['net_sharpe']:+.2f} ({r['net_bps']:+.2f}bps)")

    # IS / OOS split
    is_m, oos_m = gross.index < OOS_START, gross.index >= OOS_START
    def shp(x):
        return float(x.mean() / x.std() * ANN) if x.std() else float("nan")
    is_oos = {
        "is_n": int(is_m.sum()), "oos_n": int(oos_m.sum()),
        "is_gross_sharpe": shp(gross[is_m]), "oos_gross_sharpe": shp(gross[oos_m]),
        "is_net_sharpe": shp(net[is_m]), "oos_net_sharpe": shp(net[oos_m]),
        "is_gross_bps": float(gross[is_m].mean() * 1e4),
        "oos_gross_bps": float(gross[oos_m].mean() * 1e4),
    }
    print(f"IS  (<{OOS_START}) n={is_oos['is_n']:4d}: gross Sharpe {is_oos['is_gross_sharpe']:+.2f} "
          f"({is_oos['is_gross_bps']:+.2f}bps)  net {is_oos['is_net_sharpe']:+.2f}")
    print(f"OOS (>={OOS_START}) n={is_oos['oos_n']:4d}: gross Sharpe {is_oos['oos_gross_sharpe']:+.2f} "
          f"({is_oos['oos_gross_bps']:+.2f}bps)  net {is_oos['oos_net_sharpe']:+.2f}")

    # permutation (gross, timing), bootstrap, t-test, DSR
    perm = permutation_test(gross, target, pos, n_perm=2000, metric="sharpe")
    boot = bootstrap_ci(gross, statistic="sharpe", n_boot=2000)
    tt = t_test_mean_return(net)
    # n_trials: 4 predictors x 2 conditionings = 8 cells scanned this study
    n_trials = len(predictors) * 2
    per_period_sharpe = float(gross.mean() / gross.std()) if gross.std() else float("nan")
    dsr = deflated_sharpe_ratio(
        observed_sharpe=per_period_sharpe, n_obs=len(gross),
        n_trials=n_trials, returns=gross,
    )
    print(f"permutation (gross Sharpe, n=2000): p = {perm['p_value']:.3f}")
    print(f"bootstrap gross-Sharpe 95% CI: [{boot['ci_low']:+.2f}, {boot['ci_high']:+.2f}]")
    print(f"t-test NET mean != 0: t={tt['t_stat']:+.2f} p={tt['p_value']:.3f}")
    print(f"deflated Sharpe (n_trials={n_trials}): PSR_deflated = {dsr['psr_deflated']:.3f}")

    out["best_candidate"] = {
        "name": best, "is_oos": is_oos, "permutation": perm, "bootstrap": boot,
        "t_test_net": tt, "deflated_sharpe": dsr, "n_trials": n_trials,
        "net_sharpe": r["net_sharpe"], "net_bps": r["net_bps"],
    }

    # --- 4) money-shot plot ---
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    # left: gross vs net bps per predictor (+ cost wall)
    names = predictors
    g_bps = [results[p]["gross_bps"] for p in names]
    n_bps = [results[p]["net_bps"] for p in names]
    y = np.arange(len(names))
    ax[0].barh(y + 0.18, g_bps, height=0.36, color="steelblue", label="gross")
    ax[0].barh(y - 0.18, n_bps, height=0.36,
               color=["seagreen" if v > 0 else "indianred" for v in n_bps], label="net")
    ax[0].axvline(0, color="k", lw=0.8)
    ax[0].axvline(-RT_COST * 1e4, color="grey", ls="--", lw=0.9)
    ax[0].text(-RT_COST * 1e4, len(names) - 0.5, " 3 bps cost", fontsize=7, color="grey", va="top")
    ax[0].set_yticks(y); ax[0].set_yticklabels(names, fontsize=9)
    ax[0].set_xlabel("bps/trade")
    ax[0].set_title("MIM predictors -> last-30m return\nfirst-30m signal ~0; no predictor clears cost net")
    ax[0].legend(fontsize=8, loc="lower right"); ax[0].grid(alpha=0.3, axis="x")
    # right: scatter of best signal vs target with the (flat) regression line
    sub = pd.concat([d[best].rename("s"), d["last30"].rename("t")], axis=1).dropna()
    ax[1].scatter(sub["s"] * 1e4, sub["t"] * 1e4, s=4, alpha=0.15, color="slategrey")
    xs = np.linspace(sub["s"].min(), sub["s"].max(), 50)
    b1, b0 = np.polyfit(sub["s"], sub["t"], 1)
    ax[1].plot(xs * 1e4, (b0 + b1 * xs) * 1e4, color="crimson", lw=2,
               label=f"beta={b1:+.3f}")
    ax[1].axhline(0, color="k", lw=0.6); ax[1].axvline(0, color="k", lw=0.6)
    ax[1].set_xlim(np.percentile(sub["s"], 1) * 1e4, np.percentile(sub["s"], 99) * 1e4)
    ax[1].set_ylim(np.percentile(sub["t"], 1) * 1e4, np.percentile(sub["t"], 99) * 1e4)
    ax[1].set_xlabel(f"{best} signal (bps)"); ax[1].set_ylabel("last-30m return (bps)")
    ax[1].set_title(f"Best candidate '{best}': near-flat slope\n(gross pulse is real but sub-cost)")
    ax[1].legend(fontsize=9); ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "intraday_momentum.png", dpi=110)
    plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2))
    print("\nVerdict: REJECTED. The canonical first-30m -> last-30m signal is empty "
          "(beta ~0, gross Sharpe -0.05), confirming 0040/0041. The only gross pulse "
          "(12th half-hour momentum) is +0.6 bps and dies on the 3 bps cost. The "
          "liquid-index intraday cost wall holds (cf. 0012-0015, 0038-0041).")


if __name__ == "__main__":
    main()
