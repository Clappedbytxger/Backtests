# Strategie 0060 — Walk-Forward der eingefrorenen 0059-Regel (+ Konzentrations-Fix)

**Status: testing — der ehrliche Pfad bestätigt Richtung und Modell-Vorsprung,
bleibt aber statistisch unbewiesen.** Dazu ein kritischer Universums-Bug
gefunden und gefixt (Stablecoin-Kontamination), der die Vorgänger-Zahlen
LEICHT GESCHÖNT hatte.

## Zweck

0059-Vorbehalt schließen: der CPCV-Stitch ist kein handelbarer Pfad (Modelle
für 2020 sahen 2021–26). Hier läuft die am 2026-06-11 eingefrorene Regel als
echter Walk-Forward: **monatlicher Refit, expanding window, Training nur auf
Zeilen mit bei Refit-Zeitpunkt realisiertem Label (Datum ≤ t−28d), erster Fit
2020-12-31** → out-of-time-Pfad 2021-02 … 2026-06 (5.4 Jahre). Ridge α=1.0 im
identischen Protokoll als Gate-Kontrolle.

## Der Stablecoin-Fund (wichtigste Einzellehre dieses Schritts)

Das Live-Buch der Regel hielt **95% in RLUSD („Ripple USD") + U („United
Stables")** — zwei Stablecoins, die 2025/26 in die CMC-Top-150 aufstiegen und
in der Namens-Exclusion fehlten. Die inverse-Vol-Gewichtung lässt ein
Quasi-Null-Vol-Asset das Buch schlucken (verstecktes Cash). Fix zweischichtig:
Namensliste ergänzt + **struktureller Peg-Guard** (Mitglied nur bei trailing
60d-Vol ≥ 10% p.a., PIT-safe) — fängt künftige Stablecoins automatisch
(`tests/test_crypto_pegged_guard.py`). **Effekt ehrlich beziffert:** der
Walk-Forward des 12er-Buchs fiel durch den Fix von +0.78 auf **+0.64 vs
Markt** — die „Cash-Position" hatte 2025/26 geschmeichelt. Alle Studien
(0058/0059/0060) wurden mit bereinigtem Universum neu gerechnet; 0059-Gates
und finale Zelle blieben unverändert (Gate A sogar stärker: 71/79/89%
Split-Siege).

## Ergebnisse (Walk-Forward, netto, 2021-02 … 2026-06)

**OOT-IC: LGBM +0.138 vs Ridge +0.130** (vs CPCV +0.151/+0.137 — milder
Haircut); LGBM gewinnt 56% der 280 Wochen.

| | LGBM eingefroren (8er-Buch) | **LGBM min-Buch-12** | Ridge, gleiche Regel |
|---|---|---|---|
| Sharpe netto | +0.52 | **+0.59** | +0.32 |
| CAGR netto | +12.7% | **+18.4%** | −0.6% |
| MaxDD | −72% | −73% | −80% |
| vs Markt (Hedge-Sharpe) | +0.38 | **+0.64** | **−0.15** |
| Bootstrap-KI | [−0.50, +0.90] | [−0.24, +1.11] | [−0.89, +0.50] |
| t-Test p | 0.38 | 0.14 | 0.73 |
| PSR (Einzeltest) | 0.81 | 0.94 | 0.37 |
| DSR konservativ (62 Trials) | 0.068 | — | — |
| vs Markt je Jahr | 21:+1.6 22:+1.3 **23:−2.3** 24:−0.9 25:+1.0 26:+1.5 | 21:+1.9 22:+1.8 **23:−0.8** 24:−0.3 25:+0.1 26:+0.1 | 21:+0.1 … 25:−0.5 |

**Drei Befunde:**
1. **Der LGBM-vs-Ridge-Abstand überlebt out-of-time** (+0.38/+0.64 vs −0.15
   bei identischer Regel) — Gate A war kein CPCV-Artefakt; die Ridge-Variante
   verdient OOT sogar nichts (CAGR −0.6%).
2. **Erwarteter Selektions-Haircut:** CPCV +0.81 → Walk-Forward +0.38 (Basis).
   Der Walk-Forward cleant den Modell-Fit-Kanal, NICHT die Regel-Selektion
   (Hebel wurden auf voller Historie gewählt) — den Rest cleant nur Live.
3. **Konzentrations-Fix wirkt wie erwartet** (EIN registrierter Versuch):
   min. Buchgröße 12 glättet 2023 von −2.3 auf −0.8 und hebt die Relative auf
   +0.64 — mechanisch plausible Diversifikation, kein neues Mining. Bleibt
   mit t-p 0.14 unbewiesen.

## Verdikt

Richtung bestätigt, Signifikanz nicht erreicht — **kein Kandidat, testing.**
Auf einem 5.4-Jahres-Pfad mit einem −0.8…−2.3-Relativ-Jahr (2023) ist das
KI-mit-0 das ehrliche Ergebnis. Es gibt keinen weiteren historischen Hebel,
der das beweisen könnte, ohne neues Mining zu sein → Live-Forward.

## Live-Forward-Registrierung (eingefroren 2026-06-11)

- **Primäre Variante:** LGBM0 (15/0.05/100, 0057-Fixparams), h=28-Rang-Target,
  Features = 0058-Basis-11, Universum CMC-Top-150 × Binance-USDT × Peg-Guard,
  Monats-Rebalance (Monatsultimo), **Dezil long-only mit min. Buchgröße 12**,
  Hold-Band-Buffer 2×, Liquiditäts-Floor $5M (21d-Median-Dollarvol),
  inverse-Vol-Gewichte. Sekundär (Vergleich): identisch ohne min_k.
- **Signal:** `scripts/crypto_live_signal.py` (monatlich nach Ultimo,
  `--refresh` mit Sandbox off). Aktuelles Buch siehe Konsole/REPORT-Anhang.
- **Erfolgskriterium (~24 Monate):** Hedge-vs-Markt-Sharpe > 0 über ≥ 24
  Monats-Perioden UND kein neues Relativ-Jahr < −1.5; Abbruch bei
  kumulativer Hedge-Differenz < −30%.
- Modell-Refit monatlich expanding (Teil der Regel, kein Re-Tuning; jede
  Änderung an Features/Hebeln beendet den Forward-Test).

## Artefakte

`results/metrics.json`, `wf_predictions_lgbm.parquet`,
`wf_returns_lgbm{,_mink12}.parquet`, `walkforward_equity_alpha.png`.
