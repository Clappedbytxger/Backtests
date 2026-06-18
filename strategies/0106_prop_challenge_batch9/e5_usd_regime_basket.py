"""I0096 - USD-regime gated commodity-FX basket (extend I0078's AUDUSD-only finding).
USD downtrend (SMA50<SMA200 of DXY) -> long commodity-FX basket (AUD/NZD/long-CAD),
long-only (no short = beta trap, I0078 lesson). Check perm vs random regime + corr to 0086.
"""
import numpy as np, pandas as pd
from _common import (ann_sharpe, cagr_mdd, load_close, perm_test_rotation,
                     save_stream, scale_to_vol)

DXY = load_close("DX-Y.NYB")
LEGS = {"AUD": ("AUDUSD=X", +1), "NZD": ("NZDUSD=X", +1), "CAD": ("USDCAD=X", -1)}
SPREAD = 1.6 / 1e4; SWAP = 0.5 / 1e4


def run(verbose=True):
    rets = pd.DataFrame({c: load_close(p).pct_change() * s for c, (p, s) in LEGS.items()}).dropna()
    dxy = DXY.reindex(rets.index).ffill()
    regime = (dxy.rolling(50).mean() < dxy.rolling(200).mean()).astype(float)  # 1 = USD down -> long
    w = regime.shift(1).fillna(0.0)   # act next bar
    basket = rets.mean(axis=1)
    gross = w * basket
    turn = w.diff().abs().fillna(0.0)
    net = gross - turn * SPREAD - w * SWAP
    net = net.loc[rets.index[200]:]
    # permutation: weight rotation vs returns (timing test)
    W = pd.DataFrame({c: w for c in rets.columns})
    if verbose:
        s = ann_sharpe(net); c, m = cagr_mdd(net); n = len(net)
        bh = ann_sharpe(basket.loc[net.index])
        perm = perm_test_rotation(W.loc[net.index], rets.loc[net.index])
        print(f"I0096 USD-Regime Commodity-FX-Korb: Sharpe={s:+.2f} (B&H-Korb {bh:+.2f}) "
              f"CAGR={c:+.2%} MaxDD={m:.1%} time-in={w.loc[net.index].mean():.0%}")
        print(f"   perm_p(rotation)={perm:.3f} IS/OOS {ann_sharpe(net.iloc[:n//2]):+.2f}/{ann_sharpe(net.iloc[n//2:]):+.2f}")
    return net


if __name__ == "__main__":
    d = run()
    save_stream("i0096_usd_regime_basket", scale_to_vol(d))
