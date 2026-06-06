# Strategie 0039 — Opening-Range-Fade / Continuation (ES 1-Minute Intraday)

- **Kategorie:** mean-reversion / intraday
- **Status:** abgelehnt
- **Datum:** 2026-06-07
- **Universum:** S&P 500 e-mini Future (ES), echte 1-Minuten-Bars; Zielinstrument
  Micro E-mini S&P 500 (MES, intraday-Returns identisch zu ES).
- **Stichprobe:** 2010-06-07 .. 2026-06-05 — **4.048 RTH-Sessions, 5,5 Mio
  1-Minuten-Bars** (erstmals echte Intraday-Tiefe *und* echte Stichprobengröße).

Höchste Prioritäts-Hypothese des Prop-Edge-Frameworks (#1: Intraday-Index-
Mean-Reversion via Opening-Range-Fade).

## 1. Hypothese

Nach den ersten N Minuten der RTH-Session definiert die Opening Range (OR) das
Hoch/Tief. Der erste Ausbruch aus dieser Range überschießt (Liquiditätsabzug /
Überreaktion) und kehrt zurück → **Ausbruch faden** (Short bei Up-Break, Long bei
Down-Break), flat über Nacht. Profil: viele kleine Gewinne, glatte Kurve — das
prop-konforme Ziel.

## 2. Makro-Begründung

Am Open ist die Liquidität dünn; der erste Range-Ausbruch wird oft von Stop-Runs
und kurzfristigen Orderungleichgewichten getrieben, nicht von Information.
Liquiditätsanbieter, die den Ausbruch faden, werden für die Bereitstellung
bezahlt (Framework-Baustein #1). Ökonomisch plausibel — empirisch im liquiden
Index aber wegarbitriert.

## 3. Regeln (Look-Ahead-Schutz)

- RTH = 09:30–16:00 ET. OR = Hoch/Tief der ersten `N` Minuten (`N ∈ {5,15,30}`).
- Nach dem OR-Fenster: erster Bar mit `High ≥ OR_high` (Up-Break) bzw.
  `Low ≤ OR_low` (Down-Break) = Ausbruch.
- **Eintritt zum Open des NÄCHSTEN Bars** nach dem Ausbruch (look-ahead-sicher;
  die OR ist vor dem Ausbruch abgeschlossen, der Eintritt liegt strikt danach).
- Fade-Position = `−sign(Ausbruch)`. Exit nach festem Horizont `hold ∈
  {5,15,30,60 min, Session-Close}`. Flat über Nacht.

**Datenquelle:** Databento GLBX.MDP3, `ES.c.0` Continuous-Front-Month, Schema
`ohlcv-1m` (neuer Loader `quantlab.futures_intraday`, Parquet-Cache, Kosten-Guard).
Bars am Intervall-START gestempelt; RTH-Open (Volumen-Sprung 09:30) verifiziert.

## 4. Kosten- & Ausführungsannahmen

`MES_INTRADAY`-Preset: ~1,5 bps/Seite = **3 bps Round-Trip** (konservativ
gepolstert). Der Brutto-Edge muss diese 3 bps mit Sicherheitsmarge schlagen.

## 5. Ergebnisse (netto nach Kosten)

**Kein Edge — kein Horizont, kein OR-Fenster schlägt die Kosten.** Netto bps/Trade
des Fades über das ganze Gitter (siehe Heatmap `results/or_fade_grid.png`):

| OR \ hold | 5m | 15m | 30m | 60m | Close |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5 min | −2,9 | −2,3 | −2,6 | −3,0 | −5,2 |
| 15 min | −2,7 | −2,9 | −2,6 | −2,7 | −3,2 |
| 30 min | −2,8 | −2,9 | −2,7 | −2,7 | −2,6 |

Brutto-Edge durchweg ≈ 0 (Maximum +0,70 bps), **Trefferquote ~48–50 % (Münzwurf)**.
Die **Continuation** (Gegenrichtung) ist genauso tot (alle Zellen netto negativ).

Beste (am wenigsten schlechte) Zelle OR=5/hold=15m: brutto +0,70 bps, netto
−2,30 bps, **Sharpe(aktiv) −0,06**, Win 49 % → statistisch nicht von Null
unterscheidbar.

## 6. Robustheit — die ökonomisch begründete Verfeinerung scheitert ebenfalls

OR-**Breite** als Konditionierung (weiter Ausbruch = mehr Überreaktion → stärkere
Reversion; Breite ist vor dem Ausbruch bekannt, also look-ahead-sicher), Fade-Netto
nach Terzilen:

| Konfiguration | schmal | mittel | weit |
| --- | ---: | ---: | ---: |
| OR=5, hold=15m | −2,64 | −2,93 | −1,32 |
| OR=15, hold=30m | −2,08 | −2,59 | −3,22 |
| OR=30, hold=30m | −3,35 | −2,75 | −2,06 |

Kein Terzil schlägt die Kosten; das beste (OR=5 weit, −1,32 bps) verliert weiter
und ist bereits Multiple-Testing-Gebiet.

## 7. Verdict

**Abgelehnt am Kosten-Gate.** Der Opening-Range-Ausbruch hat auf dem liquiden
S&P-500-Future **keinen gerichteten Intraday-Edge** — Brutto ≈ 0, Win ~49 % über
4.048 Sessions, weder als Fade noch als Continuation, weder bei engen noch weiten
Ranges. Bei 3 bps MES-Kosten ist jede Variante netto negativ. **Dieselbe Wand wie
BTC 0012–0015 und Gap-Fade 0038:** auf einem liquiden, effizienten Markt ist der
gerichtete Intraday-Brutto-Edge ~0 und die Kosten sind die bindende Grenze — empirisch
exakt die Teil-7-Warnung des Frameworks (intraday sitzen die meisten/schnellsten
Gegner). Anders als 0038 ist hier **kein** Look-Ahead-Artefakt im Spiel: die Engine
ist sauber, das Signal ist schlicht leer.

**Wert:** Erstmals mit echter Intraday-Tiefe (5,5 Mio Bars) belegt, dass der
populärste Intraday-MR-Ansatz auf dem Index keine handelbare Richtung trägt. Die
Datenpipeline (`futures_intraday.py`) und das RTH-/OR-Gerüst stehen wiederverwendbar
für die nächste Hypothese. **Nächster Schritt:** Time-of-Day (#3, 1h-Daten bereits
da) und ES↔NQ-Lead-Lag (#5, relational/marktneutral) — Letzteres ist die
vielversprechendste verbleibende Klasse, weil es nicht auf einen gerichteten
Einzelmarkt-Edge angewiesen ist.
