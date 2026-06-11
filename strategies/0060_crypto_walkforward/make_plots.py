"""Plot for 0060: walk-forward equity + alpha curves (base vs min_k=12)."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx

from run import TOP_N

R = Path(__file__).resolve().parent / "results"

uni = cx.build_universe(top_n=TOP_N)
panels = cx.get_price_panels(uni)
fp = cf.build_feature_panels(panels)
mkt = fp["market"]
btc = fp["returns"]["BTCUSDT"]

base = pd.read_parquet(R / "wf_returns_lgbm.parquet")["net"]
mink = pd.read_parquet(R / "wf_returns_lgbm_mink12.parquet")["net"]
start = base.ne(0).idxmax()

fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                         gridspec_kw={"height_ratios": [2, 1]})
for s, label, lw in [
    (mink.loc[start:], "Walk-Forward min-Buch-12 (PRIMÄR, netto)", 2.0),
    (base.loc[start:], "Walk-Forward 0059-Original (8-Namen-Buch, netto)", 1.4),
    (mkt.loc[start:], "Markt (cap-weighted)", 1.0),
    (btc.loc[start:], "BTC B&H", 1.0),
]:
    seg = s.fillna(0.0)
    axes[0].plot(seg.index, (1 + seg).cumprod(), label=label, linewidth=lw)
axes[0].set_yscale("log")
axes[0].set_title("0060 — echter Walk-Forward der eingefrorenen Regel (monatl. Refit, expanding)")
axes[0].legend()
axes[0].grid(alpha=0.3)

for s, label in [(mink, "min-Buch-12"), (base, "0059-Original")]:
    seg = s.loc[start:]
    hedged = (seg - mkt.reindex(seg.index)).dropna()
    axes[1].plot(hedged.index, hedged.cumsum(), label=label)
axes[1].axhline(0, color="k", lw=0.8)
axes[1].set_title("kumulierte Hedge-Differenz vs Markt (additiv)")
axes[1].legend()
axes[1].grid(alpha=0.3)
fig.tight_layout()
fig.savefig(R / "walkforward_equity_alpha.png", dpi=130)
print("saved:", R / "walkforward_equity_alpha.png")
