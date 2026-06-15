# Strategie 0095 — 2s5s10s-Butterfly-MR (I0062) + Mid-Month-Reinvestment (I0056)

> Batch-2-Ideen aus `D:\Backtest Ideas`: **I0062** (Hoch-Prio, #s23 Curve-Butterfly-RV)
> + **I0056** (#s03 Mid-Month-Coupon/Reinvestment-Flow). Beide verankert an den lebenden
> Familien (0087 RV-MR, 0075 Rates-Flow).

- **Kategorie:** rates / RV-Mean-Reversion (I0062, markt-neutral) bzw. Monatsmitte-Flow (I0056)
- **Status:** **abgelehnt** — I0062 echtes neutrales Mikro-Signal aber sub-cost; I0056 insignifikant
- **Datum:** 2026-06-15
- **Daten:** FRED (DGS2/DGS5/DGS10) für die Fly; yfinance (IEF/TLT) für Mid-Month. Alles gratis.

## 1. I0062 — 2s5s10s-Butterfly-Mean-Reversion

**Konstruktion:** 50-50-Fly `fly_yield = y5 − 0,5·(y2 + y10)` (DV01-neutral → level- &
slope-neutral). z-Score über 60 Tage; Entry |z|>2 (MR), Exit z→0, Stop |z|>3,5. Long-Fly
(long Bauch / short Flügel) profitiert, wenn `fly_yield` fällt. P&L aus FRED-Yield-Changes ×
DV01, Kosten je Round-Trip modelliert.

**Ergebnis (Basis win60/z2):**

| Metrik | Wert |
| --- | ---: |
| Brutto-Sharpe | **+0,34** |
| Permutation (Timing vs Zufall) | **p = 0,000** |
| Beta zu Level (Δy10) | **−0,000** |
| Beta zu Slope (Δ2s10s) | **+0,000** |
| IS / OOS / ex-2022 (netto@2bp) | −0,73 / −0,73 / −0,71 |

**Kosten-Sensitivität (entscheidend):**

| Kosten/RT | 0,0 bp | 0,5 bp | 1,0 bp | 1,5 bp | 2,0 bp |
| --- | ---: | ---: | ---: | ---: | ---: |
| Netto-Sharpe | +0,34 | +0,07 | −0,20 | −0,47 | −0,73 |

**Befund:** Der Butterfly ist die **sauberste Markt-Neutralität im Katalog** (Beta zu Level
UND Slope exakt 0,000 — per Konstruktion) und das **Timing schlägt Zufall hochsignifikant**
(perm p=0,000). Aber: **Brutto-Sharpe nur 0,34** und der **Breakeven liegt bei ~0,5 bp/RT.**
Ein 2s5s10s-Fly ist ein **4-Bein-Trade** (ZT, 2× ZF, ZN) — realistisch ≥1 bp/RT → netto
negativ. Das ist die **0041-Klasse: echtes, statistisch reales, markt-neutrales RV-Signal,
das unter der Kostenwand liegt** (wie der ES-NQ-RV-Spread). 9-Zellen-Robustheitsgitter
(win 40/60/90 × z 1,5/2,0/2,5): netto alle negativ [−1,21; −0,46].

**Verdict I0062: abgelehnt als Standalone — real aber sub-cost.** Nur mit Maker-/HFT-
Ausführung (sub-0,5 bp) handelbar, was für ein Retail-/Prop-Konto außer Reichweite ist
(gleiche Schlussfolgerung wie 0041). Der Mechanismus (Flow-Dislokation am Kurven-Bauch
kehrt zurück) ist **echt** — er trägt nur zu wenig Brutto-Edge, um 4 Beine zu bezahlen.

## 2. I0056 — Mid-Month-Reinvestment-Flow (um den 15.)

Long IEF/TLT im Fenster [Tag 14–16], **unter Ausschluss der letzten 2 Monatstage** (damit
0075 nicht doppelt zählt). Permutation gegen zufällige Mid-Month-Blöcke.

| Markt | Fenster-Ø | t / p | Netto-Sharpe | perm p | Boot-95%-KI | n |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| IEF (10y) | +6,12 bps | t=1,69 / 0,092 | +0,04 | 0,226 | [−0,9; +13,4] | 276 |
| TLT (30y) | +11,99 bps | t=1,65 / 0,099 | +0,18 | 0,145 | [−2,2; +26,3] | 276 |

**Befund:** Richtung stimmt (positiv, langes Ende stärker — konsistent mit dem
Duration-Flow-Mechanismus von 0075), aber **kein Test erreicht Signifikanz**: t-p ~0,09-0,10,
Permutation p>0,14, **Boot-KI berührt überall die 0.** Genau wie die Idee selbst warnte: der
Mid-Month-Coupon-Flow ist **kleiner und diffuser** als das Monatsende. Reinvestment verteilt
sich über mehrere Settlement-Tage statt sich an einem Benchmark-Rebalancing-Stichtag zu
konzentrieren (anders als 0075).

**Verdict I0056: abgelehnt** — schwacher, insignifikanter Flow; kein Mehrwert über 0075.

## 3. Gesamt-Verdict

Beide abgelehnt, aber unterschiedlich lehrreich: **I0062 ist ein echtes, perfekt
markt-neutrales RV-Signal, das an der 4-Bein-Kostenwand stirbt** (sub-cost, 0041-Klasse);
**I0056 ist ein richtungsrichtiger, aber zu schwacher/diffuser Flow** (Monatsmitte < Monatsende).
Bestätigt die Batch-1-Meta-Lehre: nur der **konzentrierte** Monatsend-Stichtag (0075) und die
**großmagnitude** 30y-Concession (0078) tragen; die feineren Verwandten (Kurven-Bauch-RV,
Monatsmitte) sind real, aber zu klein für die Kostenwand.
