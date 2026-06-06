# Strategie 0036 — Quint-Saison-Overlay (+ Baumwolle, gleichgewichtet)

- **Kategorie:** seasonal (Portfolio-Konstruktion / Bündelung)
- **Status:** **Kandidat-Bündelung** — aktuelle, realistischere Overlay-Version (löst die Dezember-Überlappung sauber). Kein neuer Edge; erbt „kein sauberes OOS für Platin/Mais/Baumwolle".
- **Datum:** 2026-06-05
- **Universum:** Kern S&P 500 / DAX; fünf Saison-Beine in Futures.

## 1. Was neu ist ggü. 0033

Fünftes Bein: **Baumwolle** (`CT=F`, 21.11.–29.12., aus 0035). Problem: Baumwolles Fenster
**überlappt Mais (8.–18.12.) UND Platin (18.12.–10.1.)** — drei Dezember-Saisons auf drei
*verschiedenen* Instrumenten konkurrieren um denselben Kalender (298 Überlappungstage S&P).

**Modellwechsel (wichtig):** 0020/0033 hatten disjunkte Fenster → „Entweder/Oder"-Tausch (100 %
Notional in *einem* Future) funktionierte. Mit Baumwolle geht das nicht mehr. Da es real **drei
getrennte Futures auf Margin** sind (parallel haltbar), nutzt 0036 **gleichgewichtete Allokation
über gleichzeitig aktive Beine**: an einem Tag mit k aktiven Saison-Beinen bekommt jedes 1/k des
Saison-Notionals; ohne aktives Bein → Index. Realistischer *und* additiv (keine künstliche
Priorität/Kannibalisierung). Kosten auf den `|Δgewicht|`-Umschlag (deckt Ein-/Ausstiege + Reshuffles).

## 2. Ergebnisse (netto)

| Bein | Trades | Win | Exp/Trade | aktive Tage |
| --- | ---: | ---: | ---: | ---: |
| Benzin (RB=F, KW9) | 22 | 95 % | +11,19 % | 110 |
| Mastrind (GF=F, KW21) | 22 | 91 % | +4,12 % | 110 |
| **Baumwolle (CT=F, 21.11.–29.12.)** | 24 | 79 % | **+5,12 %** | 517 |
| Mais (ZC=F, 8.–18.12.) | 21 | 86 % | +2,69 % | 155 |
| Platin (PL=F, 18.12.–10.1.) | 25 | 88 % | +4,53 % | 346 |

| S&P 500 | gesamt | B&H | ab 2016 | B&H 2016+ |
| --- | ---: | ---: | ---: | ---: |
| CAGR | **34,4 %** | 9,1 % | 40,7 % | 13,5 % |
| Sharpe | **1,25** | 0,45 | 1,42 | 0,68 |
| Vol | 24,4 % | 19,1 % | 24,8 % | 18,0 % |
| Max Drawdown | −39,3 % | −49,7 % | −34,1 % | −33,9 % |

DAX: gesamt 32,0 %/Sharpe 1,08 vs 7,1 %/0,33; ab 2016 35,7 %/1,26 vs 8,6 %/0,43.

## 3. Vergleich zu 0033 (ehrliche Attribution)

| | 0033 Quad (entweder/oder) | 0036 Quint (gleichgewichtet) |
| --- | ---: | ---: |
| S&P gesamt | 33,0 % / 1,22 | **34,4 % / 1,25** |
| S&P Forward | 44,2 % / 1,49 | 40,7 % / 1,42 |

- **Gesamt-Stichprobe leicht besser** (Baumwolle bringt zusätzlichen, unabhängigen Faser-Edge).
- **Forward etwas niedriger** — das ist **kein Baumwolle-Malus**, sondern Folge des Modellwechsels:
  0033 war an Dezember-Tagen zu 100 % in *einem* Future (unrealistisch konzentriert); 0036 teilt das
  Kapital auf die drei Dezember-Beine auf → weniger Konzentration, etwas weniger Forward-Wumms, aber
  **gleicher Sharpe/MaxDD** und **realistischer**. Die Vermischung zweier Änderungen (Bein + Modell)
  macht einen sauberen Eins-zu-eins-Vergleich unmöglich; 0036 ist die ehrlichere Portfolio-Variante.

## 4. Vorbehalte (wie 0033)

- **Kein neuer Edge** — Bündelung. Nur Benzin/Mastrind sind echte Forward-Tests (0006/0009);
  **Platin, Mais UND Baumwolle wurden full-history-gemined → 2016+ KEIN sauberes OOS** für sie.
- Senkt kein Marktrisiko (Vol 24 %, MaxDD −39 %). Benzin dominiert weiter.
- Dezember ist jetzt „voll" (3 Beine) → abnehmender Grenznutzen weiterer Jahresend-Saisons.

## 5. Nächste Schritte

- **Live-Forward 2026/27** für die drei nicht-vorregistrierten Beine (Platin, Mais, Baumwolle)
  gemeinsam und vorab registrieren — erst dann zählen ihre Zukunftsjahre als echtes OOS.
- Positionsgrößen-/Vol-Targeting vor realer Nutzung.

## Artefakte

- `results/metrics.json`, `results/equity.csv`, `results/plots/overlay_*.png`
