"""I0067 Stufe-1 robustness sweep: cache per-stock ORB tables once, then vary
selection sharpness (TOP_K, relative-volume threshold), cost, and sub-period.

Goal: ground the verdict. The base run gave gross Sharpe 0.62 (far below the
claimed 2.81), net-negative. Is there ANY faithful configuration that recovers a
tradable edge, and where does the gap to 2.81 come from?
"""
from __future__ import annotations

import pickle
from pathlib import Path
import numpy as np
import pandas as pd

import _common as C
from quantlab.equities_intraday import get_equities_intraday
import e8_stocksinplay_orb as e8

CACHE = Path("results/per_stock_tables.pkl")


def load_tables():
    if CACHE.exists():
        return pickle.loads(CACHE.read_bytes())
    # Memory-light: load ONE symbol's intraday frame, reduce it to its small daily
    # ORB table, then discard the frame (a 50-frame dict is ~3 GB and swaps).
    per = {}
    for i, s in enumerate(e8.UNI, 1):
        d = get_equities_intraday([s], "ohlcv-1m", "2018-05-01", "2026-06-01", max_usd=0.01)
        df = d.get(s)
        if df is not None and not df.empty:
            t = e8.per_stock_daily(df)
            if not t.empty:
                per[s] = t
        del d, df
        print(f"  table {i}/{len(e8.UNI)} {s}", flush=True)
    CACHE.write_bytes(pickle.dumps(per))
    return per


def portfolio(per, top_k, rvol_min, cost_bps):
    all_dates = sorted(set().union(*[set(t.index) for t in per.values()]))
    g_rows, n_rows, nsel = [], [], []
    for d in all_dates:
        cands = []
        for s, t in per.items():
            if d in t.index:
                r = t.loc[d]
                rv = r["rvol"]
                if np.isfinite(rv) and rv >= rvol_min:
                    # recompute net at this cost: r_net stored at 4bps; r_gross is clean
                    cands.append((r["r_gross"], rv))
        if len(cands) < 3:
            continue
        cands.sort(key=lambda x: x[1], reverse=True)
        sel = cands[:top_k]
        rg = np.array([c[0] for c in sel])
        # cost-in-R scales with cost_bps; approximate via the 4bps-calibrated ratio
        # stored implicitly: r_net = r_gross - cost4*entry/risk. We re-derive cost at
        # cost_bps by storing the per-trade cost ratio. (Recomputed below if needed.)
        g_rows.append((d, rg.sum()))
        nsel.append(len(sel))
    g = pd.Series(dict(g_rows)).sort_index()
    return g, np.mean(nsel) if nsel else 0


def cost_adjusted(per, top_k, rvol_min, cost_bps):
    """Net sum-R using the exact per-trade cost ratio (cost4 -> scale to cost_bps)."""
    all_dates = sorted(set().union(*[set(t.index) for t in per.values()]))
    g_rows, n_rows = [], []
    scale = cost_bps / e8.COST_BPS_RT
    for d in all_dates:
        cands = []
        for s, t in per.items():
            if d in t.index:
                r = t.loc[d]; rv = r["rvol"]
                if np.isfinite(rv) and rv >= rvol_min:
                    cost4 = r["r_gross"] - r["r_net"]  # cost in R at 4 bps
                    cands.append((r["r_gross"], r["r_gross"] - scale * cost4, rv))
        if len(cands) < 3:
            continue
        cands.sort(key=lambda x: x[2], reverse=True)
        sel = cands[:top_k]
        g_rows.append((d, np.sum([c[0] for c in sel])))
        n_rows.append((d, np.sum([c[1] for c in sel])))
    g = pd.Series(dict(g_rows)).sort_index(); n = pd.Series(dict(n_rows)).sort_index()
    return g, n


def sh(s):
    return s.mean() / s.std(ddof=1) * np.sqrt(252) if len(s) > 2 and s.std(ddof=1) > 0 else 0


if __name__ == "__main__":
    per = load_tables()
    print(f"per-stock tables: {len(per)} symbols")
    print("\n=== selection sharpness x cost (gross / net ann.Sharpe) ===")
    print(f"{'TOP_K':>5} {'rvol_min':>8} {'cost_bps':>8} {'avg_n':>6} {'grossSh':>8} {'netSh':>7}")
    for top_k in (5, 10, 20):
        for rvol_min in (0.0, 1.5, 2.5):
            for cost_bps in (1.0, 2.0, 4.0):
                g, n = cost_adjusted(per, top_k, rvol_min, cost_bps)
                if len(g) < 50:
                    continue
                print(f"{top_k:5d} {rvol_min:8.1f} {cost_bps:8.1f} {0:6d} {sh(g):8.3f} {sh(n):7.3f}".replace(" 0 ", " . "))
    # sub-period of the best gross config
    print("\n=== gross sub-period stability (TOP_K=10, rvol>=0) ===")
    g, _ = cost_adjusted(per, 10, 0.0, 4.0)
    for yr in range(2018, 2027):
        s = g[(g.index >= pd.Timestamp(f"{yr}-01-01").tz_localize(g.index.tz)) &
              (g.index < pd.Timestamp(f"{yr+1}-01-01").tz_localize(g.index.tz))]
        if len(s) > 20:
            print(f"  {yr}: ann.Sharpe {sh(s):6.3f}  meanR/day {s.mean():+.3f}  days {len(s)}")
