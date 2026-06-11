"""Plots for 0059: Gate-A split ICs, final equity vs benchmarks, alpha curve."""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx

from run import LEVER_HORIZON, TOP_N, lever_portfolio

R = Path(__file__).resolve().parent / "results"
with open(R / "metrics.json", encoding="utf-8") as f:
    m = json.load(f)

# ── 1. Gate A: per-split IC, LGBM0 vs Ridge, 3 Horizonte ────────────────────
fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
for ax, h in zip(axes, (7, 14, 28)):
    g = m["gate_a"][f"h{h}"]
    ridge = np.array(g["ridge_split_ics"], dtype=float)
    best = g["best_lgbm"]["grid_index"]
    # split ICs of best config are not stored per split in metrics.json for
    # lgbm; approximate via win_frac annotation, plot ridge vs stitched bars
    ax.axhline(g["ridge_ic_stitched"], color="crimson", ls="--",
               label=f"Ridge stitched ({g['ridge_ic_stitched']:+.3f})")
    ics = [row["ic_stitched"] for row in g["lgbm_grid"]]
    ax.bar(range(len(ics)), ics, color=["#3b6ea5" if i != best else "#1f4e79"
                                        for i in range(len(ics))])
    ax.set_title(f"h={h}d — LGBM-Gitter vs Ridge\n"
                 f"best schlägt Ridge in {g['best_lgbm']['win_frac']:.0%} der Splits")
    ax.set_xlabel("LGBM-Konfig")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")
fig.tight_layout()
fig.savefig(R / "gate_a_ic.png", dpi=130)

# ── 2. Finale Variante: Equity + Alpha-Kurve ────────────────────────────────
final = m["final"]
lever = {k: (None if final["lever"]["liq_floor"] == 0 and k == "liq_floor"
             else final["lever"][k])
         for k in ("rebalance", "quantile", "buffer_mult", "liq_floor")}

uni = cx.build_universe(top_n=TOP_N)
panels = cx.get_price_panels(uni)
fp = cf.build_feature_panels(panels)
ret, vol30 = fp["returns"], fp["vol30"]
costs = cf.cost_panel(fp["dvol_med21"])
mkt = fp["market"]
btc = ret["BTCUSDT"]

stitched = pd.read_parquet(R / f"lgbm_best_predictions_h{LEVER_HORIZON}.parquet")
port = lever_portfolio(stitched, ret, vol30, costs, fp["dvol_med21"], lever)
net = port["returns"]
active = port["weights"].abs().sum(axis=1) > 0
net_a = net[active]
start = net_a.index[0]

fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                         gridspec_kw={"height_ratios": [2, 1]})
for s, label, lw in [
    (net_a, f"0059 final ({final['name']}, netto)", 2.0),
    (mkt.loc[start:], "Markt (cap-weighted)", 1.2),
    (btc.loc[start:], "BTC B&H", 1.2),
]:
    seg = s.fillna(0.0)
    axes[0].plot(seg.index, (1 + seg).cumprod(), label=label, linewidth=lw)
axes[0].set_yscale("log")
axes[0].set_title("0059 — LGBM h28, ME-Dezil, Buffer 2x, Liq>=5M (CPCV-OOS, netto)")
axes[0].legend()
axes[0].grid(alpha=0.3)

hedged = (net_a - mkt.reindex(net_a.index)).dropna()
axes[1].plot(hedged.index, hedged.cumsum(), color="#1f4e79")
axes[1].axhline(0, color="k", lw=0.8)
axes[1].set_title("kumulierte Hedge-Differenz vs Markt (Alpha-Kurve, additiv)")
axes[1].grid(alpha=0.3)
fig.tight_layout()
fig.savefig(R / "final_equity_alpha.png", dpi=130)
print("saved:", R / "gate_a_ic.png", "+", R / "final_equity_alpha.png")
