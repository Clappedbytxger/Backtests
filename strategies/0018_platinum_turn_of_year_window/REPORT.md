# Strategie 0018 — Platin Jahreswechsel-Fenster (18.12.–17.1.)

- **Kategorie:** seasonal
- **Status:** testing (**stärkster Seasonax-Lead bisher**, noch kein validierter Edge)
- **Datum:** 2026-06-04
- **Universum:** Platin-Futures (NYMEX, yfinance `PL=F`, kontinuierlicher Front-Monat)
- **Stichprobe:** Gesamt 2000–2026. In-Sample 2000–2013 / Out-of-Sample 2013–2026
  (Schnitt am 1. Juli, damit kein Winter-Trade zerschnitten wird).

## 1. Hypothese

Platin zeigt laut Seasonax-Testversion eine wiederkehrende Stärke von **18. Dezember
bis 17. Januar** (über den Jahreswechsel): jeden Winter long im Platin-Future, sonst
flat, soll Buy & Hold risikoadjustiert schlagen.

## 2. Makro-Begründung

**Erstmals plausibel — anders als bei 0016/0017.** Platin ist zu ~70% Industrie-/
Automotive-Metall (Katalysatoren) und zu einem erheblichen Teil Schmuckmetall. Zwei
sich überlagernde Saisontreiber zum Jahreswechsel:
1. **Schmuck-Fabrikation vor dem chinesischen Neujahr** (Ende Jan./Feb.): Hersteller
   kaufen im Dezember/Januar Rohplatin ein → Nachfragesog.
2. **Jahresstart-Restocking** der Auto-/Industrieabnehmer mit neuen Jahresbudgets.

Das ist eine echte Angebots-/Nachfrage-Story, kein reines Kalenderartefakt — daher
ein ernsthafter Test statt sofortigem Data-Mining-Verdacht. Der Permutationstest
(Lehre aus 0017) bleibt trotzdem der Schiedsrichter.

## 3. Regeln

- Long (Gewicht 1.0) an allen Handelstagen im Intervall [18. Dez. (Jahr y),
  17. Jan. (Jahr y+1)]; sonst flat. Ein Trade pro Winter, ~18–20 Handelstage.
- **Look-Ahead-Schutz:** datumsbasiertes Signal, Engine verzögert um einen Bar
  (`shift(1)`). **Futures-Guard** (CLAUDE-Lehre 0005): Abbruch bei nicht-positivem
  Schlusskurs (kein Vorkommen bei Platin).

## 4. Kosten- & Ausführungsannahmen

`IBKR_FUTURES`: Kommission in wenige bps gefaltet, 2 bps Slippage + 0,5 bps Gebühren
pro Seite (~5 bps Round-Trip). Alle Zahlen **netto**. Ausführung am Folgetag.

## 5. Ergebnisse (gesamt 2000–2026, netto nach Kosten)

| Kennzahl                |             Wert |
| ----------------------- | ---------------: |
| CAGR                    |            5,68% |
| Sharpe                  |         **0,45** |
| Sortino                 |             0,70 |
| Calmar                  |             0,32 |
| Max Drawdown            |          −17,55% |
| Trefferquote            |     93% (25/27)  |
| Profit-Faktor           |            16,5  |
| Payoff-Ratio            |             1,32 |
| Expectancy/Trade        |           +5,08% |
| Ø Haltedauer            |     18,3 Tage    |
| Trades                  |          **27**  |
| Exposure                |            8,3%  |

**Vergleich Buy & Hold:** CAGR 6,42%, Sharpe **0,30**, MaxDD **−73,5%**. Das Fenster
liefert nahezu gleiche Rendite bei nur **8% Marktzeit**, höherem Sharpe und einem
Viertel des Drawdowns — und umgeht die −73%-Achterbahn von Platin komplett.

### In-Sample vs. Out-of-Sample — **konsistent über beide Hälften**

| Periode             | Trades | Win  | Expectancy/Trade | Sharpe |
| ------------------- | -----: | ---: | ---------------: | -----: |
| In-Sample 2000–2013 |     14 | 100% |           +4,76% |   0,69 |
| OOS 2013–2026       |     13 |  85% |           +5,43% |   0,36 |

Beide Hälften klar positiv (anders als Nasdaq, wo alles in der 2. Hälfte lag). Die
OOS-Hälfte ist etwas schwächer im Sharpe (höhere Vola, 2 Verlierer), aber mit
+5,4% Expectancy sogar leicht höherer Rendite/Trade. Die Equity-Kurve steigt über
die **gesamten** 26 Jahre als saubere Treppe — kein Era-Artefakt.

## 6. Signifikanz (gesamte Stichprobe)

| Test                              |             Wert |
| --------------------------------- | ---------------: |
| Permutationstest p-Wert           |     **0,001** ✓  |
| Bootstrap Sharpe 95%-KI           |  [0,04, 0,87] ✓  |
| t-Test mittlere Rendite p         |     **0,001** ✓  |
| Deflated Sharpe (n_trials = 121)  |       0,00 (PSR) |

Der entscheidende **Permutationstest besteht mit p = 0,001**: das konkrete
Dezember–Januar-Timing schlägt 99,9% gleich langer Zufallsfenster. Bei einem
**driftarmen Future** (B&H-Sharpe nur 0,30 über 26 Jahre) ist das doppelt
aussagekräftig — der Effekt kann *nicht* bloß eingefangene Aufwärtsdrift sein
(genau die Falle, die Nasdaq/0017 entlarvt hat). Bootstrap-KI und t-Test bestätigen.
DSR = 0 ist wie immer die volle Such-Strafe; Gewicht liegt auf Permutation + IS/OOS
+ Robustheit + Makro.

## 7. Robustheit

- **Fenster-Verschiebung:** 121/121 Kombinationen positiv (siehe Heatmap). Hier —
  anders als bei der Trend-Aktie Nasdaq — **aussagekräftig**, weil der Future kaum
  driftet: ein zusammenhängendes Plateau bei niedriger Drift + signifikanter
  Permutation = robuster Saisoneffekt.
- **Teilperioden:** beide Hälften positiv und konsistent (§5).
- **Offene Risiken (Hauptvorbehalte):**
  1. **Kein echtes Out-of-Sample** — Seasonax minte das Fenster auf allen Daten.
     IS/OOS-Split = interne Konsistenz, kein Forward-Test.
  2. **Roll-Artefakt-Risiko:** Platin-Kontrakte sind Jan/Apr/Jul/Okt; die
     `PL=F`-Continuous-Serie rollt um den Januar-Verfall (~Mitte Januar) vom
     Jan- in den Apr-Kontrakt — also **genau am Fensterende**. Ein Teil des Effekts
     könnte ein Stitching-/Roll-Gap sein statt echter Spot-Stärke. Muss vor
     Eskalation auf einem einzeln gehaltenen Kontrakt / sauber ratio-adjustierten
     Serie gegengeprüft werden.
  3. Nur 27 Trades — solide für ein Saisonfenster, aber Power weiter begrenzt.

## 8. Verdict

**Behalten als stärksten Lead, noch nicht handeln.** 0018 ist der bisher beste
Seasonax-Kandidat: Permutation p = 0,001 (vs. Nasdaq 0,31), **konsistent über beide
Hälften**, 27 Trades (mehr als Charter/Nasdaq), klar besserer Sharpe als B&H bei 8%
Marktzeit — und erstmals eine **echte Makro-Ursache** (Schmucknachfrage vor CNY +
Jahresstart-Restocking). Genau das Profil, das ein Saisonfenster haben sollte.

**Nächster Schritt (0019):** (1) **Roll-Artefakt ausschließen** — Effekt auf einem
einzeln gehaltenen Jan/Apr-Kontrakt bzw. sauber ratio-adjustierter Serie nachrechnen;
(2) bei Bestätigung **vorab fixierter Forward-Test** wie 0006/0009 (eine Regel, keine
weitere Suche). Übersteht das Fenster beides, wird aus dem Lead ein echter Kandidat —
der dritte forward-bestätigte Saison-Edge neben Benzin (0006) und Mastrind (0009).
