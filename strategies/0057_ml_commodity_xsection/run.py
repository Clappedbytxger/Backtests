"""0057 — ML-Signalgenerierung auf der Commodity-Cross-Section (Roadmap-Phasen 2-5).

Hypothese (vorab registriert, ML-COMMODITY-SIGNAL-ROADMAP.md): bekannte
Rohstoff-Risikoprämien (Carry/Basis, Basis-Momentum, Momentum, Hedging
Pressure, Skew, Vol-Regime, Makro-Zustand) tragen *nichtlinear kombiniert*
mehr Information über den 1W-3M-Querschnitt als ein lineares Faktormodell.

Design:
- Universum: 17 GLBX-Futures (CME/NYMEX/COMEX/CBOT; ICE-Softs nicht im
  Datensatz — dokumentierte Einschränkung).
- Features: theoriegetrieben, PIT-safe, per Datum rang-transformiert
  (quantlab.commodity_features). Targets: rang-transformierte Forward-Returns.
- Validierung: CPCV (8 Gruppen, 2 Test-Gruppen => 28 Splits) mit Purge =
  Label-Horizont + Embargo 1% (quantlab.cpcv). KEIN Walk-Forward-Einzelpfad.
- Portfolio: Quintil-L/S, inverse-vol Legs, woechentliches Rebalancing,
  6 bps/Seite (quantlab.ml_portfolio).
- Gates (Roadmap Teil 5): GBT muss Ridge klar schlagen, PBO < 0.5,
  Permutation p < 0.05, DSR ueberlebt, Subperioden-Decay moderat, netto > 0.

Multiple-Testing-Buchhaltung: jede (Modell x Hyperparameter x Horizont)-Zelle
zaehlt als Trial; ein vorab fixiertes 8er-Gitter ersetzt Optuna-TPE, damit
n_trials klein UND exakt zaehlbar bleibt (bewusste Abweichung von der Roadmap,
gleiche Disziplin, ehrlicherer DSR).
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="X does not have valid feature names")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.commodity_features import assemble_design_matrix, build_feature_panels
from quantlab.cpcv import make_cpcv_splits, pbo_cscv, stitch_oos_predictions
from quantlab.cross_sectional import _rebalance_dates
from quantlab.metrics import compute_metrics
from quantlab.ml_portfolio import run_ml_portfolio
from quantlab.significance import deflated_sharpe_ratio, t_test_mean_return

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)

HORIZONS = (5, 21, 63)
PRIMARY_HORIZON = 21
COST_BPS_SIDE = 6.0
N_GROUPS, N_TEST_GROUPS = 8, 2
EMBARGO_FRAC = 0.01
# Purge in calendar days ~ 1.5x the trading-day label horizon.
PURGE_DAYS = {5: 10, 21: 35, 63: 95}

MACRO_COLS = ["dxy_ret_63", "real_rate", "real_rate_chg_63", "term_spread", "vix", "vix_pct"]

RIDGE_ALPHAS = (0.1, 1.0, 10.0)
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


# ── Models ───────────────────────────────────────────────────────────────────

def make_ridge(alpha: float):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(StandardScaler(), Ridge(alpha=alpha))


def make_lgbm(**params):
    from lightgbm import LGBMRegressor

    return LGBMRegressor(**{**LGBM_FIXED, **params})


def make_mlp():
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    return make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=(32, 16),
            early_stopping=True,
            max_iter=400,
            random_state=7,
        ),
    )


def _xy(df: pd.DataFrame, feature_cols: list[str], fillna: bool):
    x = df[feature_cols]
    if fillna:
        # Rank features: 0 == cross-sectional median. Macro: column median.
        x = x.fillna({c: 0.0 for c in x.columns if c not in MACRO_COLS})
        x = x.fillna(x.median(numeric_only=True))
    return x.values, df["y"].values


# ── CPCV evaluation of one config ────────────────────────────────────────────

def evaluate_config(
    model_factory,
    df: pd.DataFrame,
    splits: list[dict],
    returns: pd.DataFrame,
    vol20: pd.DataFrame,
    fillna: bool,
    collect_importance: bool = False,
) -> dict:
    """Fit per CPCV split, stitch OOS predictions, run the L/S portfolio."""
    feature_cols = [c for c in df.columns if c not in ("y", "fwd_ret")]
    dates = df.index.get_level_values("date")

    preds_per_split: list[pd.DataFrame] = []
    split_sharpes: list[float] = []
    importances: list[pd.Series] = []

    for sp in splits:
        tr = df[dates.isin(sp["train"])]
        te = df[dates.isin(sp["test"])]
        x_tr, y_tr = _xy(tr, feature_cols, fillna)
        x_te, _ = _xy(te, feature_cols, fillna)

        model = model_factory()
        model.fit(x_tr, y_tr)
        pred = pd.Series(model.predict(x_te), index=te.index, name="pred")
        pred_panel = pred.unstack("root")
        preds_per_split.append(pred_panel)

        if collect_importance and hasattr(model, "feature_importances_"):
            importances.append(
                pd.Series(model.feature_importances_, index=feature_cols)
            )

        # Per-split OOS portfolio Sharpe: weights only inside the test window.
        port = run_ml_portfolio(
            returns, pred_panel.reindex(returns.index),
            vol=vol20, rebalance="W",
            cost_bps_per_side=COST_BPS_SIDE,
        )
        r = port["returns"]
        active = port["weights"].abs().sum(axis=1) > 0
        r = r[active]
        if len(r) > 40 and r.std() > 0:
            split_sharpes.append(float(r.mean() / r.std() * np.sqrt(252)))

    stitched = stitch_oos_predictions(splits, preds_per_split)
    port = run_ml_portfolio(
        returns, stitched.reindex(returns.index), vol=vol20,
        rebalance="W", cost_bps_per_side=COST_BPS_SIDE,
    )
    out = {
        "stitched_preds": stitched,
        "net": port["returns"],
        "gross": port["gross_returns"],
        "split_sharpes": np.array(split_sharpes),
        "turnover": port["turnover"],
    }
    if collect_importance and importances:
        out["importances"] = pd.DataFrame(importances)
    return out


def ann_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    r = r[r != 0.0]  # only days with a book on
    if len(r) < 40 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(252))


def prediction_permutation_test(
    stitched: pd.DataFrame,
    returns: pd.DataFrame,
    vol20: pd.DataFrame,
    n_perm: int = 500,
    seed: int = 42,
) -> dict:
    """Null: 'die Rangfolge traegt keine Information' — Vorhersagen pro
    Rebalance-Datum quer ueber die Instrumente shuffeln (wie
    cross_sectional_permutation_test, hier auf dem ML-Output)."""
    rng = np.random.default_rng(seed)
    rb = _rebalance_dates(returns.index, "W")
    pred_rb = stitched.reindex(rb)

    observed = ann_sharpe(
        run_ml_portfolio(returns, stitched.reindex(returns.index), vol=vol20,
                         rebalance="W", cost_bps_per_side=COST_BPS_SIDE)["returns"]
    )
    null = np.empty(n_perm)
    cols = pred_rb.columns
    for i in range(n_perm):
        shuffled = pd.DataFrame(
            {dt: pd.Series(rng.permutation(row.values), index=cols)
             for dt, row in pred_rb.iterrows()}
        ).T
        r = run_ml_portfolio(returns, shuffled.reindex(returns.index, method="ffill"),
                             vol=vol20, rebalance="W",
                             cost_bps_per_side=COST_BPS_SIDE)["returns"]
        null[i] = ann_sharpe(r)
    null = null[np.isfinite(null)]
    p = float((np.sum(null >= observed) + 1) / (len(null) + 1))
    return {"observed": observed, "p_value": p,
            "null_mean": float(null.mean()), "null_std": float(null.std())}


def label_permutation_test(
    model_factory,
    df: pd.DataFrame,
    splits: list[dict],
    returns: pd.DataFrame,
    vol20: pd.DataFrame,
    fillna: bool,
    n_perm: int = 30,
    seed: int = 42,
) -> dict:
    """Roadmap-Permutation: Labels pro Datum shuffeln und KOMPLETT neu
    trainieren — testet, ob das Modell echte Struktur lernt (teuer, daher
    weniger Wiederholungen; ergaenzt den schnellen Vorhersage-Shuffle)."""
    rng = np.random.default_rng(seed)
    base = evaluate_config(model_factory, df, splits, returns, vol20, fillna)
    observed = ann_sharpe(base["net"])

    null = []
    for _ in range(n_perm):
        df_p = df.copy()
        df_p["y"] = (
            df_p.groupby(level="date")["y"]
            .transform(lambda s: rng.permutation(s.values))
        )
        res = evaluate_config(model_factory, df_p, splits, returns, vol20, fillna)
        null.append(ann_sharpe(res["net"]))
    null = np.array([x for x in null if np.isfinite(x)])
    p = float((np.sum(null >= observed) + 1) / (len(null) + 1))
    return {"observed": observed, "p_value": p,
            "null_mean": float(null.mean()), "null_std": float(null.std()),
            "n_perm": int(len(null))}


# ── Main ─────────────────────────────────────────────────────────────────────

def main(label_perms: int = 30) -> None:
    t0 = time.time()
    print("Building feature panels ...")
    panels = build_feature_panels()
    returns, vol20 = panels["returns"], panels["vol20"]
    print(f"  universe={returns.shape[1]} days={returns.shape[0]} "
          f"({returns.index[0].date()}..{returns.index[-1].date()})")

    design = {}
    for h in HORIZONS:
        design[h] = assemble_design_matrix(panels, horizon=h, sample_freq="W")
        d = design[h]
        print(f"  horizon {h:>2}d: {len(d):,} rows, "
              f"{d.index.get_level_values('date').nunique()} dates")

    splits = {
        h: make_cpcv_splits(
            design[h].index.get_level_values("date").unique(),
            n_groups=N_GROUPS, n_test_groups=N_TEST_GROUPS,
            purge_days=PURGE_DAYS[h], embargo_frac=EMBARGO_FRAC,
        )
        for h in HORIZONS
    }

    # ── Phase 2 + 3: alle Konfigurationen unter identischem CPCV ───────────
    configs: dict[str, dict] = {}
    for h in HORIZONS:
        for a in RIDGE_ALPHAS:
            configs[f"ridge_a{a}_h{h}"] = dict(
                factory=lambda a=a: make_ridge(a), horizon=h, fillna=True,
                family="ridge",
            )
        for i, params in enumerate(LGBM_GRID):
            configs[f"lgbm_g{i}_h{h}"] = dict(
                factory=lambda p=params: make_lgbm(**p), horizon=h, fillna=False,
                family="lgbm", params=params,
            )

    results: dict[str, dict] = {}
    for name, cfg in configs.items():
        h = cfg["horizon"]
        res = evaluate_config(
            cfg["factory"], design[h], splits[h], returns, vol20,
            cfg["fillna"], collect_importance=(cfg["family"] == "lgbm"),
        )
        results[name] = res
        print(f"  {name:18s} stitched-OOS net Sharpe {ann_sharpe(res['net']):+.2f} "
              f"| split-Sharpe median {np.median(res['split_sharpes']):+.2f} "
              f"({time.time()-t0:,.0f}s)")

    # ── Phase 4: Multi-Horizont-Ensembles (je Familie) ──────────────────────
    for family in ("ridge", "lgbm"):
        members = {
            h: max(
                (n for n, c in configs.items()
                 if c["family"] == family and c["horizon"] == h),
                key=lambda n: ann_sharpe(results[n]["net"]),
            )
            for h in HORIZONS
        }
        # Vorhersagen je Horizont pro Datum rangskalieren, dann mitteln.
        panels_norm = []
        for h, n in members.items():
            p = results[n]["stitched_preds"]
            panels_norm.append(p.rank(axis=1).sub(p.notna().sum(axis=1).div(2), axis=0))
        ens = sum(p.fillna(0) for p in panels_norm).where(
            sum(p.notna() for p in panels_norm) > 0
        )
        port = run_ml_portfolio(returns, ens.reindex(returns.index), vol=vol20,
                                rebalance="W", cost_bps_per_side=COST_BPS_SIDE)
        results[f"{family}_ens"] = {
            "stitched_preds": ens, "net": port["returns"],
            "gross": port["gross_returns"],
            "split_sharpes": np.array([]), "turnover": port["turnover"],
        }
        print(f"  {family}_ens          stitched-OOS net Sharpe "
              f"{ann_sharpe(port['returns']):+.2f}")

    # ── Phase 5: MLP-Negativkontrolle (nur Primaer-Horizont) ───────────────
    res = evaluate_config(make_mlp, design[PRIMARY_HORIZON],
                          splits[PRIMARY_HORIZON], returns, vol20, fillna=True)
    results[f"mlp_h{PRIMARY_HORIZON}"] = res
    print(f"  mlp_h{PRIMARY_HORIZON}            stitched-OOS net Sharpe "
          f"{ann_sharpe(res['net']):+.2f}")

    n_trials = len(results)
    print(f"\nTotal configs tried (n_trials for DSR): {n_trials}")

    # ── Ridge-Gate + Auswahl ────────────────────────────────────────────────
    def family_best(family: str) -> str:
        return max((n for n in results if n.startswith(family)),
                   key=lambda n: ann_sharpe(results[n]["net"]))

    best_ridge = family_best("ridge")
    best_lgbm = family_best("lgbm")
    sr_ridge = ann_sharpe(results[best_ridge]["net"])
    sr_lgbm = ann_sharpe(results[best_lgbm]["net"])

    # Split-weiser Vergleich je Horizont (gleiche CPCV-Splits => paarbar).
    frac_lgbm_wins = {}
    for h in HORIZONS:
        rid_h = max((n for n, c in configs.items()
                     if c["family"] == "ridge" and c["horizon"] == h),
                    key=lambda n: ann_sharpe(results[n]["net"]))
        lgb_h = max((n for n, c in configs.items()
                     if c["family"] == "lgbm" and c["horizon"] == h),
                    key=lambda n: ann_sharpe(results[n]["net"]))
        s_r = results[rid_h]["split_sharpes"]
        s_l = results[lgb_h]["split_sharpes"]
        n_common = min(len(s_r), len(s_l))
        frac_lgbm_wins[h] = float(np.mean(s_l[:n_common] > s_r[:n_common]))

    print(f"\nBest Ridge: {best_ridge} ({sr_ridge:+.2f}) | "
          f"Best LGBM: {best_lgbm} ({sr_lgbm:+.2f})")
    for h in HORIZONS:
        print(f"Ridge-Gate h={h}: LGBM gewinnt {frac_lgbm_wins[h]:.0%} der CPCV-Splits")

    # ── PBO ueber alle Konfigurationen ──────────────────────────────────────
    ret_mat = pd.DataFrame({n: r["net"] for n, r in results.items()})
    pbo = pbo_cscv(ret_mat, n_blocks=16)
    print(f"PBO (CSCV, {pbo['n_combinations']} Kombinationen): {pbo['pbo']:.3f}")

    # ── Volle Batterie auf dem Gesamtsieger ────────────────────────────────
    winner = max(results, key=lambda n: ann_sharpe(results[n]["net"]))
    win = results[winner]
    net = win["net"]
    print(f"\n=== Sieger: {winner} ===")
    m = compute_metrics(net)
    print(f"  net Sharpe {m['sharpe']:.2f}  CAGR {m['cagr']*100:.1f}%  "
          f"MaxDD {m['max_drawdown']*100:.1f}%")
    gross_sr = ann_sharpe(win["gross"])
    print(f"  gross Sharpe {gross_sr:+.2f}  | Kosten-Drag "
          f"{(win['gross'].mean()-net.mean())*252*100:.2f}%/Jahr")

    perm = prediction_permutation_test(win["stitched_preds"], returns, vol20)
    print(f"  Permutation (Rank-Shuffle, 500): p={perm['p_value']:.3f} "
          f"(obs {perm['observed']:+.2f}, null {perm['null_mean']:+.2f})")

    label_perm = None
    if label_perms > 0 and winner in configs:
        cfg = configs[winner]
        label_perm = label_permutation_test(
            cfg["factory"], design[cfg["horizon"]], splits[cfg["horizon"]],
            returns, vol20, cfg["fillna"], n_perm=label_perms,
        )
        print(f"  Label-Permutation (Retrain, {label_perm['n_perm']}): "
              f"p={label_perm['p_value']:.3f}")

    active = net[net != 0]
    sp_pp = active.mean() / active.std(ddof=1)
    trial_pp = [
        (lambda r: r.mean() / r.std(ddof=1) if r.std(ddof=1) > 0 else 0.0)(
            rr["net"][rr["net"] != 0]
        )
        for rr in results.values()
    ]
    dsr = deflated_sharpe_ratio(
        observed_sharpe=float(sp_pp), n_obs=len(active),
        n_trials=n_trials, returns=active, trial_sharpes=trial_pp,
    )
    print(f"  DSR (n_trials={n_trials}): {dsr['psr_deflated']:.3f}")
    tt = t_test_mean_return(active)
    print(f"  t-Test aktive Tage: t={tt['t_stat']:.2f} p={tt['p_value']:.3f}")

    # Subperioden-Decay.
    sub = {
        "full": ann_sharpe(net),
        "pre2015": ann_sharpe(net[net.index < "2015-01-01"]),
        "2015_2020": ann_sharpe(net[(net.index >= "2015-01-01") & (net.index < "2020-01-01")]),
        "post2020": ann_sharpe(net[net.index >= "2020-01-01"]),
    }
    print("  Subperioden-Sharpe: " + "  ".join(f"{k}={v:+.2f}" for k, v in sub.items()))

    # SHAP-/Importance-Stabilitaet des besten LGBM.
    imp_stab = None
    if "importances" in results[best_lgbm]:
        imp = results[best_lgbm]["importances"]
        # Stability = mean pairwise Spearman of the feature ranking BETWEEN
        # splits (rows), i.e. correlate the transposed rank matrix.
        corr = imp.rank(axis=1).T.corr(method="spearman").values
        imp_stab = float(corr[np.triu_indices_from(corr, k=1)].mean())
        top = imp.mean().sort_values(ascending=False).head(8)
        print("\n  LGBM Feature-Importance (mean gain ueber Splits):")
        for k, v in top.items():
            print(f"    {k:16s} {v:,.0f}")
        print(f"  Importance-Rang-Stabilitaet (mean Spearman ueber Splits): "
              f"{imp_stab:.2f}")

    # ── Persistenz ──────────────────────────────────────────────────────────
    summary = {
        "n_trials": n_trials,
        "cost_bps_per_side": COST_BPS_SIDE,
        "cpcv": {"n_groups": N_GROUPS, "n_test_groups": N_TEST_GROUPS,
                 "purge_days": PURGE_DAYS, "embargo_frac": EMBARGO_FRAC},
        "config_sharpes": {n: ann_sharpe(r["net"]) for n, r in results.items()},
        "split_sharpes": {n: r["split_sharpes"].tolist() for n, r in results.items()},
        "ridge_gate": {
            "best_ridge": best_ridge, "best_ridge_sharpe": sr_ridge,
            "best_lgbm": best_lgbm, "best_lgbm_sharpe": sr_lgbm,
            "frac_lgbm_wins_per_horizon": frac_lgbm_wins,
        },
        "pbo": pbo,
        "winner": winner,
        "winner_metrics": m,
        "winner_gross_sharpe": gross_sr,
        "permutation_pred_shuffle": perm,
        "permutation_label_retrain": label_perm,
        "dsr": {k: v for k, v in dsr.items()},
        "ttest_active": tt,
        "subperiod_sharpe": sub,
        "lgbm_importance_rank_stability": imp_stab,
    }
    (RESULTS / "metrics.json").write_text(json.dumps(summary, indent=2, default=float))
    ret_mat.to_parquet(RESULTS / "config_returns.parquet")
    net.to_frame("net_return").to_csv(RESULTS / "winner_returns.csv")
    print(f"\nSaved -> {RESULTS}  ({time.time()-t0:,.0f}s total)")


if __name__ == "__main__":
    lp = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    main(label_perms=lp)
