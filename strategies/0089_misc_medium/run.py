"""Strategy 0089 — I0026 Sector residual momentum + I0030 Crypto weekend vol.

I0026: 11 GICS sector ETFs, residual (vs SPY) 12-1 momentum, L/S terciles vs raw
       momentum. Tests if de-beta'd momentum beats raw (cleaner factor).
I0030: BTC weekend vs weekday realized vol (the only stable crypto-calendar fact
       per #s13) + a weekend mean-reversion trade. Vola edge, not direction.
"""
import sys, json; sys.path.insert(0,'src'); from pathlib import Path
import numpy as np, pandas as pd
from quantlab.data import get_prices
from quantlab.cross_sectional import run_cross_sectional, cross_sectional_permutation_test
from quantlab.metrics import compute_metrics
ANN=np.sqrt(252)
def ns(r): r=pd.Series(r).dropna(); return float(r.mean()/r.std()*ANN) if r.std() else float('nan')
out={}
# ---- I0026 sector residual momentum ----
secs=["XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB"]
px=pd.DataFrame({s:get_prices(s,start="1999-01-01")["Close"] for s in secs})
spy=get_prices("SPY",start="1999-01-01")["Close"]
rets=px.pct_change(); spyr=spy.pct_change().reindex(rets.index)
# rolling beta per sector, residual returns
resid=pd.DataFrame(index=rets.index,columns=rets.columns,dtype=float)
var=spyr.rolling(252).var()
for c in rets.columns:
    beta=rets[c].rolling(252).cov(spyr)/var
    resid[c]=rets[c]-beta*spyr
raw_mom=px.shift(21)/px.shift(252)-1.0
res_mom=resid.rolling(231).sum().shift(21)  # residual 12-1
for name,sig in [("raw_momentum",raw_mom),("residual_momentum",res_mom)]:
    r=run_cross_sectional(px,sig,rebalance="ME",quantile=0.33,long_short=True,cost_bps_per_side=2.0,min_names=6)
    perm=cross_sectional_permutation_test(px,sig,n_perm=1500,metric="sharpe",rebalance="ME",quantile=0.33,long_short=True,cost_bps_per_side=2.0,min_names=6)
    m=compute_metrics(r["returns"])
    out[f"I0026_{name}"]={"sharpe":m["sharpe"],"cagr_pct":float(m["cagr"]*100),"perm_p":perm["p_value"]}
    print(f"I0026 {name}: net Sharpe {m['sharpe']:+.2f}, perm p={perm['p_value']:.3f}")
# ---- I0030 crypto weekend ----
btc=pd.read_parquet("data/cache/crypto/binance_BTC_USDT_1h.parquet")
btc.index=pd.to_datetime(btc.index)
hr=btc["Close"].pct_change()
day=pd.Series(btc.index.dayofweek,index=btc.index)
wknd=day>=5
vol_wknd=hr[wknd].std()*np.sqrt(24*365); vol_wk=hr[~wknd].std()*np.sqrt(24*365)
out["I0030_weekend_vol"]={"weekend_ann_vol":float(vol_wknd),"weekday_ann_vol":float(vol_wk),"ratio":float(vol_wknd/vol_wk)}
print(f"I0030 BTC weekend vol {vol_wknd:.2f} vs weekday {vol_wk:.2f} (ratio {vol_wknd/vol_wk:.2f})")
Path("strategies/0089_misc_medium/results/metrics.json").write_text(json.dumps(out,indent=1,default=str))
