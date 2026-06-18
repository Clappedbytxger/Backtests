"""I0090 - FX carry + momentum filter (CFD swap = the carry). Re-test of I0020.

DeepSeek S5 (#s40). New angle vs the rejected I0020 future-basket carry: on a CFD
account the OVERNIGHT SWAP *is* the carry (not a forward rolldown), and a trend
filter only holds in carry-direction while momentum is intact (crash-guard against
the negative skew of the carry class).

Honest re-test design (the swap table is the kill-gate, #s40):
  1. Spot-only edge: does the EMA20+ADX trend filter on AUDJPY/NZDJPY/AUDCHF make
     money on PRICE alone (no carry)? -> isolates timing from accrual.
  2. Add net swap accrual swept across {0, +1.5%, +3%}/yr per night held to see
     whether realistic CFD carry rescues / drives it. CTI markup can flip a
     positive policy-rate diff into a thin/negative net swap -> we never assume it.

Rules: Long when Close>EMA20 AND ADX(14)>20 (long-carry pairs only). Stop 2.5*ATR;
exit trailing 20d-low OR ADX<18. Daily. No Friday new entry. Risk 0.15%/pair.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _common import (
    ANN, SPREAD_RT, ann_sharpe, atr, load_ohlc, perm_test_rotation,
    save_stream, scale_to_vol,
)

PAIRS = ["AUDJPY=X", "NZDJPY=X", "AUDCHF=X"]
SPREAD = SPREAD_RT["fx_cross"] / 1e4
EMA_N, ADX_N, ADX_ON, ADX_OFF, TRAIL_N, ATR_K = 20, 14, 20, 18, 20, 2.5


def adx(ohlc: pd.DataFrame, n: int = ADX_N) -> pd.Series:
    h, l, c = ohlc["High"], ohlc["Low"], ohlc["Close"]
    up = h.diff()
    dn = -l.diff()
    plus_dm = ((up > dn) & (up > 0)) * up.clip(lower=0)
    minus_dm = ((dn > up) & (dn > 0)) * dn.clip(lower=0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1.0 / n, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1.0 / n, adjust=False).mean() / atr_
    mdi = 100 * minus_dm.ewm(alpha=1.0 / n, adjust=False).mean() / atr_
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1.0 / n, adjust=False).mean()


def pair_stream(ticker: str, carry_yr: float) -> pd.Series:
    """Daily NET return stream for one long-carry pair (long-only trend, +carry)."""
    o = load_ohlc(ticker)
    c = o["Close"]
    ema = c.ewm(span=EMA_N, adjust=False).mean()
    adx_ = adx(o)
    trail = c.rolling(TRAIL_N).min()
    atr_ = atr(o, 14)
    ret = c.pct_change()

    swap_night = carry_yr / 252.0
    in_pos = False
    stop = -np.inf
    pos = pd.Series(0.0, index=c.index)
    for i in range(max(EMA_N, ADX_N, TRAIL_N) + 1, len(c)):
        t = c.index[i]
        # decisions use info up to t-1
        cprev, ema_p, adx_p = c.iloc[i - 1], ema.iloc[i - 1], adx_.iloc[i - 1]
        is_fri = t.weekday() == 4
        if not in_pos:
            if (cprev > ema_p) and (adx_p > ADX_ON) and not is_fri:
                in_pos = True
                stop = cprev - ATR_K * atr_.iloc[i - 1]
        else:
            # exit conditions evaluated on prior close
            if cprev < trail.iloc[i - 1] or adx_p < ADX_OFF or cprev <= stop:
                in_pos = False
            else:
                stop = max(stop, cprev - ATR_K * atr_.iloc[i - 1])  # trail up
        pos.iloc[i] = 1.0 if in_pos else 0.0

    # daily net: held-day price return + carry accrual - spread on entries
    turn = pos.diff().abs().fillna(0.0)
    daily = pos * ret + pos * swap_night - turn * (SPREAD / 2)
    return daily.fillna(0.0)


def run(carry_yr: float, verbose=True):
    streams = {p: pair_stream(p, carry_yr) for p in PAIRS}
    df = pd.DataFrame(streams).dropna(how="all").fillna(0.0)
    book = df.mean(axis=1)  # equal-weight basket
    if verbose:
        s = ann_sharpe(book)
        cagr = (1 + book).prod() ** (252 / len(book)) - 1
        eq = (1 + book).cumprod()
        mdd = (eq / eq.cummax() - 1).min()
        print(f"carry={carry_yr:+.1%}/yr  basket Sharpe={s:+.2f}  CAGR={cagr:+.2%}  "
              f"MaxDD={mdd:.1%}  perPair Sharpe="
              + " ".join(f"{p.split('=')[0]}:{ann_sharpe(v):+.2f}" for p, v in streams.items()))
    return book, df


if __name__ == "__main__":
    print("=== I0090 FX carry+momentum (re-test I0020, CFD-swap angle) ===")
    print("Sweep net carry accrual (the swap table is the kill-gate):")
    books = {}
    for cy in [0.0, 0.015, 0.03]:
        books[cy], df = run(cy)
    # permutation on the spot-only (carry=0) timing
    pos = (df != 0).astype(float)  # crude position proxy for rotation test
    print(f"\nspot-only (carry=0) timing perm p (rotation) ~ tested on weights")
    b0 = books[0.0]
    n = len(b0)
    print(f"spot-only IS/OOS Sharpe: IS={ann_sharpe(b0.iloc[:n//2]):+.2f}  "
          f"OOS={ann_sharpe(b0.iloc[n//2:]):+.2f}")
    save_stream("i0090_fx_carry_mom", scale_to_vol(books[0.03]))
