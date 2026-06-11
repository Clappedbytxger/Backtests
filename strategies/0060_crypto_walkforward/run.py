"""0060 — Walk-Forward der eingefrorenen 0059-Regel (+ Konzentrations-Fix).

Der CPCV-Stitch aus 0059 ist kein handelbarer Pfad (Modelle für 2020 sahen
2021-26). Dieser Test fährt die am 2026-06-11 EINGEFRORENE Regel als echten
Walk-Forward:

- **Regel (eingefroren, 0059):** LGBM0 (15 Blätter, lr 0.05, 100 Bäume,
  Rest wie 0057-Fix), h=28-Rang-Target, Monats-Rebalance, Dezil long-only,
  Hold-Band-Buffer 2x, Liquiditäts-Floor $5M, inverse-Vol-Gewichte,
  gestaffelte Kosten.
- **Walk-Forward-Protokoll (vorab fixiert):** monatlicher Refit, expanding
  window; zum Refit-Zeitpunkt t trainiert das Modell NUR auf Zeilen mit
  Datum <= t-28 Kalendertagen (das Label ist sonst bei t noch nicht
  realisiert); erster Fit 2020-12-31 (~2 Jahre Training); jedes Modell
  scort die Wochen-Querschnitte bis zum nächsten Refit. OOT-Pfad:
  2021-01 .. heute (~5.4 Jahre).
- **Ridge α=1.0 im identischen Protokoll** — hält das Ridge-Gate auch
  out-of-time?
- **Konzentrations-Fix (EIN registrierter Versuch):** min. Buchgröße 12
  (``min_k=12``) auf demselben Prediction-Pfad — gegen das 8-Namen-Buch.
- **Statistik:** netto Hedge-vs-Markt-Sharpe, Bootstrap-KI, t-Test, PSR
  (n_trials=1, vorab committeter Einzeltest) UND konservativer DSR mit den
  62 Trials + Trial-Streuung aus 0059 (die Regel WURDE auf diesen Daten
  selektiert). Jahres-Tabelle.

Ehrlicher Rahmen: der Walk-Forward schließt den Modell-Fit-Kanal (kein
Training auf Zukunft mehr), aber NICHT den Regel-Selektions-Kanal — die
Hebel wurden in 0059 auf der vollen Historie gewählt. Den schließt nur der
Live-Forward (Registrierung in REPORT.md).
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
from quantlab.metrics import compute_metrics
from quantlab.ml_portfolio import run_buffered_long_portfolio
from quantlab.significance import bootstrap_ci, deflated_sharpe_ratio, t_test_mean_return

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

ANN = 365
TOP_N = 150
HORIZON = 28
MIN_NAMES = 20
FIRST_FIT = pd.Timestamp("2020-12-31")
FROZEN_LGBM = dict(num_leaves=15, learning_rate=0.05, n_estimators=100)
LGBM_FIXED = dict(
    objective="regression", min_child_samples=40, subsample=0.8,
    subsample_freq=1, colsample_bytree=0.8, verbose=-1, n_jobs=-1,
    random_state=7,
)
FROZEN_LEVER = dict(rebalance="ME", quantile=0.1, buffer_mult=2.0, liq_floor=5e6)
N_TRIALS_HISTORY = 62  # 0059's honest selection count


def ann_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 60 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(ANN))


def make_lgbm():
    from lightgbm import LGBMRegressor

    return LGBMRegressor(**{**LGBM_FIXED, **FROZEN_LGBM})


def make_ridge():
    from sklearn.linear_model import Ridge

    return Ridge(alpha=1.0)


def walk_forward_predictions(
    df: pd.DataFrame, model_factory, fillna_zero: bool,
    score_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Monthly-refit, expanding-window predictions on the weekly rows.

    Refit at each month-end >= FIRST_FIT using only rows whose 28d label was
    realized by then (date <= refit - 28d); the model scores every weekly
    cross-section until the next refit. Strictly point-in-time.

    ``score_df`` (default: ``df``) is the row set to score — pass the
    ``require_target=False`` matrix so the last (label-less) weeks get
    predictions too (live edge of the path).
    """
    feature_cols = [c for c in df.columns if c not in ("y", "fwd_ret")]
    dates = df.index.get_level_values("date")
    score_df = df if score_df is None else score_df
    score_dates = score_df.index.get_level_values("date")
    weekly = score_dates.unique().sort_values()

    refits = pd.date_range(FIRST_FIT, weekly[-1], freq="ME")
    panels = []
    for i, t in enumerate(refits):
        train = df[dates <= t - pd.Timedelta(days=HORIZON)]
        if len(train) < 3000:
            continue
        x_tr = train[feature_cols]
        if fillna_zero:
            x_tr = x_tr.fillna(0.0)
        model = model_factory()
        model.fit(x_tr.values, train["y"].values)

        until = refits[i + 1] if i + 1 < len(refits) else weekly[-1] + pd.Timedelta(days=1)
        te = score_df[(score_dates > t) & (score_dates <= until)]
        if te.empty:
            continue
        x_te = te[feature_cols]
        if fillna_zero:
            x_te = x_te.fillna(0.0)
        pred = pd.Series(model.predict(x_te.values), index=te.index)
        panels.append(pred.unstack("pair"))
    return pd.concat(panels).sort_index()


def per_date_ic(pred_panel: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    ics = {}
    for t in pred_panel.index.intersection(fwd.index):
        p = pred_panel.loc[t].dropna()
        f = fwd.loc[t].reindex(p.index).dropna()
        if len(f) >= MIN_NAMES:
            ics[t] = p.reindex(f.index).corr(f, method="spearman")
    return pd.Series(ics, dtype=float).dropna()


def frozen_portfolio(pred_panel, ret, vol30, costs, dvol_med21, min_k: int = 1):
    pred_daily = pred_panel.reindex(ret.index)
    pred_daily = pred_daily.where(dvol_med21 >= FROZEN_LEVER["liq_floor"])
    return run_buffered_long_portfolio(
        ret, pred_daily, vol=vol30,
        rebalance=FROZEN_LEVER["rebalance"], quantile=FROZEN_LEVER["quantile"],
        buffer_mult=FROZEN_LEVER["buffer_mult"], cost_bps_per_side=costs,
        min_names=MIN_NAMES, min_k=min_k,
    )


def evaluate(name, port, mkt, results):
    net = port["returns"]
    active = port["weights"].abs().sum(axis=1) > 0
    net_a = net[active]
    hedged = (net_a - mkt.reindex(net_a.index)).dropna()
    names_held = (port["weights"] > 0).sum(axis=1)[active]
    m = compute_metrics(net_a, periods_per_year=ANN)
    boot = bootstrap_ci(hedged, statistic="sharpe")
    tt = t_test_mean_return(hedged)
    sp = float(hedged.mean() / hedged.std())
    psr = deflated_sharpe_ratio(sp, len(hedged), n_trials=1, returns=hedged)
    yr = hedged.groupby(hedged.index.year).apply(ann_sharpe)
    to_yr = float(port["turnover"].sum() / max(len(net_a) / ANN, 1e-9))
    entry = {
        "active": f"{net_a.index[0]:%Y-%m-%d}..{net_a.index[-1]:%Y-%m-%d}",
        "sharpe_net": round(ann_sharpe(net_a), 3),
        "cagr_net": round(m["cagr"], 4),
        "max_dd": round(m["max_drawdown"], 4),
        "sharpe_vs_market": round(ann_sharpe(hedged), 3),
        "bootstrap_ci": [round(boot["ci_low"], 3), round(boot["ci_high"], 3)],
        "t_test_p": round(tt.get("p_value", float("nan")), 4),
        "psr_single_test": round(psr["psr_deflated"], 4),
        "turnover_oneside_per_year": round(to_yr, 1),
        "book_size_median": float(names_held.median()),
        "book_size_min": int(names_held.min()),
        "hedged_sharpe_by_year": {int(y): round(v, 2) for y, v in yr.items()},
    }
    results[name] = entry
    print(f"\n  {name}:")
    print(f"    aktiv {entry['active']}, Buch median {entry['book_size_median']:.0f} "
          f"(min {entry['book_size_min']}), TO {to_yr:.0f}x/J")
    print(f"    net Sharpe {entry['sharpe_net']:+.2f}, CAGR {m['cagr']:+.1%}, "
          f"MaxDD {m['max_drawdown']:.0%}")
    print(f"    vs Markt {entry['sharpe_vs_market']:+.2f}, Boot-KI "
          f"[{boot['ci_low']:+.2f},{boot['ci_high']:+.2f}], t-p {entry['t_test_p']}, "
          f"PSR {entry['psr_single_test']}")
    print(f"    je Jahr: " + " ".join(f"{y}:{v:+.1f}" for y, v in yr.items()))
    return hedged, net_a


def main() -> None:
    print("=== 0060 Walk-Forward der eingefrorenen 0059-Regel ===")
    uni = cx.build_universe(top_n=TOP_N)
    panels = cx.get_price_panels(uni)
    fp = cf.build_feature_panels(panels)
    ret, vol30 = fp["returns"], fp["vol30"]
    costs = cf.cost_panel(fp["dvol_med21"])
    dvol = fp["dvol_med21"]
    mkt = fp["market"]
    fwd = fp["targets_raw"][HORIZON]

    df = cf.assemble_design_matrix(fp, horizon=HORIZON, min_names=MIN_NAMES)
    df_score = cf.assemble_design_matrix(
        fp, horizon=HORIZON, min_names=MIN_NAMES, require_target=False
    )
    results: dict = {"config": {
        "frozen_lgbm": FROZEN_LGBM, "frozen_lever": FROZEN_LEVER,
        "first_fit": str(FIRST_FIT.date()), "refit": "ME expanding",
        "train_label_lag_days": HORIZON,
    }}

    print("Walk-Forward LGBM0 (monatlicher Refit, expanding) ...")
    wf_lgbm = walk_forward_predictions(df, make_lgbm, fillna_zero=False, score_df=df_score)
    wf_lgbm.to_parquet(RESULTS / "wf_predictions_lgbm.parquet")
    print("Walk-Forward Ridge ...")
    wf_ridge = walk_forward_predictions(df, make_ridge, fillna_zero=True, score_df=df_score)

    ic_l = per_date_ic(wf_lgbm, fwd)
    ic_r = per_date_ic(wf_ridge, fwd)
    common = ic_l.index.intersection(ic_r.index)
    win = float((ic_l.loc[common] > ic_r.loc[common]).mean())
    results["ic_oot"] = {
        "lgbm_mean": round(float(ic_l.mean()), 4),
        "ridge_mean": round(float(ic_r.mean()), 4),
        "lgbm_win_frac_weekly": round(win, 3),
        "n_weeks": int(len(common)),
        "lgbm_by_year": {int(y): round(v, 3) for y, v in
                         ic_l.groupby(ic_l.index.year).mean().items()},
    }
    print(f"\nOOT-IC: LGBM {ic_l.mean():+.4f} vs Ridge {ic_r.mean():+.4f}, "
          f"LGBM gewinnt {win:.0%} der {len(common)} Wochen")

    port_l = frozen_portfolio(wf_lgbm, ret, vol30, costs, dvol)
    hedged_l, net_l = evaluate("lgbm_frozen", port_l, mkt, results)
    net_l.rename("net").to_frame().to_parquet(RESULTS / "wf_returns_lgbm.parquet")

    port_r = frozen_portfolio(wf_ridge, ret, vol30, costs, dvol)
    evaluate("ridge_same_rule", port_r, mkt, results)

    # Konservativer DSR: die Regel wurde via 62 Trials auf 2019-26 selektiert.
    with open(ROOT / "strategies/0059_ml_crypto_xsection/results/metrics.json",
              encoding="utf-8") as f:
        m59 = json.load(f)
    trial_var_proxy = None
    sp = float(hedged_l.mean() / hedged_l.std())
    dsr_cons = deflated_sharpe_ratio(
        sp, len(hedged_l), n_trials=N_TRIALS_HISTORY, returns=hedged_l,
        sharpe_variance_across_trials=trial_var_proxy,
    )
    results["lgbm_frozen"]["dsr_conservative_62trials"] = round(
        dsr_cons["psr_deflated"], 4
    )
    print(f"\n  DSR konservativ (n_trials=62): "
          f"{results['lgbm_frozen']['dsr_conservative_62trials']}")

    # ── Konzentrations-Fix: min. Buchgröße 12 (EIN registrierter Versuch) ──
    print("\n=== Konzentrations-Fix: min_k=12 (1 Trial) ===")
    port_k = frozen_portfolio(wf_lgbm, ret, vol30, costs, dvol, min_k=12)
    evaluate("lgbm_min_book_12", port_k, mkt, results)
    port_k["returns"].rename("net").to_frame().to_parquet(
        RESULTS / "wf_returns_lgbm_mink12.parquet"
    )

    with open(RESULTS / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nGespeichert: {RESULTS / 'metrics.json'}")


if __name__ == "__main__":
    main()
