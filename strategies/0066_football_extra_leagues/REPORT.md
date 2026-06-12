# Strategie 0066 — Extra-Ligen-Eignungstest (Erweiterung des Live-Pollings)

- **Kategorie:** value betting / Daten-Eignung / Cross-Liga
- **Status:** abgeschlossen — formales Gate 0/14 PASS (zweimal falsch
  dimensioniert), strukturelle Befunde positiv → 8 Ligen als Extension-Tier
  ins Live-Polling (Gate 0065 unverändert)
- **Datum:** 2026-06-12
- **Universum:** 14 football-data-Extra-Länder (Österreich, Dänemark,
  Schweiz, Polen, Argentinien, Mexiko, China, Schweden, Norwegen, Finnland,
  USA, Brasilien, Japan, Irland); Russland (keine B365-Daten), Rumänien
  (kein API-Key), Australien (Datei defekt) ausgeschlossen

## 1. Ausgangsfrage & Daten-Blocker

Können weitere Fußball-Ligen mit dem eingefrorenen 0064-Test validiert
werden? **Nein:** die Extra-Dateien (`/new/{LAND}.csv`) enthalten NUR
Schlussquoten — keine Collection-Quoten, also kein EV-zur-Entscheidungszeit
und kein CLV im 0063-Sinn. Stattdessen registrierter **Eignungstest** auf die
zwei Strukturbedingungen: (a/b) Pinnacle-Orakel liquide + kalibriert,
(c) Soft-Book-Bias existiert.

## 2. Zwei Läufe, zwei formale FAILs — beide an der Messung, nicht am Signal

**Lauf 1** (Gate c: ≥50 Bet365-Close-Value-Wetten): 0/14 PASS — aber weil
B365-Schlussquoten in den Extra-Dateien **erst seit Saison 2025/26**
existieren (n=3–41 möglich statt ≥50). Die beobachteten Bias-Raten waren
hoch (7–48 Value-Wetten/100 Spiele).

**Lauf 2** (Amendment: Orakel-Gates auf voller Pinnacle-Historie ab 2019,
Bias auf der voll abgedeckten Markt-Durchschnitts-Schlussquote AvgC,
Rate ≥ 50 % des Benchmarks): wieder 0/14 — weil das `n ≥ 50` aus der
B365-Spezifikation stehen blieb und mit dem selteneren AvgC-Maß
(~0,5–3/100 Spiele × 1.000–3.000 Spiele = n 8–45) strukturell unerreichbar
ist. **Dieselbe Fehlerklasse wie das 0064-ROI-Gate: Schwelle registriert,
ohne das erreichbare n gegen das verfügbare n zu rechnen — zweimal im
selben Programm.** Es gab bewusst keinen dritten Gate-Umbau (das wäre
Gate-Shopping bis zum PASS).

## 3. Die strukturellen Befunde (das, was die Daten wirklich sagen)

Benchmark = identische Schlussquoten-Linse auf den 18 validierten Ligen
(42.227 Spiele ab 2019-07): Marge 3,2 %, AvgC-Value-Rate 0,56/100,
B365C-Value-Rate 4,79/100 mit realisiertem ROI **+3,7 %** (≈ mean EV +4,5 % —
die Orakel-Erwartung bestätigt sich dort, wo n groß ist).

| Befund | Ergebnis über die 14 Kandidaten |
| --- | --- |
| Orakel liquide | **14/14**: Pinnacle-Close-Marge 3,1–4,7 % (Benchmark 3,2 %) |
| Orakel kalibriert | Brier-Differenzen Shin−Mult ±0,0004 ≈ Rauschen, 9/14 pro Shin |
| Bias-Rate (AvgC) | **13/14 ≥ Benchmark-Rate** (0,5–3,1 vs 0,56/100); nur Finnland darunter (0,09) |
| Gepoolte Sanity | Flat-ROI +12,4 % [−10,6 %, +37,2 %], n=216 — konsistent mit mean EV +6 %, nicht widerlegend |

Die Kandidaten-Ligen sehen unter derselben Linse aus wie das validierte
Panel — eher *ineffizienter* (höhere Bias-Raten), was der Nischen-These
(0064: OOS > IS) entspricht.

## 4. Entscheidung & Begründung

**8 neue Ligen in den Extension-Tier des Live-Pollings** (AUT, DNK, SWZ,
POL, ARG, MEX, CHN, IRL): Der Extension-Tier war von Anfang an als „nicht
Gate-relevant, nur Reporting" registriert — die 6 Sommer-Ligen kamen ohne
jede Backtest-Evidenz hinein; diese 8 haben jetzt **mehr** Evidenz (Orakel
sane, Bias-Rate ≥ Benchmark, Sanity +). Das registrierte 0065-Gate (18
validierte Ligen) bleibt unangetastet. Live schützt zusätzlich: kein
Pinnacle → keine Wette.

**Budget-Schutz:** Extension-Tier pollt mit 24h-Lookahead (validiert: 48h,
wie registriert) — kürzerer Vorlauf ist für die CLV-Messung konservativ.
Quota-Guard unverändert; Scan-Reihenfolge validiert-zuerst.

Erster Tick mit 32 Ligen: 5 Credits kumuliert, 1 neuer Alert (League of
Ireland — Freitagsspiele).

## 5. Lehren

1. **Erreichbares n VOR jeder Schwellen-Registrierung rechnen** — zweimal in
   diesem Programm verletzt (0064-ROI-Gate, 0066 zweifach). Jede Schwelle
   der Form „n ≥ X" braucht die Gegenrechnung „wie viel n liefert die
   Datenquelle maximal?".
2. **football-data-Extra-Dateien:** nur Schlussquoten; B365C erst ab 2025/26;
   AvgC voll seit 2012; Pinnacle-Close fehlt in den jüngsten Saisons
   einzelner Länder (ARG/USA 2026) — Spaltenexistenz ≠ Datendeckung, immer
   Coverage je Saison prüfen (Verwandte der 0025-Frozen-Feed-Lehre).

## Artefakte

- `run.py` (mit dokumentiertem Amendment), `results/metrics.json`,
  `results/close_value_bets.csv`
- `quantlab/football_data.py::get_extra_league` (neuer Loader)
- Live-Polling-Update in `scripts/football_live_paper.py` (32 Ligen,
  Tier-Lookahead)
