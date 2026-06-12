# Strategie 0063 — Football Value Betting (Pinnacle-Orakel, Phase 0+1)

- **Kategorie:** value betting / behavioral / cross-bookmaker
- **Status:** testing (Phase 0 PASS, Phase-1-Gate auf der Headline-Zelle FAIL — Lead in der Nachbar-Zelle)
- **Datum:** 2026-06-12
- **Universum:** 7 Fußball-Ligen — Premier League (E0), Championship (E1),
  Bundesliga (D1), 2. Bundesliga (D2), La Liga (SP1), Serie A (I1), Ligue 1 (F1)
- **Stichprobe:** Saisons 2019/20–2025/26 (Pinnacle-Schlussquoten erst ab
  2019/20 verfügbar), 17.080 Spiele mit vollem Quotensatz

## 1. Hypothese

De-viggte Pinnacle-Quoten sind der beste öffentliche Schätzer fairer
Spielausgangs-Wahrscheinlichkeiten. Bietet Bet365 (Soft Book) eine Quote über
der fairen Pinnacle-Quote, ist das eine +EV-Wette. Beweis-Metrik ist der
**Closing Line Value** (gewettete Quote vs de-viggte Pinnacle-Schlusslinie),
nicht die verrauschte P&L.

## 2. Makro-Begründung

Pinnacle hat die niedrigste Marge (gemessen: 2,8–3,0 % vs Bet365 5,5 %),
limitiert Gewinner nicht und aggregiert scharfes Geld. Soft Books bepreisen
behaviorale Verzerrungen (Lieblingsteams, Favoriten-Bias) und reagieren träger
auf News. Die Schlusslinie ist der genaueste Outcome-Prädiktor → systematisch
besser als die Schlusslinie einkaufen = bewiesener Skill, lange bevor die
Ergebnis-Varianz es zeigt.

## 3. Regeln (vorab registriert)

- **fair_p:** de-viggte Pinnacle-Quote zur **Collection-Zeit** (`PSH/PSD/PSA`,
  Fr/Di nachmittags — gleicher Zeitpunkt wie die Bet365-Quoten der CSV).
  Schlusslinie (`PSC*`) **nur** zur CLV-Messung (sonst Look-ahead).
- **Wette** Outcome i, wenn `B365_i × fair_p_i − 1 > Schwelle`;
  Schwellen-Scan {2, 3, 4, 5} %, Headline vorab 3 %.
- **De-Vig:** multiplicative / Shin / power; beste Methode per Kalibrierung
  (Brier/Log-Loss) auf der Schlusslinie.
- **Einsatz:** flat 1 Einheit (Kelly erst ab Phase 2).
- **Daten-Fehler-Guard:** EV > 20 % = mutmaßlicher CSV-Tippfehler →
  ausgeschlossen (3–6 Wetten je Zelle).
- **Trials:** 3 Methoden × 4 Schwellen = 12.

## 4. Kosten- & Ausführungsannahmen

Drei Szenarien: brutto (steuerabsorbierendes Buch), 5,3 % Wettsteuer auf den
Einsatz, 1 % Quoten-Slippage. Kein IBKR-Modell — der „Markt" ist der Buchmacher
selbst.

## 5. Ergebnisse

### Phase 0 — De-Vig-Validierung: PASS

| Check | Ergebnis |
| --- | --- |
| Margen reproduziert | Pinnacle open 3,03 % / close 2,83 % / Bet365 5,47 % (Median) — plausibel |
| Kalibrierung (Brier, Schlusslinie) | **Shin 0,591541** < power 0,591546 < multiplicative 0,591596 |
| Kalibrierung (Log-Loss) | gleiche Reihenfolge (Shin 0,99135) |
| Unit-Tests | 15/15 grün (`tests/test_devig.py`) |

Die Kalibrierungs-Differenzen sind winzig, aber konsistent gerichtet: Shin
korrigiert den Favoriten-Longshot-Bias am besten — wie die Literatur erwartet.

### Phase 1 — CLV-Backtest (CLV einheitlich an der Shin-Schlusslinie gemessen)

| Selektion | Schwelle | n | Median-CLV | 95%-KI | ROI brutto | ROI n. Steuer |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| multiplicative | 2 % | 832 | −0,52 % | [−1,3 %, +0,4 %] | +14,8 % | +9,5 % |
| multiplicative | 3 % | 552 | −0,69 % | [−1,5 %, +0,6 %] | +23,2 % | +17,9 % |
| **shin** | **2 %** | **385** | **+1,01 %** | **[+0,19 %, +2,19 %]** | +15,9 % | +10,6 % |
| shin (Headline) | 3 % | 233 | +0,59 % | [−0,80 %, +2,36 %] | +25,7 % | +20,4 % |
| power | 2 % | 301 | +1,01 % | [+0,19 %, +2,26 %] | +6,4 % | +1,1 % |
| power | 3 % | 176 | +1,07 % | [−0,10 %, +2,76 %] | +4,9 % | −0,4 % |

**Gate-Zelle shin @ 2 %** (n=385, mittl. Quote 5,77, Win 23,1 %):
Median-CLV **+1,01 %**, KI schließt 0 aus, 55,8 % der Wetten mit positivem CLV.
Je Liga: **5/7 positiv** (2. Bundesliga +1,9 %, Championship +2,2 %, Serie A
+2,2 %, Bundesliga +0,5 %, Premier League +0,7 %; Ligue 1 −0,3 %, La Liga
−1,2 %). Je Saison: **4/7 positiv** (19/20, 20/21, 22/23, 24/25; 25/26 ≈0).
ROI nach Steuer +10,6 %, **KI [−12,8 %, +36,3 %] enthält die 0** — kein
P&L-Beweis. Slippage 1 % kostet ~1 ROI-Punkt (unkritisch).

### Formales Gate (vorab: shin @ 3 %): **FAIL**

Ligen 4/7, Saisons 4/7, Median-CLV-KI [−0,8 %, +2,4 %] enthält die 0.

## 6. Ehrliche Einordnung (die eigentlichen Befunde)

1. **Mess-Artefakt gefangen (wichtigste Lehre):** Im ersten Lauf maß jede
   Selektionsmethode den CLV gegen ihre *eigene* de-viggte Schlusslinie. Die
   multiplicative-Zellen zeigten Median-CLV +2,7 % mit KI ohne 0 — gegen die
   bestkalibrierte Shin-Schlusslinie gemessen wurde daraus **−0,7 %**. Die
   Methode wählte Longshots, deren faire Probs sie selbst inflationiert, und
   bestätigte sich dann selbst. **Selektions- und Mess-Maßstab müssen
   entkoppelt sein** — Verwandter der Permutations-Null-Lehre (0052/0057).
2. **Fat-Tail-Lotterie statt P&L-Beweis:** Das Wett-Buch ist longshot-lastig
   (Median-Quote 4,75; 85 % Draw/Auswärts), Top-5-Gewinner = 95 % des
   Gesamt-PnL. Alle ROI-KIs enthalten die 0 — exakt das Profil, das die
   0038-Lehre disqualifiziert. Nur der CLV ist hier beweisfähig, und der ist
   dünn.
3. **Bet-Flow zerfällt über die Zeit:** Wetten je Saison (shin @ 2 %):
   90 → 72 → 60 → 46 → 47 → 50 → **20** (25/26). Bet365 hat sich an Pinnacle
   angenähert — der Snapshot-Edge dieser Datenquelle nimmt ab. Die letzte
   Saison hat ≈0 CLV.
4. **Snapshot-Daten unterschätzen UND überschätzen zugleich:** football-data
   liefert 1 Quote/Spiel (Fr/Di). Live-Polling sieht mehr Divergenz-Fenster
   (mehr Flow als hier), aber CSV-Quoten können Tippfehler enthalten
   (EV-Cap-Guard) und sind nicht garantiert zeitsynchron — beides löst nur
   Phase 3 (Paper-Live) auf.
5. **Multiple Testing:** Die bestandene Zelle (shin @ 2 %) ist 1 von 12
   registrierten Trials und nicht die vorab fixierte Headline (3 %). Power @
   2 % bestätigt sie (fast identisches CLV-Profil) — Plateau-Indiz, kein Beweis.

## 7. Verdikt & nächste Schritte

**Phase 0 bestanden** (Loader + De-Vig + CLV-Tracker stehen, Shin = Methode der
Wahl). **Phase-1-Gate formal nicht bestanden**, aber ein konsistenter
CLV-Lead bei niedriger Schwelle: Median +1 % über 385 Wetten, KI > 0, 5/7
Ligen — getragen von Zweitligen/Championship (ineffizienter), nicht von
Premier League/La Liga. Gegen den Lead spricht der Flow-Zerfall bis 25/26.

Entscheidungsbedarf (mit Robin im Claude-Chat): (a) Schwelle auf 2 % als neue
Headline registrieren und Phase 2 (Robustheit, Kelly, Liga-Selektion) fahren,
oder (b) direkt Phase 3 (Live-Paper-CLV via Odds-API) als ehrlichsten Test des
heutigen Edges — der Backtest sagt über 2026-Flow wenig.

## Artefakte

- `run.py` — Phase 0+1 (Kalibrierung + CLV-Backtest)
- `results/metrics.json` — volle Grid-Ergebnisse, Gate-Breakdown
- `results/trades.csv` — 233 Wetten der Headline-Zelle
- Neue Infra: `quantlab/football_data.py`, `quantlab/devig.py`,
  `quantlab/clv.py`, `tests/test_devig.py`
