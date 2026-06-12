"""0063 — Football Value Betting, Phase 0+1 (Roadmap FOOTBALL-VALUE-BETTING).

Pinnacle als Orakel: de-viggte Pinnacle-Quoten = faire Wahrscheinlichkeiten.
Wette beim Soft Book (Bet365), wenn dessen Quote über der fairen liegt.
Beweis-Metrik ist CLV (Quote vs de-viggte Pinnacle-SCHLUSSlinie), nicht P&L.

Vorab registriertes Design:

- **Daten:** football-data.co.uk, 7 Ligen (E0/E1/D1/D2/SP1/I1/F1) x
  7 Saisons (2019/20-2025/26 — Pinnacle-Closing erst ab 2019/20).
- **Phase-0-Gate:** De-Vig reproduziert Pinnacle-Margen (~2-6%); Methoden-
  Vergleich multiplicative/Shin/power per Brier + Log-Loss auf der
  de-viggten SCHLUSSlinie gegen Ergebnisse. Beste Methode = Headline.
- **Signal (look-ahead-frei):** fair_p aus de-viggter Pinnacle-Quote zur
  COLLECTION-Zeit (PSH/PSD/PSA, Fr/Di nachmittags — gleiche Zeit wie die
  B365-Quoten). Schlusslinie (PSC*) NUR zur CLV-Messung.
- **Regel:** Wette Outcome i, wenn ``B365_i * fair_p_i - 1 > Schwelle``;
  Schwellen-Scan [2%, 3%, 4%, 5%] (registrierte Trials), Headline 3%.
- **Daten-Fehler-Guard:** EV > 20% = mutmaßlicher Quoten-Tippfehler in der
  CSV -> ausgeschlossen, Anzahl berichtet.
- **Einsatz:** flat 1 Einheit (Kelly erst Phase 2+).
- **Kosten:** beide Steuer-Szenarien — 0% (absorbierendes Buch) und 5,3%
  auf den Einsatz; Slippage-Szenario 1% schlechtere Quote.
- **Phase-1-Gate:** Median-CLV > 0 über >= 2 Saisons UND >= 3 Ligen;
  Bootstrap-KI des Median-CLV schließt 0 aus.

Trials dieses Laufs: 3 De-Vig-Methoden x 4 Schwellen = 12.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.clv import clv, clv_summary  # noqa: E402
from quantlab.devig import METHODS, devig, margin  # noqa: E402
from quantlab.football_data import get_matches  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

DIVISIONS = ["E0", "E1", "D1", "D2", "SP1", "I1", "F1"]
SEASONS = ["1920", "2021", "2122", "2223", "2324", "2425", "2526"]
THRESHOLDS = [0.02, 0.03, 0.04, 0.05]
HEADLINE_THRESHOLD = 0.03
TAX = 0.053
SLIPPAGE = 0.01
EV_CAP = 0.20

OUTCOMES = ["H", "D", "A"]
PS = ["PSH", "PSD", "PSA"]
PSC = ["PSCH", "PSCD", "PSCA"]
B365 = ["B365H", "B365D", "B365A"]


def load_panel() -> pd.DataFrame:
    df = get_matches(DIVISIONS, SEASONS)
    need = PS + PSC + B365 + ["FTR"]
    n_raw = len(df)
    df = df.dropna(subset=need).reset_index(drop=True)
    print(f"Panel: {len(df)} Spiele mit vollen Quoten (von {n_raw} geladen)")
    return df


def calibration_table(df: pd.DataFrame) -> pd.DataFrame:
    """Brier/Log-Loss der drei De-Vig-Methoden auf der Pinnacle-Schlusslinie."""
    y = pd.get_dummies(df["FTR"])[OUTCOMES].to_numpy(float)
    odds_close = df[PSC].to_numpy(float)
    rows = []
    for method in METHODS:
        p = devig(odds_close, method=method)
        ok = np.isfinite(p).all(axis=1)
        brier = ((p[ok] - y[ok]) ** 2).sum(axis=1).mean()
        logloss = -np.log(np.clip((p[ok] * y[ok]).sum(axis=1), 1e-12, 1)).mean()
        rows.append({"method": method, "brier": brier, "log_loss": logloss, "n": int(ok.sum())})
    return pd.DataFrame(rows).set_index("method")


def build_bets(df: pd.DataFrame, method: str, measure_method: str = "shin") -> pd.DataFrame:
    """Long-Format: eine Zeile je (Spiel, Outcome) mit EV > 0.

    Die CLV-Messung nutzt IMMER die bestkalibrierte Methode (Shin) auf der
    Schlusslinie, unabhängig von der Selektionsmethode — sonst misst z. B.
    multiplicative seine eigenen longshot-inflationierten fairen Probs und
    bucht Schein-CLV (im ersten Lauf +2,7% Schein vs −0,7% ehrlich).
    """
    fair_open = devig(df[PS].to_numpy(float), method=method)
    fair_close = devig(df[PSC].to_numpy(float), method=measure_method)
    b365 = df[B365].to_numpy(float)
    ev = b365 * fair_open - 1.0

    frames = []
    for j, outcome in enumerate(OUTCOMES):
        mask = np.isfinite(ev[:, j]) & (ev[:, j] > 0)
        sub = df.loc[mask, ["Div", "Season", "Date", "HomeTeam", "AwayTeam", "FTR"]].copy()
        sub["outcome"] = outcome
        sub["odds"] = b365[mask, j]
        sub["ev"] = ev[mask, j]
        sub["fair_p_open"] = fair_open[mask, j]
        sub["fair_p_close"] = fair_close[mask, j]
        sub["win"] = (sub["FTR"] == outcome).astype(float)
        frames.append(sub)
    bets = pd.concat(frames, ignore_index=True)

    bets["clv"] = clv(bets["odds"].to_numpy(), bets["fair_p_close"].to_numpy())
    # Flat 1 Einheit: Brutto-PnL, Steuer auf den Einsatz, Slippage auf die Quote.
    bets["pnl_gross"] = bets["odds"] * bets["win"] - 1.0
    bets["pnl_tax"] = bets["pnl_gross"] - TAX
    odds_slip = 1.0 + (bets["odds"] - 1.0) * (1.0 - SLIPPAGE)
    bets["pnl_slip"] = odds_slip * bets["win"] - 1.0
    bets["suspect"] = bets["ev"] > EV_CAP
    return bets


def roi_with_ci(pnl: np.ndarray, n_boot: int = 10_000, seed: int = 1) -> dict:
    pnl = np.asarray(pnl, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pnl), size=(n_boot, len(pnl)))
    boot = pnl[idx].mean(axis=1)
    return {
        "roi": float(pnl.mean()),
        "roi_ci_low": float(np.percentile(boot, 2.5)),
        "roi_ci_high": float(np.percentile(boot, 97.5)),
    }


def evaluate(bets: pd.DataFrame, threshold: float) -> dict:
    sel = bets[(bets["ev"] > threshold) & ~bets["suspect"]]
    if len(sel) < 30:
        return {"n_bets": int(len(sel))}
    out = {
        "n_bets": int(len(sel)),
        "n_suspect_excluded": int(((bets["ev"] > threshold) & bets["suspect"]).sum()),
        "avg_odds": float(sel["odds"].mean()),
        "win_rate": float(sel["win"].mean()),
        "clv": clv_summary(sel["clv"].to_numpy()),
        "roi_gross": roi_with_ci(sel["pnl_gross"].to_numpy()),
        "roi_tax": roi_with_ci(sel["pnl_tax"].to_numpy()),
        "roi_slip": roi_with_ci(sel["pnl_slip"].to_numpy()),
    }
    return out


def gate_breakdown(bets: pd.DataFrame, threshold: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    sel = bets[(bets["ev"] > threshold) & ~bets["suspect"]]
    by_div = sel.groupby("Div").agg(
        n=("clv", "size"), median_clv=("clv", "median"),
        roi_gross=("pnl_gross", "mean"), roi_tax=("pnl_tax", "mean"),
    )
    by_season = sel.groupby("Season").agg(
        n=("clv", "size"), median_clv=("clv", "median"),
        roi_gross=("pnl_gross", "mean"), roi_tax=("pnl_tax", "mean"),
    )
    return by_div, by_season


def main() -> None:
    df = load_panel()

    # ---- Phase 0: Margen-Check + De-Vig-Kalibrierung -----------------------
    m_open = margin(df[PS].to_numpy(float))
    m_close = margin(df[PSC].to_numpy(float))
    m_b365 = margin(df[B365].to_numpy(float))
    print("\n=== Phase 0: Margen (Median) ===")
    print(f"Pinnacle open  : {np.median(m_open):.4f}")
    print(f"Pinnacle close : {np.median(m_close):.4f}")
    print(f"Bet365         : {np.median(m_b365):.4f}")

    calib = calibration_table(df)
    print("\n=== Phase 0: De-Vig-Kalibrierung (Pinnacle-Schlusslinie) ===")
    print(calib.to_string(float_format=lambda x: f"{x:.6f}"))
    best_method = calib["brier"].idxmin()
    print(f"\nBeste Methode (Brier): {best_method}")

    # ---- Phase 1: Backtest über Methoden x Schwellen -----------------------
    metrics: dict = {
        "panel": {
            "n_matches": int(len(df)),
            "divisions": DIVISIONS,
            "seasons": SEASONS,
            "margin_median": {
                "pinnacle_open": float(np.median(m_open)),
                "pinnacle_close": float(np.median(m_close)),
                "bet365": float(np.median(m_b365)),
            },
        },
        "calibration": calib.reset_index().to_dict(orient="records"),
        "best_method": best_method,
        "n_trials": len(METHODS) * len(THRESHOLDS),
        "grid": {},
    }

    print("\n=== Phase 1: Methoden x Schwellen (Median-CLV / ROI brutto / ROI 5,3% Steuer) ===")
    all_bets: dict[str, pd.DataFrame] = {}
    for method in METHODS:
        bets = build_bets(df, method)
        all_bets[method] = bets
        for thr in THRESHOLDS:
            res = evaluate(bets, thr)
            metrics["grid"][f"{method}_thr{thr:.2f}"] = res
            if res.get("n_bets", 0) >= 30:
                print(
                    f"{method:>15} thr {thr:.0%}: n={res['n_bets']:>5}  "
                    f"CLV med {res['clv']['median']:+.4f} "
                    f"[{res['clv']['median_ci_low']:+.4f},{res['clv']['median_ci_high']:+.4f}]  "
                    f"ROI {res['roi_gross']['roi']:+.4f}  "
                    f"ROI(Steuer) {res['roi_tax']['roi']:+.4f}"
                )

    # ---- Gate-Auswertung auf der Headline-Zelle ----------------------------
    bets = all_bets[best_method]
    by_div, by_season = gate_breakdown(bets, HEADLINE_THRESHOLD)
    print(f"\n=== Gate: {best_method} @ {HEADLINE_THRESHOLD:.0%} — je Liga ===")
    print(by_div.to_string(float_format=lambda x: f"{x:+.4f}"))
    print(f"\n=== je Saison ===")
    print(by_season.to_string(float_format=lambda x: f"{x:+.4f}"))

    n_div_pos = int((by_div["median_clv"] > 0).sum())
    n_season_pos = int((by_season["median_clv"] > 0).sum())
    headline = metrics["grid"][f"{best_method}_thr{HEADLINE_THRESHOLD:.2f}"]
    ci_excludes_zero = headline["clv"]["median_ci_low"] > 0
    gate_pass = n_div_pos >= 3 and n_season_pos >= 2 and ci_excludes_zero
    print(
        f"\nGate Phase 1: Ligen mit Median-CLV>0: {n_div_pos}/{len(by_div)}, "
        f"Saisons: {n_season_pos}/{len(by_season)}, "
        f"KI>0: {ci_excludes_zero} -> {'PASS' if gate_pass else 'FAIL'}"
    )

    metrics["gate"] = {
        "headline": f"{best_method} @ {HEADLINE_THRESHOLD:.0%}",
        "divisions_positive_clv": n_div_pos,
        "seasons_positive_clv": n_season_pos,
        "clv_ci_excludes_zero": bool(ci_excludes_zero),
        "pass": bool(gate_pass),
        "by_division": by_div.reset_index().to_dict(orient="records"),
        "by_season": by_season.reset_index().to_dict(orient="records"),
    }

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    sel = bets[(bets["ev"] > HEADLINE_THRESHOLD) & ~bets["suspect"]]
    sel.to_csv(RESULTS / "trades.csv", index=False)
    print(f"\nGespeichert: results/metrics.json, results/trades.csv ({len(sel)} Wetten)")


if __name__ == "__main__":
    main()
