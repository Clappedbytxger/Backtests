"""Plots for the 0057 report from saved config returns."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import plotting

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

m = pd.read_parquet(RESULTS / "config_returns.parquet")
winner = m["lgbm_g7_h63"]
ridge = m["ridge_a0.1_h21"]

eq_w = (1 + winner.fillna(0)).cumprod()
eq_r = (1 + ridge.fillna(0)).cumprod()

fig = plotting.plot_equity(
    eq_w, benchmark=eq_r,
    strategy_label="LightGBM h63 (bester GBT)",
    benchmark_label="Ridge h21 (bester linear)",
    title="0057 — ML Commodity Cross-Section (CPCV-OOS, netto)",
    caption="Gestitchte CPCV-OOS-Pfade, Quintil-L/S, inverse-Vol-Legs, "
            "Wochen-Rebalancing, 6 bps/Seite. Beide Modellfamilien unter "
            "identischen 28 purged Splits.",
)
fig.axes[0].axvline(pd.Timestamp("2015-01-01"), color="gray", linestyle="--", linewidth=1)
plotting.savefig(fig, RESULTS / "equity.png")
plotting.savefig(plotting.plot_drawdown(winner), RESULTS / "drawdown.png")

# Sharpe aller Konfigurationen als Balken (Selektion-Landschaft).
import matplotlib.pyplot as plt
import numpy as np

sharpes = {}
for c in m.columns:
    r = m[c].dropna()
    r = r[r != 0]
    sharpes[c] = r.mean() / r.std() * np.sqrt(252) if len(r) > 40 else float("nan")
s = pd.Series(sharpes).sort_values()
fig2, ax = plt.subplots(figsize=(10, 8))
colors = ["#2c7fb8" if c.startswith("lgbm") else
          "#de2d26" if c.startswith("ridge") else "#756bb1" for c in s.index]
ax.barh(range(len(s)), s.values, color=colors)
ax.set_yticks(range(len(s)))
ax.set_yticklabels(s.index, fontsize=7)
ax.axvline(0, color="black", linewidth=0.8)
ax.set_xlabel("Netto-Sharpe (gestitchte CPCV-OOS)")
ax.set_title("0057 — alle 36 Konfigurationen (blau=LGBM, rot=Ridge, lila=Ens/MLP)")
fig2.tight_layout()
plotting.savefig(fig2, RESULTS / "config_sharpes.png")
print("plots saved")
