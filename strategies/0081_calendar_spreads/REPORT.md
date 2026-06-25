# Strategie 0081 — Calendar- & Inter-Commodity-Spreads (Handoff-Gruppe I0001-I0007)

> Roadmap-Top-Ideengruppe aus `D:\Backtest Ideas` (#s01/#s14). Einzelkontrakt-Ketten
> via Databento (~$32 vom Restkredit, genehmigt). Neue Infra `quantlab.futures_chain`.

- **Kategorie:** calendar-spread / inter-commodity / seasonal
- **Status:** abgelehnt (kein sauberes Lead — alle 5 Spreads null in 2010-2026)
- **Datum:** 2026-06-15
- **Universum:** ZC, NG, RB (Calendar-Spreads); ZS/ZM/ZL (Crush), CL/RB/HO (Crack)
- **Stichprobe:** 2010-2026 (Databento GLBX Tagesbars, alle gelisteten Kontrakte)

## 1. Hypothese

Ein Spread ist roll-sauber (Jahres-Roll außerhalb des Saisonfensters) und beta-neutral
→ isoliert die saisonale Angebots-/Nachfrage-Transition ohne die Richtungs-/Roll-
Artefakte, die die Outright-Versionen töteten (0028/0029, 0080). Fünf vorab fixierte
Saison-Spreads, jeweils long im Fenster.

## 2. Konstruktion (roll-sauber)

Spread-Return = dollar-neutrale Bein-Differenz (Long-Leg-%Return − Short-Leg-%Return),
gebaut aus Einzelkontrakten (`futures_chain.calendar_spread_return` für gleiche Root,
`matched_month_spread_return` für Inter-Commodity mit gleichem Liefermonat). Jahr je
Kontrakt aus `instrument_id` + letztem Handelstag aufgelöst (einstellige Jahrescodes
kollidieren über Dekaden — via instrument_id getrennt). Jeder Spread wird nur im
Saisonfenster gehalten → der Jahres-Roll fällt zwischen die Fenster (roll-sauber).

## 3. Ergebnisse (vorregistrierte Fenster)

| Spread | Jahre | gross Sharpe | netto | % Jahre + | Permutation | Boot-KI (bps/Tag) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| I0001 Mais Jul/Dez (1.12–15.6) | 17 | +0,15 | +0,15 | 53 % | **0,644** | [−1,91, +2,96] |
| I0003 NatGas Mär/Apr (1.10–20.2) | 16 | −0,73 | −0,74 | 19 % | **1,000** | [−10,56, +0,02] |
| I0004 RBOB Jul/Nov (1.2–20.5) | 14 | +0,09 | +0,08 | 57 % | **0,405** | [−4,60, +5,49] |
| I0002 Soja-Crush (1.10–31.1) | 16 | −0,02 | −0,04 | 50 % | 0,038 | [−2,20, +2,05] |
| I0007 3-2-1 Crack (15.2–25.5) | 14 | −0,01 | −0,02 | 64 % | 0,176 | [−7,87, +7,49] |

**Leads (perm p<0,05 UND Boot-KI ohne 0): keine.**

## 4. Diagnose

- **Mais Jul/Dez (Flaggschiff, am besten begründet): klar NULL** (perm p=0,644, Boot-KI
  mit 0, 53 % Jahre positiv = Münzwurf). Der Lehrbuch-Old-Crop/New-Crop-Spread schlägt
  Zufalls-Timing 2010-2026 NICHT. Das ist der aussagekräftigste Befund — die ökonomisch
  sauberste Spread-Hypothese trägt nicht mehr.
- **NatGas Mär/Apr: falsche Richtung** (Sharpe −0,73, perm p=1,0) — der „Widow-Maker"-
  Spread fällt im Herbst-Fenster, statt zu steigen; die 0028-Dynamik ist als Spread
  nicht long-handelbar.
- **RBOB Jul/Nov: null** (p=0,41).
- **Crush: grenzwertig, aber kein Edge** — perm p=0,038 (Fenster ist „bester" Sub-Zeitraum
  im Capture), aber Sharpe ~0 und Boot-KI [−2,20,+2,05] mit 0: das Fenster ist relativ
  hoch-gerankt, aber sein ABSOLUTER Return ist nicht signifikant positiv (gleiches Muster
  wie 0067-H2 / 0049-h12 — Rang ≠ Edge).
- **Crack: null** (p=0,176). **Wichtig:** die roll-NAIVE Erstversion (unabhängige
  Front-Kontrakte je Bein) gab perm p=0,006 mit Boot-KI [−20,+110] bps = reines
  Roll-Artefakt (per-Leg-Roll-Sprünge, nicht back-adjustiert). Die roll-saubere
  Matched-Expiry-Version (gleicher Liefermonat, im Fenster gehalten) entlarvt das:
  p=0,006→0,176. **Lehre 0029 erneut bestätigt** — Inter-Commodity-Fronts müssen
  matched-expiry/roll-sauber sein, sonst ist jede Signifikanz ein Roll-Artefakt.

## 5. Verdict

**Abgelehnt — die Roadmap-Top-Calendar-Spread-Gruppe trägt in 2010-2026 keinen sauberen
Edge.** Alle fünf vorregistrierten Saison-Spreads sind null (Mais/RBOB/Crack) bzw.
falsch-gerichtet (NG) bzw. rang-hoch-aber-absolut-null (Crush). Konsistent mit (a) 0067
(Nearby-Spreads: 4 Nullen + 1 schwach), (b) der Bestand-Lehre, dass cross-sektionale/
saisonale Rohstoff-Prämien im 2010er-Jahrzehnt zerfallen sind (0047/0048), und (c) 0080
(Mais-Sommer-Short war ein Roll-Artefakt). **Die Spreads beheben das Roll-Problem
korrekt — aber wenn die saubere Reihe getestet wird, ist schlicht kein Saison-Edge mehr
da.** Die $32-Investition hat die roadmap-prominenteste offene Idee definitiv geklärt.

**Bleibender Gewinn:** roll-saubere Einzelkontrakt-Ketten-Infra (`quantlab.futures_chain`:
`calendar_spread_return` + `matched_month_spread_return`, instrument_id-Jahresauflösung)
wiederverwendbar für jede künftige Spread-/Term-Structure-Frage; 8 Roots (ZC/ZS/ZM/ZL/
NG/RB/HO/CL) Tagesketten 2010-2026 gecacht.
