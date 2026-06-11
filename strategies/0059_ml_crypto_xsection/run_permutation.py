"""0059 Permutation: Label-Shuffle (innerhalb jedes Datums) + Komplett-Retrain.

Die ehrliche Null (0057-Lehre): nicht die fertigen Prediction-Ränge shuffeln
(kosten-verseuchte Null), sondern die TRAININGS-Labels innerhalb jedes Datums
permutieren und die gesamte Pipeline (28 CPCV-Fits -> Stitch -> finale
Hebel-Variante -> Kosten) neu durchlaufen. Das testet: "Hat die Pipeline
etwas Echtes gelernt, oder fittet sie Rauschen mit gleicher Kapazität?"

Wichtig bei der Interpretation: auch diese Null ZAHLT volle Kosten — das
Null-MITTEL wird mitberichtet (stark negatives Mittel = die p-Aussage ist
nur "besser als kostenzahlender Zufall"). Der komplementäre Test "Edge > 0"
ist der Bootstrap-KI der Hedge-Returns in run.py.

Statistik: netto Hedge-vs-Markt-Sharpe der final selektierten Variante.
p = Anteil der Permutationen >= beobachtet.

Aufruf: run_permutation.py [n_perm]  (Default 50; ~1-2 h CPU)
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message="X does not have valid feature names")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx
from quantlab.cpcv import make_cpcv_splits, stitch_oos_predictions

from run import (  # noqa: E402 — 0059's own pre-registered pieces
    ANN, LEVER_HORIZON, LEVERS, MIN_NAMES, TOP_N,
    ann_sharpe, lever_portfolio, make_lgbm,
)

RESULTS = Path(__file__).resolve().parent / "results"


def stitched_from_labels(df, splits, params, y_col):
    feature_cols = [c for c in df.columns if c not in ("y", "fwd_ret", "y_perm")]
    dates = df.index.get_level_values("date")
    preds = []
    for sp in splits:
        tr = df[dates.isin(sp["train"])]
        te = df[dates.isin(sp["test"])]
        model = make_lgbm(**params)
        model.fit(tr[feature_cols].values, tr[y_col].values)
        preds.append(
            pd.Series(model.predict(te[feature_cols].values), index=te.index)
            .unstack("pair")
        )
    return stitch_oos_predictions(splits, preds)


def main() -> None:
    n_perm = int(sys.argv[1]) if len(sys.argv) > 1 else 50

    with open(RESULTS / "metrics.json", encoding="utf-8") as f:
        metrics = json.load(f)
    final = metrics["final"]
    lever = {
        k: (None if final["lever"][k] == 0 and k == "liq_floor" else final["lever"][k])
        for k in ("rebalance", "quantile", "buffer_mult", "liq_floor")
    }
    h = LEVER_HORIZON
    best = metrics["gate_a"][f"h{h}"]["best_lgbm"]
    params = best["params"]
    observed = final["lever"]["sharpe_net_vs_market"]
    print(f"Permutation auf {final['name']}: lever={lever}, params={params}, "
          f"beobachtet vs Markt {observed:+.3f}, n_perm={n_perm}")

    uni = cx.build_universe(top_n=TOP_N)
    panels = cx.get_price_panels(uni)
    fp = cf.build_feature_panels(panels)
    ret, vol30 = fp["returns"], fp["vol30"]
    costs = cf.cost_panel(fp["dvol_med21"])
    dvol_med21 = fp["dvol_med21"]
    mkt = fp["market"]

    df = cf.assemble_design_matrix(fp, horizon=h, min_names=MIN_NAMES)
    dm_dates = df.index.get_level_values("date").unique().sort_values()
    splits = make_cpcv_splits(
        dm_dates, n_groups=8, n_test_groups=2, purge_days=h + 7, embargo_frac=0.01
    )

    rng = np.random.default_rng(42)
    null_sharpes = []
    t0 = time.time()
    for i in range(n_perm):
        # shuffle the label across names WITHIN each date
        df = df.copy()
        df["y_perm"] = (
            df.groupby(level="date")["y"]
            .transform(lambda s: rng.permutation(s.values))
        )
        stitched = stitched_from_labels(df, splits, params, "y_perm")
        port = lever_portfolio(stitched, ret, vol30, costs, dvol_med21, lever)
        net = port["returns"]
        active = port["weights"].abs().sum(axis=1) > 0
        hedged = (net[active] - mkt.reindex(net[active].index)).dropna()
        null_sharpes.append(ann_sharpe(hedged))
        if (i + 1) % 5 == 0:
            el = time.time() - t0
            print(f"  perm {i + 1}/{n_perm} (Ø {el / (i + 1):.0f}s) "
                  f"null so far: mean {np.nanmean(null_sharpes):+.2f}", flush=True)

    null_arr = np.array(null_sharpes, dtype=float)
    p = float(np.mean(null_arr >= observed))
    out = {
        "observed_sharpe_vs_market": observed,
        "n_perm": n_perm,
        "p_value": p,
        "null_mean": float(np.nanmean(null_arr)),
        "null_std": float(np.nanstd(null_arr)),
        "null_sharpes": [round(float(x), 4) for x in null_arr],
    }
    with open(RESULTS / "permutation.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nLabel-Retrain-Permutation: p={p:.4f} "
          f"(Null mean {out['null_mean']:+.3f} ± {out['null_std']:.3f})")
    print(f"Gespeichert: {RESULTS / 'permutation.json'}")


if __name__ == "__main__":
    main()
