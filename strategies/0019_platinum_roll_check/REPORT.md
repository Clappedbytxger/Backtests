# Strategie 0019 — Platin Jahreswechsel: Roll-Check + früherer Ausstieg

- **Kategorie:** seasonal (Diagnose/Refinement zu 0018)
- **Status:** Roll-Artefakt **ausgeschlossen** → 0018-Edge bestätigt, sauberer Exit gefunden
- **Datum:** 2026-06-04
- **Universum:** Platin-Futures (yfinance `PL=F`, kontinuierlicher Front-Monat)
- **Stichprobe:** Gesamt 2000–2026 (27 Winter). IS/OOS-Schnitt 1. Juli des Mittel-Jahres.

## 1. Frage

0018 fand ein starkes, permutations-signifikantes (p = 0,001), makro-begründetes
Platin-Fenster 18.12.–17.1. Offenes Risiko: `PL=F` ist eine *kontinuierliche*
Front-Monats-Serie. Platin-Kontrakte sind Jan/Apr/Jul/Okt; die volumenbasierte
Rolle vom Januar- in den April-Kontrakt liegt **Mitte Januar (~13.–20.)** — genau
am Basis-Ausstieg 17.1. **Ist ein Teil des Edges nur ein Roll-/Stitching-Gap?**
Der User-Auftrag: bei Roll im Fenster einen leicht früheren Ausstieg testen.

## 2. Methode (drei unabhängige Blickwinkel)

1. **Durchschnittlicher Saison-Pfad** — mittlere kumulierte Rendite über alle
   Winter, ausgerichtet am Einstiegstag. Steigt sie schon im Dezember (vor dem
   Roll), ist der Edge echte Spot-Stärke.
2. **Mittlere Rendite je Kalendertag** — konzentriert sich der Gewinn auf wenige
   Roll-Tage (Mitte Jan.) oder ist er verteilt?
3. **Frühere-Ausstiegs-Varianten** — Einstieg konstant ~18.12., Exit bei 17.1.
   (Basis), 13.1., 10.1., 5.1., 31.12., 28.12.; jede mit eigener Permutation.
   Übersteht der Edge einen Exit **vor** dem Roll, ist die Artefakt-These widerlegt.

## 3. Ergebnisse

### Saison-Pfad (Plot `avg_seasonal_path.png`)

Die mittlere kumulierte Rendite steigt **stetig ab Tag 0**. Bis ~Tag 9 (Ende
Dezember, **vor** dem Mitte-Januar-Roll) sind im Schnitt **+2,85%** aufgebaut — von
insgesamt +4,92% über das volle Fenster. **~58% des Edges entstehen im Dezember.**
Kein flacher Verlauf mit spätem Sprung → keine Roll-Gap-Signatur.

### Kalendertag-Beiträge (Plot `per_calendar_day.png`)

Die Gewinne verteilen sich breit: starke Tage sind u.a. 23.12. (+1,3%), 26.12.
(+1,5%), 30.12., 02.–05.01. — **außerhalb** der Roll-Zone. In nur **15%** der Winter
fällt der größte Einzeltag in die Roll-Zone (13.–20.1.) — keine Konzentration auf
den Roll.

### Edge je Ausstiegsdatum (Plot `edge_vs_exit.png`, Tabelle `exit_variants.csv`)

| Exit       | Trades | Win | Expectancy/Trade | Ø Hold | Sharpe | Perm p   | Exp IS | Exp OOS |
| ---------- | -----: | --: | ---------------: | -----: | -----: | -------: | -----: | ------: |
| 17.01. (Basis) | 27 | 93% |          +5,08% |  18,3d |   0,45 | **0,001** | +4,76% | +5,43% |
| 13.01.     |     27 | 89% |          +4,46% |  15,9d |   0,39 | **0,003** | +4,33% | +4,60% |
| **10.01.** |     27 | 85% |        **+4,20%**|  13,8d | **0,37**| **0,003** | +3,70% | +4,75% |
| 05.01.     |     27 | 78% |          +3,45% |  10,2d |   0,28 | **0,008** | +1,72% | +5,31% |
| 31.12. *(pre-roll)* | 26 | 92% |     +2,61% |   7,8d |   0,16 | **0,016** | +2,02% | +3,20% |
| 28.12. *(pre-roll)* | 24 | 75% |     +1,40% |   6,3d |  −0,08 |   0,103   | +0,53% | +2,15% |

**Die Expectancy fällt glatt und monoton mit der Haltedauer — sie bricht nicht am
Roll ein.** Selbst der **reine Dezember-Exit 31.12.** (komplett vor dem Roll) bleibt
permutations-signifikant (p = 0,016, 92% Trefferquote). Wäre der Effekt ein
Roll-Artefakt, müsste er beim Ausstieg vor Mitte Januar abrupt auf ~0 kollabieren —
das Gegenteil ist der Fall. Nur der ultrakurze 28.12.-Exit (6 Tage) verliert
Signifikanz, schlicht weil zu wenig vom echten Fenster übrig bleibt.

## 4. Verdict

**Roll-Artefakt ausgeschlossen. Der 0018-Edge ist echte saisonale Spot-Stärke.** Drei
unabhängige Belege: (1) >½ des Gewinns akkumuliert im Dezember vor dem Roll; (2) der
größte Tagesmove liegt nur in 15% der Winter in der Roll-Zone; (3) der Edge bleibt
signifikant bis hin zu einem reinen Dezember-Exit.

**Empfohlene Regel-Verfeinerung: Ausstieg ~10. Januar statt 17. Januar.** Der 10.1.
liegt knapp **vor** der Roll-Zone, eliminiert jede Roll-Kontamination und behält ~83%
der Basis-Expectancy (+4,20% vs +5,08%/Trade), bei p = 0,003, 85% Trefferquote,
Sharpe 0,37 und konsistentem IS/OOS (+3,70% / +4,75%). Sauberer und kaum schwächer.

**Grenze der Analyse (ehrlich):** Eine kontraktgenaue Bestätigung bräuchte
Einzelkontrakt-Daten (Norgate/Barchart) — yfinance liefert keine verlässlichen
einzelnen Platin-Kontrakte. Dies ist eine starke Triangulation, kein
Kontrakt-für-Kontrakt-Beweis. Für eine Live-Allokation vor Roll-Risiken den Roll
zusätzlich auf Kontraktebene prüfen.

**Nächster Schritt (0020):** vorab fixierter **Forward-Test** der verfeinerten Regel
(Einstieg 18.12., Exit 10.1., long Platin) — eine Regel, keine weitere Suche, wie
0006/0009. Übersteht sie das, ist Platin der dritte forward-bestätigte Saison-Edge
neben Benzin (0006) und Mastrind (0009).
