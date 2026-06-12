# Strategie 0065 — Football Value Betting, Phase 3: Live-Paper-Forward

- **Kategorie:** value betting / live-forward / paper
- **Status:** testing — **Live-Forward registriert 2026-06-12, läuft ab erstem Tick**
- **Datum (Registrierung):** 2026-06-12
- **Universum:** 18 validierte Ligen (Backtest-Panels 0063/0064) + 6
  Extension-Sommer-Ligen (Allsvenskan, Eliteserien, Veikkausliiga, MLS,
  Brasileirão, J-League — nur Reporting, NICHT Gate-relevant)
- **Werkzeug:** `scripts/football_live_paper.py` + `quantlab/odds_live.py`
  (The Odds API, Gratis-Tier ~500 Credits/Monat)

## 1. Zweck

Der Backtest (0063/0064) hat den CLV-Beweis auf dem Freitag-Snapshot erbracht
(18/18 Ligen Median-CLV > 0), aber zwei Fragen kann nur Live-Polling
beantworten: (1) Ist der **heutige** Edge groß genug (Flow zerfiel bis 25/26
auf 1,6 Wetten/Woche)? (2) Fängt tägliches Polling **größere** Divergenzen als
der Wochen-Snapshot (mittlerer CLV im Backtest nur +1,1 % brutto — nach
Slippage ~+0,2 %, zu dünn für die Einkommens-Decke)?

## 2. Eingefrorene Regel (aus 0063/0064, KEINE neuen Trials)

- Pinnacle-1X2-Quoten Shin-de-viggen → faire Wahrscheinlichkeiten.
- Paper-Wette auf Outcome i bei `beste_Soft-Book-Quote_i × fair_p_i − 1 > 2 %`,
  EV-Cap 20 % (Datenfehler-Guard), beste Quote über die Soft-Book-Allowlist
  (bet365, tipico, winamax, unibet, …; Exchanges/Sharps ausgeschlossen).
- Erste Sichtung zählt (kein Nachbessern); ¼-Kelly-Stake (Cap 2 %) dokumentiert.
- Events nur im 48h-Lookahead (entspricht der Backtest-Snapshot-Distanz).
- **CLV = gewettete Quote × Shin-faire-p der Schlusslinie − 1**, Schlusslinie =
  letzter Pinnacle-Snapshot vor Anpfiff (Staleness wird mitprotokolliert).

## 3. Vorab registriertes Gate (Erfolg = alle drei, auf validierten Ligen)

1. **n ≥ 150** geschlossene Paper-Wetten,
2. **Median-CLV ≥ +1 %** (Bootstrap-KI wird mitberichtet),
3. **mittlerer CLV nach 1 %-Slippage-Äquivalent > 0**
   (Slippage je Wette = 0,01 × (Quote−1) × fair_p_close).

**Auswertung:** sobald n ≥ 150 erreicht ist, spätestens am **2026-10-31**
(Saisonstart der EU-Ligen ist August; Juni/Juli liefern v. a.
Extension-Ligen-Daten, die NICHT ins Gate fließen). **Bei FAIL wird das
Programm beendet** — keine Schwellen-/Liga-Nachjustierung auf den Live-Daten
(das wäre Mining auf dem Forward). Bei PASS: Phase 4 (Echtgeld-Micro) nur
nach Verifikation der Steuer-Absorption (Existenzbedingung, siehe 0064).

## 4. Betrieb

```
# Setup (einmalig): Gratis-Key von https://the-odds-api.com
#   -> D:\Backtests\.oddsapi.key  (gitignored via *.key)
# Liga-Keys einmalig verifizieren:
.\.venv\Scripts\python.exe scripts\football_live_paper.py --list-sports

# Täglicher Tick (idealerweise vormittags; an Spieltagen gern 2.,
# abends ~2-4h vor Anpfiff -> frischere Schlusslinien-Proxys):
.\.venv\Scripts\python.exe scripts\football_live_paper.py

# Nur Status ansehen (0 Credits):
.\.venv\Scripts\python.exe scripts\football_live_paper.py --report
```

State (git-versioniert = fälschungssicherer Forward-Log):
`state/paper_bets.csv`, `state/pinnacle_snapshots.csv`, `state/quota.json`.
Credit-Budget: kostenloser `/events`-Vorfilter pollt `/odds` (1 Credit) nur
für Ligen mit Spielen < 48h; Quota-Guard stoppt den Scan unter 25 Credits.

## 5. Bekannte Grenzen (ehrlich, vorab)

1. **Schlusslinien-Proxy ist stale:** bei 1 Tick/Tag bis zu ~24h vor Anpfiff
   (Lineup-News der letzten Stunde fehlen). Das macht den gemessenen CLV
   tendenziell RAUSCHIGER, nicht systematisch geschmeichelt — die Staleness
   wird je Wette geloggt und im Report als Median ausgewiesen.
2. **Bet365 via Aggregator ≠ Bet365-Anzeige:** kleine Quoten-Differenzen und
   Verzögerungen möglich; dafür ist das 1 %-Slippage-Äquivalent im Gate.
3. **Juni/Juli = EU-Sommerpause:** validierte Ligen liefern erst ab August
   Volumen; die Extension-Ligen überbrücken (und sind nebenbei ein weiterer
   ehrlicher Cross-OOS im 0064-Geist — separat berichtet).
4. **Eine Quote je Sichtung:** das Skript wettet bei Erst-Überschreitung der
   Schwelle, nicht am Optimum — konservativ und reproduzierbar.

## 6. Ergebnisse

*(läuft — wird nach Gate-Auswertung gefüllt; Zwischenstände via `--report`)*

## Artefakte

- `quantlab/odds_live.py` — API-Client + eingefrorene Alert-/CLV-Logik
- `tests/test_odds_live.py` — 7 netzfreie Logik-Guards
- `scripts/football_live_paper.py` — täglicher Tick (Scan/Close/Settle/Report)
- `state/` — Paper-Bet-Log (CSV, eingecheckt)
