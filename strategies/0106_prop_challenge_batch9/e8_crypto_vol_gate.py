"""I0099 - Crypto vol/trend regime gate (PIT-clean replacement for I0086 MVRV).
Price-based, no on-chain PIT problem: SMA200 trend gate x realized-vol-TS gate sizes
the living I0080 crypto-TSMOM sleeve. Compare gated vs ungated (Sharpe AND MaxDD/bust,
I0083 discipline): the gate is only worth it if it cuts the tail without killing Sharpe.
"""
import numpy as np, pandas as pd
from _common import ann_sharpe, cagr_mdd, load_close, save_stream

BTC = load_close("BTC-USD", start="2014-01-01")
I0080 = "../0103_prop_challenge_batch5/results/streams/i0080_crypto_tsmom.parquet"


def run(verbose=True):
    sleeve = pd.read_parquet(I0080).iloc[:, 0]
    sleeve.index = pd.to_datetime(sleeve.index).tz_localize(None)
    btc = BTC.copy(); btc.index = pd.to_datetime(btc.index).tz_localize(None)
    ret = btc.pct_change()
    sma200 = btc.rolling(200).mean()
    trend_mult = np.where(btc > sma200, 1.0, 0.4)
    rv = ret.rolling(20).std() / ret.rolling(100).std()
    vol_mult = np.where(rv > 1.5, 0.5, 1.0)
    mult = pd.Series(trend_mult * vol_mult, index=btc.index).shift(1)  # act next bar
    j = pd.concat([sleeve.rename("s"), mult.rename("m")], axis=1).dropna()
    gated = j["s"] * j["m"]
    ungated = j["s"]
    if verbose:
        su, cu, mu = ann_sharpe(ungated), *cagr_mdd(ungated)
        sg, cg, mg = ann_sharpe(gated), *cagr_mdd(gated)
        wd_u = ungated.min() * 1e4; wd_g = gated.min() * 1e4
        print(f"I0099 Krypto-Vol/Trend-Gate (gated vs ungated I0080):")
        print(f"   ungated: Sharpe={su:+.2f} CAGR={cu:+.2%} MaxDD={mu:.1%} worstDay={wd_u:.0f}bps")
        print(f"   GATED  : Sharpe={sg:+.2f} CAGR={cg:+.2%} MaxDD={mg:.1%} worstDay={wd_g:.0f}bps")
        print(f"   verdict: {'tail cut, Sharpe kept -> useful' if mg > mu and sg >= su - 0.1 else 'gate hurts Sharpe (I0083-type) -> only if daily-DD binds'}")
    return gated


if __name__ == "__main__":
    g = run()
    save_stream("i0099_crypto_gated", g)
