"""I0095 - Commodity-FX <-> commodity lead-lag / catch-up RV (USDCAD<->WTI, AUDUSD<->XAU).
Commodity leads the commodity-currency; trade the FX catch-up when it diverges.
Explore confirms a LAG exists (commodity[t]->fx[t+1] corr >= contemporaneous). Reported on
the daily NET stream (Sharpe + perm), not per-trade (positions chain back-to-back).
"""
import numpy as np, pandas as pd
from _common import (ann_sharpe, cagr_mdd, load_close, perm_test_rotation,
                     save_stream, scale_to_vol, zscore)

PAIRS = {"CAD~WTI": ("USDCAD=X", -1, "CL=F"), "AUD~XAU": ("AUDUSD=X", +1, "GC=F")}
SPREAD = 1.6 / 1e4


def explore_lag():
    print("--- Explore: does a LAG exist? (corr commodity[t]->fx[t+1] vs contemp) ---")
    for nm, (fxp, sgn, cm) in PAIRS.items():
        fx = (load_close(fxp).pct_change() * sgn); co = load_close(cm).pct_change()
        d = pd.concat([fx.rename("fx"), co.rename("co")], axis=1).dropna()
        print(f"  {nm}: contemp={d['co'].corr(d['fx']):+.3f}  commodity->fx[+1]={d['co'].corr(d['fx'].shift(-1)):+.3f}")


def run(verbose=True):
    streams = {}; Ws = {}; Rs = {}
    for nm, (fxp, sgn, cm) in PAIRS.items():
        rfx = load_close(fxp).pct_change() * sgn; rco = load_close(cm).pct_change()
        df = pd.concat([rfx.rename("fx"), rco.rename("co")], axis=1).dropna()
        zC = zscore(df["co"].rolling(20).sum(), 252)
        zF = zscore(df["fx"].rolling(20).sum(), 252)
        div = (zC - zF).shift(1)
        corr60 = df["co"].rolling(60).corr(df["fx"]).shift(1)
        # position: +1 (long fx catch-up) when commodity ran ahead (div>1.5), held while |div|>0.3
        raw = pd.Series(0.0, index=df.index)
        pos = 0
        for k in range(260, len(df)):
            t = df.index[k]
            if pos != 0 and abs(div.loc[t]) < 0.3:
                pos = 0
            if pos == 0 and corr60.loc[t] >= 0.3 and abs(div.loc[t]) > 1.5:
                pos = 1 if div.loc[t] > 0 else -1
            raw.loc[t] = pos
        turn = raw.diff().abs().fillna(0.0)
        net = raw * df["fx"] - turn * SPREAD
        streams[nm] = net
        Ws[nm] = raw; Rs[nm] = df["fx"]
        if verbose:
            nn = net[raw != 0]
            print(f"I0095 {nm}: time-in={ (raw!=0).mean():.0%} Sharpe={ann_sharpe(net):+.2f} "
                  f"CAGR={cagr_mdd(net)[0]:+.2%} MaxDD={cagr_mdd(net)[1]:.1%}")
    book = pd.concat(streams, axis=1).fillna(0.0).mean(axis=1)
    book = book.loc[book.ne(0).idxmax():]
    if verbose:
        W = pd.DataFrame(Ws).fillna(0.0); R = pd.DataFrame(Rs).fillna(0.0)
        al = W.index.intersection(R.index)
        n = len(book)
        print(f"I0095 BOOK: Sharpe={ann_sharpe(book):+.2f} perm_p(rot)={perm_test_rotation(W.loc[al], R.loc[al]):.3f} "
              f"IS/OOS {ann_sharpe(book.iloc[:n//2]):+.2f}/{ann_sharpe(book.iloc[n//2:]):+.2f}")
    return book


if __name__ == "__main__":
    explore_lag()
    b = run()
    if b.std():
        save_stream("i0095_commodity_fx_leadlag", scale_to_vol(b))
