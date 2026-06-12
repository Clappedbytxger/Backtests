# Strategie 0062 — Phase 5 / Track B: CNN auf Preis-Chart-Bildern (JKX 2023)

**Status: abgelehnt (sauberes Null).** Die „echte Signalgenerierung"-Wette
der Roadmap — eine CNN extrahiert Preismuster direkt aus Chart-Bildern
(Jiang/Kelly/Xiu 2023, *J. Finance*) — überträgt sich NICHT auf die
wöchentliche Crypto-Cross-Section: **0 von 28 CPCV-Splits gegen Track A.**

## Design (vorab registriert, 2 Trials)

- **Bilder:** JKX-Spezifikation — 20-Tage-OHLC, 3 px/Tag (Open-Tick |
  High-Low-Bar | Close-Tick), MA-20-Linie, Volumen-Balken unten, 64×60
  binär, **per Bild min/max-skaliert** (das implizite Scaling ist laut JKX
  ein Hauptgrund der Vorhersagekraft; per Unit-Test verifiziert: identische
  Form bei $0.001 und $50k ⇒ identisches Bild). `quantlab/price_images.py`,
  4 Guards (Geometrie, Skalierungs-Invarianz, Look-ahead, Fenster).
- **Samples:** exakt die 35.428 Zeilen der Track-A-Design-Matrix (h=28,
  weekly) → identische 28 purged CPCV-Splits, fairer Head-to-Head.
- **Target:** binär ``fwd_28 > 0`` (JKX); Cross-Section-Ranking per p(up).
- **CNN fix, keine Architektur-Suche:** 2 Conv-Blöcke (32/64, 5×3-Kernel,
  BatchNorm, ReLU, MaxPool), Dropout 0.5, 1 FC-Logit; Adam 1e-3, Batch 256,
  max. 8 Epochen, Early Stopping (10% Val, Patience 2), Seed 7. CPU,
  ~4,6 min/Split, 2,2 h gesamt.
- **Gates (Roadmap Teil 6):** schlägt Track A (Split-ICs >50% + gestitchter
  IC höher) ODER Rank-Korrelation < 0.5 UND Ensemble schlägt LGBM in IC und
  Portfolio. Danach wäre der Walk-Forward-Check gefolgt (0061-Protokoll).

## Ergebnisse

| | LGBM0 (Track A) | CNN (Track B) | Ensemble (Mittel der Ränge) |
|---|---|---|---|
| Stitched OOS-IC | **+0.151** | +0.012 | +0.109 |
| Split-Siege vs LGBM | — | **0/28** | **0/28** |
| Portfolio net (eingefr. Regel) | +0.81 | +0.23 | +0.64 |
| vs Markt | **+0.45** | −0.70 | +0.04 |

- **Gate „CNN schlägt Track A": FAIL** — die CNN-ICs liegen pro Split bei
  −0.01…+0.02, LGBM bei +0.13…+0.18; kein einziger Split geht an die CNN.
- **Gate „Ensemble": FAIL** — die Rank-Korrelation ist zwar nur **+0.044**
  (unkorreliert ✓), aber Unkorreliertheit nützt nichts, wenn das zweite
  Modell ~kein Signal trägt: das Ensemble VERWÄSSERT (IC +0.151 → +0.109,
  vs Markt +0.45 → +0.04). Ein Null-Signal beimischen ist Rauschen, keine
  Diversifikation.
- Kein Walk-Forward-Check (Gate verfehlt — Disziplin wie 0061).

## Warum (ehrliche Einordnung, keine Ausrede)

1. **Datenskala:** JKX trainieren auf MILLIONEN täglicher US-Aktien-Bilder
   (1993–2019); hier stehen ~25k wöchentliche Crypto-Bilder pro Split-
   Training. Eine CNN, die Muster selbst finden soll, braucht genau das,
   was dieses Setup nicht hat: Masse.
2. **Crypto-Charts sind kreuzkorreliert** — der dominante Bildinhalt ist
   der gemeinsame Marktmove, der im Querschnitt nichts rankt (Track A
   rank-transformiert pro Datum, die CNN sieht nur das Einzelbild).
3. Der IC von +0.012 könnte sogar ein Hauch echt sein — aber bei 0/28
   Splits gegen die Messlatte gibt es keinen legitimen Iterationspfad,
   der nicht Architektur-Mining wäre (Roadmap-Checkliste: n_trials ehrlich
   inkl. Architektur-Suche — bewusst NICHT begonnen).

## Verdikt

Track B abgelehnt; **damit ist die Crypto-ML-Roadmap (Phasen 0–5) komplett
abgearbeitet.** Bestand: PIT-Universum + Survivorship-Gates (0058), erstes
bestandenes Ridge-Gate + Hebel-Mechanik (0059), Walk-Forward + Peg-Guard +
registrierter Live-Forward (0060), Phase 4 (0061) und Phase 5 (0062) je
sauber abgelehnt. Einziger offener Faden: der **Live-Forward der
eingefrorenen Track-A-Regel** (monatlich, `scripts/crypto_live_signal.py`).

## Artefakte

`results/metrics.json` (alle 28 Split-ICs beider Modelle),
`results/cnn_predictions_h28.parquet`; Bild-Builder `quantlab/price_images.py`
+ `tests/test_price_images.py`; OHLC-Panels in `crypto_xsection` ergänzt.
