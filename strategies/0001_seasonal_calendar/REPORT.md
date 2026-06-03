# Strategie 0001 — Saisonale Kalendereffekte

- **Kategorie:** seasonal
- **Status:** abgelehnt (als eigenständiger Edge) / iterieren (Sell-in-May als Overlay)
- **Datum:** 2026-06-03
- **Universum:** S&P 500 (USA), Nasdaq 100 (USA), DAX (Deutschland),
  FTSE 100 (UK), Nikkei 225 (Japan)
- **Stichprobe:** In-Sample ≤ 2010 (nur Auswahl) / Out-of-Sample 2011–2026 (Auswertung)

## 1. Hypothese

Wiederkehrende Kalenderfenster — Turn-of-Month (Monatswechsel), Jahreswechsel und
die „Sommerflaute" (Mai–Oktober) — erzeugen abnormale Renditen auf breiten
Aktienindizes, die sich long-only mit besserem risikoadjustiertem Profil als Buy
& Hold handeln lassen, netto nach IBKR-Kosten.

## 2. Makro-Begründung

- **Turn-of-Month:** Monatsend-Zuflüsse aus Pensions-/Gehaltszahlungen,
  Fonds-Reinvestitionen und Index-Rebalancing bündeln Kaufdruck an der Grenze.
- **Jahreswechsel:** Tax-Loss-Selling läuft zum Jahresende aus, Window-Dressing,
  dünne Feiertagsliquidität, Neujahres-Zuflüsse.
- **Sell-in-May (Halloween):** historisch schwächere Sommerrenditen, verknüpft mit
  saisonalen Liquiditäts- und Risikoappetit-Zyklen.

## 3. Regeln

Long-only-Positionsgewicht 1.0 innerhalb des Kalenderfensters, sonst flat.
Signale sind Entscheidungszeit-Signale und werden von der Engine um einen
Handelstag verzögert (kein Look-Ahead). Effekt/Markt für die Vertiefung wurde
**ausschließlich** anhand des In-Sample-Sharpe gewählt.

## 4. Kosten- & Ausführungsannahmen

IBKR gestaffelte Kommission ($0,0035/Aktie, $0,35 Minimum, 1% Deckel),
**2 Basispunkte** Slippage (`IBKR_LIQUID_ETF`), 0,2 bps Regulierungsgebühr.
Kosten werden bei jeder Positionsänderung berechnet; alle Zahlen sind **netto**.

## 5. Out-of-Sample-Panel (netto, 2011–2026)

| Markt              | Effekt        | OOS Sharpe | B&H Sharpe |  CAGR | Marktzeit | Trades | Trefferq. | Profit-Faktor |
| ------------------ | ------------- | ---------: | ---------: | ----: | --------: | -----: | --------: | ------------: |
| S&P 500 (USA)      | Turn-of-Month |       0.12 |       0.75 |  2.6% |       19% |    186 |       60% |          1.38 |
| S&P 500 (USA)      | Jahreswechsel |      -0.48 |       0.75 |  0.5% |        4% |     16 |       69% |          1.76 |
| S&P 500 (USA)      | Sell-in-May   |       0.46 |       0.75 |  7.4% |       50% |     16 |       75% |          7.72 |
| Nasdaq 100 (USA)   | Turn-of-Month |       0.18 |       0.87 |  3.3% |       19% |    186 |       61% |          1.37 |
| Nasdaq 100 (USA)   | Jahreswechsel |      -0.37 |       0.87 |  0.5% |        4% |     16 |       56% |          1.50 |
| Nasdaq 100 (USA)   | Sell-in-May   |       0.46 |       0.87 |  8.2% |       50% |     16 |       81% |          6.40 |
| DAX (Deutschland)  | Turn-of-Month |      -0.20 |       0.42 | -0.4% |       19% |    186 |       56% |          1.01 |
| DAX (Deutschland)  | Jahreswechsel |      -0.23 |       0.42 |  1.2% |        4% |     16 |       88% |          3.78 |
| DAX (Deutschland)  | Sell-in-May   |       0.45 |       0.42 |  7.6% |       50% |     16 |       69% |          3.97 |
| FTSE 100 (UK)      | Turn-of-Month |      -0.01 |       0.18 |  1.7% |       19% |    186 |       62% |          1.22 |
| FTSE 100 (UK)      | Jahreswechsel |      -0.36 |       0.18 |  1.1% |        4% |     16 |       69% |          3.23 |
| FTSE 100 (UK)      | Sell-in-May   |       0.23 |       0.18 |  4.0% |       50% |     16 |       88% |          3.81 |
| Nikkei 225 (Japan) | Turn-of-Month |      -0.11 |       0.59 |  0.2% |       20% |    186 |       54% |          1.06 |
| Nikkei 225 (Japan) | Jahreswechsel |      -0.26 |       0.59 |  0.9% |        4% |     16 |       62% |          2.13 |
| Nikkei 225 (Japan) | Sell-in-May   |       0.33 |       0.59 |  6.2% |       50% |     16 |       69% |          3.46 |

### Vertiefung: gewählter Effekt (Sell-in-May auf DAX)

| Kennzahl        |               Wert |
| --------------- | -----------------: |
| CAGR            |              7.57% |
| Sharpe          | 0.45 (B&H 0.42)    |
| Sortino         |               0.59 |
| Max Drawdown    |            -38.78% |
| Trefferquote    |              68.8% |
| Profit-Faktor   |               3.97 |
| Ø Haltedauer    |           121 Tage |
| Trades          |                 16 |

## 6. Signifikanz

| Test                          |          Wert |
| ----------------------------- | ------------: |
| Permutationstest p-Wert       |         0.114 |
| Bootstrap Sharpe 95%-KI       | [-0.06, 0.95] |
| Deflated Sharpe (P[Sharpe>0]) |         0.000 |
| Getestete Varianten           |            15 |

- **Permutationstest p = 0,114** — nicht signifikant (≈11% zufälliger Timings
  erreichten dasselbe Ergebnis).
- **Deflated Sharpe ≈ 0** — nach Korrektur für die 15 getesteten Varianten ist das
  Resultat vollständig mit Auswahl-Zufall vereinbar.
- Fazit: Der In-Sample-Gewinner übersteht ehrliche Signifikanztests **nicht**.

## 7. Robustheit

- **Turn-of-Month** hat die statistische Power (186 Trades), aber **keinen
  OOS-Edge** nach Kosten (Sharpe 0,12 / 0,18 / -0,20 / -0,01 / -0,11). Die
  klassische Anomalie scheint nach 2010 weitgehend wegarbitragiert. Marktzeit nur
  ~19%.
- **Sell-in-May** ist **über alle fünf Märkte positiv und konsistent**
  (Sharpe 0,23–0,46) — ein echtes Robustheitssignal — aber:
  - es unterperformt Buy & Hold in starken Bullenmärkten (USA), weil es das halbe
    Jahr aussetzt;
  - nur 16 Trades pro Markt → einzeln schwache Power;
  - sein eigentlicher Nutzen liegt auf der **Drawdown**-Seite: die Kapitalkurve
    (`results/plots/equity.png`) umschifft den 2011er-Ausverkauf und dämpft 2020,
    endet aber nahe Buy & Hold — also ähnliche Rendite bei ~halber Marktzeit.

## 8. Verdict

**Abgelehnt als eigenständiger Rendite-Edge.** Kein Kalendereffekt schlägt Buy &
Hold netto nach Kosten statistisch signifikant im OOS-Zeitraum, und der
In-Sample-Gewinner wird vom Deflated Sharpe erledigt. Das ist das Framework, das
korrekt arbeitet — es weigert sich, ein data-gemintes Muster zu bestätigen.

**Wert der Iteration:** Die marktübergreifende Konsistenz von Sell-in-May und die
Halbierung der Marktzeit bei ähnlicher Rendite machen es zu einem Kandidaten für
ein **Risiko-Overlay**, nicht für eine Alpha-Quelle. Genau das wird in
**Strategie 0002** (gepooltes Sell-in-May) mit echter statistischer Power getestet.

### Artefakte
`results/metrics.json`, `results/oos_panel.csv`, `results/trades.csv`,
`results/card.json`, `results/equity.csv`,
`results/plots/{equity,drawdown,monthly_heatmap,bucket_tdom_from_end}.png`
