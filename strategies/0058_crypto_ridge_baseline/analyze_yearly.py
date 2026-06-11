"""Post-run analysis: IC stability over time + fair selection benchmarks."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import pandas as pd
from quantlab import crypto_xsection as cx
from quantlab import crypto_features as cf

R = ROOT / "strategies" / "0058_crypto_ridge_baseline" / "results"
ANN = 365

uni = cx.build_universe(top_n=150)
panels = cx.get_price_panels(uni)
fp = cf.build_feature_panels(panels)
ret, memb = fp["returns"], panels["membership_daily"]
ew = ret.where(memb.shift(1)).mean(axis=1)
mkt = fp["market"]


def ann_sharpe(r):
    r = r.dropna()
    return float(r.mean() / r.std() * np.sqrt(ANN)) if len(r) > 60 and r.std() > 0 else np.nan


print("=== IC per year (Spearman, stitched OOS) ===")
for h in (7, 28):
    pred = pd.read_parquet(f"{R}/ridge_predictions_h{h}.parquet")
    fwd = fp["targets_raw"][h]
    ics = {}
    for t in pred.index.intersection(fwd.index):
        p = pred.loc[t].dropna()
        f = fwd.loc[t].reindex(p.index).dropna()
        if len(f) >= 20:
            ics[t] = p.reindex(f.index).corr(f, method="spearman")
    ics = pd.Series(ics).dropna()
    byyear = ics.groupby(ics.index.year).agg(["mean", "count"])
    print(f"\nh={h}:")
    print(byyear.round(3).to_string())

print("\n=== Long-only vs equal-weight pool (selection skill) ===")
for h in (7, 14, 28):
    lo = pd.read_parquet(f"{R}/returns_h{h}_long_only.parquet")["net"]
    active = lo.index[lo.ne(0) | (lo.index > lo.ne(0).idxmax())]
    lo = lo.loc[active[0]:]
    diff_ew = (lo - ew.reindex(lo.index)).dropna()
    diff_mkt = (lo - mkt.reindex(lo.index)).dropna()
    yr = diff_ew.groupby(diff_ew.index.year).apply(ann_sharpe)
    print(f"h={h}: vs EW Sharpe {ann_sharpe(diff_ew):+.2f} | vs Mkt {ann_sharpe(diff_mkt):+.2f} "
          f"| vs EW per year: " + " ".join(f"{y}:{v:+.1f}" for y, v in yr.items()))

print("\n=== L/S gross/net per year (h=28) ===")
ls = pd.read_parquet(f"{R}/returns_h28_long_short.parquet")
for col in ("gross", "net"):
    s = ls[col]
    yr = s.groupby(s.index.year).apply(ann_sharpe)
    print(f"{col:5s}: " + " ".join(f"{y}:{v:+.1f}" for y, v in yr.items()))
