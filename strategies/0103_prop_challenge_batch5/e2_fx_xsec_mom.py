"""I0081 - Cross-sectional FX momentum (USD-cross basket, breadth lever).

Rank tradable currencies by 12-1m return vs USD; long top tertile / short bottom,
equal-vol weighted, monthly rebalance, 1-month hold. The edge IS the diversified
breadth (many simultaneous decorrelated bets), not single-pair timing.

All pairs converted to "foreign currency value in USD" so the rank is a clean
currency-strength momentum:  XXXUSD -> price ;  USDXXX -> 1/price.
Carry leg NOT modelled (swap-rate dependent) -- momentum only, per spec caveat.

Cost: FX spread 1.6 bps RT -> 0.8/side on monthly turnover + 0.5 bps/night swap.

Run: PYTHONPATH=src .venv/Scripts/python.exe strategies/0103_prop_challenge_batch5/e2_fx_xsec_mom.py
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.metrics import compute_metrics

# pair -> invert? (True if quoted USDXXX so 1/price = foreign-in-USD)
PAIRS = {
    "EURUSD=X": False, "GBPUSD=X": False, "AUDUSD=X": False, "NZDUSD=X": False,
    "USDJPY=X": True, "USDCAD=X": True, "USDCHF=X": True,
    "USDNOK=X": True, "USDSEK=X": True,
}
LB_LONG, LB_SKIP = 252, 21
LEG_VOL = 0.10
SPREAD_SIDE = C.SPREAD_RT["fx"] / 2.0 / 1e4
SWAP_NIGHT = C.SWAP_PER_NIGHT["fx"] / 1e4


def build_panel() -> pd.DataFrame:
    cols = {}
    for tk, inv in PAIRS.items():
        try:
            p = get_prices(tk, start="2003-01-01")["Close"]
            cols[tk.replace("=X", "")] = (1.0 / p) if inv else p
        except Exception as e:
            print(f"skip {tk}: {e}")
    return pd.DataFrame(cols).sort_index().ffill(limit=3)


def main():
    px = build_panel()
    rets = px.pct_change()
    mom = px.shift(LB_SKIP) / px.shift(LB_LONG) - 1.0      # 12-1m, known at t
    sigma = rets.rolling(40).std() * np.sqrt(252)

    # month-end rebalance dates
    me = px.index.to_series().groupby([px.index.year, px.index.month]).transform("max") == px.index.to_series()
    weights = pd.DataFrame(np.nan, index=px.index, columns=px.columns)
    for dt in px.index[me.values]:
        m = mom.loc[dt].dropna()
        if m.size < 6:
            continue
        n_side = max(1, m.size // 3)
        longs = m.nlargest(n_side).index
        shorts = m.nsmallest(n_side).index
        sg = sigma.loc[dt]
        w = pd.Series(0.0, index=px.columns)
        for c in longs:
            w[c] = LEG_VOL / sg[c] if sg[c] > 0 else 0.0
        for c in shorts:
            w[c] = -LEG_VOL / sg[c] if sg[c] > 0 else 0.0
        # dollar-neutralize and normalize gross to ~1
        w = w - w.mean()
        gross = w.abs().sum()
        if gross > 0:
            w = w / gross
        weights.loc[dt] = w.values
    weights = weights.ffill()
    w_held = weights.shift(1)                               # execute next session
    valid = w_held.notna().any(axis=1)
    w_held = w_held[valid].fillna(0.0)
    R = rets.reindex(w_held.index).fillna(0.0)

    gross = (w_held * R).sum(axis=1)
    dW = w_held.diff().abs().fillna(w_held.abs())
    spread_cost = dW.sum(axis=1) * SPREAD_SIDE
    swap_cost = w_held.abs().sum(axis=1) * SWAP_NIGHT
    net = (gross - spread_cost - swap_cost).dropna()

    yearly = net.groupby(net.index.year).apply(lambda s: float((1 + s).prod() - 1))
    m = compute_metrics(C.scale_to_vol(net, 0.10))
    out = {
        "idea": "I0081", "name": "Cross-sectional FX momentum (12-1m, monthly)",
        "n_pairs": int(px.shape[1]),
        "period": f"{net.index.min().date()}..{net.index.max().date()}",
        "gross_sharpe": round(C.ann_sharpe(gross), 3),
        "net_sharpe": round(C.ann_sharpe(net), 3),
        "net_sharpe_scaled10vol": round(m["sharpe"], 3),
        "net_maxdd_at10vol": round(m["max_drawdown"], 4),
        "ann_cost_bps": round(float((spread_cost + swap_cost).mean() * 252 * 1e4), 1),
        "perm_p_timing": round(C.perm_test_rotation(w_held, R, n=1500), 4),
        "yearly_net": {str(int(y)): round(float(v), 3) for y, v in yearly.items()},
    }
    C.save_stream("i0081_fx_xsec_mom", net)
    print("=== I0081 Cross-sectional FX momentum ===")
    print(json.dumps({k: v for k, v in out.items() if k != "yearly_net"}, indent=2))
    print("yearly net:", out["yearly_net"])
    (C.RESULTS / "e2_fx_xsec_mom.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
