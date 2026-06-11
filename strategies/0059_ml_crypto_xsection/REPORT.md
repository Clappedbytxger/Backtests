# Strategie 0059 — Crypto-Cross-Section: LightGBM gegen die Ridge-Messlatte (Roadmap Phase 3)

**Status: testing/Lead — bester ML-Befund des Katalogs, aber KEIN validierter
Edge** (Bootstrap-KI der Marktrelative berührt 0, DSR 0.32, Alpha-Drawdown
2023–24). Erste Strategie im Katalog, die das **Ridge-Gate besteht**.

## Hypothese

Die bekannten Crypto-Faktoren (0058: Momentum, Size, Amihud, Vol, Past-Alpha)
tragen NICHTLINEAR kombiniert (GBT) mehr Querschnitts-Information als linear —
und die 0058-Diagnose „hoher IC monetarisiert nicht" ist mit den vorab
registrierten IC→PnL-Hebeln (Turnover/Konzentration/Liquidität) behebbar.

## Design (vorab registriert, alles gezählt)

- Identische 28 purged CPCV-Splits wie 0058; identische Features/Targets.
- LGBM-Gitter wie 0057 (8 Konfigs, fix), Ridge α=1.0 als Messlatte.
- Hebel-Scan NUR h=28, long-only, symmetrisch auf LGBM und Ridge:
  Rebalance {W, ME} × {Quintil, Dezil} × Buffer-Band {aus, 2×} ×
  Liquiditäts-Floor {aus, $5M} = 16 Varianten/Modell.
- Auswahlregel vorab: höchster netto Hedge-vs-Markt-Sharpe unter den
  LGBM-Hebeln; **n_trials = 62** (0058: 6 + 24 Grid-Bewertungen + 32 Hebel).
- Neue Engine: `ml_portfolio.run_buffered_long_portfolio` (Hold-Band gegen
  Quantilsgrenzen-Churn; Tests: Turnover-Reduktion, Band-Invariante,
  Hellseher-Guard).

## Ergebnisse

### Gate A — LGBM schlägt Ridge: BESTANDEN (alle 3 Horizonte)

| Horizont | Ridge IC | bestes LGBM | LGBM IC | Split-Siege |
|---|---|---|---|---|
| 7d | +0.095 | LGBM0 (15 Blätter, lr 0.05, 100 Bäume) | **+0.104** | **71%** |
| 14d | +0.113 | LGBM0 | **+0.123** | **79%** |
| 28d | +0.137 | LGBM0 | **+0.151** | **89%** |

*(Stand nach dem 0060-Peg-Guard-Rerun — Stablecoins RLUSD/„U" entfernt;
Gate A wurde dadurch leicht STÄRKER, finale Zelle unverändert.)*

Erstmals im Katalog belegbare Nichtlinearität (0057: 25–46% Split-Siege =
Fail). Bemerkenswert: **die KLEINSTE Konfiguration gewinnt durchgängig**;
große Konfigs (31 Blätter × 300 Bäume) verlieren gegen Ridge in bis zu 100%
der Splits — die Nichtlinearität ist real, aber flach; Kapazität muss klein
bleiben.

### Hebel-Scan h=28 — die 0058-Diagnose war richtig

Das Plateau ist monoton und ökonomisch kohärent: **Liquiditäts-Floor ist der
stärkste Hebel** (+0.78 vs +0.42 ohne), dann Dezil > Quintil, Buffer > kein
Buffer, ME ≥ W. Turnover fällt von 22–24×/J auf **6×/J** — die Kosten-Wand
aus 0058 ist damit umgangen. Ridge in der identischen besten Zelle: +0.40 →
der LGBM-Vorsprung (+0.78) überlebt die Portfolio-Übersetzung.

| Variante (h=28, long-only) | netto Sharpe | vs Markt | Turnover |
|---|---|---|---|
| **ME, Dezil, Buffer 2×, Liq ≥ $5M (final)** | **+0.98** | **+0.81** | 6×/J |
| ME, Dezil, kein Buffer, Liq ≥ $5M | +0.96 | +0.76 | 9×/J |
| W, Dezil, Buffer 2×, Liq ≥ $5M | +0.88 | +0.69 | 10×/J |
| … 0058-Baseline (W, Quintil, ohne alles) | +0.58 | −0.55 | 22×/J |

### Volle Batterie auf der finalen Variante

| Test | Ergebnis | Urteil |
|---|---|---|
| PBO (CSCV, 59 Konfigs) | **0.007** | pass — Konfig-Ranking extrem stabil |
| Label-Retrain-Permutation (200) | **p < 0.005**, Null-Mittel −0.32 | pass* |
| Bootstrap-KI Hedge-Sharpe | **[−0.07, +1.20]** | **berührt 0 → fail** |
| DSR (n_trials=62) | **0.36** | **fail** (<0.5) |
| Regime vs Markt | Bull 20-21 **+1.59** / Bear 22 **+1.70** / 2023+ **+0.03** | gemischt |

\* Permutations-Vorbehalt (0057-Lehre): auch die Label-Retrain-Null zahlt
volle Kosten (Mittel −0.30) — p sagt „besser als kostenzahlende
Rausch-Pipeline", der „Edge > 0"-Test ist der Bootstrap, und der scheitert.

### Was die Alpha-Kurve zeigt

Kumulativ +1.2 über 6.2 Jahre vs Markt, **6 von 7 Jahren positiv** — aber
2023 ist ein katastrophales Relativ-Jahr (−3.2; BTC-Dominanz-Ära, Alts tot)
mit ~2 Jahren Unterwasser-Strecke auf der Alpha-Kurve. Kein monotoner Decay
(2025/26 wieder +1.3/+1.5), aber ein Faktor-Crash-Risiko, das Sharpe/IC nicht
zeigen.

## Ehrliche Vorbehalte

1. **CPCV-Stitch ist kein handelbarer Pfad:** Modelle, die 2020 vorhersagen,
   sind (purged) auch auf 2021–2026 trainiert. CPCV beantwortet
   Modellvergleich + Skill-Schätzung; der handelbare Beweis ist nur
   Walk-Forward/Live.
2. **Konzentration:** Dezil × $5M-Floor = Median **8 Namen** (min. 2!) —
   idiosynkratisches Risiko; ein 2-Namen-Buch ist kein Querschnitt mehr.
3. Buch startet erst 2020-03 (Floor + Feature-Warmup) — kein 2019, und der
   Start fällt auf den COVID-Boden.
4. Benchmarks friktionslos; Delisting-Limbo neutral (0058).
5. Erbt CMC-Mcap-/Mapping-Imperfektionen aus 0058.

## Verdikt & nächste Schritte

**Ridge-Gate bestanden, Mechanismus kohärent, aber als Edge nicht validiert**
(Bootstrap-KI mit 0, DSR 0.32, 2023-Crash). Einstufung **testing/Lead** —
deutlich über 0057 (sauberes Null), unter den bestätigten Saison-Leads.

Vorab registrierte nächste Schritte (Reihenfolge):
1. **Live-/Walk-Forward** der eingefrorenen finalen Regel (LGBM0 h28, ME,
   Dezil, Buffer 2×, Liq ≥ $5M; monatlich, ~6 Trades/J Aufwand) — der
   einzige Test, der den CPCV-Vorbehalt schließt. Regel eingefroren
   2026-06-11.
2. Konzentrations-Fix als EIN registrierter Versuch: Mindest-Buchgröße 12
   (q dynamisch) — erst nach Live-Start, nicht rückwirkend optimieren.
3. Phase 4 (On-Chain/Funding) nur als inkrementeller Test gegen DIESE
   Messlatte; Phase 5 (CNN) erst nach gemeinsamem Review.

## Artefakte

`results/metrics.json` (Gates, Grid, Hebel, DSR), `results/permutation.json`
(200 Label-Retrain-Perms), `lgbm_best_predictions_h{7,14,28}.parquet`,
`final_hedged_returns.parquet`, `gate_a_ic.png`, `final_equity_alpha.png`;
`analyze_final.py` (Jahres-/Plateau-Tabellen), `run_permutation.py`.
