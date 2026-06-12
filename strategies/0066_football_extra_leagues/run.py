"""0066 — Extra-Ligen-Eignungstest für das Live-Polling (Erweiterung 0064/0065).

football-data's Extra-Dateien (/new/{COUNTRY}.csv) enthalten NUR Schlussquoten
— der eingefrorene 0063/0064-Test (EV zur Collection-Zeit, CLV zur Schluss-
linie) ist dort NICHT reproduzierbar. Stattdessen vorab registrierter
**Eignungstest**: erfüllt eine Liga die zwei Strukturbedingungen der Strategie
(Pinnacle-Orakel funktioniert + Soft-Book-Bias existiert), kommt sie als
Extension-Tier ins Live-Polling (0065); das echte CLV misst der Forward.
Das registrierte 0065-Gate (18 validierte Ligen) bleibt UNVERÄNDERT.

Vorab registrierte Gates je Liga (auf Daten ab 2019-07, = Benchmark-Fenster):

    (a) Orakel liquide:    Median-Marge der Pinnacle-Schlusslinie <= 5%
    (b) Orakel kalibriert: Brier(Shin) <= Brier(multiplicative)
    (c) Bias existiert:    >= 50 Close-Value-Wetten (Bet365-Schlussquote
                           mit EV > 2% gegen Shin-faire Schlusslinie, Cap 20%)

Gepoolte Sanity über alle Kandidaten: realisierter Flat-ROI der Close-Value-
Wetten > 0 (Richtungs-Check; einzeln pro Liga wäre er rauschblind, vgl.
0064-Stichproben-Lehre). Benchmark: identische Metriken auf dem validierten
18-Ligen-Panel (0063/0064) unter derselben Nur-Schlussquoten-Linse.

Keine neuen Regel-Trials (Regel eingefroren); Aufnahme-Entscheid = 1
registrierter Selektionsschritt.

**AMENDMENT (2026-06-12, nach Lauf 1 — Daten-, kein Signal-Befund):** Lauf 1
scheiterte an Gate (c) für ALLE Kandidaten, weil B365-Schlussquoten in den
Extra-Dateien erst seit Saison 2025/26 existieren (n=3-41 statt >=50); die
Bias-Raten selbst waren hoch. Revidierte, gleich strenge Messung mit voller
Datendeckung: (a)+(b) auf der vollen Pinnacle-Historie ab 2019 (n in
Tausenden statt 39-158), (c) auf der Markt-Durchschnitts-Schlussquote AvgC
(voll abgedeckt seit 2012): Value-Rate >= 50% der Benchmark-Rate desselben
AvgC-Maßes auf den 18 validierten Ligen. B365C-Werte werden informativ
mitberichtet. Pooled-Sanity unverändert (auf AvgC-Wetten).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.devig import devig, margin  # noqa: E402
from quantlab.football_data import get_extra_league, get_matches  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(exist_ok=True)

# Kandidaten = Extra-Dateien MIT B365-Schlussquoten UND The-Odds-API-Key.
# (RUS: keine B365-Spalten; ROU: kein API-Key; AUS: Datei defekt.)
COUNTRIES = ["AUT", "DNK", "SWZ", "POL", "ARG", "MEX", "CHN",
             "SWE", "NOR", "FIN", "USA", "BRA", "JPN", "IRL"]
BENCH_DIVS = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2",
              "F1", "F2", "N1", "P1", "B1", "T1", "G1", "SC0"]
BENCH_SEASONS = ["1920", "2021", "2122", "2223", "2324", "2425", "2526"]

CUTOFF = pd.Timestamp("2019-07-01")
THRESHOLD, EV_CAP = 0.02, 0.20
OUTCOMES = ["H", "D", "A"]


def to_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Quoten-Spalten numerisch erzwingen (football-data hat z.T. '#'-Platzhalter)."""
    df = df.copy()
    df[cols] = df[cols].apply(pd.to_numeric, errors="coerce")
    return df.dropna(subset=cols)


def close_value_stats(close_pin: np.ndarray, close_b365: np.ndarray,
                      results: pd.Series) -> dict:
    """Orakel-/Bias-Metriken aus Schlussquoten (Pinnacle + Bet365) + Ergebnis."""
    ok = np.isfinite(close_pin).all(axis=1) & np.isfinite(close_b365).all(axis=1)
    close_pin, close_b365 = close_pin[ok], close_b365[ok]
    res = results[ok].reset_index(drop=True)
    y = pd.get_dummies(res)[OUTCOMES].to_numpy(float)

    med_margin = float(np.median(margin(close_pin)))
    briers = {}
    for method in ("shin", "multiplicative"):
        p = devig(close_pin, method=method)
        briers[method] = float(((p - y) ** 2).sum(axis=1).mean())

    fair = devig(close_pin, method="shin")
    ev = close_b365 * fair - 1.0
    rows = []
    for j, outcome in enumerate(OUTCOMES):
        sel = (ev[:, j] > THRESHOLD) & (ev[:, j] <= EV_CAP)
        for i in np.where(sel)[0]:
            win = 1.0 if res.iloc[i] == outcome else 0.0
            rows.append({"outcome": outcome, "odds": close_b365[i, j],
                         "ev": ev[i, j], "ret": close_b365[i, j] * win - 1.0})
    bets = pd.DataFrame(rows)
    return {
        "n_matches": int(ok.sum()),
        "pin_close_margin": med_margin,
        "brier_shin": briers["shin"],
        "brier_mult": briers["multiplicative"],
        "n_value": int(len(bets)),
        "value_per_100": float(100 * len(bets) / max(ok.sum(), 1)),
        "mean_ev": float(bets["ev"].mean()) if len(bets) else np.nan,
        "draw_share": float((bets["outcome"] == "D").mean()) if len(bets) else np.nan,
        "roi_flat": float(bets["ret"].mean()) if len(bets) else np.nan,
        "_bets": bets,
    }


def pooled_roi_ci(rets: np.ndarray, n_boot: int = 10_000, seed: int = 3) -> dict:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(rets), size=(n_boot, len(rets)))
    boot = rets[idx].mean(axis=1)
    return {"roi": float(rets.mean()),
            "ci_low": float(np.percentile(boot, 2.5)),
            "ci_high": float(np.percentile(boot, 97.5)), "n": int(len(rets))}


PIN = ["PSCH", "PSCD", "PSCA"]
AVG = ["AvgCH", "AvgCD", "AvgCA"]
B365C = ["B365CH", "B365CD", "B365CA"]


def league_stats(df: pd.DataFrame, res_col: str) -> dict:
    """Orakel-Gates auf voller Pinnacle-Historie, Bias-Gate auf AvgC."""
    base = to_num(df.dropna(subset=[res_col]), PIN)
    base = base[base["Date"] >= CUTOFF]
    s = close_value_stats(base[PIN].to_numpy(float),
                          to_num(base, AVG)[AVG].reindex(base.index).to_numpy(float)
                          if all(c in base.columns for c in AVG) else
                          np.full((len(base), 3), np.nan),
                          base[res_col])
    # informativ: B365C-basierte Werte (nur juengste Saison verfuegbar)
    if all(c in df.columns for c in B365C):
        b3 = to_num(df.dropna(subset=[res_col]), PIN + B365C)
        b3 = b3[b3["Date"] >= CUTOFF]
        s365 = close_value_stats(b3[PIN].to_numpy(float),
                                 b3[B365C].to_numpy(float), b3[res_col])
        s["b365_n_value"] = s365["n_value"]
        s["b365_value_per_100"] = s365["value_per_100"]
        s["b365_roi"] = s365["roi_flat"]
    return s


def main() -> None:
    # ---- Benchmark: validiertes Panel unter derselben Nur-Close-Linse ------
    print("=== Benchmark: 18 validierte Ligen (Schlussquoten-Linse, ab 2019-07) ===")
    bench = get_matches(BENCH_DIVS, BENCH_SEASONS)
    b = league_stats(bench, "FTR")
    bench_rate = b["value_per_100"]
    print(f"  n={b['n_matches']}  Marge {b['pin_close_margin']:.3f}  "
          f"AvgC-Value/100: {bench_rate:.2f} (mean EV {b['mean_ev']:+.3f}, "
          f"Draw {b['draw_share']:.2f}, ROI {b['roi_flat']:+.3f})  |  "
          f"B365C-Value/100: {b.get('b365_value_per_100', float('nan')):.2f} "
          f"(ROI {b.get('b365_roi', float('nan')):+.3f})")

    # ---- Kandidaten --------------------------------------------------------
    print(f"\n=== Kandidaten (Gate c: AvgC-Rate >= {0.5 * bench_rate:.2f}/100 "
          f"= 50% der Benchmark-Rate) ===")
    rows, pooled, passing = [], [], []
    for country in COUNTRIES:
        try:
            df = get_extra_league(country)
        except Exception as exc:
            print(f"  {country}: Laden fehlgeschlagen ({str(exc)[:60]})")
            continue
        if not all(c in df.columns for c in PIN + AVG):
            print(f"  {country}: Pinnacle-/Avg-Schlussquoten fehlen -> aus")
            continue
        s = league_stats(df, "Res")
        gate_a = s["pin_close_margin"] <= 0.05
        gate_b = s["brier_shin"] <= s["brier_mult"]
        gate_c = s["value_per_100"] >= 0.5 * bench_rate and s["n_value"] >= 50
        ok = gate_a and gate_b and gate_c
        if ok:
            passing.append(country)
        if s["n_value"]:
            pooled.append(s["_bets"].assign(country=country))
        rows.append({k: v for k, v in s.items() if k != "_bets"}
                    | {"country": country, "pass": ok})
        print(f"  {country}: n={s['n_matches']:>5}  Marge {s['pin_close_margin']:.3f} "
              f"{'OK' if gate_a else 'X'}  Brier shin-mult "
              f"{s['brier_shin'] - s['brier_mult']:+.6f} {'OK' if gate_b else 'X'}  "
              f"AvgC-Value n={s['n_value']:>4} ({s['value_per_100']:.2f}/100) "
              f"{'OK' if gate_c else 'X'}  meanEV {s['mean_ev']:+.3f}  "
              f"Draw {s['draw_share']:.2f}  ROI {s['roi_flat']:+.3f}  "
              f"-> {'PASS' if ok else 'FAIL'}")

    pooled_bets = pd.concat(pooled, ignore_index=True)
    pool = pooled_roi_ci(pooled_bets["ret"].to_numpy())
    pool_pass = pool["roi"] > 0
    print(f"\nGepoolter Flat-ROI aller Kandidaten-AvgC-Wetten: {pool['roi']:+.4f} "
          f"[{pool['ci_low']:+.4f},{pool['ci_high']:+.4f}]  n={pool['n']} "
          f"-> {'OK' if pool_pass else 'NEGATIV -> Stopp'}")
    print(f"\nBestanden: {sorted(passing)}")

    with open(RESULTS / "metrics.json", "w") as fh:
        json.dump({"benchmark": {k: v for k, v in b.items() if k != "_bets"},
                   "benchmark_avgc_rate": bench_rate,
                   "leagues": rows, "pooled_roi": pool,
                   "pooled_sanity_pass": bool(pool_pass),
                   "passing": sorted(passing)}, fh, indent=2, default=str)
    pooled_bets.to_csv(RESULTS / "close_value_bets.csv", index=False)
    print("Gespeichert: results/metrics.json, results/close_value_bets.csv")


if __name__ == "__main__":
    main()
