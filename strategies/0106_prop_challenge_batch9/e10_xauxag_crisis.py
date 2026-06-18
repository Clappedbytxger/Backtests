"""I0101 - Crisis-convex XAU/XAG safe-haven spread (VIX-spike gated).
Long Gold / Short Silver ONLY in risk-off (VIX>25 & spiking). Flight-to-quality:
gold = pure safe-haven, silver ~50% industrial -> ratio widens convexly in stress.
Value = NEGATIVE correlation to the equity-beta book (crash hedge), not standalone Sharpe.
"""
import numpy as np, pandas as pd
from _common import (ANN, ann_sharpe, cagr_mdd, load_close, save_stream, scale_to_vol)

GOLD = load_close("GC=F"); SILVER = load_close("SI=F"); VIX = load_close("^VIX")
SPREAD = (4.0 + 6.0) / 1e4; SWAP = 2.0 / 1e4


def run(verbose=True):
    df = pd.concat([GOLD.rename("G"), SILVER.rename("S"), VIX.rename("V")], axis=1).dropna()
    rG, rS = df["G"].pct_change(), df["S"].pct_change()
    volG, volS = rG.rolling(20).std(), rS.rolling(20).std()
    vix, vsma = df["V"], df["V"].rolling(20).mean()
    stress = (vix > 25) & (vix / vsma > 1.2)
    exit_reg = (vix < 20) & (vix < vsma)
    idx = df.index; pos = 0; days = 0; daily = pd.Series(0.0, index=idx)
    events = 0
    for k in range(25, len(idx)):
        t = idx[k]
        wS = (volG.loc[t] / volS.loc[t]) if volS.loc[t] > 0 else 1.0
        nrm = 1.0 + wS
        if pos != 0:
            daily.loc[t] = (1.0 / nrm) * rG.loc[t] - (wS / nrm) * rS.loc[t] - 2 * SWAP  # long G / short S
            days += 1
            if bool(exit_reg.shift(1).fillna(False).loc[t]) or days >= 20:
                pos = 0
        if pos == 0 and bool(stress.shift(1).fillna(False).loc[t]):
            pos = 1; days = 0; events += 1
            daily.loc[t] += (1.0 / nrm) * rG.loc[t] - (wS / nrm) * rS.loc[t] - SPREAD - 2 * SWAP
    daily_active = daily[daily != 0]
    if verbose:
        s = ann_sharpe(daily_active); c, m = cagr_mdd(daily)
        print(f"I0101 XAU/XAG crisis-spread: stress-entries={events} active-days={len(daily_active)} "
              f"active-day Sharpe={s:+.2f}")
        # crash-hedge value: correlation to the equity-beta book (i0076 RSI2)
        try:
            i76 = pd.read_parquet("../0103_prop_challenge_batch5/results/streams/i0076_rsi2_ungated.parquet").iloc[:, 0]
            i76.index = pd.to_datetime(i76.index).tz_localize(None)
            full = daily.copy(); full.index = pd.to_datetime(full.index).tz_localize(None)
            j = pd.concat([full.rename("x"), i76.rename("y")], axis=1).dropna()
            jc = j[j["x"] != 0]  # correlation on active (stress) days
            print(f"   corr to I0076 (equity-beta) on stress-active days = {jc['x'].corr(jc['y']):+.2f} "
                  f"(negative = hedge value); total return over stress days = {daily.sum()*100:+.1f}%")
        except Exception as e:
            print(f"   (hedge-corr skipped: {e})")
    return daily


if __name__ == "__main__":
    d = run()
    save_stream("i0101_xauxag_crisis", d)
