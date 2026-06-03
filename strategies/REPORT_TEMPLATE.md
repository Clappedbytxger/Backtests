# Strategie NNNN — <Name>

> Konventionen für jeden Report: **auf Deutsch** schreiben, Indizes/Aktien mit
> **vollem Namen** nennen (nicht den Ticker), Tabellen mit `quantlab.reporting`
> ausrichten und jede Visualisierung mit einer erklärenden Caption versehen.

- **Kategorie:** <seasonal | mean-reversion | momentum | ...>
- **Status:** <idea | testing | validated | rejected>
- **Datum:** <YYYY-MM-DD>
- **Universum:** <volle Namen>
- **Stichprobe:** In-Sample <Zeitraum> / Out-of-Sample <Zeitraum>

## 1. Hypothese

Ein Satz: Welcher Edge, auf welchen Assets, warum jetzt.

## 2. Makro-Begründung

*Warum sollte das existieren?* Die ökonomische Ursache (Flows, Anreize,
Angebot/Nachfrage, Verhalten). Ein Muster ohne Ursache gilt als data-gemint, bis
das Gegenteil bewiesen ist.

## 3. Regeln

Exakte Entry-/Exit-Logik, Positionsgrößen, Haltedauer. Look-Ahead-Schutz
vermerken (Signale werden von der Engine verzögert).

## 4. Kosten- & Ausführungsannahmen

IBKR-Kommissionsmodell, Slippage (bps), Gebühren, Ausführungszeitpunkt.

## 5. Ergebnisse (Out-of-Sample, netto nach Kosten)

| Kennzahl                  | Wert |
| ------------------------- | ---: |
| CAGR                      |      |
| Sharpe                    |      |
| Sortino                   |      |
| Calmar                    |      |
| Max Drawdown (+ Dauer)    |      |
| Trefferquote              |      |
| Profit-Faktor             |      |
| Payoff-Ratio              |      |
| Expectancy                |      |
| Ø Haltedauer              |      |
| Trades                    |      |

## 6. Signifikanz

| Test                          | Wert |
| ----------------------------- | ---: |
| Permutationstest p-Wert       |      |
| Bootstrap Sharpe 95%-KI       |      |
| Deflated Sharpe (Varianten N) |      |
| t-Test mittlere Rendite       |      |

## 7. Robustheit

Über Märkte / Parameter / Teilperioden. Übersteht es das Out-of-Sample?

## 8. Verdict

Behalten / ablehnen / iterieren — und der eine Grund dafür.
