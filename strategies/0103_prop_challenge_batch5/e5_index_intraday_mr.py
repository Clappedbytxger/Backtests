"""I0084 - Index intraday MEAN-REVERSION (re-test of the cost-wall reject).

Batch 3 (8/8) killed intraday DIRECTION/trend of a single index CFD. Intraday MR is
a DIFFERENT mechanism (trade WITH the spread-revert). Skeptical re-test, reject-not-
final. NO overnight -> NO swap; only the 3 bps RT index-CFD spread (the binding wall).

  Per RTH session (ES/NQ 15-min bars): VWAP fade.
    dev[i] = Close[i] - VWAP[i] ; thr = k * day_ATR(bars).
    dev > +thr  -> SHORT next bar open ;  dev < -thr -> LONG next bar open.
    Exit: price touches VWAP, OR adverse 1.5*ATR stop, OR session close (flat).
    One position per instrument per session. Decision uses Close[i], fill at Open[i+1].

Cost: index CFD 3 bps round-trip per trade. Honest gross-first read + random-sign perm.

Run: PYTHONPATH=src .venv/Scripts/python.exe strategies/0103_prop_challenge_batch5/e5_index_intraday_mr.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

import _common as C
from quantlab.metrics import compute_metrics

FUT = C.CACHE / "futures"
INSTR = {"ES": "ES_c_0_ohlcv-15m_RTH.parquet", "NQ": "NQ_c_0_ohlcv-15m_RTH.parquet"}
RT_COST = C.SPREAD_RT["index"] / 1e4          # 3 bps round-trip
K_DEV, STOP_ATR = 1.0, 1.5


def session_trades(day: pd.DataFrame) -> list[tuple[pd.Timestamp, float]]:
    """Return list of (exit_time, net_trade_return) for one RTH session."""
    o, h, l, c, v = (day["Open"].values, day["High"].values, day["Low"].values,
                     day["Close"].values, day["Volume"].values)
    n = len(c)
    if n < 6:
        return []
    tp = (h + l + c) / 3.0
    cum_pv = np.cumsum(tp * v)
    cum_v = np.cumsum(v)
    vwap = cum_pv / np.where(cum_v == 0, np.nan, cum_v)
    bar_ret = np.diff(c, prepend=c[0]) / c
    atr = pd.Series(np.abs(bar_ret)).expanding(min_periods=3).mean().values * c  # price-units ATR proxy
    out = []
    pos = 0; entry = 0.0; entry_atr = 0.0; direction = 0
    for i in range(n - 1):
        if pos != 0:
            px = c[i]
            hit_vwap = (direction == 1 and px >= vwap[i]) or (direction == -1 and px <= vwap[i])
            adverse = (direction == 1 and px <= entry - STOP_ATR * entry_atr) or \
                      (direction == -1 and px >= entry + STOP_ATR * entry_atr)
            if hit_vwap or adverse:
                ret = direction * (px / entry - 1.0) - RT_COST
                out.append((day.index[i], ret)); pos = 0; direction = 0
        if pos == 0 and not np.isnan(vwap[i]) and atr[i] > 0:
            dev = c[i] - vwap[i]
            thr = K_DEV * atr[i]
            if dev > thr:
                direction, pos, entry, entry_atr = -1, 1, o[i + 1], atr[i]
            elif dev < -thr:
                direction, pos, entry, entry_atr = +1, 1, o[i + 1], atr[i]
    if pos != 0:                                    # force flat at session close
        ret = direction * (c[-1] / entry - 1.0) - RT_COST
        out.append((day.index[-1], ret))
    return out


def run_instrument(path: Path) -> tuple[pd.Series, dict]:
    df = pd.read_parquet(path)
    df = df[df.index >= "2010-01-01"]
    recs = []
    for _, day in df.groupby(df.index.date):
        recs.extend(session_trades(day))
    if not recs:
        return pd.Series(dtype=float), {}
    tr = pd.Series({t: r for t, r in recs}).sort_index()
    # daily aggregation (sum of intraday trade returns that day)
    daily = tr.groupby(tr.index.normalize()).sum()
    info = {
        "n_trades": int(tr.size),
        "trades_per_day": round(float(tr.size / daily.size), 2),
        "gross_mean_bps": round(float((tr + RT_COST).mean() * 1e4), 3),
        "net_mean_bps": round(float(tr.mean() * 1e4), 3),
        "net_sharpe_per_trade": round(C.sharpe_per_trade(tr.values), 4),
        "win": round(float((tr > 0).mean()), 3),
        "perm_p_sign": round(C.perm_test_sign(tr.values, n=4000), 4),
    }
    return daily, info


def main():
    out = {"idea": "I0084", "name": "Index intraday VWAP-fade MR (ES/NQ 15m)"}
    streams = {}
    for name, fn in INSTR.items():
        daily, info = run_instrument(FUT / fn)
        out[name] = info
        streams[name] = daily
        print(f"[{name}] {info}")
    combined = pd.concat(streams.values(), axis=1).fillna(0.0).mean(axis=1)
    m = compute_metrics(C.scale_to_vol(combined, 0.10)) if combined.std() > 0 else {"sharpe": 0, "max_drawdown": 0}
    out["combined"] = {
        "net_sharpe_daily": round(C.ann_sharpe(combined), 3),
        "net_sharpe_scaled10vol": round(m["sharpe"], 3),
        "net_maxdd_at10vol": round(m["max_drawdown"], 4),
    }
    C.save_stream("i0084_index_intraday_mr", combined)
    print("=== I0084 combined ===", json.dumps(out["combined"], indent=2))
    (C.RESULTS / "e5_index_intraday_mr.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
