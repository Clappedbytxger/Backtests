# Strategie 0021 — Platin Jahreswechsel: Forward-/Out-of-Sample-Test

- **Kategorie:** seasonal (Validierung von 0018/0019)
- **Status:** Kandidat — Cross-Instrument- & Cross-Asset-OOS bestanden; echter
  zeitlicher Forward-Test (Live-Winter) vorab registriert, noch ausstehend
- **Datum:** 2026-06-04
- **Eingefrorene Regel:** Long vom **18.12. bis 10.1.** jeden Winter, sonst flat.
  Ein Trade/Winter, ~14 Handelstage. T+1-Ausführung, Kosten netto. (Exit 10.1.
  aus 0019 — knapp vor dem Mitte-Januar-Futures-Roll.)

## 1. Das Ehrlichkeitsproblem

0018 hat das Platin-Fenster auf der **vollen Historie** geminte (Seasonax), und der
10.1.-Exit kam aus einem In-Sample-Exit-Scan in 0019. Damit existiert in den
vorhandenen Daten **kein sauberer zeitlicher Out-of-Sample** — der IS/OOS-Split in
0018 ist interne Konsistenz, kein Forward-Test. Der **einzige echte zeitliche
Forward-Test** ist, die eingefrorene Regel auf **ungesehene künftige Winter** (ab
Dez. 2026) zu handeln. Das ist unten vorab registriert.

Was sich **jetzt** sauber prüfen lässt: Hält die **eingefrorene Regel** — ohne
jedes Re-Fitting — auch auf Instrumenten, auf denen das Fenster **nie gemint** wurde?

## 2. Methode — zwei ungesehene Instrumente, identische Regel

1. **PPLT** — physisch besicherter Platin-ETF. Gleicher **Spot**-Platinpreis, aber
   völlig anderes Instrument **ohne Futures-Roll**. Hält das Fenster hier, ist der
   Edge **kein PL=F-Continuous-/Roll-Artefakt** (unabhängig von 0019s Argumentation).
2. **PA=F** — Palladium, das **Schwester-PGM-Metall** mit derselben Makro (Auto-
   Katalysator-Nachfrage + Jahresstart-Restocking + Schmuck). Das Fenster wurde auf
   **Platin** gewählt, nie auf Palladium → ein **echt ungesehenes Asset**. Funktionieren
   dieselben Daten ohne Re-Fitting, **generalisiert** die Jahreswechsel-PGM-Saison —
   echter Out-of-Sample-Beleg für die *Auswahl*, nicht nur das Instrument.

`PL=F` selbst ist nur als **In-Sample-Referenz** (0018/0019) enthalten, klar markiert.

## 3. Ergebnisse (eingefrorene Regel, netto nach Kosten)

| Instrument | Rolle | Stichprobe | Trades | Win | Exp/Trade | Sharpe | (B&H) | CAGR | Perm p | Bootstrap-Sharpe-KI | t-Test p |
| ---------- | ----- | ---------- | -----: | --: | --------: | -----: | ----: | ---: | -----: | ------------------- | -------: |
| **PL=F** | Referenz (in-sample) | 2000–2026 | 27 | 85% | +4,20% | 0,37 | 0,30 | 4,70% | **0,003** | [−0,03; 0,78] | 0,004 |
| **PPLT** | OOS-Instrument (Spot, kein Roll) | 2010–2026 | 17 | 82% | +4,49% | 0,36 | 0,07 | 4,53% | **0,003** | [−0,14; 0,84] | 0,022 |
| **PA=F** | OOS-Asset (Schwester-PGM, ungesehen) | 2000–2026 | 27 | 93% | +6,60% | 0,34 | 0,26 | 6,51% | **0,004** | **[0,01; 0,63]** | 0,018 |

## 4. Interpretation

**Beide ungesehenen Instrumente bestätigen die eingefrorene Regel — ohne Re-Fitting.**

- **PPLT (kein Roll):** Dieselben Dezember-/Januar-Tage liefern auf dem physischen
  ETF +4,49%/Trade, 82% Win, **Perm p=0,003** — bei einem Instrument, das **keinen
  Futures-Roll** hat. Das schließt das Roll-/Stitching-Artefakt **unabhängig** aus
  (komplementär zu 0019) und zeigt zugleich den krassen Kontrast zu B&H (Sharpe 0,36
  vs **0,07**): Platin-Spot driftet über 16 Jahre praktisch nicht — der gesamte Edge
  ist Timing, keine eingefangene Drift.
- **PA=F (ungesehenes Asset):** Das auf Platin gewählte Fenster generalisiert
  **sauber** auf das Schwestermetall Palladium: **93% Win**, +6,60%/Trade,
  **Perm p=0,004**, und als einziges der drei schließt das **Bootstrap-KI [0,01; 0,63]
  die Null aus**. Die Kapitalkurve ist eine ruhige Saison-Treppe, während Palladium-B&H
  über 26 Jahre seitwärts schlingert. Das ist der stärkste Beleg: ein verwandtes, beim
  Mining nie berührtes Asset zeigt denselben Effekt mit gleicher Signifikanz.

Alle drei sind über die Permutation konsistent signifikant (p = 0,003–0,004), mit
Expectancy 4,2–6,6%/Trade und Trefferquoten 82–93%. Die makroökonomische Lesart
(PGM-Restocking + Schmucknachfrage vor chin. Neujahr) ist genau das, was eine
Generalisierung Platin→Palladium erwarten lässt.

## 5. Grenzen (ehrlich)

1. **Kein zeitlicher Forward-Test.** Dies ist Cross-Instrument-/Cross-Asset-OOS,
   kein Out-of-Time-Test. Die Fenster-**Daten** sind weiterhin die auf Platin
   geminten — Palladium zeigt, dass die *Makro* generalisiert, aber beide PGM teilen
   **denselben Treiber**, sind also nicht vollständig unabhängig.
2. **Geteilte Makro = korrelierte Evidenz.** Platin und Palladium können in einem
   gemeinsamen PGM-Schock zusammen kippen; zwei PGM sind nicht zwei unabhängige Ziehungen.
3. **PPLT erst ab 2010** (17 Winter) — kürzere Stichprobe.
4. **Kontraktgenauer Beweis** bräuchte weiterhin Norgate/Barchart-Einzelkontrakte
   (yfinance hat keine) — PPLT ist hier der beste verfügbare roll-freie Ersatz.

## 6. Vorab-Registrierung — echter Live-Forward-Test

**Eingefroren am 2026-06-04, vor jedem ungesehenen Winter:**
- **Regel:** Long Platin (`PL=F` bzw. PPLT) **18.12. → 10.1.**, ein Trade/Winter,
  T+1-Ausführung, IBKR-Kosten. Keine Parameter mehr anzufassen.
- **Erste ungesehene Beobachtung:** Winter **2026/27** (Einstieg ~18.12.2026).
- **Erfolgskriterium:** über die nächsten ~5 Winter Expectancy klar > 0 und
  Trefferquote in der Größenordnung der ~85%-Historie; ein bis zwei Verlierer sind
  erwartbar (Historie hatte 15% Verlierer) und kein Falsifikat.
- **Optionale Generalisierungs-Bestätigung:** Palladium (`PA=F`) parallel mitlaufen
  lassen — beide PGM im selben Fenster.

## 7. Verdict

**Platin steigt von „Lead" zu echtem Kandidaten auf.** Die eingefrorene
Jahreswechsel-Regel besteht zwei ungesehene Tests ohne Re-Fitting: einen
roll-freien ETF (PPLT, schließt das Artefakt unabhängig aus) **und** ein beim Mining
nie berührtes Schwester-Asset (Palladium, 93% Win, Perm p=0,004, Bootstrap-KI ohne
Null). Zusammen mit 0018 (Perm p=0,001, IS≈OOS, echte Makro) und 0019
(Roll-Artefakt ausgeschlossen) ist das die bisher am breitesten validierte
Saison-Idee im Katalog.

**Bleibt offen:** der echte **zeitliche** Forward-Test über künftige Winter (ab
Dez. 2026, §6 registriert). Bis dahin ist Platin der **dritte Saison-Kandidat** neben
Benzin (0006) und Mastrind (0009) — und der bestbegründete von den dreien. Das
0020-Triple-Overlay kann das Platin-Bein damit mit deutlich höherer Zuversicht führen,
bleibt aber bis zum Live-Forward formal „Kandidat", nicht „validated".
