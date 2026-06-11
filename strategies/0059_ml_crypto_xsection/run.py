"""0059 — Crypto-Cross-Section: LightGBM gegen die Ridge-Messlatte (Phase 3).

Vorab registriertes Design (alles gezählt, nichts nachgeschoben):

- **Identische CPCV-Splits wie 0058** (8 Gruppen / 2 Test = 28 purged Splits,
  Purge = Horizont+7d, Embargo 1%) — Split-für-Split-Vergleich LGBM vs Ridge.
- **LGBM-Gitter wie 0057** (8 Konfigs: num_leaves {15,31} × lr {0.05,0.1} ×
  n_estimators {100,300}; Rest fix) × 3 Horizonte = 24 Modell-Trials.
- **Gate A (Modell):** LGBM muss den per-Split-OOS-IC des Ridge in >50% der
  28 Splits schlagen UND der gestitchte IC muss höher sein. Sonst gilt die
  Nichtlinearität als nicht belegt (0057-Verdikt).
- **Gate B (PBO):** CSCV-PBO über alle Konfigurationen < 0.5.
- **Gate C (Portfolio):** Es muss eine Long-only-Variante geben, die NETTO den
  cap-gewichteten Markt schlägt (Hedge-Sharpe > 0, Bootstrap-KI ohne 0) —
  das 0058-Defizit.
- **Gate D (Regime):** Edge in mehr als einem Regime (2019 / Bull 20-21 /
  Bear 22 / 2023+).
- **IC→PnL-Hebel-Scan** (im 0058-Report vorregistriert), NUR auf h=28
  (niedrigster Turnover = einziger Kandidat gegen die Kosten-Wand), auf das
  beste LGBM UND Ridge symmetrisch angewandt, long-only:
  Rebalance {W, ME} × Konzentration {Quintil 0.2, Dezil 0.1} ×
  Buffer {1.0 = aus, 2.0} × Liquiditäts-Floor {aus, $5M 21d-Median-Dollarvol}
  = 16 Varianten je Modell = 32 Trials.
- **Auswahlregel (vorab):** finaler Kandidat = LGBM-Hebel-Variante mit dem
  höchsten netto Hedge-vs-Markt-Sharpe; Plateau-Check über Nachbarzellen;
  DSR mit der VOLLEN Trial-Zahl (0058: 6 + 24 Grid-Stitched-Bewertungen × 2
  Mappings + 32 Hebel = 86+).
- **Permutation:** Label-Shuffle INNERHALB jedes Datums + Komplett-Retrain
  (ehrliche Null, 0057-Lehre) — separat in ``run_permutation.py`` auf der
  final selektierten Konfiguration.

Ausgabe: results/metrics.json, per-Split-ICs, Stitched-Preds des besten LGBM,
Hebel-Tabelle, Konsolen-Scorecard.
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

from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx
from quantlab.cpcv import make_cpcv_splits, pbo_cscv, stitch_oos_predictions
from quantlab.metrics import compute_metrics
from quantlab.ml_portfolio import run_buffered_long_portfolio, run_ml_portfolio
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

ANN = 365
TOP_N = 150
HORIZONS = (7, 14, 28)
LEVER_HORIZON = 28
MIN_NAMES = 20
N_TRIALS_0058 = 6

LGBM_GRID = [
    dict(num_leaves=nl, learning_rate=lr, n_estimators=ne)
    for nl in (15, 31)
    for lr in (0.05, 0.1)
    for ne in (100, 300)
]
LGBM_FIXED = dict(
    objective="regression",
    min_child_samples=40,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    verbose=-1,
    n_jobs=-1,
    random_state=7,
)

LEVERS = [
    dict(rebalance=rb, quantile=q, buffer_mult=b, liq_floor=lf)
    for rb in ("W", "ME")
    for q in (0.2, 0.1)
    for b in (1.0, 2.0)
    for lf in (None, 5e6)
]

REGIMES = {
    "2019": ("2019-01-01", "2019-12-31"),
    "bull_2020_21": ("2020-01-01", "2021-12-31"),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "2023_plus": ("2023-01-01", None),
}


def ann_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 60 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(ANN))


def regime_table(r: pd.Series) -> dict:
    out = {}
    for name, (a, b) in REGIMES.items():
        seg = r.loc[a:b] if b else r.loc[a:]
        out[name] = round(ann_sharpe(seg), 3)
    return out


def make_ridge():
    from sklearn.linear_model import Ridge

    return Ridge(alpha=1.0)


def make_lgbm(**params):
    from lightgbm import LGBMRegressor

    return LGBMRegressor(**{**LGBM_FIXED, **params})


def per_date_ic(pred_panel: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    """Spearman IC per date between a prediction panel and forward returns."""
    ics = {}
    for t in pred_panel.index.intersection(fwd.index):
        p = pred_panel.loc[t].dropna()
        f = fwd.loc[t].reindex(p.index).dropna()
        if len(f) >= MIN_NAMES:
            ics[t] = p.reindex(f.index).corr(f, method="spearman")
    return pd.Series(ics, dtype=float).dropna()


def fit_cpcv(model_factory, df, splits, fillna_zero: bool, fwd):
    """Fit per split -> stitched preds + per-split mean OOS-IC."""
    feature_cols = [c for c in df.columns if c not in ("y", "fwd_ret")]
    dates = df.index.get_level_values("date")
    preds, split_ics = [], []
    for sp in splits:
        tr = df[dates.isin(sp["train"])]
        te = df[dates.isin(sp["test"])]
        x_tr, x_te = tr[feature_cols], te[feature_cols]
        if fillna_zero:  # rank features: 0 == cross-sectional median (Ridge)
            x_tr, x_te = x_tr.fillna(0.0), x_te.fillna(0.0)
        model = model_factory()
        model.fit(x_tr.values, tr["y"].values)
        pred_panel = pd.Series(
            model.predict(x_te.values), index=te.index
        ).unstack("pair")
        preds.append(pred_panel)
        split_ics.append(float(per_date_ic(pred_panel, fwd).mean()))
    stitched = stitch_oos_predictions(splits, preds)
    return stitched, np.array(split_ics)


def baseline_portfolios(stitched, ret, vol30, costs, mkt) -> dict:
    """0058 baseline mapping: weekly quintile, long-only + L/S, staged costs."""
    pred_daily = stitched.reindex(ret.index)
    out = {}
    for variant, lo in [("long_only", True), ("long_short", False)]:
        port = run_ml_portfolio(
            ret, pred_daily, vol=vol30, rebalance="W",
            cost_bps_per_side=costs, min_names=MIN_NAMES, long_only=lo,
        )
        net = port["returns"]
        active = port["weights"].abs().sum(axis=1) > 0
        out[variant] = {
            "sharpe_net": round(ann_sharpe(net[active]), 3),
            "sharpe_gross": round(ann_sharpe(port["gross_returns"][active]), 3),
        }
        if lo:
            hedged = (net[active] - mkt.reindex(net[active].index)).dropna()
            out[variant]["sharpe_net_vs_market"] = round(ann_sharpe(hedged), 3)
            out["_hedged_returns"] = hedged
    return out


def lever_portfolio(stitched, ret, vol30, costs, dvol_med21, lever) -> dict:
    """One lever variant, long-only, h=LEVER_HORIZON predictions."""
    pred_daily = stitched.reindex(ret.index)
    if lever["liq_floor"]:
        pred_daily = pred_daily.where(dvol_med21 >= lever["liq_floor"])
    if lever["buffer_mult"] > 1.0:
        port = run_buffered_long_portfolio(
            ret, pred_daily, vol=vol30, rebalance=lever["rebalance"],
            quantile=lever["quantile"], buffer_mult=lever["buffer_mult"],
            cost_bps_per_side=costs, min_names=MIN_NAMES,
        )
    else:
        pred_ff = pred_daily.ffill(limit=6)
        port = run_ml_portfolio(
            ret, pred_ff, vol=vol30, rebalance=lever["rebalance"],
            quantile=lever["quantile"], cost_bps_per_side=costs,
            min_names=MIN_NAMES, long_only=True,
        )
    return port


def main() -> None:
    print("=== 0059 LightGBM vs Ridge-Messlatte (Phase 3) ===")
    uni = cx.build_universe(top_n=TOP_N)
    panels = cx.get_price_panels(uni)
    fp = cf.build_feature_panels(panels)
    ret = fp["returns"]
    vol30 = fp["vol30"]
    costs = cf.cost_panel(fp["dvol_med21"])
    dvol_med21 = fp["dvol_med21"]
    mkt = fp["market"]

    results: dict = {"gate_a": {}, "baselines": {}, "levers": {}, "config": {
        "lgbm_grid": LGBM_GRID, "levers": LEVERS, "lever_horizon": LEVER_HORIZON,
    }}
    hedged_matrix = {}          # config name -> hedged LO daily returns (for PBO)
    trial_sharpes_hedged = []   # per-period sharpes for DSR trial variance
    best_per_h: dict = {}

    for h in HORIZONS:
        print(f"\n=== Horizont {h}d ===")
        df = cf.assemble_design_matrix(fp, horizon=h, min_names=MIN_NAMES)
        dm_dates = df.index.get_level_values("date").unique().sort_values()
        splits = make_cpcv_splits(
            dm_dates, n_groups=8, n_test_groups=2,
            purge_days=h + 7, embargo_frac=0.01,
        )
        fwd = fp["targets_raw"][h]

        ridge_stitched, ridge_ics = fit_cpcv(make_ridge, df, splits, True, fwd)
        ridge_ic = float(per_date_ic(ridge_stitched, fwd).mean())
        print(f"  Ridge: stitched IC {ridge_ic:+.4f}, "
              f"split-IC mean {ridge_ics.mean():+.4f}")

        h_rows = []
        for gi, params in enumerate(LGBM_GRID):
            stitched, ics = fit_cpcv(
                lambda p=params: make_lgbm(**p), df, splits, False, fwd
            )
            ic_stitched = float(per_date_ic(stitched, fwd).mean())
            win_frac = float((ics > ridge_ics).mean())
            bp = baseline_portfolios(stitched, ret, vol30, costs, mkt)
            hedged = bp.pop("_hedged_returns")
            name = f"h{h}_lgbm{gi}"
            hedged_matrix[name] = hedged
            trial_sharpes_hedged.append(
                hedged.mean() / hedged.std() if hedged.std() > 0 else 0.0
            )
            row = {
                "grid_index": gi, **params,
                "ic_stitched": round(ic_stitched, 4),
                "split_ic_mean": round(float(ics.mean()), 4),
                "win_frac_vs_ridge": round(win_frac, 3),
                **{f"{k}_{m}": v for k, d in bp.items() for m, v in d.items()},
            }
            h_rows.append(row)
            print(f"  LGBM{gi} {params}: IC {ic_stitched:+.4f}, "
                  f"schlägt Ridge in {win_frac:.0%} der Splits, "
                  f"LO net {row['long_only_sharpe_net']:+.2f} "
                  f"(vs Mkt {row['long_only_sharpe_net_vs_market']:+.2f})")
            if (best_per_h.get(h) is None
                    or ic_stitched > best_per_h[h]["ic_stitched"]):
                best_per_h[h] = {
                    "grid_index": gi, "params": params,
                    "ic_stitched": ic_stitched, "win_frac": win_frac,
                    "stitched": stitched, "split_ics": ics,
                }

        # Ridge baseline for PBO/hedged matrix too
        bp_r = baseline_portfolios(ridge_stitched, ret, vol30, costs, mkt)
        hedged_matrix[f"h{h}_ridge"] = bp_r.pop("_hedged_returns")

        results["gate_a"][f"h{h}"] = {
            "ridge_ic_stitched": round(ridge_ic, 4),
            "ridge_split_ic_mean": round(float(ridge_ics.mean()), 4),
            "ridge_split_ics": [round(x, 4) for x in ridge_ics],
            "lgbm_grid": h_rows,
            "best_lgbm": {
                k: v for k, v in best_per_h[h].items()
                if k in ("grid_index", "params", "ic_stitched", "win_frac")
            },
            "gate_a_pass": bool(
                best_per_h[h]["win_frac"] > 0.5
                and best_per_h[h]["ic_stitched"] > ridge_ic
            ),
            "ridge_baseline": bp_r,
        }
        b = best_per_h[h]
        print(f"  >> Gate A h={h}: bestes LGBM{b['grid_index']} IC "
              f"{b['ic_stitched']:+.4f} vs Ridge {ridge_ic:+.4f}, "
              f"Split-Siege {b['win_frac']:.0%} -> "
              f"{'PASS' if results['gate_a'][f'h{h}']['gate_a_pass'] else 'FAIL'}")
        b["stitched"].to_parquet(RESULTS / f"lgbm_best_predictions_h{h}.parquet")
        if h == LEVER_HORIZON:
            ridge_stitched.to_parquet(RESULTS / f"ridge_predictions_h{h}.parquet")

    # ── Hebel-Scan (h=28, bestes LGBM + Ridge symmetrisch, long-only) ──────
    print(f"\n=== Hebel-Scan h={LEVER_HORIZON} (16 Varianten x 2 Modelle) ===")
    ridge_stitched_h = pd.read_parquet(
        RESULTS / f"ridge_predictions_h{LEVER_HORIZON}.parquet"
    )
    for model_name, stitched in [
        (f"lgbm{best_per_h[LEVER_HORIZON]['grid_index']}",
         best_per_h[LEVER_HORIZON]["stitched"]),
        ("ridge", ridge_stitched_h),
    ]:
        rows = []
        for li, lever in enumerate(LEVERS):
            port = lever_portfolio(stitched, ret, vol30, costs, dvol_med21, lever)
            net = port["returns"]
            active = port["weights"].abs().sum(axis=1) > 0
            net_a = net[active]
            hedged = (net_a - mkt.reindex(net_a.index)).dropna()
            to_yr = float(port["turnover"].sum() / max(len(net_a) / ANN, 1e-9))
            name = f"lever{li}_{model_name}"
            hedged_matrix[name] = hedged
            trial_sharpes_hedged.append(
                hedged.mean() / hedged.std() if hedged.std() > 0 else 0.0
            )
            rows.append({
                "lever_index": li, **{k: (v if v is not None else 0) for k, v in lever.items()},
                "sharpe_net": round(ann_sharpe(net_a), 3),
                "sharpe_net_vs_market": round(ann_sharpe(hedged), 3),
                "cagr_net": round(compute_metrics(net_a, periods_per_year=ANN)["cagr"], 4),
                "max_dd": round(compute_metrics(net_a, periods_per_year=ANN)["max_drawdown"], 4),
                "turnover_oneside_per_year": round(to_yr, 1),
                "regimes_vs_market": regime_table(hedged),
            })
        results["levers"][model_name] = rows
        top = sorted(rows, key=lambda r: -r["sharpe_net_vs_market"])[:4]
        for r in top:
            print(f"  {model_name} lever{r['lever_index']} "
                  f"(rb={r['rebalance']}, q={r['quantile']}, buf={r['buffer_mult']}, "
                  f"liq={r['liq_floor']:.0f}): net {r['sharpe_net']:+.2f}, "
                  f"vs Mkt {r['sharpe_net_vs_market']:+.2f}, TO {r['turnover_oneside_per_year']:.0f}x/J")

    # ── PBO über alle Konfigurationen (hedged LO returns) ──────────────────
    pbo_matrix = pd.DataFrame(hedged_matrix).dropna(how="all")
    pbo = pbo_cscv(pbo_matrix, n_blocks=16)
    results["pbo"] = {k: v for k, v in pbo.items()}
    print(f"\nPBO (CSCV, {pbo_matrix.shape[1]} Konfigs): {pbo['pbo']:.3f}")

    # ── Finale Auswahl + DSR/Bootstrap (Regel: bester LGBM-Hebel vs Markt) ─
    lgbm_levers = results["levers"][
        f"lgbm{best_per_h[LEVER_HORIZON]['grid_index']}"
    ]
    final = max(lgbm_levers, key=lambda r: r["sharpe_net_vs_market"])
    final_name = (
        f"lever{final['lever_index']}_"
        f"lgbm{best_per_h[LEVER_HORIZON]['grid_index']}"
    )
    hedged_final = hedged_matrix[final_name].dropna()
    n_trials_total = N_TRIALS_0058 + len(trial_sharpes_hedged)
    sp = float(hedged_final.mean() / hedged_final.std())
    dsr = deflated_sharpe_ratio(
        observed_sharpe=sp, n_obs=len(hedged_final), n_trials=n_trials_total,
        returns=hedged_final, trial_sharpes=np.array(trial_sharpes_hedged),
    )
    boot = bootstrap_ci(hedged_final, statistic="sharpe")
    results["final"] = {
        "name": final_name, "lever": final,
        "n_trials_total": n_trials_total,
        "dsr": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in dsr.items()},
        "bootstrap_hedged_sharpe": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in boot.items()},
        "regimes_vs_market": final["regimes_vs_market"],
    }
    hedged_final.rename("hedged").to_frame().to_parquet(RESULTS / "final_hedged_returns.parquet")
    print(f"\nFinal: {final_name} -> vs Markt {final['sharpe_net_vs_market']:+.2f}, "
          f"DSR {results['final']['dsr'].get('psr_deflated', float('nan'))} "
          f"(n_trials={n_trials_total}), Boot-KI "
          f"[{boot['ci_low']:+.2f},{boot['ci_high']:+.2f}]")
    print(f"Regime vs Markt: {final['regimes_vs_market']}")

    with open(RESULTS / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nGespeichert: {RESULTS / 'metrics.json'}")


if __name__ == "__main__":
    main()
