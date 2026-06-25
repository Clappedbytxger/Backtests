"""I0085 - FX RV / cointegrated pair reversion (breadth, cheapest instrument).

Market-neutral RV-MR on correlated USD majors with a ROLLING (look-ahead-free)
hedge ratio -- the classic RV backtest pitfall is a full-sample beta, avoided here.
  Clusters: EURUSD~GBPUSD , AUDUSD~NZDUSD.
  beta_t = rolling OLS(logP1 ~ logP2, 120d) using data <= t-1.
  spread = logP1 - beta*logP2 ; z = (spread - mean120)/std120.
  |z| > 2 enter (s=+1 long spread when z<-2, s=-1 when z>+2),
  |z| < 0.5 exit ; |z| > 3.5 stop ; 20d time-stop. Re-estimate beta daily.
  pnl_day = s_held * (r1 - beta_held * r2).

Cost: FX 1.6 bps RT/leg -> 0.8/side on turnover + 0.5 bps/night/leg swap.

Run: PYTHONPATH=src .venv/Scripts/python.exe strategies/0103_prop_challenge_batch5/e6_fx_rv_coint.py
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.metrics import compute_metrics

Z_IN, Z_OUT, Z_STOP, T_STOP, WIN = 2.0, 0.5, 3.5, 20, 120
SPREAD_SIDE = C.SPREAD_RT["fx"] / 2.0 / 1e4
SWAP_NIGHT = C.SWAP_PER_NIGHT["fx"] / 1e4
CLUSTERS = {"EURUSD~GBPUSD": ("EURUSD=X", "GBPUSD=X"),
            "AUDUSD~NZDUSD": ("AUDUSD=X", "NZDUSD=X")}


def rolling_beta(lp1: pd.Series, lp2: pd.Series, win: int) -> pd.Series:
    cov = lp1.rolling(win).cov(lp2)
    var = lp2.rolling(win).var()
    return (cov / var).shift(1)        # use window ending t-1


def run_cluster(p1: pd.Series, p2: pd.Series) -> tuple[pd.Series, dict]:
    df = pd.concat([p1.rename("p1"), p2.rename("p2")], axis=1, sort=True).dropna()
    lp1, lp2 = np.log(df["p1"]), np.log(df["p2"])
    beta = rolling_beta(lp1, lp2, WIN)
    spread = lp1 - beta * lp2
    z = (spread - spread.rolling(WIN).mean()) / spread.rolling(WIN).std()

    zv, bv = z.values, beta.values
    pos = np.zeros(len(zv)); cur, held = 0, 0
    for i in range(len(zv)):
        zi = zv[i]
        if cur != 0:
            held += 1
            if np.isnan(zi) or abs(zi) > Z_STOP or abs(zi) < Z_OUT or held >= T_STOP:
                cur, held = 0, 0
        if cur == 0 and not np.isnan(zi) and not np.isnan(bv[i]):
            if zi < -Z_IN:
                cur, held = +1, 0      # spread cheap -> long spread
            elif zi > Z_IN:
                cur, held = -1, 0
        pos[i] = cur
    s = pd.Series(pos, index=df.index)
    s_held = s.shift(1).fillna(0.0)
    r1, r2 = df["p1"].pct_change(), df["p2"].pct_change()
    beta_held = beta.shift(1).fillna(0.0)
    gross = s_held * (r1 - beta_held * r2)

    turn = s_held.diff().abs().fillna(s_held.abs())
    spread_cost = turn * 2 * SPREAD_SIDE
    swap_cost = (s_held.abs() * (1 + beta_held.abs())) * SWAP_NIGHT
    net = (gross - spread_cost - swap_cost).dropna()
    seg = (s_held != s_held.shift()).cumsum()[s_held != 0]
    trades = net.groupby(seg).sum()
    info = {
        "n_trades": int(trades.size),
        "exposure_frac": round(float((s_held != 0).mean()), 3),
        "gross_sharpe": round(C.ann_sharpe(gross), 3),
        "net_sharpe": round(C.ann_sharpe(net), 3),
        "trade_win": round(float((trades > 0).mean()), 3) if trades.size else 0.0,
        "trade_mean_bps": round(float(trades.mean() * 1e4), 2) if trades.size else 0.0,
    }
    return net, info


def main():
    px = {tk: get_prices(tk, start="2003-01-01")["Close"]
          for pair in CLUSTERS.values() for tk in pair}
    streams, per_cluster = {}, {}
    for name, (a, b) in CLUSTERS.items():
        net, info = run_cluster(px[a], px[b])
        streams[name] = net
        per_cluster[name] = info
        print(f"[{name}] {info}")

    combined = pd.concat(streams.values(), axis=1).fillna(0.0).mean(axis=1)
    combined = combined[combined.index >= max(s.index.min() for s in streams.values())]
    m = compute_metrics(C.scale_to_vol(combined, 0.10))
    yearly = combined.groupby(combined.index.year).apply(lambda s: float((1 + s).prod() - 1))
    out = {
        "idea": "I0085", "name": "FX RV cointegrated pair reversion",
        "period": f"{combined.index.min().date()}..{combined.index.max().date()}",
        "per_cluster": per_cluster,
        "combined_gross_sharpe": round(C.ann_sharpe(pd.concat(streams.values(), axis=1).mean(axis=1)), 3),
        "combined_net_sharpe": round(C.ann_sharpe(combined), 3),
        "net_sharpe_scaled10vol": round(m["sharpe"], 3),
        "net_maxdd_at10vol": round(m["max_drawdown"], 4),
        "yearly_net": {str(int(y)): round(float(v), 3) for y, v in yearly.items()},
    }
    C.save_stream("i0085_fx_rv_coint", combined)
    print("=== I0085 FX RV cointegration ===")
    print(json.dumps({k: v for k, v in out.items() if k not in ("yearly_net", "per_cluster")}, indent=2))
    print("yearly net:", out["yearly_net"])
    (C.RESULTS / "e6_fx_rv_coint.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
