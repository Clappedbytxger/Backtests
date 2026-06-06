# Strategie 0040 — Intraday Time-of-Day-Effekte (ES 1-Minute, NQ 1h Cross-Check)

- **Kategorie:** strukturell / intraday
- **Status:** abgelehnt
- **Datum:** 2026-06-07
- **Universum:** S&P 500 e-mini (ES) 1-Minute; Nasdaq-100 e-mini (NQ) 1h als
  unabhängiger Cross-Check. Zielinstrument MES/MNQ.
- **Stichprobe:** 2010-06-07 .. 2026-06-05, ~3.900–4.046 RTH-Sessions.

Prop-Edge-Framework-Hypothese #3 (strukturelle, wiederkehrende Intraday-Fluss-
Muster — zeitlich exakt definierbar, also testbar wie die Saisonfenster, nur täglich).

## 1. Hypothese

Wiederkehrende Tageszeit-Muster tragen eine handelbare Richtung: **Schluss-
Stunden-Drift** (Close-Auktion / MOC-Imbalance / Index-Rebalancing-Flows),
**Lunch-Reversion** (Vormittagsbewegung kehrt mittags um), **Morgen→Nachmittag-
Continuation**. Zeitlich fixiertes Fenster, flat über Nacht.

## 2. Makro-Begründung

Eröffnungsauktion, Lunch-Flaute und Schluss-Auktion erzeugen wiederkehrende
Liquiditäts-/Fluss-Muster; geplante Rebalancing- und MOC-Orders konzentrieren
sich in der Schlussphase. Plausibel — aber empirisch auf dem liquiden Index
nicht in handelbarer Stärke vorhanden.

## 3. Regeln (Look-Ahead-Schutz)

- RTH = 09:30–16:00 ET, Minuten-Index 0..389. Fenster-Rendite = Close(Ende) /
  Open(Start) − 1, ein Round-Trip/Tag, flat über Nacht.
- Konditionale Tests nutzen nur abgeschlossene frühere Fenster (z. B. Lunch-Trade
  auf `−sign(Morgen)`, Morgen ist vor dem Lunch abgeschlossen) → look-ahead-sicher.
- Daten: Databento GLBX.MDP3 (`ES.c.0` 1m, `NQ.c.0` 1h), `quantlab.futures_intraday`.

## 4. Kosten

`MES_INTRADAY`: 3 bps Round-Trip (konservativ). Ein Trade/Tag.

## 5. Ergebnisse (netto nach Kosten)

| Fenster | Mittel (bps) | Sharpe | Win% | Netto (bps) |
| --- | ---: | ---: | ---: | ---: |
| Erste 30m (9:30–10:00) | +0,59 | 0,32 | 50,7 | −2,41 |
| Vormittag (9:30–11:00) | +0,31 | 0,11 | 52,0 | −2,69 |
| Lunch (12:00–13:00) | +0,53 | 0,34 | 52,2 | −2,47 |
| **Letzte 60m (15:00–16:00)** | **+0,11** | **0,05** | 50,4 | −2,89 |
| **Letzte 30m (15:30–16:00)** | **−0,08** | −0,04 | 49,8 | −3,08 |
| **Letzte 15m (15:45–16:00)** | **−0,55** | −0,38 | 48,2 | −3,55 |
| Voll-RTH (9:30–16:00) | +2,82 | **0,55** | 54,4 | −0,18 |

**Konditional:** corr(Morgen, Lunch) = −0,06; corr(Morgen, Nachmittag) = +0,025
(beide ≈ 0). Lunch-Fade-Morgen netto −2,62 bps (Sharpe 0,24); Nachmittag-Follow-
Morgen netto −2,06 bps (Sharpe 0,27) — beide Münzwurf, keiner schlägt die Kosten.

**NQ-1h-Cross-Check:** die Schluss-Stunde ET 15:00 ist auf NQ **nicht besonders**
(Sharpe −0,06) — bestätigt unabhängig, dass keine Schluss-Drift existiert.

## 6. Drei Befunde, alle gegen die Hypothese

1. **Die „Schluss-Stunden-Drift" ist abwesend.** Letzte 60/30/15 Minuten tragen
   keine positive Drift (die letzten 15 min sind leicht negativ). Die ES-
   Intraday-Gewinne sind über die ganze Session verteilt (≈ linear, siehe linker
   Plot), nicht in die Schluss-Auktion konzentriert. Die bekannte Aktien-
   „Overnight-Anomalie" liegt über Nacht — und über Nacht sind wir prop-bedingt flat.
2. **Das einzige Fenster mit echtem Sharpe (Voll-RTH, 0,55) ist reines Long-Beta**
   (immer long die Session) und netto ~0 nach einem Round-Trip — kein Edge,
   sondern die Intraday-Risikoprämie, die gerade so die Kosten zahlt.
3. **Konditionale Struktur ist leer**: Intraday-Autokorrelation ≈ 0 (wie BTC 0015);
   weder Lunch-Reversion noch Morgen→Nachmittag funktionieren.

## 7. Verdict

**Abgelehnt.** Kein Tageszeit-Fenster hat eine gerichtete, kostenschlagende Kante;
die Prop-Folklore „letzte Stunde" und „Lunch-Reversion" überlebt auf ES 2010–2026
nicht. Wie 0039 ohne Look-Ahead — das Signal ist schlicht leer, und das einzige
mit Sharpe ist Beta. Bestätigt das Muster (0012–0015 / 0038 / 0039 / 0040): die
Intraday-**Richtung** eines einzelnen liquiden Markts ist netto nicht handelbar.
**Konsequenz:** verbleibende prop-taugliche Klasse = **relational/marktneutral**
(ES↔NQ-Lead-Lag, #5) — der nächste und letzte Test der Framework-Liste.
