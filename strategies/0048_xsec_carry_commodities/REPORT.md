# Strategie 0048 — Cross-Sectional Commodity Carry (Terminstruktur)

- **Kategorie:** cross-sectional / carry (relative-value)
- **Status:** abgelehnt (schwach; IS→OOS-Kollaps)
- **Datum:** 2026-06-09
- **Universum:** 17 liquide CME/NYMEX/COMEX/CBOT-Rohstoffe (WTI-Rohöl, Erdgas,
  Heizöl, Benzin, Gold, Silber, Kupfer, Platin, Palladium, Mais, Weizen,
  Sojabohnen, Sojaöl, Sojamehl, Lebendrind, Mastrind, Mageschwein) — keine
  ICE-Softs (anderes Dataset)
- **Stichprobe:** In-Sample 2010-06 – 2018-05 / Out-of-Sample 2018-06 – 2026-06

## 1. Hypothese

Ranke die Rohstoffe monatlich nach **Roll-Yield** (Front- vs. 2.-Kontrakt):
long die Backwardation-Märkte (Front > 2., ein Long verdient den Roll die Kurve
hinauf), short die Contango-Märkte. Dollar-neutral. Der Edge ist relativ und
**strukturell** — der nächste Schritt aus 0047, wo das negative Momentum-Vorzeichen
auf eine Carry/Reversion-Story zeigte.

## 2. Makro-Begründung

Commodity Carry ist einer der persistentesten dokumentierten Faktoren
(Koijen/Moskowitz/Pedersen/Vrugt 2018 „Carry"; Gorton/Rouwenhorst). Anders als
Momentum ist er **strukturell, nicht behavioral**: Backwardation spiegelt knappe
Lagerbestände / Convenience Yield (Verbraucher zahlen für prompte Lieferung),
also ist die Prämie eine Lagerrisiko-Kompensation, die nicht wegarbitragiert
wird. Das war die a-priori stärkste der cross-sektionalen Hypothesen.

## 3. Regeln

- **Signal:** `carry = log(Front / 2. Kontrakt)`, annualisiert je Markt über den
  nominalen Kontrakt-Abstand (Energie ~1 Monat … PGM ~3 Monate), damit Märkte mit
  unterschiedlichem Kurven-Abstand vergleichbar ranken.
- **Rebalancing:** letzter Handelstag jedes Monats.
- **Gewichte:** Top-Quartil (Backwardation) long, Bottom-Quartil (Contango) short,
  gleichgewichtet, Gross 2.0 / Netto 0.0.
- **Look-Ahead-Schutz:** Signal am Monatsend-Close; Engine forward-fillt + shiftet.
- **Roll-Schutz (entscheidend):** Returns kommen aus einer **back-adjusteten**
  Front-Reihe. Der Roll-Tag wird exakt aus dem `instrument_id`-Wechsel erkannt und
  der Stitch-Gap genullt (die graduelle Intra-Kontrakt-Konvergenz = der echte
  Carry bleibt erhalten, nur der fiktive Sprung verschwindet).

## 4. Kosten- & Ausführungsannahmen

6 bps pro Seite (12 bps Round-Trip) auf den Umschlag bei jedem Rebalancing —
gemischter Wert für ein liquides Rohstoff-Futures-Buch.

## 5. Ergebnisse (Out-of-Sample, netto nach Kosten)

| Kennzahl                  | naiv (Artefakt) | **roll-korrigiert** |
| ------------------------- | --------------: | ------------------: |
| Sharpe FULL               | −1.32           | **−0.12**           |
| Sharpe **IS** (2010–2018) | −1.11           | **+0.31**           |
| Sharpe **OOS** (2018–2026)| −1.57           | **−0.40**           |
| CAGR OOS                  | −40.2 %         | −11.7 %             |
| Benchmark EW Long-Only OOS Sharpe | —       | **+0.56**           |

## 6. Signifikanz (OOS, netto, roll-korrigiert)

| Test                                | Wert |
| ----------------------------------- | ---: |
| Permutationstest (Rank-Shuffle) p   | 0.774 |
| Bootstrap Sharpe 95 %-KI            | [−1.03, +0.26] |
| Deflated Sharpe (N=8)               | 0.006 |
| t-Test mittlere Tagesrendite        | t=−1.02, p=0.309 |

Kein Test zeigt Signal; das KI umschließt die Null. Kein handelbarer Edge.

## 7. Robustheit

OOS-Sharpe über das Gitter (Quantil × Rebalancing × Annualisierung): alle 8 Zellen
zwischen −0.01 und −0.46 — **keine positive Zelle**. Mittlerer annualisierter Carry
je Markt ist dagegen ökonomisch sinnvoll (Benzin +6.5 %, Sojamehl +5.2 %,
Heizöl +4.0 % in Backwardation; Erdgas −24.7 %, Weizen −13.0 %, Mageschwein −7.6 %
in tiefem Contango) — die *Signal-Ökonomik* stimmt, die *Strategie-PnL* trägt nicht.

## 8. Roll-Artefakt — die methodische Kern-Lehre

Der naive Test (`Front.pct_change()`) gab OOS-Sharpe **−1.57**, t-Test p=0.000
*negativ*, Permutation p=1.000 — scheinbar ein katastrophal invertierter Faktor.
**Es war ein Roll-Artefakt (Lehre 0028/0029), diesmal vor jedem Report gefangen:**
Databentos `.c.0`-Continuous ist *nicht* back-adjusted, also bucht `pct_change`
den Roll-Sprung mit. Zerlegung: an Roll-Tagen verlor das Buch **−39 bps/Tag**, an
Nicht-Roll-Tagen nur −1.1 bps. Bei tiefem Contango (Erdgas) springt die Reihe an
jedem Monatsroll nach oben; die Strategie shortet Contango und frisst den Sprung —
den ein echter Roller nie zahlt. Korrektur via exaktem `instrument_id`-Roll-Tag +
Gap-Nullung hob OOS von −1.57 auf −0.40.

## 9. Verdict

**Abgelehnt.** Roll-korrigiert ist Commodity Carry auf dieser 17-Markt-CME-Palette
2010–2026 **kein handelbarer Edge**: IS mild positiv (+0.31), OOS negativ (−0.40),
insgesamt insignifikant — das IS→OOS-Kollaps-Muster (wie Nasdaq 0017, Zucker 0034),
konsistent mit Faktor-Zerfall/Crowding im selben 2010er-Jahrzehnt, das auch das
Momentum (0047) tötete.

**Zwei bleibende Gewinne:**

1. **Roll-korrekte Terminstruktur-Infrastruktur** (`quantlab.futures_curve` +
   `roll_adjusted_front_panel` via `instrument_id`) — wiederverwendbar für jede
   künftige Futures-Carry-/Spread-Arbeit. Die ~$1.56 Databento-Daten liegen
   gecached.
2. **Die Roll-Disziplin trägt auch auf bezahlten Daten.** Der naive Carry sah aus
   wie ein starker (negativer) Faktor und wäre ohne die Roll-Korrektur grob
   fehlinterpretiert worden. Genau das Muster, das 0028 als Lead vortäuschte.

**Offen:** Der echte Koijen-Carry nutzt die *volle* Kurve (mehr Kontrakte) statt
nur Front/2. — eine mögliche Verfeinerung. Aber nach Momentum (0047) und Carry
(0048) ist die naheliegende cross-sektionale Rohstoff-Klasse 2010–2026 erschöpft;
beide Faktoren sind in diesem Jahrzehnt zerfallen.
