# Roadmap: ML-Signalgenerierung auf Commodity-Futures (für Claude Code)

> Handoff für Claude Code. Ziel: ML *generiert* Signale (nicht nur Meta-Labeling
> bestehender). Baut auf der `Backtests`-Pipeline auf. Hardware: MacBook Air
> (LightGBM auf Tages-/Wochendaten für ~30 Instrumente = Sekunden bis Minuten).
> Nur Gratis-/vorhandene Tools. Stand: Juni 2026.
> Alle Effekte sind Hypothesen zum Validieren, keine Anlageberatung.

---

## Teil 0 — Edge-These (ehrlich, bevor wir bauen)

ML findet hier **keine magischen Muster, die Menschen nicht sehen**. Die
dokumentierte Edge ist enger und realistischer:

> ML kombiniert **bekannte Rohstoff-Risikoprämien** (Carry, Basis,
> Basis-Momentum, Momentum, Hedging Pressure) **nichtlinear und
> zustandsabhängig** — in einem Markt, der weniger von Faktor-ML-Fonds
> überlaufen ist als der Aktien-Cross-Section.

Die Alpha-Quelle ist dreifach: (a) Qualität des theoriegetriebenen
Feature-Engineerings, (b) nichtlineare Interaktionen, die lineare Faktormodelle
verpassen (GBT fängt sie), (c) das weniger institutionalisierte Rohstoff-Universum.

**Realistische Erwartung:** Auch das kann ein Null-Ergebnis liefern — aber ein
*gut begründetes* Null, kein blindes Feature-Mining. Wenn es trägt, ist es eine
zweite, von deiner Saisonalität unkorrelierte Edge-Familie. Das ist der Sinn.

**Warum nicht Deep Learning:** LSTM/Transformer überanpassen verrauschte
Finanzdaten, brauchen mehr Daten als du hast, und schlagen GBT auf tabellarischen
Features nicht. LightGBM ist in der Commodity-Literatur durchgängig das beste
Modell (Wang & Zhang 2024). NN nur als Vergleichsmodell in der letzten Phase.

---

## Teil 1 — Modell-Stack

| Rolle | Modell | Zweck |
| --- | --- | --- |
| **Pflicht-Benchmark** | Ridge / Elastic Net | Wenn GBT das nicht schlägt → bei linear bleiben (Ockham) |
| **Workhorse** | LightGBM (Regressor + Ranker) | Nichtlineare Interaktionen, SHAP-interpretierbar |
| **Zweitmeinung** | Random Forest / XGBoost | Ensemble-Diversität |
| **Vergleich (Phase 4)** | kleines MLP (PyTorch-MPS) | nur um zu zeigen, dass es NICHT besser ist |
| Tuning | Optuna (TPE + pruning) | jeder Trial zählt in den DSR |
| Erklärbarkeit | SHAP (TreeExplainer) | Feature-Stabilität über Folds |

---

## Teil 2 — Universum & Daten (der eigentliche Engpass)

**Universum (~25–30 liquide, prop-/IBKR-handelbare Futures):**
- Energie: CL, NG, HO, RB, BZ
- Metalle: GC, SI, HG, PL, PA
- Getreide/Oilseeds: ZC, ZW, ZS, ZL, ZM
- Softs: SB, KC, CC, CT, OJ
- Vieh: LE, GF, HE
- (optional erweiterbar, je Datenlage)

**Datenschichten:**

| Daten | Quelle | Kosten | Zweck |
| --- | --- | --- | --- |
| **Terminstruktur** (Front + ≥1 Deferred) | **Databento GLBX** (Pipeline existiert) | Gratis-Credits | Carry, Basis, Basis-Momentum — ohne das geht der halbe Feature-Satz nicht |
| Continuous-Preise + Roll | vorhandener Loader + `roll.py` | – | Returns, Momentum, Vol |
| **COT (Commitments of Traders)** | **CFTC** (wöchentlich) | **gratis** | Hedging-Pressure-Feature |
| Makro | FRED | gratis | Dollar-Index, Realzins, Term-Spread, VIX |
| Lagerbestände (optional) | EIA (Energie), USDA (Ags) | gratis | fundamentale Features (vgl. Alt-Data-Roadmap) |

**Kritisch:** Ohne Terminstruktur kein Carry/Basis → kein echter Rohstoff-Edge,
nur Momentum auf Continuous (das hast du quasi schon). Erste Engineering-Aufgabe
ist daher der `term_structure.py`-Loader aus Databento: pro Tag und Commodity
mindestens Front- und Second-Month-Settlement, daraus die abgeleiteten Features.

---

## Teil 3 — Features (theoriegetrieben, jede mit Ökonomik)

| Feature | Definition | Ökonomische Ursache |
| --- | --- | --- |
| **Carry / Roll-Yield** | (F_front − F_deferred)/F_deferred, annualisiert | Lagerhaltungstheorie: Backwardation = Knappheitsprämie |
| **Basis** | (Spot − Future)/Future bzw. Front/Deferred-Spread | Convenience Yield, Storage Costs |
| **Basis-Momentum** | Differenz der Returns von Front- vs. Deferred-Leg über k Monate (Boons & Prado 2019) | fängt Variation der Risikoprämie, die Basis allein verpasst |
| **Time-Series-Momentum** | 1/3/6/12M Return | Underreaction, langsame Info-Diffusion |
| **Cross-Sectional-Momentum** | Return-Rang vs. Universum | relative Stärke (Miffre & Rallis) |
| **Hedging Pressure** | Netto-Short-Position Commercials / Open Interest (COT) | Risikotransfer: Hedger zahlen Prämie an Spekulanten (Keynes) |
| **Skewness** | realisierte Schiefe der Tagesreturns, 1J | Lotterie-Präferenz → negative-skew-Prämie (Bakshi et al.) |
| **Open-Interest-Trend** | Δ Open Interest | Bestätigung/Erschöpfung von Flows |
| **Vol-Regime** | realisierte 20/60d-Vol, Vol-Perzentil | Konditionierung, Sizing |
| **Makro-Interaktionen** | Dollar-Trend, Realzins, VIX-Regime | gemeinsame Treiber über Rohstoffe |

**PIT-Disziplin (Pflicht):** COT wird mit Verzögerung veröffentlicht (Dienstag-
Daten, Freitag-Release) → erst ab Release-Datum nutzbar. Klimatologie/Vol-
Baselines nur aus Vergangenheitsfenstern. Eigener Look-ahead-Unit-Test wie im Repo.

---

## Teil 4 — Target & Portfolio-Design

- **Target:** Forward-Return über mehrere Horizonte (1W / 1M / 3M), **cross-
  sektional rang-transformiert pro Datum** (GKX-Stil) — robust gegen Niveau-Drift
  und gemeinsame Bewegungen.
- **Multi-Horizont-Ensemble:** je Horizont ein Modell, Vorhersagen aggregieren →
  glättet Performance, senkt Turnover (CFA-Befund).
- **Hybrid gegen das Kleine-N-Problem:** zusätzlich **Per-Commodity-Modelle**
  (Wang & Zhang: Top-Faktoren je Rohstoff verschieden) und mit dem Cross-Sectional-
  Modell ensemblen.
- **Portfolio:** Long Top-Quintil, Short Bottom-Quintil, vol-getargetet (gleicher
  Risikobeitrag je Position), wöchentliches/monatliches Rebalancing,
  **Turnover-Penalty + volle Kostenmodelle** (Spread dominiert bei den dünnen
  Softs — OJ/KC/CC — deine BTC-Lehre).

---

## Teil 5 — Validierung: CPCV statt Walk-Forward (der Kern)

Plain Walk-Forward ist hier nicht streng genug. Forschung (Backtest-Overfitting-
Studien 2024) zeigt: **Combinatorial Purged Cross-Validation (CPCV)** liefert
niedrigere Probability of Backtest Overfitting (PBO) und bessere DSR-Statistik.

1. **CPCV (de Prado):** mehrere Train/Test-Splits über kombinatorische Gruppen,
   mit **Purging** (Samples entfernen, deren Label-Fenster ins Testset ragt) und
   **Embargo** (~1–2 % der Zeitachse nach jedem Testblock sperren). Verteilung der
   OOS-Sharpes statt eines Pfades → PBO direkt berechenbar.
2. **DSR mit ehrlichem n_trials:** jeder Optuna-Trial × Feature-Set × Horizont ×
   Modell zählt. (Und: den DSR-Bug aus der Hauptpipeline vorher fixen —
   Per-Period-Sharpe übergeben, `n_trials=1`-Degeneration abfangen.)
3. **Permutationstest:** Labels pro Datum shuffeln → verschwindet die
   Portfolio-Edge? Trennt echte Vorhersage von Glück.
4. **Ridge-Benchmark-Gate:** GBT muss Ridge OOS *klar* schlagen, sonst linear.
5. **SHAP-Stabilität:** Feature-Ranking über CPCV-Folds — springt es, ist es
   Noise-Fitting.
6. **Subperioden-Decay:** Post-2015 und Post-2020 separat (publizierte Faktoren
   decayen).

**Gate für „Kandidat":** PBO < 0,5, OOS-Sharpe-Verteilung mehrheitlich > Ridge,
Permutation p < 0,05, DSR überlebt, Decay moderat, Netto-positiv nach Spread.

---

## Teil 6 — Phasenplan (Deliverables im `strategies/NNNN`-Stil)

| Phase | Ziel | Deliverable | Gate |
| --- | --- | --- | --- |
| **0** | Terminstruktur-Daten | `quantlab/term_structure.py` (Databento) + COT-Loader | Carry/Basis für ≥20 Commodities rechenbar, PIT-Test grün |
| **1** | Feature-Pipeline | `quantlab/commodity_features.py` (alle Features, PIT) | Feature-Matrix reproduzierbar, keine Lecks |
| **2** | Linearer Benchmark | Ridge-Cross-Sectional-L/S | sauberer CPCV-Backtest als Messlatte |
| **3** | LightGBM-Signal | `strategies/00XX_ml_commodity_xsection/` (REPORT.md) | schlägt Ridge in PBO + OOS-Sharpe-Verteilung |
| **4** | Ensemble + Per-Commodity-Hybrid | Multi-Horizont + Hybrid-REPORT | glatter, OOS-stabil, Decay moderat |
| **5** | NN-Vergleich (Negativ-Kontrolle) | kurzer Report | zeigt: NN schlägt GBT NICHT → GBT bleibt |

---

## Teil 7 — `quantlab`-Erweiterungen

- `quantlab/term_structure.py` — Databento-Multi-Kontrakt-Loader, Carry/Basis.
- `quantlab/cot_data.py` — CFTC-COT-Loader, Hedging-Pressure, PIT-Release-Logik.
- `quantlab/commodity_features.py` — alle Features, rang-transformiert, PIT.
- `quantlab/cpcv.py` — Combinatorial Purged CV + PBO-Berechnung.
- `quantlab/ml_portfolio.py` — Rank → Quintil-L/S, Vol-Targeting, Turnover-Kosten.
- Tests: PIT-Look-ahead-Guard, COT-Release-Timing, Roll-Korrektheit.

---

## Teil 8 — Anti-Selbstbetrugs-Checkliste (ML-Commodity-Edition)

- **CPCV, nicht Walk-Forward.** PBO ist die Kennzahl, nicht ein hübscher Pfad.
- **n_trials ehrlich** (Optuna inklusive). ML potenziert Multiple Testing.
- **Ridge ist das Gate.** Wenn GBT linear nicht klar schlägt, ist die
  Nichtlinearität eingebildet.
- **Terminstruktur-Daten korrekt rollen** — Carry-Features sind extrem
  roll-artefakt-anfällig (deine `0029`-Lehre × 10).
- **COT-PIT:** niemals die Dienstagsdaten vor dem Freitagsrelease nutzen.
- **Spread bindet** bei dünnen Softs. Netto-nach-Kosten, immer.
- **Per-Commodity ≠ universell:** kein gemeinsamer Faktor erwartbar; Heterogenität
  ist normal, nicht Bug.
- **Decay einplanen:** publizierte Prämien schrumpfen; Subperioden trennen.
- **Kein NN-FOMO:** wenn das MLP nicht klar gewinnt (wird es nicht), GBT behalten.

---

## Teil 9 — Referenzen

- Wang & Zhang (2024), „Predictability of Commodity Futures Returns with ML",
  *Journal of Futures Markets* — LightGBM bester, AR(1) für manche besser.
- Gu, Kelly & Xiu (2020, RFS) — ML-Asset-Pricing-Methodik, Cross-Section.
- Boons & Prado (2019), „Basis-Momentum", *Journal of Finance*.
- Basu & Miffre (2013), Hedging Pressure, *JBF*.
- Bakshi, Gao & Rossi (2019), Risk sources in commodity returns, *Mgmt Science*.
- CFA Institute (2025), „Machine Learning in Commodity Futures" (Kap. 8).
- Backtest-Overfitting-/CPCV-Literatur (2024) — PBO, DSR, CPCV > Walk-Forward.
- López de Prado, *Advances in Financial ML* — Triple-Barrier, CPCV, DSR.

---

*Reihenfolge wie immer: erst der Beweis (CPCV-/PBO-überlebend, Ridge-schlagend,
Netto-positiv), dann Kapital. Wenn es ein Null wird, ist es ein sauberes Null —
und du weißt, dass die zweite Edge-Familie woanders liegt.*
