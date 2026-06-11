"""0061 Walk-Forward-Check der Gate-bestandenen Variante (funding_tvl).

Identisches 0060-Protokoll (monatlicher Refit, expanding, Label-Lag 28d,
erster Fit 2020-12-31, eingefrorene Hebel + min_k=12) — nur die Feature-Menge
ist base+funding+tvl. Vergleich gegen den 0060-Basis-Pfad (vs Markt +0.64).
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message="X does not have valid feature names")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "strategies" / "0060_crypto_walkforward"))

from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx
from quantlab.significance import bootstrap_ci, t_test_mean_return

from run import (  # 0060 protocol — single source of truth
    HORIZON, MIN_NAMES, TOP_N, ann_sharpe, frozen_portfolio, make_lgbm,
    walk_forward_predictions,
)

RESULTS = Path(__file__).resolve().parent / "results"


def main() -> None:
    uni = cx.build_universe(top_n=TOP_N)
    panels = cx.get_price_panels(uni)
    fp = cf.build_feature_panels(panels)
    p4 = cf.phase4_features(panels)
    ret, vol30 = fp["returns"], fp["vol30"]
    costs = cf.cost_panel(fp["dvol_med21"])
    dvol = fp["dvol_med21"]
    mkt = fp["market"]

    out = {}
    for name, extra in [("base", None), ("funding_tvl", p4)]:
        df = cf.assemble_design_matrix(
            fp, horizon=HORIZON, min_names=MIN_NAMES, extra_features=extra
        )
        df_score = cf.assemble_design_matrix(
            fp, horizon=HORIZON, min_names=MIN_NAMES, require_target=False,
            extra_features=extra,
        )
        preds = walk_forward_predictions(df, make_lgbm, fillna_zero=False, score_df=df_score)
        port = frozen_portfolio(preds, ret, vol30, costs, dvol, min_k=12)
        net = port["returns"]
        active = port["weights"].abs().sum(axis=1) > 0
        net_a = net[active]
        hedged = (net_a - mkt.reindex(net_a.index)).dropna()
        boot = bootstrap_ci(hedged, statistic="sharpe")
        yr = hedged.groupby(hedged.index.year).apply(ann_sharpe)
        out[name] = {
            "sharpe_net": round(ann_sharpe(net_a), 3),
            "sharpe_vs_market": round(ann_sharpe(hedged), 3),
            "bootstrap_ci": [round(boot["ci_low"], 3), round(boot["ci_high"], 3)],
            "t_p": round(t_test_mean_return(hedged)["p_value"], 4),
            "by_year": {int(y): round(v, 2) for y, v in yr.items()},
        }
        print(f"  {name:12s}: net {out[name]['sharpe_net']:+.2f}, "
              f"vs Markt {out[name]['sharpe_vs_market']:+.2f} "
              f"KI [{boot['ci_low']:+.2f},{boot['ci_high']:+.2f}], "
              f"je Jahr " + " ".join(f"{y}:{v:+.1f}" for y, v in yr.items()))

    with open(RESULTS / "walkforward_check.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Gespeichert: {RESULTS / 'walkforward_check.json'}")


if __name__ == "__main__":
    main()
