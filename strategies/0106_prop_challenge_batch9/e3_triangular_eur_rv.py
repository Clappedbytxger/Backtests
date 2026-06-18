"""I0094 - Triangular EUR-cross cointegration RV (EURUSD/GBPUSD/EURGBP).
Fixes I0089's failure mode: EURGBP == EURUSD/GBPUSD is structurally stationary.
FINDING: the no-arb residual reverts in ~0.2 DAYS (HL median 0.2) -> it is intraday/
HFT-arbitraged, NOT daily-tradeable. The honest test (sec 4): is the gross capturable
deviation at |z|>=2 entries larger than the 3-spread wall? (spoiler: no.)
"""
import numpy as np, pandas as pd
from _common import ann_sharpe, cagr_mdd, load_close, rolling_adf_p, zscore

EU = load_close("EURUSD=X"); GB = load_close("GBPUSD=X"); EG = load_close("EURGBP=X")
WALL_3SPREAD = 3 * (1.6 / 1e4)   # 4.8 bps
SWAP = 0.7 / 1e4


def run(verbose=True):
    df = pd.concat([EU.rename("EU"), GB.rename("GB"), EG.rename("EG")], axis=1).dropna()
    resid = np.log(df["EG"]) - np.log(df["EU"] / df["GB"])
    z = zscore(resid, 100)
    adf = rolling_adf_p(resid, 250)
    live = adf.shift(1) <= 0.10          # HL lower-bound gate dropped (HL~0.2d, sub-daily)
    rEG = df["EG"].pct_change()
    z_dec = z.shift(1); idx = df.index
    # next-bar reversion capture: enter at |z|>=2, exit next close (deviation is gone fast)
    daily = pd.Series(0.0, index=idx)
    entries = []
    for k in range(260, len(idx) - 1):
        t, t1 = idx[k], idx[k + 1]
        if bool(live.loc[t]) and not np.isnan(z_dec.loc[t]) and abs(z_dec.loc[t]) >= 2.0:
            pos = -1 if z_dec.loc[t] > 0 else 1
            daily.loc[t1] = pos * rEG.loc[t1] - WALL_3SPREAD - SWAP
            entries.append(abs(resid.loc[t]))   # gross deviation magnitude at entry
    daily = daily[daily != 0]
    gross_dev = np.array(entries)
    if verbose:
        s = ann_sharpe(daily); c, m = cagr_mdd(daily)
        print(f"I0094 Triangular EUR-RV: entries(|z|>=2, ADF-live)={len(gross_dev)} "
              f"median|resid|={np.median(gross_dev)*1e4:.2f}bps vs 3-spread wall={WALL_3SPREAD*1e4:.1f}bps")
        print(f"   -> deviation {'>' if np.median(gross_dev)*1e4 > WALL_3SPREAD*1e4 else '<'} wall; "
              f"net daily Sharpe={s:+.2f} CAGR={c:+.2%} (n={len(daily)})")
        print(f"   VERDICT: no-arb residual reverts intraday (HL~0.2d) + gross dev < 3-spread wall "
              f"-> HFT-arbitraged, not daily-tradeable (Kostenwand, like 0012-0015).")
    return daily


if __name__ == "__main__":
    run()
