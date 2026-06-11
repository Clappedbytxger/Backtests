"""0058 — Crypto-Cross-Section: Ridge-Benchmark unter CPCV (Roadmap Phase 2).

Die Messlatte, die jedes spätere ML (LightGBM Phase 3, CNN Track B) schlagen
muss — bewusst VOR jedem nichtlinearen Modell gebaut (0057-Lehre: Ridge ist
in der Cross-Section oft schwer zu schlagen; ohne saubere lineare Messlatte
ist jeder ML-"Erfolg" uninterpretierbar).

Setup
-----
- PIT-Universum: wöchentliche CMC-Top-150-Snapshots inkl. Dead Coins
  (quantlab.crypto_xsection), Binance-USDT-Spot, 2017-08 ff.
- Features (quantlab.crypto_features): Momentum 1/2/4/8/12W, Size, Amihud,
  Vol/Semivol, Volume-Trend, Max-Return-Salienz, Past-Alpha/Beta — alle
  per-Datum rang-transformiert; Target = Rang des Forward-Returns.
- Ridge alpha=1.0 FIX (vorab registriert, kein Grid: auf Rang-Features mit
  n>>p ist die Regularisierung nahezu irrelevant; n_trials bleibt zählbar).
  Pro Horizont (7/14/28 Kalendertage) ein Modell -> n_trials = 3 Horizonte
  x 2 Portfolio-Varianten = 6.
- CPCV: 8 Gruppen, 2 Test-Gruppen (28 Splits), Purge = Horizont + 7d,
  Embargo 1%.
- Portfolio: Long-only Top-Quintil (primär, Roadmap: Alpha sitzt im
  Long-Leg) + Dollar-neutral L/S (sekundär); inverse-Vol-Gewichte, Wochen-
  Rebalance, gestaffelte Kosten je Liquiditätsklasse (12-100 bps/Seite).
- Benchmarks: cap-gewichteter PIT-Markt, Equal-Weight-Universum, BTC B&H.
- Subperioden: 2018-19 / 2020-21 Bull / 2022 Bear / 2023+ (Regime != Edge).

Ausgabe: results/metrics.json, results/ridge_predictions_h{h}.parquet (für
den Phase-3-Vergleich), Konsolen-Scorecard.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx
from quantlab.cpcv import make_cpcv_splits, stitch_oos_predictions
from quantlab.metrics import compute_metrics
from quantlab.ml_portfolio import run_ml_portfolio

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

ANN = 365
TOP_N = 150
HORIZONS = (7, 14, 28)
RIDGE_ALPHA = 1.0
MIN_NAMES = 20
REGIMES = {
    "2018-2019": ("2018-01-01", "2019-12-31"),
    "bull_2020_21": ("2020-01-01", "2021-12-31"),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "2023_plus": ("2023-01-01", None),
}


def ann_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 60 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(ANN))


def make_ridge():
    from sklearn.linear_model import Ridge

    return Ridge(alpha=RIDGE_ALPHA)


def fit_cpcv(df: pd.DataFrame, splits: list[dict]) -> pd.DataFrame:
    """Ridge per CPCV split -> stitched, fully-OOS prediction panel."""
    feature_cols = [c for c in df.columns if c not in ("y", "fwd_ret")]
    dates = df.index.get_level_values("date")
    preds = []
    for sp in splits:
        tr = df[dates.isin(sp["train"])]
        te = df[dates.isin(sp["test"])]
        # Rank features: 0 == cross-sectional median (honest NaN fill).
        x_tr = tr[feature_cols].fillna(0.0).values
        x_te = te[feature_cols].fillna(0.0).values
        model = make_ridge()
        model.fit(x_tr, tr["y"].values)
        pred = pd.Series(model.predict(x_te), index=te.index)
        preds.append(pred.unstack("pair"))
    return stitch_oos_predictions(splits, preds)


def oos_ic(pred_panel: pd.DataFrame, fwd: pd.DataFrame) -> dict:
    """Per-date Spearman IC of the stitched OOS predictions."""
    common = pred_panel.index.intersection(fwd.index)
    ics = []
    for t in common:
        p = pred_panel.loc[t].dropna()
        f = fwd.loc[t].reindex(p.index).dropna()
        if len(f) >= MIN_NAMES:
            ics.append(p.reindex(f.index).corr(f, method="spearman"))
    ics = pd.Series(ics, dtype=float).dropna()
    t_stat = float(ics.mean() / ics.std() * np.sqrt(len(ics))) if len(ics) > 2 else np.nan
    return {"ic_mean": float(ics.mean()), "ic_t": t_stat, "n_dates": int(len(ics))}


def regime_table(r: pd.Series) -> dict:
    out = {}
    for name, (a, b) in REGIMES.items():
        seg = r.loc[a:b] if b else r.loc[a:]
        out[name] = round(ann_sharpe(seg), 3)
    return out


def main() -> None:
    print("=== 0058 Ridge-Benchmark: Lade Universum & Panels (Cache) ===")
    uni = cx.build_universe(top_n=TOP_N)
    panels = cx.get_price_panels(uni)
    fp = cf.build_feature_panels(panels)

    ret = fp["returns"]
    memb = panels["membership_daily"]
    vol30 = fp["vol30"]
    costs = cf.cost_panel(fp["dvol_med21"])

    # ── Benchmarks ───────────────────────────────────────────────────────
    mkt = fp["market"]  # cap-weighted PIT universe
    ew = ret.where(memb.shift(1)).mean(axis=1)  # equal-weight, PIT-lagged
    btc = ret["BTCUSDT"]

    results: dict = {
        "config": {
            "top_n": TOP_N, "ridge_alpha": RIDGE_ALPHA, "horizons": HORIZONS,
            "n_trials": len(HORIZONS) * 2,
            "cost_tiers_bps_per_side": cf.COST_TIERS,
        },
        "benchmarks": {},
        "ridge": {},
    }
    for name, series in [("market_cap_weighted", mkt), ("equal_weight", ew), ("btc", btc)]:
        m = compute_metrics(series.dropna(), periods_per_year=ANN)
        m["regimes"] = regime_table(series)
        results["benchmarks"][name] = {
            k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()
        }
        print(f"  Benchmark {name}: Sharpe {m['sharpe']:.2f}, CAGR {m['cagr']:.1%}, "
              f"MaxDD {m['max_drawdown']:.0%}")

    # ── Ridge je Horizont ────────────────────────────────────────────────
    for h in HORIZONS:
        print(f"\n=== Horizont {h}d ===")
        df = cf.assemble_design_matrix(fp, horizon=h, min_names=MIN_NAMES)
        dm_dates = df.index.get_level_values("date").unique().sort_values()
        print(f"  Design-Matrix: {len(df):,} Zeilen, {len(dm_dates)} Wochen "
              f"({dm_dates[0]:%Y-%m-%d} .. {dm_dates[-1]:%Y-%m-%d})")

        splits = make_cpcv_splits(
            dm_dates, n_groups=8, n_test_groups=2,
            purge_days=h + 7, embargo_frac=0.01,
        )
        stitched = fit_cpcv(df, splits)
        stitched.to_parquet(RESULTS / f"ridge_predictions_h{h}.parquet")

        ic = oos_ic(stitched, fp["targets_raw"][h])
        print(f"  OOS-IC (Spearman): {ic['ic_mean']:+.4f}, t={ic['ic_t']:.2f}, "
              f"n={ic['n_dates']} Wochen")

        h_res = {"ic": ic, "portfolios": {}}
        pred_daily = stitched.reindex(ret.index)
        for variant, lo in [("long_only", True), ("long_short", False)]:
            port = run_ml_portfolio(
                ret, pred_daily, vol=vol30, rebalance="W",
                cost_bps_per_side=costs, min_names=MIN_NAMES, long_only=lo,
            )
            net, gross = port["returns"], port["gross_returns"]
            active = port["weights"].abs().sum(axis=1) > 0
            net_a = net[active]
            m = compute_metrics(net_a, periods_per_year=ANN)
            to_yr = float(port["turnover"].sum() / max(len(net_a) / ANN, 1e-9))
            entry = {
                "sharpe_net": round(ann_sharpe(net_a), 3),
                "sharpe_gross": round(ann_sharpe(gross[active]), 3),
                "cagr_net": round(m["cagr"], 4),
                "max_dd": round(m["max_drawdown"], 4),
                "ann_vol": round(m["annual_volatility"], 4),
                "turnover_oneside_per_year": round(to_yr, 1),
                "regimes_net": regime_table(net_a),
                "n_days_active": int(active.sum()),
            }
            if lo:
                # Long-only ist nur als Alpha relevant, wenn es den Markt
                # schlägt — Hedge-Differenz gegen den cap-gewichteten Markt.
                hedged = (net_a - mkt.reindex(net_a.index)).dropna()
                entry["sharpe_net_vs_market"] = round(ann_sharpe(hedged), 3)
                entry["regimes_vs_market"] = regime_table(hedged)
            h_res["portfolios"][variant] = entry
            print(f"  {variant:11s}: Sharpe net {entry['sharpe_net']:+.2f} "
                  f"(brutto {entry['sharpe_gross']:+.2f}), CAGR {m['cagr']:+.1%}, "
                  f"MaxDD {m['max_drawdown']:.0%}, TO {to_yr:.0f}x/J"
                  + (f", vs Markt {entry['sharpe_net_vs_market']:+.2f}" if lo else ""))
            net.rename("net").to_frame().assign(gross=gross).to_parquet(
                RESULTS / f"returns_h{h}_{variant}.parquet"
            )
        results["ridge"][f"h{h}"] = h_res

    with open(RESULTS / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nGespeichert: {RESULTS / 'metrics.json'}")


if __name__ == "__main__":
    main()
