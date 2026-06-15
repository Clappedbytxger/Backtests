# Strategie 0098 — VIX-Roll-Down-Carry slope-gated (I0064) + Cross-Asset-VRP (I0065)

> Batch-2-Ideen aus `D:\Backtest Ideas` (#s24). Beide erweitern die bestätigte VRP-Familie
> **0054/0056** (Short-Vol-Carry, echter Edge, aber tail-gefährlich).

- **Kategorie:** carry-term-structure / Volatilität
- **Status:** **I0064 = nützliche Refinement/Overlay (positiv)**; **I0065 = abgelehnt** (Blocker + schädliches Signal)
- **Datum:** 2026-06-15
- **Daten:** yfinance (^VIX/^VIX3M/VIXY/^MOVE/^GVZ/^OVX/^EVZ + SPY/GLD/USO/FXE). Alles gratis.

## 1. I0064 — Slope-gated Contango-Harvest (das positive Ergebnis)

Short VIXY (= Short-Vol) **nur bei steilem Contango** (VIX3M/VIX > Schwelle, PIT-geshiftet),
flat bei Backwardation. Hypothese: das Slope-Gate kappt den Short-Gamma-Crash-Tail (das
0056-Problem), ohne die Carry zu opfern. **Pflicht: Feb-2018 (Volmageddon) + Mär-2020 im Sample.**

| Variante | Sharpe | MaxDD | Worst-Day | Kurtosis | Zeit im Markt |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ungated (Short VIXY = 0054) | +0,60 | −92 % | −43,1 % | 9 | 100 % |
| **Gated (VIX3M/VIX > 1,05)** | **+0,59** | **−65 %** | **−33,6 %** | 8 | 81 % |

**Stress-Sub-Perioden (der eigentliche Wert):**

| Episode | Ungated Return | Gated Return | Ungated Worst-Day | Gated Worst-Day |
| --- | ---: | ---: | ---: | ---: |
| Feb-2018 | −47,5 % | **−16,0 %** | −34,2 % | −13,6 % |
| Mär-2020 | −83,3 % | **−9,5 %** | −39,1 % | −6,5 % |

**Befund:** Das Slope-Gate **erhält den Sharpe exakt** (0,60 → 0,59 — keine Carry geopfert)
und **kappt den Tail massiv** (MaxDD −92 % → −65 %; Mär-2020 −83 % → −9,5 %). Das Gate steht
genau in den Backwardation-Phasen beiseite, also in den Crashs. **Permutation p=0,38** — das
ist KEIN Widerspruch, sondern erwartet: der Permutationstest misst Sharpe, und ein zufälliges
81 %-Gate hätte denselben Sharpe; der Wert des Gates liegt im **Vermeiden der spezifischen
Backwardation-Crashs** (MaxDD/Worst-Day), nicht im Mittel. Genau das zeigt der Stress-Split.

**Verdict I0064: bestätigt als nützliches Tail-Control-Refinement der 0056-Sleeve.** Es ist
**kein neuer Standalone** (selbst gegated: MaxDD −65 %, Worst-Day −33,6 % — noch immer
short-vol-gefährlich), aber ein **komplementärer Hebel zu 0056**: 0056 = lineares Down-Sizing,
I0064 = Regime-Gate. Kombination (Gate × Down-Size) ist das beste Tail-Management. **Bestes
Batch-2-Ergebnis** — geht in die Overlay-/Refinement-Schiene (Roadmap Idee E), schärft 0056.

## 2. I0065 — Cross-Asset-VRP-Dispersion

Mittlere VRP (Implied − Realized, Vol-Punkte): **Öl 5,9 > Aktien 3,6 > Gold 2,5 > FX 1,0.**
Die VRP existiert also über Asset-Klassen (These bestätigt). Aber zwei Killer:

1. **Implementierungs-Blocker (Idee-flagged):** Nur Aktien-Vol ist retail handelbar
   (VIXY/SVXY). Bond-/FX-/Commodity-Short-Vol braucht Optionen — keine sauberen Short-Vol-ETPs.
2. **Das Ranking-Signal ist für das handelbare Bein SCHÄDLICH:** Wenn die Aktien-VRP klassen-
   übergreifend **#1 (am höchsten)** ist, hat Aktien-Short-Vol Sharpe **−1,90** — gegen **+1,56**,
   wenn sie NICHT #1 ist. Ökonomisch klar: hohe Aktien-VRP = elevierte Implied = Stress-Regime
   = genau wann Short-Vol blowt. „Short, wo VRP am reichsten" ist also kontraproduktiv für das
   einzige handelbare Bein.

**Verdict I0065: abgelehnt** — die Cross-Asset-VRP ist real als Signal, aber nicht handelbar
(nur Aktien retail-zugänglich) und das Dispersions-Ranking verschlechtert das Aktien-Bein.
Keine zugängliche Diversifikation der VRP-Familie.

## 3. Gesamt-Verdict

**I0064 ist die einzige Batch-2-Idee mit positivem Ergebnis** — ein bestätigtes Tail-Control-
Refinement, das die 0056-Short-Vol-Sleeve verbessert (Sharpe gehalten, MaxDD/Crash-Tail stark
reduziert) → Overlay-Schiene. **I0065 abgelehnt** (Implementierungs-Blocker + schädliches
Ranking). Bestätigt: die VRP-Familie lebt nur in **Equity-Vol**, und ihr bester Hebel ist
**Tail-Management** (Gate + Sizing), nicht Cross-Asset-Diversifikation.
