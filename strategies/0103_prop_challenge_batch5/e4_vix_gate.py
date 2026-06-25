"""I0083 - VIX vol-regime sizing gate (overlay; raises realized Sharpe, cuts bust).

NOT a standalone edge. Wraps the equity-beta MR sleeves (here a faithful RSI-2 index
mean-reversion book, the I0076 family). The MR/drift sleeves lose their edge and
correlate to 1 in vol spikes -- exactly when they threaten the daily/static limit.

  Gate (VIX close t-1, applied t):  VIX<20 -> 100% ;  20<=VIX<30 -> 60% ;  VIX>=30 -> 0%.

We compare UNGATED vs GATED on Sharpe AND drawdown (the MC bust lever). The honest
question (spec): does the gate cut the crash tail WITHOUT killing the edge?

Run: PYTHONPATH=src .venv/Scripts/python.exe strategies/0103_prop_challenge_batch5/e4_vix_gate.py
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

import _common as C
from quantlab.data import get_prices
from quantlab.metrics import compute_metrics

INDICES = {"US500": "^GSPC", "US30": "^DJI", "NAS100": "^NDX", "GER40": "^GDAXI"}
RT_COST = C.SPREAD_RT["index"] / 1e4          # 3 bps round-trip
SWAP_NIGHT = C.SWAP_PER_NIGHT["index"] / 1e4


def rsi2_stream(close: pd.Series) -> pd.Series:
    """Daily NET return of a Connors RSI-2 long-only MR sleeve on one index."""
    sma200 = close.rolling(200).mean()
    sma5 = close.rolling(5).mean()
    rsi = C.wilder_rsi(close, 2)
    uptrend = close > sma200
    entry = uptrend & (rsi < 10)
    exit_sig = close > sma5
    pos = np.zeros(len(close)); cur = 0
    ev, xv = entry.values, exit_sig.values
    for i in range(len(close)):
        if cur == 0 and ev[i]:
            cur = 1
        elif cur == 1 and xv[i]:
            cur = 0
        pos[i] = cur
    pos = pd.Series(pos, index=close.index)
    held = pos.shift(1).fillna(0.0)              # decide close t -> hold t+1
    ret = close.pct_change()
    turn = held.diff().abs().fillna(held.abs())
    net = held * ret - turn * (RT_COST / 2) - held.abs() * SWAP_NIGHT
    return net


def main():
    closes = {n: get_prices(tk, start="1995-01-01")["Close"] for n, tk in INDICES.items()}
    sleeves = {n: rsi2_stream(c) for n, c in closes.items()}
    book = pd.concat(sleeves.values(), axis=1).fillna(0.0).mean(axis=1)
    book = book[book.index >= "2000-01-01"]

    vix = get_prices("^VIX", start="1995-01-01")["Close"].reindex(book.index).ffill()
    vix_lag = vix.shift(1)
    scale = pd.Series(1.0, index=book.index)
    scale[vix_lag >= 20] = 0.6
    scale[vix_lag >= 30] = 0.0
    gated = book * scale

    def stats(s):
        m = compute_metrics(C.scale_to_vol(s, 0.10))
        return {"sharpe_raw": round(C.ann_sharpe(s), 3),
                "sharpe_at10vol": round(m["sharpe"], 3),
                "maxdd_at10vol": round(m["max_drawdown"], 4),
                "worst_day_bps": round(float(s.min() * 1e4), 1),
                "exposure_frac": round(float((s != 0).mean()), 3)}

    out = {"idea": "I0083", "name": "VIX vol-regime sizing gate (overlay on RSI-2 book)",
           "period": f"{book.index.min().date()}..{book.index.max().date()}",
           "ungated": stats(book), "gated": stats(gated)}
    # crash-window check: 2008-09..2009-03, 2020-02..2020-04
    for tag, a, b in [("gfc_2008", "2008-09-01", "2009-03-31"),
                      ("covid_2020", "2020-02-15", "2020-04-30")]:
        u = book[a:b]; g = gated[a:b]
        out[f"crash_{tag}"] = {"ungated_ret": round(float((1 + u).prod() - 1), 4),
                               "gated_ret": round(float((1 + g).prod() - 1), 4)}
    C.save_stream("i0083_rsi2_gated", gated)
    C.save_stream("i0076_rsi2_ungated", book)
    print("=== I0083 VIX gate (overlay on RSI-2 equity book) ===")
    print(json.dumps(out, indent=2))
    (C.RESULTS / "e4_vix_gate.json").write_text(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
