"""Strategy 0088 — COT positioning cross-section (I0041 HP, I0042 spec-reversal, I0043 momentum).

Quick kill-screen of the three COT-positioning ideas from the handoff (#s05), using
the existing 0057 infra (cot_data hedging-pressure + roll-adjusted commodity panels).
0057 already found the commodity cross-section dead post-2015 under CPCV; these are
single-feature versions, so the prior is reject — confirmed with a permutation L/S.
"""
import sys, json; sys.path.insert(0,'src'); from pathlib import Path
import numpy as np, pandas as pd
import quantlab.commodity_features as cf
from quantlab.cot_data import get_cot_panel, cot_daily_panel, COT_CODES
from quantlab.cross_sectional import run_cross_sectional, cross_sectional_permutation_test
from quantlab.metrics import compute_metrics
roots=list(COT_CODES.keys())
pp=cf.price_panels(); close=pp["front_adj"]; days=close.index; roots=list(close.columns)
cot=get_cot_panel(roots)
hp=cot_daily_panel(cot,days,"hedging_pressure").reindex(close.index).ffill()
ncl=cot_daily_panel(cot,days,"noncomm_long").reindex(close.index).ffill()
ncs=cot_daily_panel(cot,days,"noncomm_short").reindex(close.index).ffill()
oi=cot_daily_panel(cot,days,"open_interest").reindex(close.index).ffill()
net_spec=(ncl-ncs)/oi
def z(p): return (p-p.rolling(252,min_periods=126).mean())/p.rolling(252,min_periods=126).std()
signals={"I0041_HP": hp, "I0042_spec_reversal": -z(net_spec), "I0043_cot_momentum": net_spec.diff(4)}
out={}
for name,sig in signals.items():
    sig=sig.where(close.notna())
    res=run_cross_sectional(close,sig,rebalance="ME",quantile=0.33,long_short=True,cost_bps_per_side=4.0,min_names=6)
    perm=cross_sectional_permutation_test(close,sig,n_perm=1000,metric="sharpe",rebalance="ME",quantile=0.33,long_short=True,cost_bps_per_side=4.0,min_names=6)
    m=compute_metrics(res["returns"])
    out[name]={"sharpe":m["sharpe"],"cagr_pct":float(m["cagr"]*100),"perm_p":perm["p_value"]}
    print(f"{name}: net Sharpe {m['sharpe']:+.2f}, CAGR {m['cagr']*100:+.1f}%, perm p={perm['p_value']:.3f}")
Path("strategies/0088_cot_positioning/results/metrics.json").write_text(json.dumps(out,indent=1,default=str))
