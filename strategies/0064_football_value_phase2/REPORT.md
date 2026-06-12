# Strategie 0064 — Football Value Betting, Phase 2: Schwellen-/Liga-Robustheit

- **Kategorie:** value betting / behavioral / cross-bookmaker
- **Status:** testing (Gate a+c PASS — Cross-Liga-OOS stark; Gate b ROI-KI strukturell unerreichbar)
- **Datum:** 2026-06-12
- **Universum:** eingefrorene 0063-Regel auf 18 Ligen — 7 Phase-1-Ligen + **11 nie
  berührte OOS-Ligen** (Eredivisie, Primeira Liga, Pro League Belgien, Süper Lig,
  Super League Griechenland, Scottish Premiership, League One, League Two,
  LaLiga2, Serie B, Ligue 2)
- **Stichprobe:** Saisons 2019/20–2025/26; 17.080 (Phase 1) + 24.948 (OOS) Spiele,
  1.849 Wetten kombiniert

## 1. Hypothese

Die in 0063 eingefrorene Regel (Shin-De-Vig auf Pinnacle-Collection-Quoten,
wette Bet365-Outcome bei EV > 2 %, CLV gemessen an der Shin-Schlusslinie) ist
robust über Schwellen und generalisiert auf ungesehene Ligen — oder sie ist ein
Artefakt der 7 Phase-1-Ligen.

## 2. Regeln (vorab registriert, kein Re-Fit)

1. **Schwellen-Plateau** (Diagnostik): EV 0,5–6 % in 0,5 %-Schritten.
2. **Cross-Liga-OOS** (0021-Methode): eingefrorene Regel auf 11 neuen Ligen.
3. **Odds-Bucket-Analyse** (Diagnostik): Edge nach Quoten-Klasse.
4. **¼-Kelly, Cap 2 % Bankroll** (1 neuer Trial; Programm gesamt 13):
   darauf das ROI-KI-Gate.

Szenarien: primär = 0 % Steuer (absorbierendes Buch) + 1 % Slippage;
Stress = 5,3 % Einsatzsteuer + 1 % Slippage.

**Gate (vorab):** (a) OOS-Median-CLV-KI > 0; (b) ROI-Bootstrap-KI > 0 (Kelly,
primär, kombiniert); (c) Median-CLV > 0 für alle Schwellen 1–4 %.

## 3. Ergebnisse

### (a) Cross-Liga-OOS: **PASS — das stärkste Ergebnis des Programms**

1.464 Wetten auf 11 nie berührten Ligen: **Median-CLV +1,44 %,
KI [+0,97 %, +1,90 %] klar ohne 0**, 59 % der Wetten mit positivem CLV.
**Alle 11 Ligen positiv** (Süper Lig +3,7 %, LaLiga2 +2,5 %, Schottland +1,6 %,
League One/Two +1,5 %, … Portugal +0,4 %), **alle 7 Saisons positiv**. Der
OOS-CLV ist sogar *höher* als auf den Phase-1-Ligen (+1,0 %) — konsistent mit
der Roadmap-These „Nischen-Ligen sind ineffizienter".

### (c) Schwellen-Plateau: **PASS**

Median-CLV positiv an allen 12 Schwellen (+0,6 bis +1,0 %), kein Spike um die
Headline — Plateau, keine Knife-Edge. KI ohne 0 bei 0,5 %, 1 % und 2 %.

### (b) ROI-KI: **FAIL — aber strukturell, nicht empirisch**

| Szenario | ¼-Kelly-ROI | 95%-KI | flat |
| --- | ---: | --- | ---: |
| primär (0 % Steuer, 1 % Slippage) | +2,30 % | [−6,1 %, +10,9 %] | +4,63 % |
| Stress (5,3 % Steuer) | −3,00 % | [−11,4 %, +5,6 %] | −0,67 % |

Bankroll-Sim (¼-Kelly, primär, 1.849 Wetten chronologisch): Endstand 1,12×,
MaxDD −16,9 % — die Roadmap-Warnung „100–200-Wetten-Drawdowns sind normal"
empirisch bestätigt.

**Warum das Gate nicht bestehbar ist:** Der wahre Erwartungswert je Wette ist
per Definition der Schlusslinie der mittlere CLV = **+1,09 %**. Bei einer
Per-Wette-Streuung von 1,98 Einheiten braucht ein KI-Ausschluss der 0
**~126.000 Wetten** — die gesamte verfügbare Historie liefert 1.849. Das
ROI-Gate war als Kriterium falsch dimensioniert; genau dafür hat die Roadmap
CLV als Primärmetrik registriert („CLV ist der Beweis, nicht die P&L-Kurve").
Der realisierte ROI (+4,6 % flat) ist mit dem CLV-Erwartungswert vereinbar,
beweist aber nichts.

### Odds-Buckets: Der Edge lebt in der Mitte, nicht im Longshot

| Quote | n | Median-CLV | KI | Win |
| --- | ---: | ---: | --- | ---: |
| [1; 2,5) | 36 | +2,6 % | [−2,0 %, +5,5 %] | 61 % |
| **[2,5; 4)** | **995** | **+1,8 %** | **[+1,3 %, +2,2 %]** | 30 % |
| [4; 7) | 575 | +0,5 % | [−0,6 %, +1,6 %] | 22 % |
| [7; ∞) | 243 | +0,1 % | [−2,0 %, +3,3 %] | 13 % |

Der einzige Bucket mit KI ohne 0 ist **[2,5; 4)** — und das sind zu 77 %
**Unentschieden** (klassischer Draw-Bias der Soft Books). Extreme Longshots
(≥7) tragen *keinen* CLV. Das entschärft den 0063-Fat-Tail-Vorbehalt: der Edge
ist kein Longshot-Artefakt und in einem gut handelbaren Quotenbereich.

## 4. Ehrliche Einordnung

1. **Der CLV-Beweis ist jetzt zweifach erbracht** (Phase-1-Ligen + 11 ungesehene
   Ligen, 18/18 Ligen mit positivem Median-CLV, alle Saisons) — die Regel hat
   Skill im Sinne der Schlusslinie. Das ist kein Data-Mining-Artefakt mehr.
2. **Aber der Edge ist dünn:** mittlerer CLV +1,1 % brutto. Nach 1 % Slippage
   bleiben ~+0,2 %, nach 5,3 % Steuer ist er tot (Stress-ROI −3 %).
   **Steuer-Absorption ist nicht optional, sondern Existenzbedingung** — und
   die Roadmap-Annahme „2–4 % Edge nach Steuer" wird vom Freitag-Snapshot
   NICHT gestützt. Die +4,2 % EV gegen die Opening-Linie schmelzen bis zur
   Schlusslinie auf +1,1 % — Bet365s „Fehler" enthält Information, die
   Pinnacle bis zum Anpfiff einarbeitet.
3. **Flow-Zerfall bestätigt sich auf 18 Ligen:** 5,9 Wetten/Woche (23/24) →
   5,0 (24/25) → **1,6 (25/26)**. Der Snapshot-Kanal verengt sich real.
4. **Die offene Live-Frage:** football-data liefert 1 Quote/Spiel (Freitag).
   Tägliches/stündliches Polling sieht Divergenzen, die der Snapshot
   verpasst — der Live-Edge kann größer sein als +1,1 %. Ob er es ist,
   kann NUR Phase 3 (Paper-CLV) beantworten; der Backtest ist hier am Ende
   seiner Aussagekraft.

## 5. Verdikt & nächste Schritte

Robustheit bestanden, wo sie statistisch beweisbar war (CLV: 18/18 Ligen,
Plateau stabil); das ROI-KI-Gate ist mit historischen Daten prinzipiell nicht
erreichbar und sollte für Phase 3/4 durch ein **Paper-CLV-Gate** ersetzt
werden. Empfehlung (vorab zu registrieren, bevor Phase 3 gebaut wird):

> Phase-3-Gate: über 4–6 Wochen Live-Polling Median-Paper-CLV ≥ +1 % bei
> ≥ 150 Alerts UND mittlerer CLV nach Slippage > 0; darunter ist die
> Einkommens-Decke zu niedrig für den Aufwand (bei +1 % Netto-Edge braucht
> 300 €/Monat ~30.000 € Monatsumsatz — LUGAS-untauglich).

## Artefakte

- `run.py` — Phase-2-Harness (Plateau, Cross-Liga-OOS, Buckets, Kelly-Gate)
- `results/metrics.json`, `results/trades.csv` (1.849 Wetten),
  `results/plateau_bankroll.png` (Plateau + Bankroll-Pfad)
