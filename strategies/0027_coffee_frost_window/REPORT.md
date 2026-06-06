# Strategie 0027 — Kaffee Frostfenster (15.7.–28.8.)

- **Kategorie:** seasonal
- **Status:** **abgelehnt** (Permutationstest verfehlt klar; IS-Hälfte netto negativ; fat-tail-getrieben)
- **Datum:** 2026-06-05
- **Universum:** Arabica-Kaffee-Future (ICE, yfinance `KC=F`, kontinuierlicher Front-Monat)
- **Stichprobe:** Gesamt 2000–2026. In-Sample 2000–2012 / Out-of-Sample 2013–2026
  (Schnitt am 1. Januar, der nie ein Sommerfenster zerschneidet).

## 1. Hypothese

Kaffee zeigt laut Seasonax-Lead eine wiederkehrende Stärke von **15. Juli bis 28. August**:
jeden Sommer long im Arabica-Future (sonst flat) soll Buy & Hold risikoadjustiert schlagen.
Fenster ~44 Kalendertage, ~31 Handelstage.

## 2. Makro-Begründung

**Stärkere Story als Kakao (0026) — aber genau das ist die Falle.** Brasilien produziert ~⅓
des Welt-Arabica; sein Winter (Jun–Aug) trägt **Frostrisiko**, und ein harter Frost (1975,
1994, 2021) kann einen Teil der nächsten Ernte über Nacht vernichten. Frost ist *nicht*
eingepreist, weil er kommen *kann* oder nicht — eine echte Wetterprämie. Gegenkraft: die
brasilianische **Ernte** (Mai–Sep) drückt Angebot in den Markt (bärisch). Das Fenster ist ein
Tauziehen aus Erntedruck und Frostprämie.

**Der Haken (und die Lehre):** Ein *Überraschungs*-Treiber erzeugt keinen verlässlichen
Kalender-Edge. Man kann eine Überraschung nicht timen — man sitzt nur in einem
hochvolatilen Fenster long und *hofft*, dass ein Schock hineinfällt. Manchmal tut er das
(2021), oft nicht, und manchmal frisst man −24 % (2000). Der Permutationstest bestätigt das.

## 3. Regeln

- Long (Gewicht 1.0) an allen Handelstagen im Intervall [15. Juli, 28. August] jedes Jahres;
  sonst flat. Ein Trade pro Jahr, ~31 Handelstage.
- **Look-Ahead-Schutz:** datumsbasiertes Signal, Engine verzögert um einen Bar (`shift(1)`).
- **Daten-Guards:** Abbruch bei nicht-positivem Schluss (0005) und bei < 50 distinkten
  Schlusskursen/Jahr (0025). `KC=F` ist sauber: 26 J., ~235 distinkte Kurse/Jahr.

## 4. Kosten- & Ausführungsannahmen

`IBKR_FUTURES`: Kommission in wenige bps gefaltet, 2 bps Slippage + 0,5 bps Gebühren pro
Seite (~5 bps Round-Trip). Alle Zahlen **netto**. Ausführung am Folgetag.

## 5. Ergebnisse (gesamt 2000–2026, netto nach Kosten)

| Kennzahl          |             Wert |
| ----------------- | ---------------: |
| CAGR              |           2,48 % |
| Sharpe            |         **0,10** |
| Sortino           |           0,15   |
| Calmar            |           0,06   |
| Max Drawdown      |          −43,2 % |
| Trefferquote      |     54 % (14/26)  |
| Profit-Faktor     |           1,97   |
| Payoff-Ratio      |           1,69   |
| Expectancy/Trade  |         +3,41 %  |
| Median/Trade      |       **+1,55 %**|
| Ø Haltedauer      |        32,1 Tage |
| Trades            |          **26**  |
| Exposure          |          12,6 %  |

**Vergleich Buy & Hold:** CAGR 2,99 %, Sharpe **0,20**, MaxDD −71,6 %. Das Fenster bleibt
**unter** B&H und trägt mit −43 % MaxDD ein brutales Risiko bei nur 12,6 % Marktzeit.

### Fat-Tail-Lotterie, keine Saison

Mittelwert +3,41 %, aber **ohne die drei Schockjahre 2020/2021/2025 fällt er auf +1,23 % und
der Median auf −1,1 %**. Die größten Moves: 2020 **+35,2 %** (COVID-Angebotschaos), 2025
+31,5 %, 2021 +25,8 % (echter Frost), 2014 +22,8 % (Dürre) — gegen 2000 **−24,3 %**, 2019
−15,6 %, 2005 −10,4 %. Riesige Streuung in *beide* Richtungen, Trefferquote 54 % ≈ Münzwurf.
Das ist kein Saison-Edge, sondern ein Long-Vega-Sitz auf Wetterschocks.

### In-Sample vs. Out-of-Sample — alles im OOS, IS netto negativ

| Periode             | Trades | Win  | Expectancy/Trade | Sharpe | Profit-Faktor |
| ------------------- | -----: | ---: | ---------------: | -----: | ------------: |
| In-Sample 2000–2012 |     13 | 62 % |          −0,25 % |  −0,14 |      **0,93** |
| OOS 2013–2026       |     13 | 46 % |          +7,07 % |   0,34 |          3,07 |

Die **IS-Hälfte verliert netto Geld** (PF 0,93) — trotz 62 % Trefferquote, weil die Verluste
größer sind als die Gewinne. Die *gesamte* Performance liegt im OOS und stammt aus wenigen
fetten Gewinnern (Ø-Gewinn 22,7 %!). Das ist exakt das Era-Artefakt aus Nasdaq/0017: keine
über die Zeit stabile Saison, sondern eine Häufung von Schocks in der zweiten Hälfte.

## 6. Signifikanz (gesamte Stichprobe)

| Test                              |             Wert |
| --------------------------------- | ---------------: |
| Permutationstest p-Wert           |   **0,187** ✗    |
| Bootstrap Sharpe 95%-KI           | [−0,28, 0,48] ✗  |
| t-Test mittlere Rendite p         |     0,195 ✗      |
| Deflated Sharpe (n_trials = 121)  |       0,00 (PSR) |

Der **Permutationstest verfehlt klar (p = 0,187)** — schlechter noch als Kakao (0,074): das
Juli/August-Timing ist nicht von zufälligem gleich langem Sommer-Timing zu unterscheiden.
Bootstrap-KI und t-Test bestätigen die Insignifikanz.

## 7. Robustheit

- **Fenster-Verschiebung:** 118/121 Kombinationen positiv — **hier wertlos**: bei +3 % Ø-Move
  und solcher Streuung ist fast jedes Sommerfenster im Schnitt grün, ohne dass das Timing
  etwas bedeutet (vgl. Drift-/Tail-Falle 0017/0026). Der Permutationstest hebelt das Plateau aus.
- **Teilperioden:** IS netto negativ, OOS nur durch Schockjahre positiv (§5) — instabil.
- **Verteilung:** Median nahe null, Mittelwert fat-tail-getrieben, −43 % MaxDD → fragil.

## 8. Verdict

**Abgelehnt.** Kaffee-Sommerfenster besteht den Permutationstest nicht (p = 0,187), liegt unter
B&H, verliert in der IS-Hälfte netto Geld, und seine positive Gesamtzahl stammt aus einer
Handvoll Wetter-/Angebotsschock-Jahren (2020/2021/2025) — entfernt man sie, ist der Median
negativ. **Die Pointe:** die Makro-Story war *besser* als bei Kakao (echte, nicht eingepreiste
Frostprämie statt eingepreister Ernte) — und trotzdem gibt es keinen handelbaren Saison-Edge,
**weil man eine Überraschung nicht timen kann**. Long in einem volatilen Fenster zu sitzen und
auf einen Schock zu hoffen, ist kein Edge, sondern bezahltes Tail-Risiko. Reiht sich bei den
abgelehnten Saison-Leads ein (Nasdaq 0017, Ostern 0022, Akshaya 0023, Kakao 0026). Keine
Eskalation, kein Forward-Test.

**Methodisch bestätigt:** Der Permutationstest trennt zuverlässig echtes Timing auf driftarmen
Assets (Platin 0,001 / Zink 0,031) von Drift- und Tail-Illusionen (Kakao 0,074, Kaffee 0,187).
Eine starke Story ersetzt den Test nicht — sie verführt nur stärker, ihn zu überspringen.
