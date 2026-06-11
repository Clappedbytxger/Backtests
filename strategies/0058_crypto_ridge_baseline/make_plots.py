"""Plots for 0058: equity vs benchmarks (log) + OOS-IC stability by year."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx

R = Path(__file__).resolve().parent / "results"

uni = cx.build_universe(top_n=150)
panels = cx.get_price_panels(uni)
fp = cf.build_feature_panels(panels)
ret, memb = fp["returns"], panels["membership_daily"]
ew = ret.where(memb.shift(1)).mean(axis=1)
mkt = fp["market"]
btc = ret["BTCUSDT"]

lo = pd.read_parquet(R / "returns_h28_long_only.parquet")["net"]
start = lo.ne(0).idxmax()

fig, ax = plt.subplots(figsize=(11, 6))
for s, label, lw in [
    (lo, "Ridge h28 long-only Top-Quintil (netto)", 2.0),
    (mkt, "Markt (cap-weighted PIT-Universum)", 1.2),
    (ew, "Equal-Weight-Universum", 1.2),
    (btc, "BTC Buy&Hold", 1.2),
]:
    seg = s.loc[start:].fillna(0.0)
    ax.plot(seg.index, (1 + seg).cumprod(), label=label, linewidth=lw)
ax.set_yscale("log")
ax.set_title("0058 — Ridge-Benchmark Crypto-Cross-Section (CPCV-OOS, netto, ab 2019-02)")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(R / "equity_vs_benchmarks.png", dpi=130)

# IC by year
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, h in zip(axes, (7, 28)):
    pred = pd.read_parquet(R / f"ridge_predictions_h{h}.parquet")
    fwd = fp["targets_raw"][h]
    ics = {}
    for t in pred.index.intersection(fwd.index):
        p = pred.loc[t].dropna()
        f = fwd.loc[t].reindex(p.index).dropna()
        if len(f) >= 20:
            ics[t] = p.reindex(f.index).corr(f, method="spearman")
    ics = pd.Series(ics).dropna()
    byyear = ics.groupby(ics.index.year).mean()
    ax.bar(byyear.index.astype(str), byyear.values, color="#3b6ea5")
    ax.axhline(0, color="k", linewidth=0.8)
    ax.set_title(f"OOS-IC je Jahr (h={h}d)")
    ax.grid(alpha=0.3, axis="y")
fig.tight_layout()
fig.savefig(R / "ic_by_year.png", dpi=130)
print("saved:", R / "equity_vs_benchmarks.png", "+", R / "ic_by_year.png")
