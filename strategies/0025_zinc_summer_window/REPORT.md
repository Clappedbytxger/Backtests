# Strategie 0025 — Zink Sommerfenster (4.7.–30.7.)

- **Kategorie:** seasonal
- **Status:** **testing** (echter Lead auf sauberen LME-Daten; risikoadjustiert fragil,
  kein validierter Edge)
- **Datum:** 2026-06-05
- **Universum:** **LME Zink, offizielle Cash-Settlement** (Spot), Tagesdaten von
  westmetall.com, 2008–2026. Seasonax-Originalsignal lag auf **Bloomberg Zinc Subindex
  (BCOMZS)** — siehe §0.
- **Stichprobe:** Gesamt 2008–2026. In-Sample 2008–2016 / Out-of-Sample 2017–2026
  (Schnitt am 1. Januar, der nie ein Juli-Fenster zerschneidet).

## 0. Datenquellen — Recherche und Wahl (der Kern dieser Iteration)

Die erste Version von 0025 lief auf dem yfinance-Future `ZNC=F` und war **wertlos**:
das Symbol ist ab 2019 eingefroren (ab 2020 nur **ein** Kurswert pro Jahr), die ganze
OOS-Hälfte war tote Datenfläche (Diagnose im Anhang A). Der Nutzer wies darauf hin, dass
Seasonax für Zink **35 Jahre** auf dem Symbol **`BCOMZS`** zeigt. Daraufhin habe ich die
Datenlage systematisch abgeklopft:

**Was ist BCOMZS?** Der **Bloomberg Commodity Zinc Subindex (Total Return)** — *kein*
LME-Spotpreis, sondern ein **Future-basierter Index** (rollt LME-Zink-Kontrakte, enthält
also Roll-/Carry-Effekte). Das erklärt die 35 Jahre. Frei abrufbar nur als manueller
CSV-Export (Investing.com / MacroMicro), nicht programmatisch ohne Login.

**Geprüfte Quellen für eine handhabbare Zink-Tagesreihe:**

| Quelle | Was | Zugang | Historie | Befund |
| ------ | --- | ------ | -------- | ------ |
| yfinance `ZNC=F` | „Zink-Future" | frei, API | nominal 2015+ | **tot** — eingefroren ab 2019 (Anhang A) |
| yfinance `^BCOMZS` | Bloomberg-Zink-Index | frei, API | — | **tot** (1 Datenpunkt) |
| Investing.com / MacroMicro | **BCOMZS** (Seasonax-Reihe) | Login/manuell | 35 J. | exakt Seasonax, aber kein Auto-Download |
| Stooq | diverse | brauchte früher keinen Key | — | **jetzt API-Key-pflichtig** (auch Kupfer leer) |
| Nasdaq Data Link `LME/PR_ZI` | LME Zink | API-Key | bis 2008 | 403 ohne Key; freie LME-Sets ~2019 eingestellt |
| Metals-API | LME-ZNC | API-Key (Free-Tier) | ab 2008 | machbar mit Key, limitiert |
| **westmetall.com** | **LME Cash-Settlement (Spot)** | **frei, scrapebar** | **2008+** | **gewählt** ✓ |
| yfinance `DBB` | Basismetall-Korb (Al/Zn/Cu) | frei, API | 2007+ | nur ⅓ Zink → kein sauberer Zink-Test |
| Barchart / Norgate | echte Zink-Kontrakte | bezahlt | lang | Projekt-Goldstandard, nicht frei |

**Gewählt: LME official Cash-Settlement via westmetall.com.** Frei, täglich, ab 2008
(~18 Sommer), und als **physischer Spotpreis ohne Futures-Roll** sogar *sauberer* für
einen Angebots-/Nachfrage-Saisontest als ein roll-behafteter Index wie BCOMZS. Implementiert
als wiederverwendbarer Loader `src/quantlab/lme_data.py` (`get_lme_zinc`, scrapt die
Jahres-Tabellen, cached als Parquet; deckt auch Cu/Al/Pb/Ni/Sn ab). 4 656 Handelstage,
~230 distinkte Preise/Jahr, 0 nicht-positive — eine echte, lebendige Reihe.

**Tradeoffs / offene Punkte:**
- **Nicht exakt die Seasonax-Reihe.** BCOMZS (Future-TR-Index) ≠ LME-Cash (Spot). Wir testen
  dieselbe *Hypothese* auf einer unabhängigen, sauberen Reihe — ein robusteres, aber nicht
  identisches Setup. Die Spotreihe schließt zugleich ein Roll-Artefakt aus.
- **Nur 2008+ (~18 Trades)**, nicht 35 Jahre. Wer die vollen 35 J. will, exportiert BCOMZS
  einmalig als CSV aus Investing.com; ich schreibe dann einen CSV-Loader (`data/manual/`).
- **Einzelquelle**, nicht gegen einen zweiten Feed kreuzvalidiert.

## 1. Hypothese

Zink zeigt laut Seasonax-Lead eine wiederkehrende Stärke von **4. Juli bis 30. Juli**:
jeden Sommer long im Zink (sonst flat) soll Buy & Hold risikoadjustiert schlagen.

## 2. Makro-Begründung

**Schwächer als bei Platin (0018), aber vorhanden.** Zink geht zu ~50 % in die Verzinkung
(Galvanik) von Stahl für Bau und Automobil. Denkbare Sommertreiber: (1) die nord­hemisphärische
**Bausaison** läuft im Sommer auf Hochtouren → Galvanik-Nachfrage; (2) eine bekannte
**LME-Sommer­konstellation** (dünne Liquidität, Lagerzyklen Juli/August). Das ist plausibel,
aber dünner als ein scharfer kalenderfixierter Nachfrage-Event. Genau deshalb entscheidet
der Permutationstest (Lehre aus 0017).

## 3. Regeln

- Long (Gewicht 1.0) an allen Handelstagen im Intervall [4. Juli, 30. Juli] jedes Jahres;
  sonst flat. Ein Trade pro Sommer, ~19 Handelstage. Kein Jahreswechsel (anders als 0018).
- **Look-Ahead-Schutz:** datumsbasiertes Signal, Engine verzögert um einen Bar (`shift(1)`).
- **Daten-Guards:** Abbruch bei nicht-positivem Schluss (Lehre 0005) **und** bei einem Jahr
  mit < 50 distinkten Schlusskursen (Lehre 0025 — fängt einen eingefrorenen Feed wie `ZNC=F`
  automatisch ab, bevor ein Backtest läuft).

## 4. Kosten- & Ausführungsannahmen

`IBKR_FUTURES`: Kommission in wenige bps gefaltet, 2 bps Slippage + 0,5 bps Gebühren pro
Seite (~5 bps Round-Trip). Alle Zahlen **netto**. Ausführung am Folgetag. (Hinweis: LME-Cash
ist nicht direkt investierbar; das tradebare Vehikel wäre ein Zink-Future/ETF — Kosten als
Stellvertreter, vergleichbar zu 0018.)

## 5. Ergebnisse (gesamt 2008–2026, netto nach Kosten)

| Kennzahl          |             Wert |
| ----------------- | ---------------: |
| CAGR              |           3,38 % |
| Sharpe            |         **0,22** |
| Sortino           |           0,35   |
| Calmar            |           0,26   |
| Max Drawdown      |          −13,0 % |
| Trefferquote      |     67 % (12/18)  |
| Profit-Faktor     |           3,55   |
| Payoff-Ratio      |           1,78   |
| Expectancy/Trade  |         +3,71 %  |
| Ø Haltedauer      |        19,3 Tage |
| Trades            |          **18**  |
| Exposure          |           7,5 %  |

**Vergleich Buy & Hold:** CAGR 2,20 %, Sharpe **0,15**, MaxDD **−63,1 %**. Das Fenster
liefert mehr Rendite bei höherem Sharpe und einem Fünftel des Drawdowns — bei nur **7,5 %
Marktzeit** und umgeht die −63%-Achterbahn von Zink.

### In-Sample vs. Out-of-Sample — **Timing hält, Risiko verschlechtert sich**

| Periode             | Trades | Win  | Expectancy/Trade | Sharpe | Profit-Faktor |
| ------------------- | -----: | ---: | ---------------: | -----: | ------------: |
| In-Sample 2008–2016 |      9 | 67 % |          +5,53 % |   0,42 |          6,62 |
| OOS 2017–2026       |      9 | 67 % |          +1,90 % |  −0,03 |          1,99 |

Die **Trefferquote bleibt OOS identisch bei 67 %** und die Expectancy positiv — der Effekt
*kollabiert nicht* wie ein Overfit (vgl. 0005). Aber der OOS-**Sharpe fällt auf ~0**: zwei
große OOS-Verluste (2018 −6,0 %, **2024 −10,7 %**) machen Ø-Gewinn und Ø-Verlust fast gleich
groß (5,74 % vs 5,78 %). Zudem ist die IS-Hälfte von den Post-GFC-Erholungen aufgebläht
(2009 **+16,7 %**, 2010 +13,3 %) — die wiederholen sich nicht. Ehrliche Lesart: **eine reale,
aber milde und verrauschte Saison-Tendenz**, kein robuster risikoadjustierter Edge.

## 6. Signifikanz (gesamte Stichprobe)

| Test                              |             Wert |
| --------------------------------- | ---------------: |
| Permutationstest p-Wert           |     **0,031** ✓  |
| Bootstrap Sharpe 95%-KI           | [−0,25, 0,64] ✗  |
| t-Test mittlere Rendite p         |     **0,040** ✓  |
| Deflated Sharpe (n_trials = 121)  |       0,00 (PSR) |

Der **Permutationstest besteht (p = 0,031)**: das Juli-Timing schlägt ~97 % gleich langer
Zufallsfenster. Entscheidend — Zink ist über 2008–2026 **driftarm** (B&H-Sharpe nur 0,15,
−63 % MaxDD), also kann der Effekt *nicht* bloß eingefangene Aufwärtsdrift sein (die
Nasdaq-/0017-Falle). Der t-Test bestätigt (p = 0,040). **Aber** das Bootstrap-Sharpe-KI
**berührt die Null** ([−0,25; 0,64]) → risikoadjustiert nicht von Null trennbar. DSR = 0 ist
wie immer die volle Such-Strafe.

## 7. Robustheit

- **Fenster-Verschiebung:** **120/121** Kombinationen (±10 Tage) positiv — ein klares
  Plateau, und bei einem **driftarmen** Asset ist das (anders als bei der Trend-Aktie Nasdaq)
  aussagekräftig.
- **Teilperioden:** Win-Rate über beide Hälften stabil (67 %/67 %), Expectancy positiv, aber
  Sharpe IS 0,42 → OOS −0,03 (Risiko-Instabilität, s. §5).
- **Daten:** LME-Cash-Spot, kein Futures-Roll → **kein Roll-Artefakt** (Vorteil gegenüber
  einem Index-Test). Einzelquelle, nicht kreuzvalidiert; nicht die exakte BCOMZS-Reihe (§0).
- **Hauptvorbehalte:** (1) nur 18 Trades; (2) IS von 2009/2010-Erholung aufgebläht; (3) OOS
  risikoadjustiert flach; (4) kein echtes Out-of-Time-OOS (Fenster auf voller Historie gemint).

## 8. Verdict

**Schwacher Lead behalten (testing), nicht handeln.** Auf einer sauberen, unabhängigen
LME-Spotreihe (kein Roll-Artefakt, driftarm) **besteht** das Juli-Fenster den
Permutationstest (p = 0,031), zeigt ein 120/121-Robustheits-Plateau, 67 % Trefferquote in
*beiden* Hälften und schlägt B&H bei 7,5 % Marktzeit — mit einer plausiblen (wenn auch
dünnen) Galvanik-/Bausaison-Makro-Story. Das hebt 0025 klar über die abgelehnten Saison-Leads
(Nasdaq 0017, Ostern 0022, Akshaya 0023). **ABER** risikoadjustiert ist es fragil: OOS-Sharpe
~0, Bootstrap-KI berührt die Null, IS von 2009/2010 aufgebläht, nur 18 Trades, DSR = 0. Es
rangiert damit **unter** Platin (0018, p = 0,001, beide Hälften konsistent) — eher auf dem
Niveau von Charter (0016) oder dem CNY-Silber-Lead (0024): echtes Timing, schwaches Risiko.

**Nächste Schritte:** (1) **Volle 35-J.-Historie holen** — BCOMZS einmalig als CSV aus
Investing.com exportieren, CSV-Loader bauen, denselben eingefrorenen Test laufen lassen; hält
der Effekt auf 35 Jahren *und* einer zweiten (Index-)Reihe, wird aus dem schwachen Lead ein
ernster Kandidat. (2) **Cross-Instrument** wie bei Platin/0021: gleiche Regel auf einem
Zink-ETF oder Schwester-Basismetall (Blei `LME_Pb_cash` teilt Galvanik-/Bau-Treiber) ohne
Re-Fitting. (3) Bei Bestätigung: Live-Forward Juli 2026+ vorab registrieren.

---

## Anhang A — Warum yfinance `ZNC=F` unbrauchbar ist (Daten-Obduktion)

Die erste 0025-Version lief auf `ZNC=F`. Die Trade-Liste verriet den Defekt: **jeder Trade
ab 2019 verlor _exakt_ −0,05 %** (= die Round-Trip-Kosten), weil der Brutto-Move 0 war. Der
Feed ist eingefroren:

| Jahr | Null-Return-Anteil | distinkte Schlusskurse |
| ---- | -----------------: | ---------------------: |
| 2015 |             10,2 % |                    107 |
| 2017 |             19,5 % |                    182 |
| 2018 |             42,6 % |                    143 |
| 2019 |             71,0 % |                     70 |
| 2020 |             99,2 % |                  **3** |
| 2021–2026 |        100,0 % |                  **1** |

Ab 2020 existiert ein einziger, täglich wiederholter Print (zuletzt 2297,0). **Lehre (in
CLAUDE.md ergänzt):** vor jedem Saison-Test auf einem exotischen Symbol zuerst
`close.groupby(year).nunique()` und den Null-Return-Anteil prüfen — entlarvt einen toten Feed
in Sekunden, bevor ein Backtest überhaupt läuft. Genau dieser Check ist jetzt als Guard in
`run.py` (§3) eingebaut.
