"""I0100 - Risk-regime gated FX-carry (re-test I0020/I0090). The crash-gate is the new
angle: long-carry basket, but FLAT when VIX>25 or spiking, to dodge the negative-skew
carry-unwind that killed naive carry. Decisive test (sec 4): does the gate cut the
drawdown/skew vs ungated? Carry accrual swept (CTI net swap = the kill-gate).
"""
import numpy as np, pandas as pd
from scipy import stats
from _common import ann_sharpe, cagr_mdd, load_close, save_stream, scale_to_vol, perm_test_rotation

# long-carry pairs: long high-yield vs low-yield (JPY/CHF funding). long-ccy return sign.
PAIRS = {"AUDJPY=X": +1, "NZDJPY=X": +1, "AUDCHF=X": +1, "CADJPY=X": +1, "EURJPY=X": +1}
VIX = load_close("^VIX"); SPREAD = 2.2 / 1e4
# REAL retail-MT5 long swaps (Switch Markets, 2025-06; CTI feed is similar, swaps cut ~50%):
# ALL 5 pairs EARN positive long swap -> the long-carry direction is net-positive after markup.
# long-swap points: AUDJPY +10.29, AUDCHF +6.29, EURJPY +4.78, NZDJPY +3.49, CADJPY +3.13
# -> basket net swap ~ +1.3 %/yr currently (higher 2005-08 when AUD/NZD ~7%, ~0 in 2020-21).
# KEY: the gated TIMING already gives Sharpe 1.06 at carry=0 -> the swap is ADDITIVE, NOT the
# driver (unlike I0090). So the CTI swap-table is NOT the kill-gate for I0100. carry=0.013 = realistic.


def run(carry_yr=0.02, verbose=True):
    rets = pd.DataFrame({p: load_close(p).pct_change() * s for p, s in PAIRS.items()}).dropna()
    basket = rets.mean(axis=1)
    vix = VIX.reindex(rets.index).ffill()
    vsma = vix.rolling(50).mean()
    risk_on = ((vix < vsma) & (vix < 25) & (vix / vix.shift(5) < 1.3)).shift(1).fillna(False)
    swap_d = carry_yr / 252.0
    gated = (risk_on.astype(float) * (basket + swap_d)) - risk_on.astype(float).diff().abs().fillna(0) * SPREAD
    ungated = basket + swap_d
    g = gated.loc[rets.index[50]:]; u = ungated.loc[rets.index[50]:]
    if verbose:
        print(f"I0100 Risk-gated Carry (carry={carry_yr:+.1%}/yr): ")
        for nm, x in [("ungated", u), ("GATED  ", g)]:
            c, m = cagr_mdd(x)
            sk = stats.skew(x.dropna())
            print(f"   {nm}: Sharpe={ann_sharpe(x):+.2f} CAGR={c:+.2%} MaxDD={m:.1%} "
                  f"skew={sk:+.2f} worstDay={x.min()*100:.1f}% time-in={risk_on.loc[x.index].mean():.0%}")
        cg, mg = cagr_mdd(g); cu, mu = cagr_mdd(u)
        print(f"   verdict: {'gate cuts tail (MaxDD/skew better)' if mg > mu and stats.skew(g.dropna())>stats.skew(u.dropna()) else 'gate does NOT rescue (3rd carry reject)'}")
        # SKEPTICAL validation: is the gated Sharpe just the VIX-regime timing the BASKET BETA?
        # permutation = rotate the gate vs the basket return (random-timing null on the SAME gate density)
        W = pd.DataFrame({"g": risk_on.astype(float)}); R = pd.DataFrame({"g": basket})
        al = W.index.intersection(R.index)
        ng = len(g)
        print(f"   SKEPTIC: gate-rotation perm_p={perm_test_rotation(W.loc[al], R.loc[al]):.3f} "
              f"IS/OOS gated Sharpe {ann_sharpe(g.iloc[:ng//2]):+.2f}/{ann_sharpe(g.iloc[ng//2:]):+.2f} "
              f"| ungated-basket Sharpe full={ann_sharpe(u):+.2f}")
    return g


if __name__ == "__main__":
    for cy in [0.0, 0.013, 0.02, 0.04]:   # 0.013 = realistic basket net swap (real MT5 data)
        d = run(cy)
    # save the stream at the REALISTIC measured net swap (+1.3%/yr), not the optimistic +2%
    save_stream("i0100_carry_riskgated", scale_to_vol(run(0.013, verbose=False)))
