# Strategie 0076 — FOMC-Cycle "Even-Week"-Drift (Cieslak et al.)

> Idee **I0008** aus dem Handoff `D:\Backtest Ideas` (Quelle #s02, Cieslak/Morse/
> Vissing-Jorgensen, J. Finance 2019). Variante von 0052 (Pre-FOMC-Drift).

- **Kategorie:** event-driven / makro (Notenbank-Zyklus)
- **Status:** abgelehnt (Drift-Falle — Permutation scheitert)
- **Datum:** 2026-06-15
- **Universum:** S&P 500 (SPY), Nasdaq-100, DAX (Cross-Market); Stichprobe 2000-2026
- **Stichprobe:** In-Sample 2000-2012 / Out-of-Sample 2013-2026

## 1. Hypothese

Seit 1994 wird die gesamte Aktien-Risikoprämie in den **geraden Wochen** (0, 2, 4, 6)
der FOMC-Zyklus-Zeit verdient (Fortnight-Muster, an jedes FOMC-Meeting verankert),
ungerade Wochen ~flach. Long Aktien nur in geraden FOMC-Wochen, sonst Cash.

## 2. Makro-Begründung

Liquiditätszyklus im Fed-Funds-Markt + informelle Fed-Kommunikation; verallgemeinert
den Pre-FOMC-Drift (0052). FOMC-Zyklus-Zeit: Handelstage seit letztem Meeting
(Meeting-Tag = 0); cycle_week = days_since // 5; gerade Wochen long.

## 3. Regeln & Look-Ahead

Kalenderbasiert (FOMC-Termine vorab bekannt), Engine shiftet zusätzlich um T+1.
Verifizierte FOMC-Liste 2000-2026 (aus 0052; Notfall-Meetings ausgeschlossen).
Phase-Robustheit: Anker-Shift −2..+2 Tage gescannt (DSR mit 5 Trials belastet).

## 4. Kosten

`MES_INTRADAY` (3 bps RT) — bei Wochen-Level-Holds (~5,5 Tage) nicht bindend.

## 5. Ergebnisse (SPY, netto MES)

| Kennzahl | Wert |
| --- | ---: |
| Gerade-Woche Ø-Return | +5,69 bps vs ungerade +1,89 bps |
| Anteil am Gewinn | **92 % in geraden Wochen** (auf 53 % der Tage) |
| Netto-Sharpe (voll) | 0,21 (CAGR 4,0 %, MaxDD −56 %) |
| Buy & Hold SPY | **0,40** (CAGR 8,2 %) |
| Trades / Win | 646 / 58,5 % |

Die Strategie liegt risikoadjustiert **unter Buy & Hold** (0,21 vs 0,40) — sie ist
~53 % der Zeit long und erntet entsprechend die halbe Marktprämie bei vollem MaxDD.

## 6. Signifikanz (SPY)

| Test | Wert |
| --- | ---: |
| **Permutation (Brutto-Sharpe vs Zufalls-Timing gleicher Anzahl)** | **p = 0,385 ✗** |
| even-minus-odd Tages-Mean-Diff | +3,80 bps |
| t-Test gerade-Woche-Mean > 0 | t = +2,78, p = 0,0054 |
| Bootstrap gerade-Woche-Mean 95%-KI | [+1,62, +9,73] bps (ohne 0) |
| Deflated Sharpe (5 Phasen) | 0,819 |

**Die Permutation ist der entscheidende Test und sie scheitert (p=0,385).** Der
positive t-Test/Bootstrap auf den Gerade-Woche-Mean misst genau die Drift-Falle:
„gerade-Woche-Tage haben positiven Schnitt" ist überwiegend die Aktien-Risikoprämie
aus dem Long-Sein an der Hälfte der Tage — NICHT ein Timing-Edge. Die Permutation
(behält Exposure + Drift, würfelt nur das Timing) zeigt, dass das Even-Week-Timing
von zufälligem gleich-langem Timing **ununterscheidbar** ist. Exakt die Lehre 0017
(Nasdaq-Sommer: 121/121-Robustheit, aber Permutation p=0,31) und der Grund, warum
0050 (das die Permutation BESTEHT) ein Lead ist und das hier nicht.

## 7. Robustheit

- **IS→OOS pathologisch:** IS 2000-2012 netto +0,08 (≈flach), OOS 2013-2026 +0,69 —
  die ganze Performance erst nach 2013. Cieslaks stärkste Evidenz lag 1994-2013; auf
  meinem 2000-2026-Sample ist der Effekt in-sample praktisch abwesend und die
  OOS-Stärke ein Recent-Bull-Artefakt (0017-Schema).
- **Cross-Market bestätigt die Ablehnung:** Nasdaq-100 Permutation p=0,20, DAX p=0,35
  — beide scheitern, beide unter ihrem B&H (NDX 0,39 vs 0,42; DAX 0,25 vs 0,33).
- **Per-Woche-Fingerprint unsauber:** gerade Wochen im Schnitt höher (w0/w2/w4/w6 ≈
  +5,2 bps vs ungerade +2,8 bps), aber w3 (+4,9) und w7 (+7,8) brechen das saubere
  Alternieren — genau diese Unschärfe macht das Timing permutations-insignifikant.
- Phase-Shift −2..+2 alle positiv (0,24-0,55) → kein Knife-Edge, aber irrelevant, da
  die Permutation in jeder Phase die Drift nicht schlägt.

## 8. Verdict

**Abgelehnt — Drift-Falle.** Der breite Even-Week-Effekt schlägt Zufalls-Timing nicht
(Permutation p=0,385, über SPY/NDX/DAX konsistent) und liegt unter Buy & Hold. Der
beeindruckende „92 % des Gewinns in geraden Wochen"-Befund ist die Aktien-Risikoprämie
aus 53 % Marktzeit, kein Timing-Skill.

**Wichtige Abgrenzung zu 0052 (Lead):** 0052 testet das ENGE, a-priori korrekte Fenster
(Nacht IN die Ankündigung) gegen die RICHTIGE Null (zufällige Nächte) und besteht
(p=0,0034). Die breite Even-Week-Verallgemeinerung tut das nicht — der 0052-Puls ist
spezifisch das Overnight-in-den-Entscheid, KEINE breite Fortnight-Struktur. Damit ist
I0008 die schwächere, drift-konfundierte Version von I0008's eigenem Versprechen.

**Vorbehalt (ehrlich):** mein Sample beginnt 2000 (FOMC-Liste), Cieslaks Headline 1994+;
und meine Zyklus-Wochen-Operationalisierung (days_since // 5, Meeting-Tag = 0) ist EINE
plausible Definition. Aber der Phase-Scan zeigt: keine Anker-Variante rettet die
Permutation, und das pathologisch flache In-Sample (das Cieslaks Periode überlappt)
widerspricht einem stabilen strukturellen Effekt. Re-Test mit 1994-Daten würde die
Permutations-Logik nicht ändern.
