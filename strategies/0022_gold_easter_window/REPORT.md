# Strategie 0022 — Gold rund um das Osterfest (Western Easter)

- **Kategorie:** seasonal (event-getrieben, bewegliches Fest)
- **Status:** abgelehnt
- **Datum:** 2026-06-04
- **Universum:** Gold (Gold-Futures, `GC=F`)
- **Stichprobe:** In-Sample 2000–2013 / Out-of-Sample 2013–2026 (Schnitt 01.07.2013, halbiert kein Frühjahrsfenster)

## 1. Hypothese

Gold long **8 Kalendertage vor dem westlichen (gregorianischen) Ostersonntag**
kaufen und **2 Kalendertage danach** verkaufen — ein kurzes, mit dem beweglichen
Osterdatum (22. März – 25. April) mitwanderndes Fenster (~10 Kalendertage / ~6
Handelstage), jedes Jahr wiederholt.

## 2. Makro-Begründung

**Schwach bis nicht vorhanden — a priori data-mining-verdächtig.** Die gut
belegten saisonalen Gold-Nachfragetreiber sind **indisch** (Akshaya Tritiya,
Diwali, Hochzeitssaison) und das **chinesische Neujahr** — physische
Schmuck-/Anlagenachfrage in Asien. **Western Easter ist kein bekannter
Gold-Kauf-Anlass**: christlich geprägte Länder sind keine saisonalen
Physical-Gold-Käufer, und es gibt keinen plausiblen Flow-/Angebots-/Nachfrage-Kanal,
der Gold ausgerechnet in der Woche vor Ostern treiben sollte. Ein loser Anknüpfungspunkt
wäre eine gelegentliche zeitliche Nähe zu Akshaya Tritiya (meist Ende April/Anfang
Mai) — aber das fällt in den meisten Jahren *nach* das Osterfenster und ist kein
Mechanismus, sondern eine Hoffnung. Nach den Hard Rules des Projekts gilt das Muster
damit als data-gemint, bis das Gegenteil bewiesen ist. Getestet wird trotzdem ehrlich;
der **Permutationstest** (Lehre aus 0017) entscheidet, ob sich die Suche nach einer
Ursache überhaupt lohnt.

## 3. Regeln

- **Entry:** Position 1.0 (100 % long Gold-Future) ab `Ostern − 8 Kalendertage`.
- **Exit:** flat ab `Ostern + 2 Kalendertage` (Schlusskurs des letzten Fenstertages).
- Sonst durchgehend flat (im Mittel **2,4 % Marktzeit**, ~6 Handelstage/Jahr).
- **Osterdatum** pro Jahr über den gregorianischen Computus (Anonymous /
  Meeus-Jones-Butcher) berechnet — dependency-frei, exakt.
- **Look-Ahead-Schutz:** Das Signal ist ein Entscheidungszeit-Signal (nur das
  Kalenderdatum); die Engine verzögert die Ausführung um T+1, es fließen keine
  Zukunftsdaten ein.

## 4. Kosten- & Ausführungsannahmen

`IBKR_FUTURES`: Kommission in wenige bps gefaltet, **2 bps Slippage/Seite** +
0,5 bps Gebühren — ~5 bps Round-Trip. Ausführung zum Schlusskurs (T+1). Auf Gold-
Front-Month (sehr liquide) realistisch konservativ. **Futures-Guard** (Lehre 0005):
Abbruch bei nicht-positivem Kurs — hier kein Treffer.

## 5. Ergebnisse (Out-of-Sample, netto nach Kosten)

| Kennzahl                  | OOS 2013–2026 | (Gesamt 2000–2026) |
| ------------------------- | ------------: | -----------------: |
| CAGR                      |         1,17 % |             0,80 % |
| Sharpe                    |         −0,23 |              −0,35 |
| Sortino                   |         −0,40 |              −0,51 |
| Calmar                    |          0,30 |               0,09 |
| Max Drawdown              |        −3,98 % |   −8,46 % (3247 T) |
| Trefferquote              |          69 % |               65 % |
| Profit-Faktor             |          3,20 |               2,02 |
| Payoff-Ratio              |          1,42 |               1,07 |
| Expectancy/Trade          |         1,20 % |             0,83 % |
| Ø Haltedauer              |        6,0 T |              6,0 T |
| Trades                    |            13 |                 26 |

**Zum Kontext: Gold Buy & Hold (gesamt): CAGR 11,50 %, Sharpe 0,59, MaxDD −44,4 %.**

> Hinweis zum negativen Sharpe: Die Strategie ist 97,6 % der Zeit flat. Über die
> konstante Risk-free-Annahme (2 %/Jahr) liegt der annualisierte Excess-Sharpe
> negativ, weil das Kapital 11 Monate brachliegt und kein T-Bill-Carry modelliert
> wird. Die Trade-Ebene ist nominal leicht positiv (+0,83 %/Trade) — aber siehe §6.

## 6. Signifikanz

| Test                          | Wert |
| ----------------------------- | ---: |
| Permutationstest p-Wert       | **0,090** |
| Bootstrap Sharpe 95 %-KI      | **[−0,73; 0,03]** |
| Deflated Sharpe (Varianten N=49) | **0,00** |
| t-Test mittlere Rendite       | 0,179 |

**Der Permutationstest scheitert (p = 0,090).** Das Timing ist auf dem 5 %-Niveau
**nicht von zufälligem Timing unterscheidbar** — 9 % zufälliger gleich langer
Frühjahrsfenster schlagen den realen Sharpe. Die Bootstrap-KI schließt die Null
nicht aus, der t-Test ist insignifikant, DSR = 0 (Such-Strafe für 49 Fenster-Varianten).

## 7. Robustheit

42 von 49 Fenster-Verschiebungen (±6 Tage je Kante) haben positive Expectancy.
**Das ist hier kein Plateau, sondern die Drift-Falle aus 0017:** Gold ist
2000–2026 stark gestiegen, also ist *fast jedes* kurze Long-Fenster im Frühjahr
positiv — unabhängig von Ostern. Genau diese Drift-Anfälligkeit fängt der
Permutationstest ab, und er gibt grünes Licht **nicht**. IS (Expectancy 0,46 %,
PF 1,43) ist deutlich schwächer als OOS (1,20 %, PF 3,20); die hübschen OOS-Zahlen
beruhen auf 13 Trades und sind statistisch nicht belastbar.

## 8. Verdict

**Abgelehnt.** Der eine Grund: Das Fenster überlebt den Permutationstest nicht
(p = 0,09) — das Oster-Timing ist von zufälligem Frühjahrs-Timing in einem
steigenden Goldmarkt nicht zu trennen. Dazu kommen drei verstärkende Argumente:
keine Makro-Ursache (Ostern ≠ Gold-Saison), netto **0,8 % CAGR vs. 11,5 % bei Gold
Buy & Hold** (man gibt fast die gesamte Gold-Rendite für einen winzigen,
insignifikanten Kick auf), und DSR = 0. Die scheinbar guten Trade-Stats
(65 % Win, PF 2,0) sind Drift, nicht Edge. Keine Eskalation zu einem Forward-Test.
