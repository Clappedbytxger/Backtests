# Strategie 0047 — Cross-Sectional Commodity Momentum (12-1)

- **Kategorie:** cross-sectional / momentum (relative-value)
- **Status:** abgelehnt
- **Datum:** 2026-06-08
- **Universum:** 21 liquide Rohstoff-Futures (WTI-Rohöl, Erdgas, Benzin, Heizöl,
  Gold, Silber, Kupfer, Platin, Palladium, Mais, Weizen, Sojabohnen, Sojaöl,
  Sojamehl, Zucker, Kaffee, Kakao, Baumwolle, Lebendrind, Mastrind, Mageschwein)
- **Stichprobe:** In-Sample 2007–2016 / Out-of-Sample 2017–2026

## 1. Hypothese

Ranke das Rohstoff-Universum monatlich nach 12-1-Monats-Momentum, gehe long das
Top-Quartil und short das Bottom-Quartil (dollar-neutral). Der Edge ist
**relativ** — welcher Rohstoff schlägt welchen — nicht gerichtet.

**Warum dieses Paradigma:** Bricht aus der „Frequenz-Zwickmühle" der ersten 46
Strategien aus. Single-Market-Timing hatte entweder zu wenige Trades (saisonal,
11–27) oder Brutto ≈ Kosten (intraday). Cross-sectional skaliert die
Beobachtungen mit der Universumsgröße (21 Instrumente × ~2400 OOS-Tage) → das
Power-Problem verschwindet, und das Buch ist marktneutral (kein Beta-Maskerade-
Problem wie 0015).

## 2. Makro-Begründung

Cross-sectional Momentum ist einer der am besten replizierten Faktoren
(Asness/Moskowitz/Pedersen 2013, „Value and Momentum Everywhere"; Miffre &
Rallis 2007 für Rohstoffe). Treiber: langsame Diffusion von Angebots-/
Nachfrage-Information und persistente Backwardation-/Contango-Regime. **Aber:**
Die Rohstoff-Variante zerfiel nach 2008 deutlich (überfüllt durch die
Commodity-Index-Welle 2004–2014) — das war vor dem Test das Hauptrisiko.

## 3. Regeln

- **Signal:** `mom_t = Preis_{t-21} / Preis_{t-252} − 1` (12-1-Monat,
  letzter Monat übersprungen wegen Kurzfrist-Reversal).
- **Rebalancing:** letzter Handelstag jedes Monats.
- **Gewichte:** Top-Quartil long, Bottom-Quartil short, gleichgewichtet je Bein;
  jedes Bein = 100 % Kapital → Gross 2.0, Netto 0.0 (Rendite = Top-minus-Bottom-
  Spread).
- **Look-Ahead-Schutz:** Signal am Monatsend-Close; die Engine forward-fillt die
  Zielgewichte und shiftet sie um einen Tag → gehalten ab dem Folgetag.
- **Datenqualitäts-Guards:** eingefrorene Feeds verworfen (<50 distinkte Closes/
  Jahr); nicht-positive Prints (WTI −$37 am 2020-04-20) → NaN, damit Momentum sie
  ausschließt.

## 4. Kosten- & Ausführungsannahmen

6 bps pro Seite (12 bps Round-Trip) auf den Umschlag bei jedem Rebalancing —
gemischter Wert für ein liquides Rohstoff-Futures-Buch (IBKR-Kommission +
Half-Spread + Impact, im Bereich der `IBKR_FUTURES`/`IBKR_SOFTS`-Presets).

## 5. Ergebnisse (Out-of-Sample, netto nach Kosten)

| Kennzahl                  |    Wert |
| ------------------------- | ------: |
| CAGR                      |  −13.3 % |
| Sharpe (annualisiert)     |   −0.41 |
| Annualisierte Vola        |   26.1 % |
| Max Drawdown              |  −83.9 % |
| Rebalancings (≈ Trades)   |     ~115 |
| Ø Namen je Bein           | 5 long / 5 short |
| Netto-Exposure            | 0 (5.5e-17) |
| Benchmark EW Long-Only OOS Sharpe | **+0.74** |

In-Sample Sharpe −0.89, OOS −0.41 — in **beiden** Perioden negativ.

## 6. Signifikanz (OOS, netto)

| Test                                | Wert |
| ----------------------------------- | ---: |
| Permutationstest (Rank-Shuffle) p   | 0.747 |
| Bootstrap Sharpe 95 %-KI            | [−1.05, +0.23] |
| Deflated Sharpe (N=12)              | 0.003 |
| t-Test mittlere Tagesrendite        | t=−1.04, p=0.298 |

Kein Test zeigt Signal — alle konsistent mit „kein Edge", die meisten mit
**negativem** Edge.

## 7. Robustheit

OOS-Sharpe über das gesamte Parameter-Gitter (Lookback × Rebalancing):

| Lookback | monatlich | quartalsweise |
| -------- | --------: | ------------: |
| 63       |    −0.59  |        −0.61  |
| 126      |    −0.39  |        −0.43  |
| 189      |    −0.50  |        −0.18  |
| 252      |    −0.41  |        −0.57  |
| 378      |    −0.06  |        −0.29  |
| 504      |    −0.45  |        −0.58  |

**Jede einzelne Zelle negativ.** Kein Cherry-Picking-Fenster rettet es.

**Kein Kostenproblem:** Brutto-Sharpe = −0.51 (vor Kosten), Kosten-Drag nur
0.8 %/Jahr. Anders als die Intraday-Tests (0012–0015/0038–0041, wo Brutto ≈ 0 und
Kosten bindend waren) ist das Signal hier **vor Kosten genuin negativ**.

## 8. Verdict

**Abgelehnt.** Long-Gewinner/Short-Verlierer-Momentum auf Rohstoffen war
2007–2026 brutto-negativ — der Faktor ist hier tot (überfüllt/zerfallen nach der
Index-Welle), nicht von Kosten erschlagen.

**Zwei wertvolle Befunde:**

1. **Das Paradigma funktioniert methodisch.** Die Engine ist look-ahead-sicher
   (gepflanzter Hellseher-Test grün), das Buch exakt dollar-neutral, der
   cross-sektionale Permutationstest und die **korrigierte** Deflated Sharpe
   (0.003, sauber abgestuft statt mechanisch 0/1) liefern genau das erwartete
   Verhalten. Power ist kein Problem mehr (2373 OOS-Beobachtungen).

2. **Das negative Vorzeichen ist ein Hinweis, kein Fehler.** Dass das Spread
   *vor* Kosten verliert, heißt: das Bottom-Quartil (Laggards) schlug das
   Top-Quartil — konsistent mit **Mean-Reversion / Carry** statt Momentum. Das
   Vorzeichen jetzt umzudrehen und neu zu fitten wäre In-Sample-Overfit (genau
   die Falle, die das Projekt meidet). Der disziplinierte nächste Schritt ist
   eine **vorab registrierte Carry-Hypothese** (Term-Struktur: long
   Backwardation, short Contango) — strukturell (Lagerökonomie), nicht
   behavioral, also nicht wegarbitragiert. Das braucht **Mehrkontrakt-Daten**
   (yfinance liefert nur Front-Month) → das ist die eigentliche offene Hürde,
   nicht das Konzept.
