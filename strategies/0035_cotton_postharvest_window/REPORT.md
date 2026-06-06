# Strategie 0035 — Baumwolle Jahresend-Fenster (21.11.–29.12.)

- **Kategorie:** seasonal
- **Status:** **testing / starker Lead** — Permutation p=0,001, Bootstrap-KI ohne Null, beide Hälften positiv, Roll-Check bestanden.
- **Datum:** 2026-06-05
- **Universum:** ICE Cotton No. 2 Front-Month (`CT=F`). Sauber: 2000–2026, min 102 distinkte Kurse/Jahr, 0,7 % Null-Returns.
- **Stichprobe:** Gesamt 2000–2026. IS 2000–2012 / OOS 2013–2026 (Schnitt 1. Jan.).

## 1. Hypothese & Makro

Seasonax-Lead: long **21. Nov. – 29. Dez.** (~26 Handelstage). These: die **Nordhalbkugel-Ernte
(Sep–Nov)** ist bis Ende November weitgehend durch → der Erntedruck lässt nach, Preise festigen sich
ins Jahresende auf Nachfrage + Unsicherheit über die Anbaufläche der Folgesaison. Baumwolle driftet
nur schwach (B&H-Sharpe 0,13, CAGR 1,55 % über 26 J.) → Permutation aussagekräftig, kaum Drift-Fallen-
Gefahr trotz mehrwöchigem Fenster.

## 2. Ergebnisse (netto)

| Kennzahl | Gesamt | IS 2000–12 | OOS 2013–26 |
| --- | ---: | ---: | ---: |
| CAGR | 5,53 % | 7,62 % | 3,56 % |
| Sharpe | **0,40** | 0,52 | 0,25 |
| Max Drawdown | −15,9 % | −15,9 % | −12,3 % |
| Trefferquote | 77 % (20/26) | **85 %** | 69 % |
| Profit-Faktor | 6,73 | 8,99 | 4,63 |
| Expectancy/Trade | +5,84 % | +7,84 % | +3,83 % |
| Median/Trade | **+6,70 %** | +9,00 % | +3,66 % |
| Trades | 26 | 13 | 13 |
| Exposure | 10,0 % | | |

Buy & Hold: CAGR 1,55 %, **Sharpe 0,13** (driftarm → keine Drift-Falle), MaxDD −77,5 %.

## 3. Signifikanz (gesamte Stichprobe — Seasonax-gemined)

- **Permutation p = 0,001** ✓ — Timing schlägt 99,9 % gleich langer Zufallsfenster; driftarmes Asset → doppelt aussagekräftig.
- **Bootstrap-Sharpe-KI [0,03; 0,77]** ✓ — **schließt die Null aus**.
- **t-Test p = 0,002** ✓. **IS ≈ OOS beide positiv** (Sharpe 0,52/0,25; Win 85 %/69 %; Median +9,00/+3,66 %) — keine OOS-Schwäche wie Zucker/Palladium. **121/121 Robustheit.** DSR/PSR=0 (Such-Strafe).

## 4. Roll-Tag-Check (Pflicht seit 0029) — bestanden, KEIN Artefakt

Cotton-Liefermonate Mär/Mai/Jul/Okt/Dez; im November ist der Dez-Kontrakt Front, sein Roll nach März
fällt ~**Ende November**, also in den Fensteranfang. Der Check ist also scharf:

| Variante | Exp/Trade | Win | Sharpe | Perm p | IS-Exp | OOS-Exp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Basis (alle Tage)** | +5,84 % | 77 % | 0,40 | 0,001 | +7,84 % | +3,83 % |
| 23.–30. Nov. ausgeschlossen | +2,46 % | 69 % | 0,32 | **0,003** | +2,95 % | +1,95 % |

**Nur 27 % des Trade-Gewinns liegt in der Roll-Zone.** Nach Ausschluss bleibt der Edge **signifikant
(p=0,003)**, Sharpe fällt kaum (0,40→0,32), Expectancy positiv in IS *und* OOS. → echte
Jahresend-Stärke, kein Roll-Gap (wie Platin 0019 / Palladium 0031, Gegenteil von NG 0028).

## 5. Bewertung & nächste Schritte

**Einer der saubersten Seasonax-Leads im Katalog** — der einzige neben Platin (0018) und Mais-WASDE
(0032), der p≈0,001, Bootstrap-KI ohne Null, beide Hälften positiv UND einen bestandenen Roll-Check
vereint, auf einem driftarmen Asset. Makro-Story plausibel (Post-Harvest-Festigung). Unabhängige
Evidenz (neuer Sektor, kein Treiber-Overlap mit PGM/Getreide).

- **Kein echtes zeitliches OOS** (Seasonax-gemined) → Live-Forward Dez 2026 vorab registrieren.
- **Cross-Check** ohne Re-Fitting auf Baumwoll-naher Reihe (z. B. `BAL`-ETF — Achtung Roll-Decay-Vorbehalt
  wie CORN 0032) bzw. zweite Cotton-Quelle.
- Kandidat fürs Saison-Overlay (0033) als **fünftes Bein** — füllt zusammen mit Mais/Platin die
  Jahresend-Saison, aber Treiber unabhängig (Faser statt Getreide/PGM); zeitliche Nähe zu Mais
  (8.–18.12.) → Disjunktheit beachten.
- Rang: **Top-Tier der Seasonax-Leads**, neben Platin 0018 und Mais-WASDE 0032.

## Artefakte

- `results/metrics.json` (inkl. `roll_check`), `results/trades.csv`, `results/plots/*.png`
