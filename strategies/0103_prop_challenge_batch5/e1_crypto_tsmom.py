"""I0080 - Crypto time-series momentum (decorrelated sleeve + fast-pass vehicle).

Stage-1 (original form): daily TSMOM on BTC/ETH, vol-targeted, indicator exit.
  Signal (close[t-1]):  long if Close>SMA(L) AND Close>Close[-90]
                        short (optional) if Close<SMA(L) AND Close<Close[-90]
  Vol target per coin:  w = sign * (leg_vol / sigma_i), sigma_i = 20d realized*sqrt(252)
  Execution next session (shift +1). Crash-stop -2*sigma intraday is approximated at
  the daily grid (we only hold daily, so the SMA-flip is the operative exit).

Cost Step-0 (kill-gate): crypto CFD spread 20 bps RT on turnover + 8 bps/night swap
  (1:2-leverage financing, ~30%/yr) on gross exposure. This is what kills it or not.

Run: PYTHONPATH=src .venv/Scripts/python.exe strategies/0103_prop_challenge_batch5/e1_crypto_tsmom.py
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.metrics import compute_metrics

COINS = {"BTC": ("BTC-USD", "2015-01-01"), "ETH": ("ETH-USD", "2017-01-01")}
LEG_VOL = 0.10          # per-coin vol target
SMA_L = 100
TS_LB = 90
SPREAD_SIDE = C.SPREAD_RT["crypto"] / 2.0 / 1e4   # 10 bps/side
SWAP_NIGHT = C.SWAP_PER_NIGHT["crypto"] / 1e4      # 8 bps/night


def coin_weights(close: pd.Series, allow_short: bool) -> pd.Series:
    sma = close.rolling(SMA_L).mean()
    ts = close - close.shift(TS_LB)
    long = (close > sma) & (ts > 0)
    sig = pd.Series(0.0, index=close.index)
    sig[long] = 1.0
    if allow_short:
        short = (close < sma) & (ts < 0)
        sig[short] = -1.0
    sigma = close.pct_change().rolling(20).std() * np.sqrt(252)
    w = sig * (LEG_VOL / sigma)
    return w.replace([np.inf, -np.inf], np.nan)


def run_variant(closes: dict, allow_short: bool, tag: str) -> dict:
    rets, weights = {}, {}
    for name, c in closes.items():
        weights[name] = coin_weights(c, allow_short).shift(1)   # decision t-1 -> hold t
        rets[name] = c.pct_change()
    W = pd.DataFrame(weights)
    R = pd.DataFrame(rets).reindex(W.index)
    valid = W.notna().any(axis=1)
    W = W[valid].fillna(0.0)
    R = R[valid].fillna(0.0)

    gross = (W * R).sum(axis=1) / len(closes)            # equal-weight the coins
    dW = W.diff().abs().fillna(W.abs())
    spread_cost = dW.sum(axis=1) / len(closes) * SPREAD_SIDE
    swap_cost = W.abs().sum(axis=1) / len(closes) * SWAP_NIGHT
    net = gross - spread_cost - swap_cost

    per_coin = {}
    for name in closes:
        g = (W[name] * R[name])
        net_c = g - W[name].diff().abs().fillna(W[name].abs()) * SPREAD_SIDE - W[name].abs() * SWAP_NIGHT
        per_coin[name] = {"gross_sharpe": round(C.ann_sharpe(g), 3),
                          "net_sharpe": round(C.ann_sharpe(net_c), 3)}

    yearly = net.groupby(net.index.year).apply(lambda s: float((1 + s).prod() - 1))
    m = compute_metrics(C.scale_to_vol(net, 0.10))
    return {
        "tag": tag, "allow_short": allow_short,
        "period": f"{net.index.min().date()}..{net.index.max().date()}",
        "gross_sharpe": round(C.ann_sharpe(gross), 3),
        "net_sharpe": round(C.ann_sharpe(net), 3),
        "net_sharpe_scaled10vol": round(m["sharpe"], 3),
        "net_maxdd_at10vol": round(m["max_drawdown"], 4),
        "swap_ann_bps": round(float(swap_cost.mean() * 252 * 1e4), 1),
        "spread_ann_bps": round(float(spread_cost.mean() * 252 * 1e4), 1),
        "per_coin": per_coin,
        "yearly_net": {str(int(y)): round(float(v), 3) for y, v in yearly.items()},
        "perm_p_timing": round(C.perm_test_rotation(W, R, n=2000), 4),
        "_net_stream": net,
    }


def main():
    closes = {n: get_prices(tk, start=st)["Close"] for n, (tk, st) in COINS.items()}
    out = {"idea": "I0080", "name": "Crypto TSMOM (BTC/ETH, vol-targeted)"}
    lo = run_variant(closes, allow_short=False, tag="long_only")
    ls = run_variant(closes, allow_short=True, tag="long_short")
    # choose the long-only stream for the book (CTI crypto short financing is worse)
    C.save_stream("i0080_crypto_tsmom", lo.pop("_net_stream"))
    ls.pop("_net_stream")
    out["long_only"], out["long_short"] = lo, ls
    print("=== I0080 Crypto TSMOM ===")
    for k in ("long_only", "long_short"):
        v = out[k]
        print(f"\n[{k}] gross {v['gross_sharpe']}  net {v['net_sharpe']}  "
              f"perm_p {v['perm_p_timing']}  swap {v['swap_ann_bps']}bps/yr")
        print("  per-coin:", v["per_coin"])
        print("  yearly net:", v["yearly_net"])
    (C.RESULTS / "e1_crypto_tsmom.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
