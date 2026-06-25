"""Strategy 0080 — Grain summer short (corn/wheat, mid-June to mid-July).

Idea I0044 from the `D:\\Backtest Ideas` handoff (source #s16, own Seasonax run).
The grain complex shows a pronounced summer weakness ~14 June–19 July: corn
-8.3%/trade at only 10% win (9/10 years down), wheat -4.3%, grains -5.4%. Cause:
the weather/pollination risk premium unwinds after the critical pollination phase,
good crop expectations + early harvest pressure push prices down. Short the front.

Pre-registered window = 14 June -> 19 July (literal from #s16, not re-optimised).
This is the mirror of the confirmed December grain STRENGTH (0030/0032).

Mandatory checks (lesson 0017/0029):
  * Permutation against random same-count SHORT windows — controls the drift trap.
    For a short this matters because the continuous grain series itself drifts DOWN
    (contango/roll decay), so a random short can profit; the test asks whether the
    14.6-19.7 TIMING beats random short timing.
  * Roll-exclusion test — grains roll (corn Jul->Sep around late June/early July,
    inside the window); the edge must survive removing the roll zone (lesson 0029).

Data: ZC=F (corn), ZW=F (Chicago wheat), KE=F (Kansas wheat), ZS=F (soy cross-check).
yfinance continuous front, 2000+.

Run:
    .venv/Scripts/python.exe strategies/0080_grain_summer_short/run.py
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

from quantlab.costs import IBKR_FUTURES  # noqa: E402
from quantlab.data import get_prices  # noqa: E402
from quantlab.backtest import run_backtest  # noqa: E402
from quantlab.metrics import compute_metrics, trade_stats  # noqa: E402
from quantlab.seasonal import date_window_signal  # noqa: E402
from quantlab.significance import bootstrap_ci, permutation_test, t_test_mean_return  # noqa: E402
from quantlab.roll import roll_exclusion_test  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

ANN = np.sqrt(252)
START_MD, END_MD = (6, 14), (7, 19)   # pre-registered #s16 window
# Corn/wheat Jul contract rolls to Sep around late June / early July (inside window).
ROLL_ZONES = [((6, 25), (7, 3)), ((7, 11), (7, 16))]
OOS_START = "2013-01-01"


def net_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def short_window(index: pd.DatetimeIndex) -> pd.Series:
    """-1 (short) over the pre-registered summer window, else flat."""
    return -date_window_signal(index, START_MD, END_MD, name="grain_summer_short")


def main() -> None:
    out: dict = {"idea_id": "I0044", "window": [list(START_MD), list(END_MD)]}

    markets = {}
    for tk, label in [("ZC=F", "Corn"), ("ZW=F", "Wheat (Chicago)"),
                      ("KE=F", "Wheat (Kansas)"), ("ZS=F", "Soybeans (cross-check)")]:
        try:
            p = get_prices(tk, start="2000-01-01")
            if (p["Close"] <= 0).any():
                raise ValueError("non-positive")
            markets[tk] = (label, p)
        except Exception as e:  # noqa: BLE001
            print(f"{label}: skipped ({e})")

    out["markets"] = {}
    for tk, (label, p) in markets.items():
        sig = short_window(p.index)
        bt = run_backtest(p, sig, cost_model=IBKR_FUTURES)
        net, gross, posn = bt["returns"], bt["gross_returns"], bt["position"]
        ar = p["Close"].pct_change().fillna(0.0)
        ts = trade_stats(bt["trades"])
        m = compute_metrics(net)
        perm = permutation_test(gross, ar, posn, n_perm=5000, metric="sharpe")
        # per-trade returns (one short per year)
        tr = bt["trades"]["pnl"] if len(bt["trades"]) else pd.Series(dtype=float)
        boot = bootstrap_ci(tr, statistic="mean", n_boot=5000) if len(tr) > 2 else {"ci_low": float("nan"), "ci_high": float("nan")}
        bh = compute_metrics(ar)
        rec = {"label": label, "n_trades": ts["n_trades"], "win_rate": ts["win_rate"],
               "expectancy_pct": float(ts["expectancy"] * 100), "net_sharpe": m["sharpe"],
               "bh_sharpe": bh["sharpe"], "perm_p": perm["p_value"],
               "trade_mean_boot_ci_pct": [boot["ci_low"] * 100, boot["ci_high"] * 100]}
        out["markets"][tk] = rec
        print(f"=== {label} ({tk}) short {START_MD}->{END_MD} ===")
        print(f"  trades {ts['n_trades']}, win {ts['win_rate']*100:.0f}%, expectancy {rec['expectancy_pct']:+.2f}%/trade")
        print(f"  net Sharpe {m['sharpe']:+.2f} (B&H {bh['sharpe']:+.2f}), perm p={perm['p_value']:.3f}, "
              f"trade-mean CI [{rec['trade_mean_boot_ci_pct'][0]:+.2f}%, {rec['trade_mean_boot_ci_pct'][1]:+.2f}%]")

    # ---- roll-exclusion test on the primary (corn) ----
    if "ZC=F" in markets:
        _, pc = markets["ZC=F"]
        rex = roll_exclusion_test(pc, short_window(pc.index), ROLL_ZONES, n_perm=5000)
        out["roll_check_corn"] = {
            "base_perm_p": rex["base"]["perm_p"], "base_expectancy_pct": rex["base"]["expectancy"] * 100,
            "excl_perm_p": rex["roll_excluded"]["perm_p"], "excl_expectancy_pct": rex["roll_excluded"]["expectancy"] * 100,
            "share_on_roll_days": rex["share_on_roll_days"]}
        print(f"\nCorn roll-check: base perm p={rex['base']['perm_p']:.3f} (exp {rex['base']['expectancy']*100:+.2f}%) "
              f"-> excl-roll p={rex['roll_excluded']['perm_p']:.3f} (exp {rex['roll_excluded']['expectancy']*100:+.2f}%); "
              f"share on roll days {rex['share_on_roll_days']*100:.0f}%")

    # ---- IS/OOS corn ----
    if "ZC=F" in markets:
        _, pc = markets["ZC=F"]
        bt = run_backtest(pc, short_window(pc.index), cost_model=IBKR_FUTURES)
        net = bt["returns"]
        out["is_oos_corn"] = {nm: net_sharpe(net[msk]) for nm, msk in
                              [("IS 2001-2012", net.index < OOS_START), ("OOS 2013-2026", net.index >= OOS_START)]}
        print(f"Corn IS/OOS net Sharpe: IS {out['is_oos_corn']['IS 2001-2012']:+.2f} / OOS {out['is_oos_corn']['OOS 2013-2026']:+.2f}")

    # ---- plot ----
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    labs = [out["markets"][tk]["label"] for tk in out["markets"]]
    exps = [out["markets"][tk]["expectancy_pct"] for tk in out["markets"]]
    ax[0].bar(labs, exps, color=["firebrick" if e < 0 else "grey" for e in exps], edgecolor="k")
    ax[0].axhline(0, color="k", lw=0.8); ax[0].set_ylabel("expectancy %/trade (short)")
    ax[0].set_title("Grain summer short expectancy (14.6-19.7)"); ax[0].grid(alpha=0.3, axis="y")
    plt.setp(ax[0].get_xticklabels(), rotation=15, ha="right")
    if "ZC=F" in markets:
        _, pc = markets["ZC=F"]
        bt = run_backtest(pc, short_window(pc.index), cost_model=IBKR_FUTURES)
        ax[1].plot((1 + bt["returns"]).cumprod(), color="firebrick")
        ax[1].set_title("Corn summer-short equity (net)"); ax[1].grid(alpha=0.3); ax[1].set_yscale("log")
    fig.tight_layout(); fig.savefig(RESULTS / "grain_summer_short.png", dpi=110); plt.close(fig)

    (RESULTS / "metrics.json").write_text(json.dumps(out, indent=2, default=str))

    zc = out["markets"].get("ZC=F", {})
    rc = out.get("roll_check_corn", {})
    passes = (zc.get("perm_p", 1) < 0.05 and zc.get("trade_mean_boot_ci_pct", [1, 1])[1] < 0
              and rc.get("excl_perm_p", 1) < 0.05)
    print("\nVerdict:", "LEAD/testing — summer short survives permutation + roll-check."
          if passes else "see REPORT — judge per criterion.")


if __name__ == "__main__":
    main()
