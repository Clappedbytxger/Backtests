# Strategie 0016 — Charter Communications Sommerfenster (4.6.–22.7.)

- **Kategorie:** seasonal
- **Status:** testing (vielversprechender Lead, **kein** validierter Edge)
- **Datum:** 2026-06-04
- **Universum:** Charter Communications Inc. Class A (NASDAQ, ISIN US16119P1084)
- **Stichprobe:** Gesamt 2010–2026 (Notierung der heutigen Charter ab Jan. 2010).
  In-Sample 2010–2018 / Out-of-Sample 2019–2026. **Wichtig:** echtes OOS gibt es
  hier nicht — siehe §7.

## 1. Hypothese

Charter Communications zeigt laut Seasonax-Testversion eine wiederkehrende
Stärke von **4. Juni bis 22. Juli**: jedes Jahr long in diesem Fenster, sonst
flat, soll Buy & Hold risikoadjustiert schlagen.

## 2. Makro-Begründung

**Schwach — das ist der wunde Punkt.** Ein Breitband-/Kabelbetreiber hat keinen
realen Angebots-/Nachfrage-Saisonzyklus im Juni/Juli (anders als Benzin zur
Fahrsaison oder Mastrind zur Grillsaison in 0006/0009). Die einzige halbwegs
plausible Ursache ist ein **Pre-Earnings-Drift**: Charter berichtet Q2 typisch
Ende Juli, also kurz *nach* dem Fensterende — ein Anlauf-Effekt vor den Zahlen
wäre denkbar, ist aber dünn und nicht belegt. Nach der Hausregel gilt ein Muster
ohne klare Ursache als **data-gemint, bis Robustheit + OOS das Gegenteil zeigen**.

## 3. Regeln

- Long (Gewicht 1.0) an allen Handelstagen mit Datum im Intervall
  [4. Juni, 22. Juli] jedes Jahres; sonst flat. Ein Trade pro Jahr, ~33
  Handelstage Haltedauer.
- **Look-Ahead-Schutz:** Das Signal ist datums- (also entscheidungszeit-)basiert;
  die Engine verzögert es um einen Bar (`shift(1)`), Ausführung de facto ab dem
  Folgetag. Keine Same-Bar-/Zukunftsinformation.

## 4. Kosten- & Ausführungsannahmen

IBKR-Standardmodell für US-Einzelaktien (`IBKR_DEFAULT`): 0,0035 $/Aktie
Kommission (min. 0,35 $), 3 bps Slippage, 0,2 bps Gebühren pro Seite. Bei
Charter-Notional ≈ 3–4 bps/Seite, ~7 bps Round-Trip. Alle Zahlen **netto**.
Ausführung am Folgetag des Signals (Close-to-Close).

## 5. Ergebnisse (gesamt 2010–2026, netto nach Kosten)

> In-sample-Sicht: das Fenster wurde auf genau dieser Historie gewählt.

| Kennzahl               |             Wert |
| ---------------------- | ---------------: |
| CAGR                   |            7,02% |
| Sharpe                 |             0,60 |
| Sortino                |             0,96 |
| Calmar                 |             0,43 |
| Max Drawdown           |          −16,29% |
| Trefferquote           |     88% (14/16)  |
| Profit-Faktor          |            90,5  |
| Payoff-Ratio           |            12,9  |
| Expectancy/Trade       |           +7,37% |
| Ø Haltedauer           |     33,8 Tage    |
| Trades                 |              16  |
| Exposure (Zeit im Markt)|           13,1%  |

**Vergleich Buy & Hold (gesamt):** CAGR 8,29%, Sharpe **0,35**, MaxDD **−84,3%**.
Das Fenster liefert minimal weniger CAGR, aber bei nur 13% Marktzeit — also ein
Vielfaches an Rendite pro investiertem Tag — und umgeht den −84%-Absturz
2021–2022 komplett (Sharpe 0,60 vs. 0,35).

### In-Sample vs. Out-of-Sample (Konsistenz, kein echter Forward)

| Periode             | Trades | Win | Expectancy/Trade | Sharpe | MaxDD   |
| ------------------- | -----: | --: | ---------------: | -----: | ------: |
| In-Sample 2010–2018 |      9 | 89% |           +7,61% |   0,69 |  −9,67% |
| OOS 2019–2026       |      7 | 86% |           +7,06% |   0,51 | −16,29% |

Beide Hälften nahezu deckungsgleich (~7% Expectancy, ~87% Trefferquote) — die
zweite Hälfte enthält den brutalen 2022er-Einbruch und das Fenster gewann
trotzdem 6/7 Jahre. Das schließt ein reines „erste-Hälfte-Artefakt“ aus.

## 6. Signifikanz (gesamte Stichprobe)

| Test                                  |               Wert |
| ------------------------------------- | -----------------: |
| Permutationstest p-Wert               |          **0,004** |
| Bootstrap Sharpe 95%-KI               |     [0,11, 1,06]   |
| t-Test mittlere Rendite p             |          **0,001** |
| Deflated Sharpe (n_trials = 121)      |          0,00 (PSR)|

Der **Permutationstest ist der entscheidende Kontrolltest**: Er behält Exposure
und die Aufwärtsdrift der Aktie bei und würfelt nur, *wann* die Long-Tage liegen.
p = 0,004 heißt: das konkrete Juni–Juli-Timing schlägt 99,6% gleich langer
Zufallsfenster — der Effekt ist also mehr als „Charter steigt ohnehin meistens“.

Die **Deflated Sharpe = 0,00** ist hier kein Widerspruch: Wird die volle
Suchbreite belastet (121 Fenster-Varianten als konservativer Seasonax-Proxy),
kollabiert die per-Period-DSR strukturell — exakt wie bei den Discovery-Screens
0005/0008/0011. Sie sagt korrekt: *ein* in-sample gewähltes Fenster ist allein
noch kein Beweis. Das Gewicht liegt daher auf Permutation + IS/OOS + Robustheit.

## 7. Robustheit

- **Fenster-Verschiebung:** Start- und Enddatum je ±10 Kalendertage verschoben
  → **121/121 Kombinationen positiv** (Expectancy 4,2%–7,8%, exaktes Fenster
  7,4%). Ein zusammenhängendes grünes Plateau, kein Knife-Edge — sehr
  beruhigend (siehe `plots/robustness_heatmap.png`).
- **Teilperioden:** IS und OOS konsistent (§5).
- **Kein echtes Out-of-Sample.** Der schwerwiegendste Vorbehalt: Seasonax hat das
  Fenster auf der *gesamten* Historie 2010–2026 als bestes herausgesucht. Damit
  ist auch meine „OOS“-Hälfte 2019–2026 in die Fensterwahl eingeflossen. Der
  IS/OOS-Split zeigt nur *interne Konsistenz*, ist aber **kein** Forward-Test wie
  bei 0006/0009.
- **Wenige Trades:** nur 16 (1/Jahr) — dieselbe strukturelle Schwäche aller
  Einzel-Saisonfenster. Statistische Power gering.

## 8. Verdict

**Behalten als Lead, nicht handeln — noch nicht validiert.** Die Statistik ist
die stärkste, die ein frisch eingereichtes Saisonfenster im Katalog je hatte
(Permutation p = 0,004, IS≈OOS, 121/121 robust, klar besserer Sharpe als B&H).
Aber drei Dinge fehlen für einen echten Edge: (1) ein **echtes Out-of-Sample** —
das Fenster ist auf allen Daten gemint; (2) eine **belastbare Makro-Ursache** —
Breitband hat keine Juni/Juli-Saison; (3) **mehr Trades**.

**Nächster Schritt (0017):** vorab fixierte Regel ab heute **forward** testen
(wie 0006) **und/oder** dasselbe Kalenderfenster auf einen **Peer-Korb** (Comcast,
Altice, weitere Kabel/Telco) anwenden — das gibt eine Cross-Sectional-/Makro-Lesart
und vervielfacht die Trade-Zahl. Erst wenn das Fenster auf ungesehenen Daten oder
über Peers hält, wird aus dem Lead ein Kandidat.
