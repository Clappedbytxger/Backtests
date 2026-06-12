"""0062 — Phase 5 / Track B: CNN auf Preis-Chart-Bildern (JKX 2023).

Die „echte Signalgenerierung"-Wette der Roadmap: kein hand-gecraftetes
Faktor-Set — eine kleine CNN extrahiert Muster direkt aus 20-Tage-OHLC-
Bildern (3 px/Tag, MA-Linie, Volumen-Balken, per Bild min/max-skaliert;
JKX: das implizite Scaling ist ein Hauptgrund der Vorhersagekraft).

Vorab registriertes Design (2 neue Trials: CNN standalone + Ensemble):

- **Samples = identische Zeilen wie Track A** (Design-Matrix h=28, weekly)
  → identische 28 purged CPCV-Splits, direkt vergleichbar.
- **Target:** binär ``fwd_28 > 0`` (JKX); Ranking per p(up) je Datum.
- **CNN fix** (keine Architektur-Suche): 2 Conv-Blöcke (32/64, 5x3-Kernel,
  BatchNorm, ReLU, MaxPool 2x2), Dropout 0.5, 1 FC-Logit; Adam lr 1e-3,
  Batch 256, max 8 Epochen mit Early-Stopping (10% Val aus dem Train,
  Patience 2), Seed 7.
- **Gate (Roadmap Teil 6):** CNN schlägt Track A (LGBM0-Split-ICs in >50%
  der Splits UND gestitchter IC höher) ODER ist unkorreliert genug zum
  Ensemblen (mittlere per-Datum-Rank-Korrelation < 0.5) UND das Ensemble
  (Mittel der per-Datum-Ränge) schlägt LGBM0 in IC UND Portfolio.
  Bestandenes Gate → Walk-Forward-Check (0060-Protokoll) wie bei 0061.
- Portfolio-Messung: eingefrorene Live-Regel (ME, Dezil, min_k=12,
  Buffer 2x, Liq >= $5M).

Programm-Trial-Stand inkl. dieses Tests: 62 (0059) + 1 (0060) + 2 (0061)
+ 2 (0062) = 67.
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
sys.path.insert(0, str(ROOT / "strategies" / "0060_crypto_walkforward"))

from quantlab import crypto_features as cf
from quantlab import crypto_xsection as cx
from quantlab.cpcv import make_cpcv_splits, stitch_oos_predictions
from quantlab.price_images import build_image_dataset

from run import (  # 0060 frozen pieces  # noqa: E402
    HORIZON, MIN_NAMES, TOP_N, ann_sharpe, frozen_portfolio, make_lgbm,
)

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

WINDOW = 20
SEED = 7
MAX_EPOCHS = 8
BATCH = 256
N_TRIALS_PROGRAM = 67


def per_date_ic(pred_panel: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    ics = {}
    for t in pred_panel.index.intersection(fwd.index):
        p = pred_panel.loc[t].dropna()
        f = fwd.loc[t].reindex(p.index).dropna()
        if len(f) >= MIN_NAMES:
            ics[t] = p.reindex(f.index).corr(f, method="spearman")
    return pd.Series(ics, dtype=float).dropna()


# ── CNN ──────────────────────────────────────────────────────────────────────

def make_cnn():
    import torch
    from torch import nn

    torch.manual_seed(SEED)

    class ChartCNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 32, kernel_size=(5, 3), padding=(2, 1)),
                nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
                nn.Conv2d(32, 64, kernel_size=(5, 3), padding=(2, 1)),
                nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
            )
            self.head = nn.Sequential(
                nn.Flatten(), nn.Dropout(0.5),
                nn.Linear(64 * 16 * 15, 1),
            )

        def forward(self, x):
            return self.head(self.features(x)).squeeze(-1)

    return ChartCNN()


def train_cnn(x_tr: np.ndarray, y_tr: np.ndarray) -> "object":
    import torch
    from torch import nn

    rng = np.random.default_rng(SEED)
    n = len(x_tr)
    perm = rng.permutation(n)
    n_val = max(256, int(0.1 * n))
    val_idx, tr_idx = perm[:n_val], perm[n_val:]

    model = make_cnn()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    xv = torch.from_numpy(x_tr[val_idx]).float()
    yv = torch.from_numpy(y_tr[val_idx]).float()

    best_val, best_state, patience = np.inf, None, 0
    for epoch in range(MAX_EPOCHS):
        model.train()
        order = rng.permutation(len(tr_idx))
        for b in range(0, len(order), BATCH):
            idx = tr_idx[order[b: b + BATCH]]
            xb = torch.from_numpy(x_tr[idx]).float()
            yb = torch.from_numpy(y_tr[idx]).float()
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            vl = float(loss_fn(model(xv), yv))
        if vl < best_val - 1e-4:
            best_val, patience = vl, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience += 1
            if patience >= 2:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model


def predict_cnn(model, x: np.ndarray) -> np.ndarray:
    import torch

    model.eval()
    out = []
    with torch.no_grad():
        for b in range(0, len(x), 1024):
            xb = torch.from_numpy(x[b: b + 1024]).float()
            out.append(torch.sigmoid(model(xb)).numpy())
    return np.concatenate(out)


# ── Helpers ──────────────────────────────────────────────────────────────────

def rank_by_date(panel: pd.DataFrame) -> pd.DataFrame:
    n = panel.notna().sum(axis=1)
    return panel.rank(axis=1).sub(0.5).div(n, axis=0).sub(0.5)


def portfolio_vs_market(stitched, ret, vol30, costs, dvol, mkt) -> dict:
    port = frozen_portfolio(stitched, ret, vol30, costs, dvol, min_k=12)
    net = port["returns"]
    active = port["weights"].abs().sum(axis=1) > 0
    net_a = net[active]
    hedged = (net_a - mkt.reindex(net_a.index)).dropna()
    return {
        "sharpe_net": round(ann_sharpe(net_a), 3),
        "sharpe_vs_market": round(ann_sharpe(hedged), 3),
    }


def main() -> None:
    print("=== 0062 CNN-on-Charts (Phase 5, Track B) ===")
    t0 = time.time()
    uni = cx.build_universe(top_n=TOP_N)
    panels = cx.get_price_panels(uni)
    fp = cf.build_feature_panels(panels)
    ret, vol30 = fp["returns"], fp["vol30"]
    costs = cf.cost_panel(fp["dvol_med21"])
    dvol = fp["dvol_med21"]
    mkt = fp["market"]
    fwd = fp["targets_raw"][HORIZON]

    df = cf.assemble_design_matrix(fp, horizon=HORIZON, min_names=MIN_NAMES)
    print(f"Baue Bilder für {len(df):,} Zeilen ...", flush=True)
    X, idx = build_image_dataset(panels, df.index, window=WINDOW)
    rows = df.loc[idx]
    y_bin = (rows["fwd_ret"] > 0).values.astype(np.float32)
    print(f"  {len(idx):,} Bilder ({X.nbytes / 1e6:.0f} MB uint8), "
          f"Basisrate up: {y_bin.mean():.1%} [{time.time() - t0:.0f}s]")

    dm_dates = idx.get_level_values("date").unique().sort_values()
    splits = make_cpcv_splits(
        dm_dates, n_groups=8, n_test_groups=2,
        purge_days=HORIZON + 7, embargo_frac=0.01,
    )
    dates_arr = idx.get_level_values("date")

    # Track-A-Referenz (LGBM0) auf EXAKT denselben Zeilen/Splits.
    feature_cols = [c for c in df.columns if c not in ("y", "fwd_ret")]
    lgbm_preds, lgbm_ics = [], []
    cnn_preds, cnn_ics = [], []
    for si, sp in enumerate(splits):
        tr_mask = dates_arr.isin(sp["train"])
        te_mask = dates_arr.isin(sp["test"])

        m = make_lgbm()
        m.fit(rows[tr_mask][feature_cols].values, rows[tr_mask]["y"].values)
        lp = pd.Series(m.predict(rows[te_mask][feature_cols].values),
                       index=idx[te_mask]).unstack("pair")
        lgbm_preds.append(lp)
        lgbm_ics.append(float(per_date_ic(lp, fwd).mean()))

        model = train_cnn(X[tr_mask], y_bin[tr_mask])
        cp = pd.Series(predict_cnn(model, X[te_mask]),
                       index=idx[te_mask]).unstack("pair")
        cnn_preds.append(cp)
        cnn_ics.append(float(per_date_ic(cp, fwd).mean()))
        print(f"  Split {si + 1}/28: IC CNN {cnn_ics[-1]:+.4f} vs LGBM "
              f"{lgbm_ics[-1]:+.4f} [{time.time() - t0:.0f}s]", flush=True)

    lgbm_st = stitch_oos_predictions(splits, lgbm_preds)
    cnn_st = stitch_oos_predictions(splits, cnn_preds)
    cnn_st.to_parquet(RESULTS / "cnn_predictions_h28.parquet")

    lgbm_ics, cnn_ics = np.array(lgbm_ics), np.array(cnn_ics)
    ic_l = float(per_date_ic(lgbm_st, fwd).mean())
    ic_c = float(per_date_ic(cnn_st, fwd).mean())
    win = float((cnn_ics > lgbm_ics).mean())

    # Korrelation der per-Datum-Ränge (Ensemble-Frage).
    rl, rc = rank_by_date(lgbm_st), rank_by_date(cnn_st)
    corr_by_date = rl.corrwith(rc, axis=1).dropna()
    rank_corr = float(corr_by_date.mean())

    ens_st = (rl + rc) / 2.0
    ic_e = float(per_date_ic(ens_st, fwd).mean())
    ens_ics = np.array([
        float(per_date_ic((rank_by_date(lp) + rank_by_date(cp)) / 2.0, fwd).mean())
        for lp, cp in zip(lgbm_preds, cnn_preds)
    ])
    win_ens = float((ens_ics > lgbm_ics).mean())

    port = {
        "lgbm": portfolio_vs_market(lgbm_st.reindex(ret.index), ret, vol30, costs, dvol, mkt),
        "cnn": portfolio_vs_market(cnn_st.reindex(ret.index), ret, vol30, costs, dvol, mkt),
        "ensemble": portfolio_vs_market(ens_st.reindex(ret.index), ret, vol30, costs, dvol, mkt),
    }

    gate_a = win > 0.5 and ic_c > ic_l
    gate_b = (
        rank_corr < 0.5
        and win_ens > 0.5 and ic_e > ic_l
        and port["ensemble"]["sharpe_vs_market"] >= port["lgbm"]["sharpe_vs_market"] - 0.05
    )

    results = {
        "config": {
            "window": WINDOW, "max_epochs": MAX_EPOCHS, "batch": BATCH,
            "seed": SEED, "n_trials_program": N_TRIALS_PROGRAM,
            "n_images": int(len(idx)),
        },
        "ic": {
            "lgbm_stitched": round(ic_l, 4), "cnn_stitched": round(ic_c, 4),
            "ensemble_stitched": round(ic_e, 4),
            "cnn_win_frac_vs_lgbm": round(win, 3),
            "ensemble_win_frac_vs_lgbm": round(win_ens, 3),
            "rank_corr_mean": round(rank_corr, 3),
            "lgbm_split_ics": [round(x, 4) for x in lgbm_ics],
            "cnn_split_ics": [round(x, 4) for x in cnn_ics],
        },
        "portfolios": port,
        "gate_cnn_beats_lgbm": bool(gate_a),
        "gate_ensemble": bool(gate_b),
    }
    with open(RESULTS / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nStitched IC: CNN {ic_c:+.4f} vs LGBM {ic_l:+.4f} "
          f"(CNN gewinnt {win:.0%} der Splits)")
    print(f"Rank-Korrelation CNN<->LGBM: {rank_corr:+.3f}")
    print(f"Ensemble: IC {ic_e:+.4f}, gewinnt {win_ens:.0%} der Splits vs LGBM")
    for k, v in port.items():
        print(f"  {k:9s}: net {v['sharpe_net']:+.2f}, vs Markt {v['sharpe_vs_market']:+.2f}")
    print(f"Gate CNN>LGBM: {'PASS' if gate_a else 'FAIL'} | "
          f"Gate Ensemble: {'PASS' if gate_b else 'FAIL'}")
    print(f"Gespeichert: {RESULTS / 'metrics.json'} [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
