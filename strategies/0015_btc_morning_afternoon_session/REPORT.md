# Strategie 0015 — Sagt die Morgen-Richtung die Nachmittag-Richtung? (BTC)

- **Kategorie:** momentum / intraday (Session-Autokorrelation)
- **Status:** abgelehnt (Forschungsfrage beantwortet: kein verwertbarer Zusammenhang)
- **Datum:** 2026-06-04
- **Universum:** Bitcoin (BTC/USDT, Binance-Spot-Tape, gehandelt als Bitget USDT-M Perp)
- **Stichprobe:** In-Sample 2017-08 – 2022-12 (1958 Tage) / Out-of-Sample 2023-01 – 2026-06 (1249 Tage)

## 1. Hypothese / Frage

Hat die **Richtung der Morgen-Session** (00:00 → 14:00 UTC) einen Einfluss auf die
**Richtung der Nachmittag-Session** (14:00 → 24:00 UTC)? 14 UTC = US-Eröffnung /
Vola-Peak aus 0012. Vorab-registriert, *eine* Frage — keine Parametersuche.

## 2. Makro-Begründung

Zwei plausible Geschichten, IS entscheidet das Vorzeichen, OOS validiert:
- **Continuation:** Asien/Europa-Positionierung + Orderflow vor US-Open läuft
  weiter, sobald US-Desks dazukommen (Autokorrelation/Momentum).
- **Reversal:** US-Mean-Reversion-/Liquiditäts-Flows faden die Übernacht-Bewegung
  („American Reversal").

## 3. Regeln

- `M = Open[14:00] / Open[00:00] − 1` (morgens, um 14:00 vollständig bekannt).
- `A = Close[23:00] / Open[14:00] − 1` (nachmittags, strikt nach 14:00).
- Entscheidung um 14:00 mit `M`; Position `= Richtung · sign(M)` nur über den
  Nachmittag (14:00 → 24:00), danach flat → **Look-Ahead strukturell unmöglich**.
- IS legt die Richtung fest (Continuation falls IS-Korrelation ≥ 0, sonst
  Reversal). `n_trials = 2`. OOS beurteilt nur die gelockte Regel.

## 4. Kosten- & Ausführungsannahmen

Bitget USDT-M Perp, Taker 0,06 % + 2 bps Slippage = 8 bps/Seite. Ein Round-Trip
pro gehandeltem Tag = **16 bps/Tag**.

## 5. Ergebnisse — die Antwort

**Der Zusammenhang ist praktisch null.**

| Kennzahl (IS)                     |        Wert |
| --------------------------------- | ----------: |
| Pearson-Korrelation M↔A           |      +0,037 |
| Spearman                          |      +0,050 |
| OLS-Steigung                      |      +0,032 |
| Vorzeichen-Übereinstimmung        |       50,5 % |
| Morgen ↑ → Nachmittag-Mittel      |     +0,26 % (55,2 % positiv) |
| Morgen ↓ → Nachmittag-Mittel      |     −0,01 % (54,1 % positiv) |

Entscheidend: **Auch nach einem Minus-Morgen waren 54 % der Nachmittage positiv** —
der Nachmittag driftet *unbedingt* leicht nach oben (BTC-Beta); das Morgen-
Vorzeichen verschiebt das kaum. IS wählte daher „Continuation".

| Kennzahl (OOS, gelockte Continuation-Regel) | netto | brutto |
| ------------------------------------------- | ----: | -----: |
| CAGR                                        | −47,0 % | — |
| Sharpe                                      | −1,67 | −0,02 |
| Max Drawdown                                | −89,2 % | — |
| Pearson M↔A (OOS)                           | +0,033 | — |
| Vorzeichen-Übereinstimmung (OOS)            | 49,5 % | — |
| Trades (gehandelte Tage)                    | 1249 | — |

Benchmarks OOS: **stures Long-Halten des Nachmittags** Sharpe **+0,83** (CAGR
+28,6 %); voller Tag Buy&Hold Sharpe +1,06. Das einzige, was am Nachmittag
„funktioniert", ist long zu sein — *nicht* das Konditionieren auf den Morgen.

## 6. Signifikanz

| Test                              |          Wert |
| --------------------------------- | ------------: |
| t-Test mittlere Brutto-Rendite    | t = +0,06, p = 0,949 |
| t-Test mittlere Netto-Rendite     | t = −2,99, p = 0,003 *(signifikant **negativ** = Kosten)* |
| Permutationstest (brutto, Timing) | p = 0,471 |
| Bootstrap Netto-Sharpe 95%-KI     | [−2,30; −0,53] |
| Deflated Sharpe (N = 2)           | 0,000 |

Der Brutto-t-Test (p = 0,95) sagt es am deutlichsten: Das Morgen-Vorzeichen-Timing
ist von Zufall **nicht unterscheidbar**. Der einzige statistisch signifikante
Effekt ist der *negative* Netto-Drift — also die Transaktionskosten.

## 7. Robustheit

- **Magnitude-Buckets (OOS):** Nach *kleinen* Morgenbewegungen sogar leichte Anti-
  Continuation (Agreement 45,6 %); nur nach *großen* Morgenbewegungen ein Hauch
  Continuation (+0,23 %, 51,2 % Agreement) — zu schwach für 16 bps, im Rauschen.
- **Pro Jahr (OOS):** Vorzeichen-Übereinstimmung 46 % / 50 % / 51 % / 53 % — um
  50 % pendelnd, kein stabiler Effekt.
- **Split-Stunden-Scan:** IS-Korrelation für *alle* Schnitte (8–20 UTC) zwischen
  +0,015 und +0,038 — 14 UTC ist nicht besonders, und OOS bricht die schwache
  Beziehung teils ins Negative (20 UTC: −0,03). Es gibt keinen privilegierten
  Schnittpunkt; der Effekt existiert schlicht nicht robust.

## 8. Verdict

**Antwort auf die Frage: Nein.** Die Richtung der Morgen-Session (00–14 UTC) hat
**keinen verwertbaren Einfluss** auf die Richtung der Nachmittag-Session. Es gibt
eine winzige positive Autokorrelation (~0,03), die aber von Zufall nicht zu
unterscheiden ist (Brutto-Sharpe ≈ 0, Brutto-t p = 0,95, Permutation p = 0,47) und
durch Kosten in einen klaren Verlust kippt. Der einzige reale Nachmittags-Effekt
ist eine **unbedingte Long-Drift** (Beta), nicht das Konditionieren auf den
Morgen. Die wegen niedrigem Umschlag gehegte Kosten-Hoffnung trägt hier nicht,
weil schlicht kein Signal vorhanden ist, das die Kosten bezahlen könnte.
