# Strategie 0028 — Erdgas Herbstfenster (21.9.–1.11.)

- **Kategorie:** seasonal
- **Status:** **testing / stärkster Seasonax-Lead im Katalog** (Permutation p=0,001
  UND Bootstrap-Sharpe-KI schließt die Null aus — beides zugleich schaffte bisher
  kein anderer Saison-Lead).
- **Datum:** 2026-06-05
- **Universum:** NYMEX-Erdgas-Future (Henry Hub, yfinance `NG=F`, kontinuierlicher
  Front-Monat). **NUR Future, nie UNG** (Contango-Zerfall, Lehre 0004).
- **Stichprobe:** Gesamt 2000–2026. In-Sample 2000–2012 / Out-of-Sample 2013–2026
  (Schnitt am 1. Januar, der nie ein Herbstfenster zerschneidet).

## 1. Hypothese

Erdgas zeigt laut Seasonax-Lead eine wiederkehrende Stärke von **21. September bis
1. November**: jeden Herbst long im Erdgas-Future (sonst flat) soll Buy & Hold
risikoadjustiert schlagen. Fenster ~41 Kalendertage, ~29 Handelstage. Vorab durch
einen eigenen Monatsrendite-Screen über 10 Rohstoff-Kandidaten begründet — Erdgas
ragte mit Abstand heraus (Sep Ø +8,8 %/65 %, Okt +7,4 %/65 %, flankiert von tiefrotem
Dez/Jan ~ −5 %).

## 2. Makro-Begründung

**Harter physischer Lagerzyklus — kein Überraschungs-Treiber (Kaffee 0027), kein
Drift-Asset (Kakao 0026 / Nasdaq 0017).** Erdgas wird den **ganzen Sommer in Speicher
injiziert** und im **Winter verheizt**. Das saisonale Tief bildet sich am Ende der
Injection-Season (Spätsommer/Frühherbst), wenn die Speicher voll laufen und der
Kassamarkt überversorgt ist. Ab ~Ende September dreht die Forward-Kurve von „Lager
füllen" auf „Lager leeren" — der Markt beginnt, den **Winter-Heizbedarf** einzupreisen.
Gleichzeitig legt der **Hurricane-Peak im Golf (Aug–Okt)** eine Angebots-Risikoprämie
auf Förderung/LNG-Export.

**Warum das die beste Story im ganzen offenen Menü ist:** Anders als bei Kaffee (Frost
= Überraschung, nicht timebar) ist hier der *Kalender* der Treiber — der Speicherzyklus
wiederholt sich physisch jedes Jahr. Anders als bei Kakao/Nasdaq (Drift-Falle) **driftet
Erdgas nicht**, im Gegenteil: der Front-Month verliert über die Zeit (B&H CAGR −1,5 %,
MaxDD −90 % durch Contango/Roll-Decay). Ein positives Herbstfenster auf einem Asset mit
*negativer* Drift ist die stärkstmögliche Form des 0017-Gegenbeweises — es kann
unmöglich eingefangene Aufwärtsdrift sein.

## 3. Regeln

- Long (Gewicht 1.0) an allen Handelstagen im Intervall [21. September, 1. November]
  jedes Jahres; sonst flat. Ein Trade pro Jahr, ~29 Handelstage.
- **Look-Ahead-Schutz:** datumsbasiertes Signal, Engine verzögert um einen Bar (`shift(1)`).
- **Daten-Guards:** Abbruch bei nicht-positivem Schluss (0005) und bei < 50 distinkten
  Schlusskursen/Jahr (0025). `NG=F` ist sauber: 26 J., keine eingefrorenen Jahre.

## 4. Kosten- & Ausführungsannahmen

`IBKR_FUTURES`: Kommission in wenige bps gefaltet, 2 bps Slippage + 0,5 bps Gebühren pro
Seite (~5 bps Round-Trip). Alle Zahlen **netto**. Ausführung am Folgetag.

## 5. Ergebnisse (gesamt 2000–2026, netto nach Kosten)

| Kennzahl          |             Wert |        IS 2000–12 |       OOS 2013–26 |
| ----------------- | ---------------: | ----------------: | ----------------: |
| CAGR              |          12,96 % |           16,60 % |            9,73 % |
| Sharpe            |         **0,53** |              0,62 |          **0,44** |
| Sortino           |           1,02   |              1,25 |              0,79 |
| Max Drawdown      |          −44,1 % |           −28,9 % |           −44,1 % |
| Trefferquote      |     62 % (16/26) |              62 % |              62 % |
| Profit-Faktor     |           6,15   |              8,25 |              4,63 |
| Payoff-Ratio      |           3,85   |              5,16 |              2,89 |
| Expectancy/Trade  |        +15,53 %  |          +18,39 % |          +12,68 % |
| **Median/Trade**  |       **+5,71 %**|          +4,65 %  |          +6,38 %  |
| Ø Haltedauer      |        29,9 Tage |                   |                   |
| Trades            |          **26**  |                13 |                13 |
| Exposure          |          12,0 %  |                   |                   |

Buy & Hold (Front-Month): CAGR **−1,53 %**, Sharpe 0,25, MaxDD **−90,4 %**.

## 6. Signifikanz & Robustheit (gesamte Stichprobe — die Seasonax minte diese Daten)

- **Permutationstest p = 0,001** ✓ — das Timing schlägt 99,9 % gleich langer
  Zufallsfenster. Auf einem **driftarmen/-negativen** Asset doppelt aussagekräftig:
  kann KEINE Drift-Falle (0017) sein. Tier mit dem bisher stärksten Lead (Platin 0018).
- **Bootstrap-Sharpe-KI [0,16; 0,87]** ✓ — **schließt die Null aus**. Das schaffte unter
  allen Saison-Leads bisher nur Palladium (0021); Charter/Zink/Kakao/Kaffee/CNY berührten
  alle die Null. Risikoadjustiert robust, nicht nur expectancy-robust.
- **t-Test p = 0,002** ✓.
- **IS ≈ OOS:** beide Hälften liefern (Sharpe 0,62 vs 0,44; **62 % Win in beiden**;
  Expectancy +18,4 % vs +12,7 %). Keine OOS-only-Illusion wie Nasdaq 0017 oder Kaffee 0027.
- **Median-Trade +5,71 %** (IS +4,65 %, OOS +6,38 %) — **das tötet die Fat-Tail-Frage**:
  schon der *typische* Herbst gewinnt klar. Anders als Kaffee 0027 (Median −1,1 %, alles in
  Schockjahren) sind die Gewinne über die ganze Historie verteilt (2001, 04–06, 12, 18–21,
  23–25), die Verluste klein/gedeckelt (meist −5…−12 %). Payoff 3,85 = asymmetrisch.
- **Robustheit 118/121** Fenster-Verschiebungen positiv. Auf einem driftarmen Asset ist das
  ein echtes Plateau (anders als die wertlose 0017-Drift-Robustheit).
- **DSR/PSR = 0** (E[max Sharpe|null] = 2,60 bei n_trials=121 als Seasonax-Such-Proxy) — die
  übliche Multiple-Testing-Strafe. Der Tages-Sharpe (~0,5) schlägt den aufgeblähten Null-
  Erwartungswert nicht. Gilt identisch für *alle* Seasonax-Leads im Katalog (0016/0018/0025);
  Permutation + Bootstrap-KI sind hier die aussagekräftigeren Tests.

## 7. Bewertung

**Der bestbegründete und statistisch stärkste Seasonax-Lead im gesamten Katalog.** Er ist
der einzige, der gleichzeitig (1) Permutation p=0,001, (2) Bootstrap-KI ohne Null, (3) klar
positiven Median-Trade, (4) konsistente IS≈OOS-Hälften und (5) den stärksten Drift-Fallen-
Gegenbeweis (negativ driftendes Asset) liefert. Die Makro-Story ist physisch (Speicherzyklus),
nicht eingepreist-weg und nicht überraschungsabhängig.

## 8. Grenzen & nächste Schritte

- **Kein echtes zeitliches OOS:** Seasonax hat das Fenster auf der vollen Historie geminet;
  die IS/OOS-Hälften sind dieselben Daten, nur geteilt. Echte Bestätigung braucht einen
  **live-vorab-registrierten Forward-Test** (Herbst ab Sept 2026).
- **Roll-Artefakt-Risiko (0019):** `NG=F` ist roll-lastig; der Monatskontrakt rollt mehrfach
  im Fenster. Zu prüfen wie bei Platin 0019 — ob der Edge an Roll-Gaps hängt. Erschwert:
  physischer Cross-Check via UNG scheidet aus (Contango-Decay, 0004); sauberer Beweis bräuchte
  Henry-Hub-Kassa oder kontraktgenaue Daten (Barchart/Norgate).
- **−44 % MaxDD im Fenster** — Erdgas ist brutal volatil; ein schlechter Herbst (z. B. 2022
  −19 %) tut weh. Positionsgröße/Vol-Targeting nötig, bevor das live geht.
- **26 Trades** — für ein Saison-Fenster ordentlich (mehr als Charter/Platin), aber weiter
  Demut.
- **Nächster Schritt:** (a) Roll-Check 0029 analog 0019; (b) Aufnahme als viertes Bein ins
  Saison-Overlay (0020) prüfen — Herbst (Sep–Nov) füllt eine bisher leere Jahreszeit zwischen
  Mastrind (KW21/Mai) und Platin (Dez/Jan); (c) Live-Forward Herbst 2026 vorab registrieren.

## Artefakte

- `results/metrics.json` — alle Kennzahlen, Signifikanz, Robustheits-Gitter
- `results/trades.csv`, `results/equity.csv`
- `results/plots/equity_vs_bh.png`, `per_year_trades.png`, `robustness_heatmap.png`
