# Strategie 0069 — SMC Liquidity-Sweep + Break-of-Structure

- **Kategorie:** price-action / intraday / discretionary-systematisiert
- **Status:** **abgelehnt als Standalone-Markt-Schläger** — Indizes = Beta;
  **BTC = testing/Lead mit Zerfall** (echter both-direction-Timing-Edge, OOS
  nicht mehr signifikant)
- **Datum:** 2026-06-13
- **Universum:** Gold (XAU/USD, GC-Future), Bitcoin (BTC/USDT Binance Spot),
  S&P 500 (ES-Future), Nasdaq-100 (NQ-Future), British Pound (GBP/USD, 6B-Future)
- **Stichprobe:** 2016-01 bis 2026-05; OOS-Split BTC 2017-2021 / 2022-2026
- **Referenz:** Revelio-Trading-Video „I Improved TJR's Strategy" (+ Vorvideo mit
  der V1-Definition). Seine Zahlen sind laut eigener Aussage **in-sample-
  optimiert, best-case, zero-cost** („I gave the strategy the most favorable
  version of itself on purpose").

## 1. Hypothese

Das SMC-Setup — Liquiditäts-Sweep eines bestätigten Swings + Break-of-Structure —
erzeugt einen handelbaren Richtungs-Edge über fünf Asset-Klassen.

## 2. Makro-Begründung

Order-Flow-/Mikrostruktur-Story: Stop-Liquidität unter/über offensichtlichen
Swings wird abgeholt (Sweep), dann kehrt der Preis um und bricht die Struktur.
Vorab-Skepsis: liquide Index-Intraday-Richtung ist im Katalog wiederholt tot
(0012–0015/0038–0041/0049).

## 3. Regeln (eingefroren, `config.yaml` + `quantlab/smc`)

- **Swing (KORRIGIERT):** asymmetrisches Pivot `(back, forward)` — Hoch ist das
  höchste über `back` Kerzen davor UND `forward` Kerzen danach (Referenz: „6
  back / 2 forward" etc.; Confirmation-Lag = `forward`). Die erste Version nutzte
  fälschlich ein **symmetrisches** Fraktal — der Kernfehler.
- **Sweep:** Wick jenseits des jüngsten bestätigten Gegen-Swings + Re-Close
  innerhalb K=3 Bars.
- **BOS:** Close jenseits des jüngsten bestätigten Gegen-Swings, der **über/unter
  dem Reclaim** liegt (echter Struktur-Bruch, `require_structure`).
- **Entry:** Close der BOS-Bar. **Stop:** `sweep_extrem ∓ buffer·ATR(14)`.
- **Exit:** 1R-Trailing (alle außer GBPUSD), Fixed-1R (GBPUSD). Long-only Indizes.
- **Look-ahead-frei:** `tests/test_smc_causality.py` (sym. + asym. Pivot grün).

## 4. Kosten- & Ausführungsannahmen

Pro Seite: Kommission + Spread (bps) + Slippage (`slip_coef·Bar-Range`).
Vergleich zum Video zusätzlich im **Spread+Kommission-ohne-Slippage**-Modus (seine
Methode). Hinweis: meine Gold-Kosten (~3 bps RT) sind ~2× IC-Markets-Raw (~1,4
bps RT) — Teil der Gold-Netto-Differenz ist Kosten-Kalibrierung, nicht Strategie.

## 5. Reproduktion (brutto, 1 % Risiko/Trade, seine finale Config)

| Asset | mein Bestes (korrekt gebaut) | Video-Ziel | Status |
| --- | ---: | ---: | --- |
| NDX (long, 6/2, buf 0,5) | +86 % | +73 % | **getroffen** |
| SPX (long, 6/2, buf 1,0) | +54 % | +82 % | ~⅔ |
| BTC (both, 8/4, buf 1,0) | +79 % | +173 % | ~½ |
| XAUUSD (both, 12/6, buf 0,5) | +158–284 % | +477 % | ~⅓–⅗ |
| GBPUSD (both, fixed1R) | +3 % | +131 % | proxy-limitiert |

Restlücke erklärt: (a) er ist explizit in-sample-optimiert/best-case/zero-cost,
(b) Instrument-Proxies (GC/6B-Futures vs. XAU/GBP-Spot-CFD; FX-Future-Mikrostruktur
≠ Spot), (c) Kosten-Kalibrierung. Der **Swing-Fix war der größte Hebel** (BTC
+34 %→+79 %, Ø-R +0,10→+0,32; NDX traf danach sein Ziel).

## 6. Signifikanz auf der korrekt gebauten Strategie (netto Spread+Komm.)

| Config | Sharpe (B&H) | Permutation p (Null vs real) | Bootstrap Ø-R-KI | DSR |
| --- | ---: | ---: | ---: | ---: |
| **BTC both 8/4** | 0,48 (0,79) | **0,053** (−0,14 vs **+0,31**) | [+0,03, +0,53] | 0,46 |
| NDX long 6/2 | 0,54 (0,84) | 0,950 (0,77 vs 0,54) | [+0,12, +0,76] | 0,69 |
| SPX long 6/2 | 0,37 (0,68) | 0,969 (0,58 vs 0,37) | [+0,08, +0,89] | 0,52 |
| Gold both 12/6 | −0,14 (0,70) | 0,712 | [−0,08, +0,07] | 0,01 |

**Kern:** Auf den Long-only-Indizes liegt die Permutations-Null (Zufalls-Long)
ÜBER der Strategie (0,77/0,58 vs 0,54/0,37) → **Beta, kein Timing-Edge** (robust
über alle Builds). **BTC (both-direction!)** schlägt die Null (+0,31 vs −0,14,
p=0,053) → echtes Timing-Signal, **nicht Beta**. Gold: brutto stark, aber netto
durch die M5-Frequenz × Kostenwand tot.

## 7. Robustheit — BTC-Deep-Dive

- **Pivot×buffer-Gitter (24 Zellen):** Edge konzentriert im Klein-Pivot-Bereich
  (6–8 back, buf 1,0–1,5: Ø-R +0,14…+0,28, p 0,05–0,12); Groß-Pivots (10–12) tot.
  14/24 positiv — Teil-Plateau, kein Einzel-Spike.
- **Echter OOS-Split:** IS 2017-2021 Ø-R **+0,451**, p=0,063, KI ohne 0 →
  OOS 2022-2026 Ø-R **+0,161**, **p=0,250, KI [−0,13,+0,48] mit 0** = IS→OOS-
  Zerfall, OOS nicht signifikant.
- **Jahr-für-Jahr:** positiv in JEDEM Jahr 2017-2026, aber abklingend (2018-20
  Ø-R +0,57…+1,76 → 2024-26 +0,02…+0,19). Crypto wird effizienter.
- **Kosten/Funding:** robust — überlebt Spread+Komm. + 3 bps/Tag Funding + 2×
  Kosten (Ø-R bleibt +0,18). Funding tötet es nicht.

## 8. Verdict

**Standalone-Markt-Schläger: abgelehnt.** Die Index-Sleeves sind unter-
durchschnittliches Long-Beta (Permutation gegen Zufalls-Long bestanden NICHT,
über alle Builds), Gold ist netto kosten-tot, GBP proxy-limitiert.

**BTC: testing/Lead mit Zerfall.** Ein **echter** both-direction-Timing-Edge
(nicht Beta, nicht Glück: positiv jedes Jahr, kosten-/funding-robust, IS p=0,06,
Bootstrap-KI ohne 0) — der in meiner symmetrischen Fehlversion UNSICHTBAR war.
Aber OOS nicht mehr signifikant (p=0,25) und mit der Crypto-Reifung abklingend.
SMC-Sweep+BOS fängt Crypto-Trends, und die sind seit 2021 schwächer (reiht sich
in 0058–0062 ein: Crypto-Momentum real aber zerfallend).

**Meta-Lehre:** Eine faithful Reproduktion verlangt die EXAKTE Primitiv-
Definition — mein symmetrisches Fraktal statt seines asymmetrischen `(back,
forward)`-Swings drehte BTC von „tot" auf „marginaler Edge". Erst nach der
korrekten Konstruktion ist der p-Test aussagekräftig; und der drift-kontrollierte
Permutationstest auf einem **both-direction**-Asset ist der saubere Edge-vs-Beta-
Test, den das Referenz-Video nicht durchführt.
