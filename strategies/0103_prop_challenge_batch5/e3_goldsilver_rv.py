"""I0082 - Gold/Silver ratio RV mean-reversion (market-neutral, decorrelated).

Structural RV-MR (a la 0087). ratio = XAU/XAG; z = (ratio - SMA60)/std60.
  z > +2  -> short Gold / long Silver  (dollar-neutral spread, s=+1 => long (Ag-Au))
  z < -2  -> long Gold / short Silver  (s=-1)
  Exit |z| < 0.5 ; hard stop |z| > 3.5 (regime break) ; time-stop 30 trading days.
  Signal at close[t-1], applied next session.

Cost: two gold-class legs -> spread 4 bps RT/leg on turnover + 2 bps/night/leg swap.

Run: PYTHONPATH=src .venv/Scripts/python.exe strategies/0103_prop_challenge_batch5/e3_goldsilver_rv.py
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.metrics import compute_metrics

Z_IN, Z_OUT, Z_STOP, T_STOP = 2.0, 0.5, 3.5, 30
SPREAD_SIDE = C.SPREAD_RT["gold"] / 2.0 / 1e4   # 2 bps/side per leg
SWAP_NIGHT = C.SWAP_PER_NIGHT["gold"] / 1e4      # 2 bps/night per leg


def build_positions(z: pd.Series) -> pd.Series:
    """State machine -> signed spread position s in {-1,0,+1}, decided at close t."""
    s = pd.Series(0.0, index=z.index)
    pos, held = 0, 0
    zv = z.values
    out = np.zeros(len(zv))
    for i in range(len(zv)):
        zi = zv[i]
        if pos != 0:
            held += 1
            if np.isnan(zi) or abs(zi) > Z_STOP or abs(zi) < Z_OUT or held >= T_STOP:
                pos, held = 0, 0
        if pos == 0 and not np.isnan(zi):
            if zi > Z_IN:
                pos, held = +1, 0   # ratio high -> long silver / short gold
            elif zi < -Z_IN:
                pos, held = -1, 0
        out[i] = pos
    return pd.Series(out, index=z.index)


def main():
    gc = get_prices("GC=F", start="2003-01-01")["Close"]
    si = get_prices("SI=F", start="2003-01-01")["Close"]
    df = pd.concat([gc.rename("GC"), si.rename("SI")], axis=1).dropna()
    ratio = df["GC"] / df["SI"]
    z = (ratio - ratio.rolling(60).mean()) / ratio.rolling(60).std()

    pos = build_positions(z)
    held = pos.shift(1).fillna(0.0)        # decision close t-1 -> hold t
    r_gc, r_si = df["GC"].pct_change(), df["SI"].pct_change()
    # s=+1 -> long silver / short gold ; pnl = r_si - r_gc
    gross = held * (r_si - r_gc)

    turn = held.diff().abs().fillna(held.abs())
    spread_cost = turn * 2 * SPREAD_SIDE              # two legs
    swap_cost = held.abs() * 2 * SWAP_NIGHT           # two legs held
    net = (gross - spread_cost - swap_cost).dropna()

    # per-trade stats
    seg = (held != held.shift()).cumsum()[held != 0]
    trades = net.groupby(seg).sum()
    n_trades = int(trades.size)

    yearly = net.groupby(net.index.year).apply(lambda s: float((1 + s).prod() - 1))
    m = compute_metrics(C.scale_to_vol(net, 0.10))
    # rotation timing permutation on the gross spread
    W = held.to_frame("s"); R = (r_si - r_gc).reindex(W.index).to_frame("s")
    out = {
        "idea": "I0082", "name": "Gold/Silver ratio RV mean-reversion",
        "period": f"{net.index.min().date()}..{net.index.max().date()}",
        "n_trades": n_trades,
        "exposure_frac": round(float((held != 0).mean()), 3),
        "gross_sharpe": round(C.ann_sharpe(gross), 3),
        "net_sharpe": round(C.ann_sharpe(net), 3),
        "net_sharpe_scaled10vol": round(m["sharpe"], 3),
        "net_maxdd_at10vol": round(m["max_drawdown"], 4),
        "trade_win": round(float((trades > 0).mean()), 3),
        "trade_mean_bps": round(float(trades.mean() * 1e4), 2),
        "swap_ann_bps": round(float(swap_cost.mean() * 252 * 1e4), 1),
        "perm_p_timing": round(C.perm_test_rotation(W, R, n=2000), 4),
        "boot_trade_ci_bps": [round(x * 1e4, 2) for x in C.bootstrap_mean_ci(trades.values)],
        "yearly_net": {str(int(y)): round(float(v), 3) for y, v in yearly.items()},
    }
    C.save_stream("i0082_goldsilver_rv", net)
    print("=== I0082 Gold/Silver RV ===")
    print(json.dumps({k: v for k, v in out.items() if k != "yearly_net"}, indent=2))
    print("yearly net:", out["yearly_net"])
    (C.RESULTS / "e3_goldsilver_rv.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
