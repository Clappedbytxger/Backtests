"""0061 — Phase 4: Funding-Carry + On-Chain-TVL als INKREMENTELLE Features.

Roadmap-Gate Phase 4: die neuen Quellen müssen inkrementellen Wert ÜBER die
bestehende 0059-Messlatte nachweisen — nicht für sich allein "funktionieren".

Vorab registriertes Design:
- Identische CPCV-Splits wie 0058/0059 (h=28, 8/2, Purge h+7, Embargo 1%);
  identische Zeilenmenge (Phase-4-NaNs droppen keine Zeilen).
- Modell fix: LGBM0 (15 Blätter, lr 0.05, 100 Bäume) — KEIN neues Grid.
- Feature-Sets (2 neue Trials):
    BASE          die 11 0058-Features (Referenz, aus 0059 bekannt)
    +FUNDING      + funding_7, funding_z (Perp-Funding-Carry, Binance fapi —
                  verifiziert inkl. delisteter Perps)
    +FUNDING+TVL  + tvl_chg_28 (DefiLlama Chain-TVL, tote Chains historisch
                  vorhanden, nur L1/L2-Gas-Token, sonst NaN)
- Gate je Set: schlägt BASE im per-Split-IC in >50% der 28 Splits UND
  gestitchter IC höher UND Portfolio (eingefrorene Hebel + min_k=12 aus
  0060) nicht schlechter. Besteht ein Set, folgt der Walk-Forward-Check im
  0060-Protokoll.

Funding-Vorbehalt (dokumentiert): Perps existieren erst ab 2019-09 (BTC)
bzw. 2020-21 (Alts) — frühe Jahre haben NaN-Funding; LightGBM behandelt
NaN nativ, der Vergleich bleibt zeilengleich.
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
from quantlab.cpcv import make_cpcv_splits, stitch_oos_predictions
from quantlab.ml_portfolio import run_buffered_long_portfolio

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

ANN = 365
TOP_N = 150
HORIZON = 28
MIN_NAMES = 20
FROZEN_LGBM = dict(num_leaves=15, learning_rate=0.05, n_estimators=100)
LGBM_FIXED = dict(
    objective="regression", min_child_samples=40, subsample=0.8,
    subsample_freq=1, colsample_bytree=0.8, verbose=-1, n_jobs=-1,
    random_state=7,
)
FROZEN_LEVER = dict(rebalance="ME", quantile=0.1, buffer_mult=2.0, liq_floor=5e6)
MIN_K = 12  # 0060 primary


def ann_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 60 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(ANN))


def make_lgbm():
    from lightgbm import LGBMRegressor

    return LGBMRegressor(**{**LGBM_FIXED, **FROZEN_LGBM})


def per_date_ic(pred_panel: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    ics = {}
    for t in pred_panel.index.intersection(fwd.index):
        p = pred_panel.loc[t].dropna()
        f = fwd.loc[t].reindex(p.index).dropna()
        if len(f) >= MIN_NAMES:
            ics[t] = p.reindex(f.index).corr(f, method="spearman")
    return pd.Series(ics, dtype=float).dropna()


def fit_cpcv(df, splits, fwd):
    feature_cols = [c for c in df.columns if c not in ("y", "fwd_ret")]
    dates = df.index.get_level_values("date")
    preds, split_ics = [], []
    for sp in splits:
        tr = df[dates.isin(sp["train"])]
        te = df[dates.isin(sp["test"])]
        model = make_lgbm()
        model.fit(tr[feature_cols].values, tr["y"].values)
        panel = pd.Series(model.predict(te[feature_cols].values), index=te.index).unstack("pair")
        preds.append(panel)
        split_ics.append(float(per_date_ic(panel, fwd).mean()))
    return stitch_oos_predictions(splits, preds), np.array(split_ics)


def portfolio_stats(stitched, ret, vol30, costs, dvol, mkt) -> dict:
    pred_daily = stitched.reindex(ret.index).where(dvol >= FROZEN_LEVER["liq_floor"])
    port = run_buffered_long_portfolio(
        ret, pred_daily, vol=vol30, rebalance=FROZEN_LEVER["rebalance"],
        quantile=FROZEN_LEVER["quantile"], buffer_mult=FROZEN_LEVER["buffer_mult"],
        cost_bps_per_side=costs, min_names=MIN_NAMES, min_k=MIN_K,
    )
    net = port["returns"]
    active = port["weights"].abs().sum(axis=1) > 0
    net_a = net[active]
    hedged = (net_a - mkt.reindex(net_a.index)).dropna()
    return {
        "sharpe_net": round(ann_sharpe(net_a), 3),
        "sharpe_vs_market": round(ann_sharpe(hedged), 3),
    }


def main() -> None:
    print("=== 0061 Phase 4: Funding + TVL inkrementell (h=28, LGBM0 fix) ===")
    uni = cx.build_universe(top_n=TOP_N)
    panels = cx.get_price_panels(uni)
    fp = cf.build_feature_panels(panels)
    p4 = cf.phase4_features(panels)
    ret, vol30 = fp["returns"], fp["vol30"]
    costs = cf.cost_panel(fp["dvol_med21"])
    dvol = fp["dvol_med21"]
    mkt = fp["market"]
    fwd = fp["targets_raw"][HORIZON]

    cov = {n: float(p.notna().sum(axis=1).max()) for n, p in p4.items()}
    print(f"Phase-4-Coverage (max Namen/Tag): {cov}")

    sets = {
        "base": None,
        "funding": {k: p4[k] for k in ("funding_7", "funding_z")},
        "funding_tvl": p4,
    }
    dfs = {
        name: cf.assemble_design_matrix(
            fp, horizon=HORIZON, min_names=MIN_NAMES, extra_features=extra
        )
        for name, extra in sets.items()
    }
    n_rows = {n: len(d) for n, d in dfs.items()}
    assert len(set(n_rows.values())) == 1, f"Zeilenmengen ungleich: {n_rows}"

    dm_dates = dfs["base"].index.get_level_values("date").unique().sort_values()
    splits = make_cpcv_splits(
        dm_dates, n_groups=8, n_test_groups=2,
        purge_days=HORIZON + 7, embargo_frac=0.01,
    )

    results: dict = {"config": {
        "frozen_lgbm": FROZEN_LGBM, "lever": FROZEN_LEVER, "min_k": MIN_K,
        "n_new_trials": 2,
    }}
    ics = {}
    for name, df in dfs.items():
        stitched, split_ics = fit_cpcv(df, splits, fwd)
        ic_st = float(per_date_ic(stitched, fwd).mean())
        port = portfolio_stats(stitched, ret, vol30, costs, dvol, mkt)
        ics[name] = split_ics
        win = float((split_ics > ics["base"]).mean()) if name != "base" else None
        results[name] = {
            "ic_stitched": round(ic_st, 4),
            "split_ic_mean": round(float(split_ics.mean()), 4),
            "win_frac_vs_base": None if win is None else round(win, 3),
            **port,
        }
        stitched.to_parquet(RESULTS / f"predictions_{name}.parquet")
        msg = (f"  {name:12s}: IC {ic_st:+.4f}, LO net {port['sharpe_net']:+.2f}, "
               f"vs Mkt {port['sharpe_vs_market']:+.2f}")
        if win is not None:
            msg += f", schlägt BASE in {win:.0%} der Splits"
        print(msg)

    for name in ("funding", "funding_tvl"):
        r = results[name]
        gate = (
            r["win_frac_vs_base"] > 0.5
            and r["ic_stitched"] > results["base"]["ic_stitched"]
            and r["sharpe_vs_market"] >= results["base"]["sharpe_vs_market"] - 0.05
        )
        results[name]["gate_pass"] = bool(gate)
        print(f"  >> Gate {name}: {'PASS' if gate else 'FAIL'}")

    with open(RESULTS / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nGespeichert: {RESULTS / 'metrics.json'}")


if __name__ == "__main__":
    main()
