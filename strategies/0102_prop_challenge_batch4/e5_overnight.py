"""I0079 - Overnight risk-premium harvest (index CFD, regime-conditioned). Re-test 0051.

Claim (#s34, Cooper/Cliff/Gulen): the equity premium accrues overnight (close->open).
0051 found SPY overnight gross Sharpe ~0.94 but net of 3 bps/night ~0.23 < buy&hold.
Batch-4 honest gate: on a CFD you pay BOTH the spread round-trip (enter at close, exit
at next open = 1 RT/night) AND the overnight SWAP/financing — and the swap mirrors the
very premium you harvest. Plus regime conditioning K1 (uptrend) / K2 (low-vol).

  Overnight return  = Open[t] / Close[t-1] - 1
  Cost/night        = CFD index spread RT (3 bps) + overnight swap (2 bps)  = ~5 bps
  K1: Close[t-1] > SMA(Close,200)[t-1]   K2: realized-vol(20) < median(252)

Run: .venv/Scripts/python.exe strategies/0102_prop_challenge_batch4/e5_overnight.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.significance import bootstrap_ci, t_test_mean_return

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

INDICES = {"US500": "SPY", "US30": "^DJI", "NAS100": "^NDX"}
SPREAD_RT = C.SPREAD_RT["index"] / 1e4   # 3 bps round-trip (1 RT per night)
SWAP_NIGHT = C.SWAP_PER_NIGHT["index"] / 1e4  # 2 bps/night financing
COST_NIGHT = SPREAD_RT + SWAP_NIGHT       # ~5 bps total per held night


def overnight_frame(df: pd.DataFrame) -> pd.DataFrame:
    o, c = df["Open"], df["Close"]
    on = (o / c.shift(1) - 1.0).rename("on")
    sma200 = c.rolling(200).mean()
    k1 = (c.shift(1) > sma200.shift(1)).rename("k1")
    rv = c.pct_change().rolling(20).std()
    rv_med = rv.rolling(252).median()
    k2 = (rv < rv_med).rename("k2")
    return pd.concat([on, k1, k2], axis=1).dropna()


def stat(r: pd.Series, cost: float) -> dict:
    r = r.dropna()
    net = r - cost
    return {
        "n": int(len(r)),
        "gross_mean_bps": round(float(r.mean() * 1e4), 3),
        "net_mean_bps": round(float(net.mean() * 1e4), 3),
        "gross_sharpe": round(C.ann_sharpe(r), 3),
        "net_sharpe": round(C.ann_sharpe(net), 3),
        "win": round(float((r > 0).mean()), 4),
    }


def main() -> None:
    out = {"idea": "I0079", "name": "Overnight premium (regime-conditioned, re-test 0051)",
           "cost_night_bps": round(COST_NIGHT * 1e4, 2)}
    per_index = {}
    for name, tk in INDICES.items():
        df = overnight_frame(get_prices(tk, start="1995-01-01"))
        on = df["on"]
        cond = df["k1"] & df["k2"]
        on_cond = on[cond]
        bh = get_prices(tk, start="1995-01-01")["Close"].pct_change()
        rec = {
            "period": f"{on.index.min().date()}..{on.index.max().date()}",
            "unconditioned": stat(on, COST_NIGHT),
            "conditioned_K1_K2": stat(on_cond, COST_NIGHT),
            "buy_hold_sharpe": round(C.ann_sharpe(bh), 3),
            "frac_nights_active": round(float(cond.mean()), 3),
        }
        # bootstrap CI of NET conditioned overnight Sharpe + t-test of net mean
        net_cond = (on_cond - COST_NIGHT)
        boot = bootstrap_ci(net_cond, statistic="sharpe", n_boot=4000)
        tt = t_test_mean_return(net_cond)
        rec["net_cond_boot_sharpe_ci"] = [round(boot["ci_low"], 3), round(boot["ci_high"], 3)]
        rec["net_cond_ttest_p"] = round(tt["p_value"], 4)
        per_index[name] = rec
        u, c2 = rec["unconditioned"], rec["conditioned_K1_K2"]
        print(f"{name}: gross {u['gross_mean_bps']:+.2f}bps (Sh {u['gross_sharpe']:+.2f}) | "
              f"net/night {u['net_mean_bps']:+.2f}bps (Sh {u['net_sharpe']:+.2f}) | "
              f"cond net Sh {c2['net_sharpe']:+.2f} | B&H {rec['buy_hold_sharpe']:+.2f}")
    out["per_index"] = per_index
    print(f"\ncost/night = {out['cost_night_bps']} bps (3 spread + 2 swap)")
    (RESULTS / "e5_overnight.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
