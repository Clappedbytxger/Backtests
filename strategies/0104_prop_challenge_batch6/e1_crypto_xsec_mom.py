"""I0088 - crypto cross-sectional momentum over the 5 CTI coins.

#s39: cross-sectional vs time-series momentum evidence is MIXED for crypto (one
study TS 31.96% > CS 14.59% p.a.; others CS better). 5 coins is a thin cross
(lit. uses 10-50+). So this is a TEST-VARIANT next to the I0080 TSMOM, not a lead.

Design: rank 5 coins by 30d return, weekly rebalance (Fri), hold 1wk.
  - market-neutral: Long Top-2 / Short Bottom-2 (removes crypto beta)
  - long-only:      Long Top-2 only (keeps beta, fast-pass)
  - benchmark:      TS momentum (each coin long if own 30d return > 0)
Equal-sigma weighting (20d realized vol). Cost = 20 bps RT spread on turnover +
8 bps/night 1:2-CFD financing (the kill-gate, #s35). Permutation = weight rotation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from _common import (
    ANN, SPREAD_RT, SWAP_PER_NIGHT, ann_sharpe, bootstrap_mean_ci, load_close,
    perm_test_rotation, save_stream, scale_to_vol,
)

COINS = ["BTC-USD", "ETH-USD", "XRP-USD", "LTC-USD", "ADA-USD"]
L = 30
VOL_N = 20
SPREAD = SPREAD_RT["crypto"] / 1e4   # 20 bps RT
SWAP = SWAP_PER_NIGHT["crypto"] / 1e4  # 8 bps/night held


def build_panel(start="2018-01-01"):
    closes = {c: load_close(c, start="2014-01-01") for c in COINS}
    px = pd.DataFrame(closes).loc[start:]
    px = px.dropna(how="all")
    return px


def run(mode="neutral", verbose=True):
    px = build_panel()
    ret = px.pct_change()
    mom = px / px.shift(L) - 1.0
    vol = ret.rolling(VOL_N).std()
    inv_vol = 1.0 / vol.replace(0, np.nan)

    # weekly (Friday) rebalance dates
    fri = px.index[px.index.weekday == 4]
    W = pd.DataFrame(0.0, index=px.index, columns=COINS)
    for d in fri:
        m = mom.loc[:d].iloc[-1]  # decision uses data up to d (acts next bar)
        iv = inv_vol.loc[:d].iloc[-1]
        avail = m.dropna().index.intersection(iv.dropna().index)
        if len(avail) < 4:
            continue
        m2 = m[avail].sort_values()
        bottom = m2.index[:2]
        top = m2.index[-2:]
        w = pd.Series(0.0, index=COINS)
        if mode in ("neutral", "longonly"):
            for c in top:
                w[c] = iv[c]
            if mode == "neutral":
                for c in bottom:
                    w[c] = -iv[c]
        elif mode == "ts":  # time-series: long any coin with positive own momentum
            for c in avail:
                if m[c] > 0:
                    w[c] = iv[c]
        # normalize gross to 1
        g = w.abs().sum()
        if g > 0:
            w = w / g
        # hold until next Friday
        nxt = fri[fri > d]
        end = nxt[0] if len(nxt) else px.index[-1]
        W.loc[(W.index > d) & (W.index <= end)] = w.values

    W = W.shift(1).fillna(0.0)  # act next bar (look-ahead-safe)
    gross = (W * ret).sum(axis=1)
    turn = W.diff().abs().sum(axis=1).fillna(0.0)
    held_nights = W.abs().sum(axis=1)  # gross exposure ~ nights financed
    net = gross - turn * (SPREAD / 2) - held_nights * SWAP
    net = net.loc[net.index >= px.index[L + VOL_N]]

    if verbose:
        gs, ns = ann_sharpe(gross.loc[net.index]), ann_sharpe(net)
        cagr = (1 + net).prod() ** (252 / len(net)) - 1
        eq = (1 + net).cumprod()
        mdd = (eq / eq.cummax() - 1).min()
        perm = perm_test_rotation(W.loc[net.index], ret.loc[net.index])
        n = len(net)
        print(f"[{mode:9s}] grossSharpe={gs:+.2f} netSharpe={ns:+.2f} "
              f"netCAGR={cagr:+.2%} MaxDD={mdd:.1%} perm_p(rot)={perm:.3f} "
              f"turn/yr={turn.sum()/(n/252):.0f}x")
        print(f"            IS/OOS net Sharpe: IS={ann_sharpe(net.iloc[:n//2]):+.2f} "
              f"OOS={ann_sharpe(net.iloc[n//2:]):+.2f}")
    return net, W, ret


if __name__ == "__main__":
    print("=== I0088 crypto cross-sectional momentum (5 CTI coins, 2018-26) ===")
    print("Crypto CFD cost = 20 bps RT spread + 8 bps/night 1:2-financing (kill-gate)\n")
    for mode in ["ts", "longonly", "neutral"]:
        net, W, ret = run(mode)
    # benchmark: equal-weight buy&hold of the 5 coins
    px = build_panel()
    bh = px.pct_change().mean(axis=1)
    print(f"\nEW buy&hold 5 coins: Sharpe={ann_sharpe(bh):+.2f} "
          f"CAGR={(1+bh).prod()**(252/len(bh))-1:+.2%}")
    net_n, W_n, ret_n = run("neutral", verbose=False)
    save_stream("i0088_crypto_xsec_neutral", scale_to_vol(net_n))
