"""Final-variant deep dive: yearly hedged returns, EW-hedge, coverage, plateau."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx

from run import ANN, LEVER_HORIZON, MIN_NAMES, TOP_N, ann_sharpe, lever_portfolio

R = Path(__file__).resolve().parent / "results"

with open(R / "metrics.json", encoding="utf-8") as f:
    m = json.load(f)
final = m["final"]
lever = {k: (None if final["lever"]["liq_floor"] == 0 and k == "liq_floor"
             else final["lever"][k])
         for k in ("rebalance", "quantile", "buffer_mult", "liq_floor")}
best_gi = m["gate_a"][f"h{LEVER_HORIZON}"]["best_lgbm"]["grid_index"]

uni = cx.build_universe(top_n=TOP_N)
panels = cx.get_price_panels(uni)
fp = cf.build_feature_panels(panels)
ret, vol30 = fp["returns"], fp["vol30"]
costs = cf.cost_panel(fp["dvol_med21"])
dvol = fp["dvol_med21"]
mkt = fp["market"]
memb = panels["membership_daily"]
ew = ret.where(memb.shift(1)).mean(axis=1)

stitched = pd.read_parquet(R / f"lgbm_best_predictions_h{LEVER_HORIZON}.parquet")
port = lever_portfolio(stitched, ret, vol30, costs, dvol, lever)
net = port["returns"]
active = port["weights"].abs().sum(axis=1) > 0
net_a = net[active]

print(f"final {final['name']}: lever={lever}")
print(f"aktiv: {net_a.index[0]:%Y-%m-%d} .. {net_a.index[-1]:%Y-%m-%d} "
      f"({len(net_a)} Tage)")
names_held = (port["weights"] > 0).sum(axis=1)
print(f"Namen im Buch (Median/Min/Max aktiver Tage): "
      f"{names_held[active].median():.0f}/{names_held[active].min()}/{names_held[active].max()}")

for bench, bname in [(mkt, "Markt"), (ew, "EqualWeight"), (ret["BTCUSDT"], "BTC")]:
    hedged = (net_a - bench.reindex(net_a.index)).dropna()
    yr = hedged.groupby(hedged.index.year).apply(ann_sharpe)
    print(f"\nvs {bname}: gesamt {ann_sharpe(hedged):+.2f} | "
          + " ".join(f"{y}:{v:+.1f}" for y, v in yr.items()))

print("\nAbsolute net je Jahr (Sharpe):")
yr = net_a.groupby(net_a.index.year).apply(ann_sharpe)
print(" ".join(f"{y}:{v:+.1f}" for y, v in yr.items()))

print("\nLGBM-Hebel-Plateau (alle 16, sortiert vs Markt):")
rows = sorted(m["levers"][f"lgbm{best_gi}"], key=lambda r: -r["sharpe_net_vs_market"])
for r in rows:
    print(f"  rb={r['rebalance']:2s} q={r['quantile']} buf={r['buffer_mult']} "
          f"liq={int(r['liq_floor']/1e6) if r['liq_floor'] else 0}M: "
          f"net {r['sharpe_net']:+.2f} vsMkt {r['sharpe_net_vs_market']:+.2f} "
          f"TO {r['turnover_oneside_per_year']:.0f}")
