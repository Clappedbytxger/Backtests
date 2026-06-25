> **Repo-Anker:** `src/quantlab/cross_sectional.py` — `momentum_signal()` und
> `run_cross_sectional()`. Hier wechselt die Perspektive von „ein Markt über die Zeit"
> zu „viele Märkte gegeneinander" — die Heimat von Statistical Arbitrage.

## 1. Querschnitt statt Zeitreihe

Bisher (Modul 5) hast du *eine* Reihe über die Zeit modelliert. Ein **Cross-Sectional**-
Ansatz dreht das um 90°: Zu jedem Zeitpunkt vergleichst du *viele* Assets **untereinander**
und fragst nicht „steigt der Markt?", sondern „**welche** Assets relativ zu den anderen?".

Das klassische Signal ist **12-1-Momentum**: der Return der letzten 12 Monate, **ohne** den
jüngsten Monat (der oft revertiert). Damit rankst du das Universum von „stärkste" bis
„schwächste" relative Performance.

## 2. Long/Short, dollar-neutral

Aus dem Ranking baust du ein **Long/Short-Portfolio**: das obere Quantil long, das untere
short. Der entscheidende Vorteil: Wenn du **gleich viel** long wie short bist, ist das
Portfolio **dollar-neutral** — die gemeinsame Marktbewegung (das Beta aus Modul 4) hebt sich
weg. Du verdienst an der *relativen* Performance, nicht an der Marktrichtung.

Die Gewichte innerhalb jedes Beins setzt du **invers zur Volatilität** (Modul 5): ruhige
Assets bekommen mehr Kapital, wilde weniger, damit kein Einzelwert das Risiko dominiert.
Probier es aus — sortiert nach Signal, grün long, rot short:

::viz CrossSecRanking

## 3. Die Falle: hoher IC ≠ PnL

Hier die wichtigste Lehre des ganzen Tracks (Katalog 0058). Die Vorhersagekraft eines
Signals misst man mit dem **Information Coefficient (IC)** — der (Rang-)Korrelation zwischen
Signal und realisiertem Return:

$\text{IC} = \text{corr}\big(\text{rank}(\text{Signal}_t),\; \text{Return}_{t+1}\big)$.

Ein hoher, stabiler IC sieht nach einem Edge aus. **Ist es aber nicht automatisch.** Im
Crypto-Querschnitt (0058) war der OOS-IC stark und ohne Decay (t = 11,7) — und das naive
Quintil-Portfolio verdiente trotzdem **weniger als der Markt**. Schieb oben die Kosten hoch:
Der IC bleibt **exakt gleich**, aber der Netto-PnL kippt ins Negative.

Warum? Drei Gründe, die der IC nicht sieht:

- **Turnover-Kosten:** Häufiges Rebalancing handelt das ganze Buch um; bei 56–78× Umschlag
  pro Jahr (0058) frisst die Kostenwand (Modul 13) den Edge.
- **Wo der IC sitzt:** Oft im **Short-Bein** — vorhersagbar blutende Small Caps, die retail
  kaum leerverkaufen kann.
- **Konzentration:** Ein hoher IC über viele Namen heißt nicht, dass ein konzentriertes
  handelbares Buch ihn monetarisiert.

## 4. Wie man die Lücke schließt

Die Hebel, die im Katalog (0059) den IC *doch* in PnL verwandelten — und jeder zählt als
Trial (Modul 2):

- **Liquiditäts-Floor** ($5 M Volumen) **vor** dem Ranking, nicht als Kostenstrafe danach.
- **Niedrigere Rebalance-Frequenz** (monatlich statt wöchentlich) → Turnover 22× → 6×.
- **Hold-Band-Buffer:** Ränge nur wechseln, wenn sie deutlich kippen (Hysterese) → weniger
  Umschlag bei gleichem Signal.

Mit diesen Hebeln drehte sich die Marktrelative von −0,56 auf +0,78 — **bei identischem
Signal**. Die Lücke IC → PnL war eine Konstruktions-/Kostenfrage, kein Signalproblem.

> **Payoff:** Du baust ein dollar-neutrales Rank-Portfolio, misst den IC korrekt und weißt,
> dass erst Liquiditäts-Floor, Frequenz und Buffer ihn in handelbaren PnL übersetzen.

**Nächstes Modul:** Ein Signal, das nicht aus Preis-Momentum kommt, sondern aus der
**Terminstruktur** selbst — Carry.
