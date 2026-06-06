# Strategie 0026 — Kakao Aprilfenster (8.4.–20.4.)

- **Kategorie:** seasonal
- **Status:** **abgelehnt** (Permutationstest verfehlt 5 %; unter Buy & Hold; Drift-Falle)
- **Datum:** 2026-06-05
- **Universum:** Kakao-Future (ICE, yfinance `CC=F`, kontinuierlicher Front-Monat)
- **Stichprobe:** Gesamt 2000–2026. In-Sample 2000–2012 / Out-of-Sample 2013–2026
  (Schnitt am 1. Januar, der nie ein Aprilfenster zerschneidet).

## 1. Hypothese

Kakao zeigt laut Seasonax-Lead eine wiederkehrende Stärke von **8. bis 20. April**: jeden
April long im Kakao-Future (sonst flat) soll Buy & Hold risikoadjustiert schlagen. Sehr
kurzes Fenster: ~12 Kalendertage, ~8 Handelstage.

## 2. Makro-Begründung

**Plausibel, aber dünn.** Westafrika (Elfenbeinküste + Ghana, ~60 % des Weltangebots) fährt
die **Haupternte** Oktober–März und die kleinere **Mid-Crop (Zwischenernte)** April–September.
April ist der Übergang: Schäden durch den trocken-staubigen **Harmattan**-Wind an der Haupternte
werden sichtbar, und erste Sorgen um Größe/Qualität der Mid-Crop kommen auf → möglicher
Wetter-/Angebots-Aufschlag. Das ist eine echte Saison­mechanik, aber kein scharfer
kalenderfixierter Nachfrage-Event. Der Permutationstest (Lehre aus 0017) entscheidet — und er
entscheidet gegen die Hypothese.

## 3. Regeln

- Long (Gewicht 1.0) an allen Handelstagen im Intervall [8. April, 20. April] jedes Jahres;
  sonst flat. Ein Trade pro Jahr, ~8 Handelstage.
- **Look-Ahead-Schutz:** datumsbasiertes Signal, Engine verzögert um einen Bar (`shift(1)`).
- **Daten-Guards:** Abbruch bei nicht-positivem Schluss (Lehre 0005) und bei einem Jahr mit
  < 50 distinkten Schlusskursen (Lehre 0025). `CC=F` ist sauber: 26 J., ~250 distinkte
  Kurse/Jahr, kein Einfrieren.

## 4. Kosten- & Ausführungsannahmen

`IBKR_FUTURES`: Kommission in wenige bps gefaltet, 2 bps Slippage + 0,5 bps Gebühren pro
Seite (~5 bps Round-Trip). Alle Zahlen **netto**. Ausführung am Folgetag.

## 5. Ergebnisse (gesamt 2000–2026, netto nach Kosten)

| Kennzahl          |             Wert |
| ----------------- | ---------------: |
| CAGR              |           2,19 % |
| Sharpe            |         **0,06** |
| Sortino           |           0,10   |
| Calmar            |           0,13   |
| Max Drawdown      |          −16,4 % |
| Trefferquote      |     56 % (15/27)  |
| Profit-Faktor     |           2,50   |
| Payoff-Ratio      |           2,00   |
| Expectancy/Trade  |         +2,34 %  |
| Median/Trade      |       **+0,72 %**|
| Ø Haltedauer      |         8,9 Tage |
| Trades            |          **27**  |
| Exposure          |           3,6 %  |

**Vergleich Buy & Hold:** CAGR **6,20 %**, Sharpe **0,29**, MaxDD −77,7 %. Das Fenster bleibt
deutlich **unter** Buy & Hold (Sharpe 0,06 vs 0,29) und gibt zwei Drittel der Kakao-Rendite auf
für einen marginalen, insignifikanten Kick.

### Fat-Tail-getrieben, nicht typisch

Der **Median-Trade liegt bei nur +0,72 %** — der typische April ist nahezu ein Münzwurf. Der
positive Mittelwert (+2,34 %) wird von einer Handvoll Spikes getragen: 2008 **+18,9 %**, 2025
+13,6 %, 2024 +12,8 %, 2018 +9,7 %, 2023 +8,5 %. Es ist **kein** reiner Einzel-Ausreißer
(ohne den 2024-Superzyklus bleibt der Mittelwert +1,94 %), aber die Rendite stammt aus dem
fetten rechten Tail einzelner Angebotsschock-Jahre, nicht aus einer verlässlichen Saison.

### In-Sample vs. Out-of-Sample

| Periode             | Trades | Win  | Expectancy/Trade | Sharpe |
| ------------------- | -----: | ---: | ---------------: | -----: |
| In-Sample 2000–2012 |     13 | 54 % |          +1,61 % |  −0,07 |
| OOS 2013–2026       |     14 | 57 % |          +3,02 % |   0,16 |

Beide Hälften nahe der Nulllinie; die IS-Hälfte hat sogar **negativen Sharpe** (−0,07). Kein
Era ist überzeugend — beide sind Münzwurf-nah, das OOS leicht besser nur durch die 2023–2025-
Schock-Jahre.

## 6. Signifikanz (gesamte Stichprobe)

| Test                              |             Wert |
| --------------------------------- | ---------------: |
| Permutationstest p-Wert           |   **0,074** ✗    |
| Bootstrap Sharpe 95%-KI           | [−0,34, 0,43] ✗  |
| t-Test mittlere Rendite p         |     0,079 ✗      |
| Deflated Sharpe (n_trials = 49)   |       0,00 (PSR) |

Der **Permutationstest verfehlt die 5 %-Schwelle (p = 0,074)**: das April-Timing ist nicht
sauber von zufälligem gleich langem Frühjahrs-Timing zu unterscheiden. Das ist besser als die
toten Leads (Nasdaq 0,31, Akshaya 0,83), aber es besteht den Test **nicht** — und anders als
bei Zink (0025, p = 0,031 auf einem *driftarmen* Asset) ist Kakao **driftstark** (B&H-CAGR
6,2 %), sodass die scheinbare Stärke genau die 0017-Drift-Falle sein kann. Bootstrap-KI und
t-Test bestätigen die Insignifikanz.

## 7. Robustheit

- **Fenster-Verschiebung:** 48/49 Kombinationen (±6 Tage) positiv. **Hier wertlos** — exakt
  das Nasdaq-/0017-Muster: ein driftstarkes Asset (Kakao stieg über 26 J. inkl. 2024-
  Superzyklus) lässt fast jedes kurze Frühjahrsfenster grün erscheinen. Ein Plateau ist nur
  bei *driftarmen* Assets aussagekräftig (vgl. Platin 0018, Zink 0025) — nicht hier.
- **Teilperioden:** beide Hälften Münzwurf-nah, IS-Sharpe negativ (§5).
- **Verteilung:** Median ≈ 0, Mittelwert fat-tail-getrieben (§5) → fragil.

## 8. Verdict

**Abgelehnt.** Kakao-April besteht den Permutationstest nicht (p = 0,074 > 0,05), liegt klar
unter Buy & Hold (Sharpe 0,06 vs 0,29), und sein 48/49-Robustheits-Plateau ist die
Drift-Falle aus 0017 — auf einem driftstarken Asset sind kurze Frühjahrsfenster fast immer
grün. Der Median-Trade ist mit +0,72 % praktisch null; die positive Expectancy stammt aus dem
fetten Tail einzelner Angebotsschock-Jahre (2008, 2023–2025), nicht aus einer verlässlichen
Saison. Damit reiht sich 0026 bei den abgelehnten Saison-Leads ein (Nasdaq 0017, Ostern 0022,
Akshaya 0023) — und bestätigt erneut die Kern-Methode: **der Permutationstest trennt echtes
Timing (Zink 0,031 / Platin 0,001, beide driftarm) von bloßer Drift (Kakao 0,074, driftstark)**.
Keine Eskalation; kein Forward-Test.
