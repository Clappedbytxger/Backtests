# 0067 — Saison-Kalenderspreads (Front vs. Second)

**Verdikt: abgelehnt (4 saubere Nullen, 1 schwacher Beobachtungs-Kandidat unter der Lead-Schwelle).**

## Hypothese

Idee A aus `NEXT-STRATEGIES-AND-LIVE-SYSTEM.md`: die validierten Outright-
Saison-Fenster des Katalogs als Kalenderspreads ausdrücken (long Front `.c.0` /
short Second `.c.1`) — marktneutral im Rohstoff, kein Beta, die Roll-Dynamik
ist das Signal statt ein Artefakt. Ökonomische Story je Fenster: Prompt-
Nachfrage/Restocking sollte den Nahmonat gegen den Fernmonat stärken.

**Vorab registriert: exakt 5 Hypothesen = 5 Trials, Fenster wörtlich aus
Vorarbeiten übernommen, KEIN neues Fenster-Mining.**

## Daten & Konstruktion

- Databento GLBX `.c.0`/`.c.1` täglich, 2010–2026 (Cache aus 0048, kein Neukauf).
- Spread-Return = roll-bereinigter Front-Return − roll-bereinigter Second-Return;
  **beide Beine auf Roll-Tagen genullt** (`instrument_id`-Wechsel eines der
  Beine; Lehre 0028/0048 — der Stitch-Gap ist Fiktion). UTC-Sonntags-Zeilen
  verworfen (Lehre 0057).
- Kosten: 2,5 bps/Seite Front + 4,5 bps/Seite Deferred (dünner, gepolstert)
  = **14 bps je Spread-Round-Trip**, auf |ΔPosition| belastet.
- Wichtig/ehrlich: Das testet den **Nearby-Spread** (Front vs. 2. Kontrakt),
  NICHT die spezifischen Monats-Paare des Ideen-Dokuments (z. B. Mais Dez/Jul).
  Letztere bräuchten Einzelkontrakt-Ketten (Databento parent symbology) —
  separater Daten-/Engineering-Schritt, siehe „Offene Pfade".

## Batterie (alle netto, n_trials=5)

| Hyp | Fenster | n | Mean/Trade | Win | t-p | **Perm p** | Boot-KI Mean | DSR | IS/OOS |
|-----|---------|--:|-----------:|----:|----:|-----------:|--------------|----:|--------|
| H1 Benzin | KW9 (0006) | 16 | −0,00% | 44% | 0,997 | 0,465 | [−0,53; +0,65] | 0,12 | −0,35/+0,35 |
| **H2 Mastrind** | KW21 (0009) | 16 | **+0,45%** | 62% | 0,143 | **0,019** | [−0,11; +1,00] | 0,44 | +0,05/+0,85 |
| H3 Mais | 8.–18.12. (0030) | 16 | +0,11% | 62% | 0,582 | 0,375 | [−0,26; +0,49] | 0,22 | +0,40/−0,25 |
| H4 Erdgas | 21.9.–1.11. (0028) | 16 | +1,00% | 56% | 0,593 | 0,469 | [−2,15; +4,83] | 0,28 | −1,96/+4,81 |
| H5 Platin | 18.12.–10.1. (0021) | 15 | +0,07% | 53% | 0,806 | 0,578 | [−0,42; +0,56] | 0,14 | −0,16/+0,33 |

Permutation = gleich lange Fenster an zufälligen Jahres-Positionen (trägt die
volle Carry-Drift des Spreads → testet nur das TIMING; Drift-Fallen-Lehre
0016/0017). Bootstrap auf den Per-Trade-Mean. IS 2010–2018 / OOS 2019–2026.

## Befund

1. **H1/H3/H5 leer, H4 (Erdgas) eine Fat-Tail-Lotterie:** Der NG-Herbst-Spread
   hat +1,00%/Trade im Mittel, aber Win nur 56%, KI [−2,15; +4,83] und das
   Mittel hängt an 2020 (+23%) — exakt die Verteilungsform, die 0038 als
   doppelt disqualifizierend markiert hat. Die 0028-Frage („als Spread könnte
   der Effekt echt sein") ist damit beantwortet: **nein** — was als Outright
   ein Roll-Artefakt war, ist als Spread Rauschen mit einem Ausreißer-Jahr.
2. **H2 (Mastrind KW21) ist der einzige echte Timing-Befund:** Permutation
   p=0,019 — das Fenster schlägt 98% zufälliger gleich langer Fenster, und
   OHNE den Drift-Vorteil, den der Outright-Test genießt. OOS (+0,85%) >
   IS (+0,05%), kein Kollaps. ABER: Bootstrap-KI [−0,11%; +1,00%] berührt 0,
   DSR 0,439 < 0,5, t-p 0,143, n=16 → **unter der Lead-Schwelle** (dieselbe
   Messlatte, an der 0049-h12 als Selektions-Glück fiel; hier vorregistriert
   statt selektiert, daher als Beobachtungs-Kandidat notiert, nicht gehandelt).
3. Ökonomisch konsistent: Grillsaison-Prompt-Nachfrage ist die plausibelste
   der 5 Stories für eine FRONT-Stärkung (Feeder Cattle nicht lagerbar →
   Prompt-Knappheit kann nicht durch Lager arbitriert werden). Die lagerbaren
   Märkte (RB/ZC/NG/PL) zeigen nichts — Lager-Arbitrage glättet den Spread.

## Entscheid

- **Kein neues Programm, kein Handelsbein.** Der Outright 0009 (confirmed)
  bleibt das Mastrind-Vehikel; der Spread ist kein Ersatz und kein Zusatz-Edge
  mit dieser Evidenz.
- **Beobachtungs-Kandidat H2** im Hinterkopf: wenn der 0009-Live-Forward läuft,
  kostet es nichts, den GF-Spread-PnL im selben Fenster mitzuloggen (Ledger),
  und in ~5 Jahren hat der Test n≈21.

## Offene Pfade (nicht getestet, ehrlich abgegrenzt)

- **Spezifische Monats-Paare** (Mais Dez/Jul alte-vs-neue-Ernte, Soja-Crush,
  Weizen-Carry) brauchen Einzelkontrakt-Ketten statt `.c.0/.c.1` — Databento
  parent symbology, neuer Loader + Kostenabschätzung. Erst angehen, falls
  überhaupt, nach Idee B; die Nearby-Null hier senkt die Prior.

## Reproduktion

    .venv/Scripts/python.exe strategies/0067_calendar_spread_seasonals/explore.py
    .venv/Scripts/python.exe strategies/0067_calendar_spread_seasonals/run.py
