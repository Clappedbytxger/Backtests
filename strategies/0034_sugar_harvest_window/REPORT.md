# Strategie 0034 — Zucker Sommerfenster (8.6.–3.7.)

- **Kategorie:** seasonal
- **Status:** **abgelehnt** — IS/OOS-Kollaps (zweite Hälfte netto negativ), ~48 % roll-getragen, Bootstrap-KI berührt Null.
- **Datum:** 2026-06-05
- **Universum:** ICE Sugar #11 Front-Month (`SB=F`). Sauber: 2000–2026, min 78 distinkte Kurse/Jahr.
- **Stichprobe:** Gesamt 2000–2026. IS 2000–2012 / OOS 2013–2026 (Schnitt 1. Jan.).

## 1. Hypothese & Makro

Seasonax-Lead: long **8. Juni – 3. Juli** (~18 Handelstage). These: brasilianische Ernte-/
Crush-Saison (Apr–Nov) + **Cane-Frost-Risikoprämie** im brasilianischen Winter (Jun–Jul). Zucker
driftarm (B&H-Sharpe 0,22) → Permutationstest aussagekräftig.

## 2. Ergebnisse (netto)

| Kennzahl | Gesamt | IS 2000–12 | OOS 2013–26 |
| --- | ---: | ---: | ---: |
| Sharpe | 0,29 | 0,69 | **−0,31** |
| Trefferquote | 58 % | 77 % | **38 %** |
| Expectancy/Trade | +4,94 % | +10,41 % | **−0,52 %** |
| Median/Trade | +2,83 % | +10,57 % | −0,37 % |

Buy & Hold: CAGR 4,02 %, Sharpe 0,22.

## 3. Warum abgelehnt

- **IS/OOS-Kollaps (das 0017-Muster):** die gesamte Performance steckt in der ersten Hälfte
  (2000–2012, Sharpe 0,69, 77 % Win); die **zweite Hälfte verliert netto** (Sharpe −0,31, 38 % Win,
  −0,52 %/Trade). Kein stabiler Edge, sondern ein vor 2013 wirksames, danach totes Muster (vermutlich
  arbitragiert / vom 2010er-Zucker-Bärenmarkt überlagert).
- **Bootstrap-Sharpe-KI [−0,08; 0,66] berührt die Null** — risikoadjustiert nicht von Null trennbar.
- **Roll-Tag-Check (0029):** ~**48 %** des Trade-Gewinns sitzt in der Juli-Roll-Zone (29.6.–2.7.,
  Sugar-#11-Juli-Verfall; der 1.-Juli-Tagesstd ist ~6 %). Nach Ausschluss fällt die Permutation auf
  **p=0,051** (Signifikanz weg) und die OOS-Expectancy auf −1,50 %. Also halb roll-getragen, halb
  IS-only — beide Stützen brechen.
- Permutation p=0,009 auf voller Historie ist hier irreführend: sie mittelt die starke IS-Hälfte
  mit der toten OOS-Hälfte. IS/OOS-Trennung + Roll-Check entlarven es.

## 4. Lehre

Bestätigt einmal mehr: eine plausible Makro-Story (Cane-Frost) + ein guter Voll-Stichproben-p-Wert
genügen NICHT. Erst die IS/OOS-Konsistenz (hier gerissen) und der Roll-Check (hier halb getragen)
zeigen, dass kein handelbarer, stabiler Edge vorliegt. Kein Forward, kein Overlay. Kontrast zur
Baumwolle (0035), die beide Tests besteht.

## Artefakte

- `results/metrics.json`, `results/trades.csv`, `results/plots/*.png`
