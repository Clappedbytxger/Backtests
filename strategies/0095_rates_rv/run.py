"""Strategy 0095 — Treasury-Curve-Butterfly MR (I0062) + Mid-Month Reinvestment (I0056).

Batch-2 ideas from `D:\\Backtest Ideas`.

I0062 (HIGH prio, #s23): the 2s5s10s butterfly mean-reverts around a structural
level; flow dislocations (auctions, index rebalancing, convexity hedging) push it
away and arbitrageurs pull it back. Market/duration-neutral by construction (no rate
direction beta) -> a clean diversifier that double-anchors the living RV-MR family
(0087) and the living rates family (0075/0078).

  Butterfly (50-50 fly): fly_yield = y5 - 0.5*(y2 + y10), DV01-neutral so level &
  slope beta ~ 0. z-score over a rolling window; enter |z|>2 (MR), exit z->0, stop
  |z|>3.5. Long fly (long belly / short wings) profits when fly_yield falls.
  P&L from FRED yield changes x DV01 (standard rates-RV), cost per leg modeled.

I0056 (#s03): coupon/maturity reinvestment by index trackers concentrates buying
around the 15th (and month-end). Long ZN/IEF in a [T-1..T+1]-around-the-15th window,
EXCLUDING month-end days (so 0075 isn't double-counted). Permutation vs random
mid-month day blocks.

Free data: FRED (DGS2/DGS5/DGS10), yfinance (IEF/TLT/ZN=F).

Run: .venv/Scripts/python.exe strategies/0095_rates_rv/run.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
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
from quantlab.seasonal import add_calendar_features  # noqa: E402
from quantlab.significance import bootstrap_ci, permutation_test, t_test_mean_return  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ANN = np.sqrt(252)


def ns(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * ANN) if r.std() else float("nan")


def fred(sid: str, start="1990-01-01") -> pd.Series:
    key = (ROOT / ".fred.key").read_text().strip()
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
           f"&api_key={key}&file_type=json&observation_start={start}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    return pd.Series({pd.Timestamp(o["date"]): float(o["value"])
                      for o in d["observations"] if o["value"] != "."}).sort_index()


# ---------------- I0062: 2s5s10s butterfly mean-reversion ----------------
def butterfly_mr(win=60, z_in=2.0, z_out=0.0, z_stop=3.5, cost_bp=2.0) -> dict:
    y2, y5, y10 = fred("DGS2"), fred("DGS5"), fred("DGS10")
    df = pd.concat({"y2": y2, "y5": y5, "y10": y10}, axis=1).dropna()
    fly = df["y5"] - 0.5 * (df["y2"] + df["y10"])  # 50-50 fly yield (%)
    mu = fly.rolling(win).mean()
    sd = fly.rolling(win).std()
    z = ((fly - mu) / sd).dropna()
    # long-fly daily return in bp = -100 * d(fly_yield); profits when fly falls
    fly_ret_bp = -100.0 * fly.diff()
    # MR state machine on z (decision at close t, P&L earned t+1 -> shift)
    pos = pd.Series(0.0, index=z.index)
    state = 0
    for i, (dt, zz) in enumerate(z.items()):
        if state == 0:
            if zz > z_in:
                state = 1   # fly_yield high -> expect fall -> LONG fly
            elif zz < -z_in:
                state = -1
        elif state == 1:
            if zz <= z_out or zz > z_stop:
                state = 0
        elif state == -1:
            if zz >= -z_out or zz < -z_stop:
                state = 0
        pos.iloc[i] = state
    held = pos.shift(1).fillna(0.0)
    gross = held * fly_ret_bp.reindex(z.index).fillna(0.0)
    # cost on position change (bp per round trip on the fly, ~4 legs)
    cost = pos.diff().abs().fillna(pos.abs()) * cost_bp
    net = (gross - cost) / 1e4  # convert bp to return units for Sharpe consistency
    gross_u = gross / 1e4
    # betas to level (Δy10) and slope (Δy10-Δy2): should be ~0
    lvl = df["y10"].diff().reindex(z.index)
    slope = (df["y10"] - df["y2"]).diff().reindex(z.index)
    act = held != 0
    beta_lvl = float(np.polyfit(lvl[act].fillna(0), gross_u[act].fillna(0), 1)[0]) if act.sum() > 10 else np.nan
    beta_slp = float(np.polyfit(slope[act].fillna(0), gross_u[act].fillna(0), 1)[0]) if act.sum() > 10 else np.nan
    # permutation: random entry timing of same count/holding
    ar = fly_ret_bp.reindex(z.index).fillna(0.0) / 1e4
    perm = permutation_test(gross_u, ar, held, n_perm=4000, metric="sharpe")
    # per-trade stats
    trades = (pos.diff() != 0) & (pos != 0)
    cut = "2014-01-01"
    return {
        "n_obs": int(len(z)), "frac_active": float(act.mean()),
        "n_entries": int(trades.sum()),
        "gross_sharpe": ns(gross_u), "net_sharpe": ns(net),
        "net_cagr_pct": float(compute_metrics(net)["cagr"] * 100),
        "perm_p": perm["p_value"],
        "beta_to_level": beta_lvl, "beta_to_slope": beta_slp,
        "is_sharpe": ns(net[net.index < cut]), "oos_sharpe": ns(net[net.index >= cut]),
        "ex2022_sharpe": ns(net[(net.index < "2022-01-01") | (net.index >= "2023-01-01")]),
        "_net": net, "_z": z, "_fly": fly,
    }


# ---------------- I0056: mid-month reinvestment flow ----------------
def midmonth(ticker, cost, day_lo=14, day_hi=16) -> dict:
    p = get_prices(ticker, start="2002-01-01")
    feats = add_calendar_features(p.index)
    dom = pd.Series(p.index.day, index=p.index)
    # window around the 15th, EXCLUDING the last 2 trading days of month (0075 overlap)
    in_win = (dom >= day_lo) & (dom <= day_hi) & (~feats["tdom_from_end"].isin([0, 1]).values)
    sig = pd.Series(np.where(in_win, 1.0, 0.0), index=p.index)
    bt = run_backtest(p, sig, cost_model=cost)
    gross, net = bt["gross_returns"], bt["returns"]
    ar = p["Close"].pct_change().fillna(0.0)
    # event returns: per-window cumulative return
    ev = []
    pos = bt["position"].values
    r = ar.values
    i = 0
    while i < len(pos):
        if pos[i] != 0:
            j = i
            cum = 1.0
            while j < len(pos) and pos[j] != 0:
                cum *= (1 + r[j]); j += 1
            ev.append(cum - 1); i = j
        else:
            i += 1
    ev = np.array(ev)
    tt = t_test_mean_return(pd.Series(ev))
    boot = bootstrap_ci(pd.Series(ev), statistic="mean", n_boot=4000)
    perm = permutation_test(gross, ar, bt["position"], n_perm=4000, metric="sharpe")
    return {"n_windows": int(len(ev)), "event_mean_bps": float(ev.mean() * 1e4),
            "event_t": tt["t_stat"], "event_p": tt["p_value"],
            "boot_ci_bps": [boot["ci_low"] * 1e4, boot["ci_high"] * 1e4],
            "net_sharpe": ns(net), "perm_p": perm["p_value"],
            "frac_active": float((bt["position"] != 0).mean())}


def main() -> None:
    out = {"idea_ids": ["I0062", "I0056"]}

    # ---- I0062 butterfly, with a small pre-registered robustness grid ----
    print("=== I0062: 2s5s10s butterfly mean-reversion ===")
    grid = {}
    for win in (40, 60, 90):
        for z_in in (1.5, 2.0, 2.5):
            r = butterfly_mr(win=win, z_in=z_in)
            grid[f"w{win}_z{z_in}"] = r["net_sharpe"]
    base = butterfly_mr(win=60, z_in=2.0)
    out["I0062"] = {k: v for k, v in base.items() if not k.startswith("_")}
    out["I0062"]["grid_net_sharpe"] = grid
    print(f"  base (win60,z2): net Sharpe {base['net_sharpe']:+.2f} (gross {base['gross_sharpe']:+.2f}), "
          f"perm p={base['perm_p']:.3f}, CAGR {base['net_cagr_pct']:+.2f}%")
    print(f"  active {base['frac_active']:.1%}, entries {base['n_entries']}, "
          f"beta_level {base['beta_to_level']:+.3f}, beta_slope {base['beta_to_slope']:+.3f}")
    print(f"  IS/OOS/ex2022 {base['is_sharpe']:+.2f}/{base['oos_sharpe']:+.2f}/{base['ex2022_sharpe']:+.2f}")
    print(f"  grid net Sharpe range [{min(grid.values()):+.2f}, {max(grid.values()):+.2f}] over {len(grid)} cells")

    # ---- I0056 mid-month ----
    print("\n=== I0056: mid-month reinvestment flow ===")
    out["I0056"] = {}
    for tk, label, cost in [("IEF", "10y ETF", IBKR_LIQUID_ETF), ("TLT", "30y ETF", IBKR_LIQUID_ETF)]:
        r = midmonth(tk, cost)
        out["I0056"][tk] = r
        print(f"  {label}: window Ø {r['event_mean_bps']:+.2f}bps (t={r['event_t']:+.2f}, p={r['event_p']:.3f}), "
              f"net Sharpe {r['net_sharpe']:+.2f}, perm p={r['perm_p']:.3f}, "
              f"boot[{r['boot_ci_bps'][0]:+.1f},{r['boot_ci_bps'][1]:+.1f}], n={r['n_windows']}")

    # ---- plots ----
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    eq = (1 + base["_net"]).cumprod()
    ax[0].plot(eq.index, eq.values, color="navy")
    ax[0].set_title(f"I0062 butterfly MR equity (net)\nSharpe {base['net_sharpe']:+.2f}, perm p={base['perm_p']:.3f}")
    ax[0].grid(alpha=0.3); ax[0].set_ylabel("growth of 1")
    ax[1].plot(base["_z"].index, base["_z"].values, color="grey", lw=0.6)
    ax[1].axhline(2, color="firebrick", ls="--", lw=0.8); ax[1].axhline(-2, color="firebrick", ls="--", lw=0.8)
    ax[1].axhline(0, color="k", lw=0.5)
    ax[1].set_title("2s5s10s fly z-score"); ax[1].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS / "rates_rv.png", dpi=110); plt.close(fig)

    out_clean = {k: v for k, v in out.items()}
    (RESULTS / "metrics.json").write_text(json.dumps(out_clean, indent=2, default=str))

    lead62 = (base["net_sharpe"] > 0.4 and base["perm_p"] < 0.05
              and abs(base["beta_to_level"]) < 0.05 and base["oos_sharpe"] > 0)
    print("\nVerdict I0062:", "market-neutral RV-MR with edge — lead candidate."
          if lead62 else "see REPORT — weak/insignificant or not neutral.")


if __name__ == "__main__":
    main()
