# Strategie 0093 — Post-Auction-Reversal (I0054) + Vol/Size-Sizing (I0055)

> Batch-2-Ideen **I0054 + I0055** aus `D:\Backtest Ideas` (Quelle #s21 Lou/Yan/Zhang
> 2013 JFE; #s03 Sigaux). Spiegel- bzw. Sizing-Bein des Gewinners **0078**.

- **Kategorie:** event-driven / rates / Auktions-Mikrostruktur
- **Status:** **abgelehnt** (beide) — Reversal IS-only & kosten-gefressen; Sizing-These hält nicht
- **Datum:** 2026-06-15
- **Universum:** IEF/ZN=F (10y), TLT/ZB=F (30y); Auktionskalender TreasuryDirect (0078-Cache)
- **Stichprobe:** 2000-2026, IS <2014 / OOS ≥2014

## 1. Hypothesen

- **I0054:** Die Pre-Auktions-Concession (0078: Preis fällt vor der Auktion) ist eine
  Liquiditätsprämie, kein Infoschock → sie **kehrt nach Zuteilung zurück**. Long das
  laufzeitgleiche Instrument am Auktionstag-Close (T0), Exit T+2. Anderer Tagesblock als
  das 0078-Short → potenziell unkorreliert/diversifizierend.
- **I0055:** Die Concession skaliert mit Dealer-Inventarrisiko → größer bei hoher Rate-Vol
  und großem Emissionsvolumen. Sizing-Overlay auf das 0078-Short (top-Vol-/top-Size-Tercil
  größer gewichten).

## 2. Ergebnisse I0054 (Post-Auktions-Long)

| Markt | Post [T0c..T+2c] | net Sharpe | perm p | IS/OOS | Boot-95%-KI |
| --- | ---: | ---: | ---: | ---: | --- |
| **IEF (10y)** | **+7,65 bps (p=0,046)** | +0,15 | 0,059 | **+0,48 / −0,13** | [+0,1; +15,2] |
| TLT (30y) | +8,13 bps (p=0,33) | +0,08 | 0,24 | +0,58 / −0,22 | [−7,6; +24,8] |
| ZN=F (10y) | +4,08 bps (p=0,22) | −0,06 | 0,13 | +0,20 / −0,31 | [−2,3; +10,6] |
| ZB=F (30y) | +3,86 bps (p=0,52) | −0,04 | 0,34 | +0,51 / −0,40 | [−7,3; +15,7] |

**Befund:** Das Reversal existiert nur am 10y (IEF, Event-Study p=0,046, Pfad sauber:
T0 +1,5 → T+1 +2,6 → T+2 +5,0 bps) — aber:
1. **netto kosten-gefressen** (Sharpe brutto +0,43 → netto +0,15; 5-Tage-Hold × Kosten),
2. **Permutation gegen Zufalls-Long verfehlt** (p=0,059 — das Timing schlägt zufälliges
   Long-Bond-Sein nicht klar; Drift-Trap-Lehre 0016/0050),
3. **harter IS→OOS-Kollaps** (+0,48 → −0,13), Boot-KI berührt fast die 0.

Anders als das 0078-Short (perm p=0,000, IS/OOS-stabil) ist das Long-Reversal **kein
eigenständiger, robuster Edge**. Es ist genau die in 0078 notierte „post-Reversal nur am
10y schwach signifikant"-Beobachtung — als handelbares Bein zerfällt sie.

## 3. Ergebnisse I0055 (Vol/Size-Sizing des 0078-Short)

Walk-forward-Tercile (Conditioning-Variable nur gegen vergangene Events gerankt, kein
Look-ahead), Ziel: Concession (30y-Short-PnL) hi-Tercil > lo-Tercil.

| Conditioning | hi-Tercil | lo-Tercil | Erwartung |
| --- | ---: | ---: | --- |
| Rate-Vol (21d) | +44,8 bps | +40,9 bps | hi > lo — **kaum (flach)** |
| Emissionsgröße | +21,6 bps | +56,9 bps | hi > lo — **FALSCH herum** |

**Befund:** Die mechanistische These hält **nicht**. Die Vol-Abstufung ist faktisch flach
(+44,8 vs +40,9, kein nutzbarer Hebel), und die Größen-Abstufung ist **invertiert** —
kleinere Auktionen hatten die *größere* Concession. Damit ist kein Sizing-Gewinn ableitbar;
das 0078-Short bleibt ungewichtet die beste Form. (Größen-Inversion vermutlich, weil große
Emissionen die liquidesten/best-absorbierten Benchmark-Auktionen sind.)

## 4. Verdict

**Beide abgelehnt.** Das einzige robuste Auktions-Bein bleibt der **0078-Pre-Auktions-Short
am 30y** (perm p=0,000, IS/OOS-stabil). I0054 (Long-Reversal) ist real nur am 10y, dort aber
IS-only, kosten-gefressen und schlägt Zufalls-Timing nicht (p=0,059). I0055 (Sizing) findet
keine verwertbare Vol-/Size-Abstufung (Größe sogar gegenläufig). **Kein Mehrwert über 0078;
das diversifizierende „zweite Tagesfenster" trägt nicht.**

**Lehre:** Der Concession-Mechanismus ist asymmetrisch — die *Short*-Seite (Aufbau der
Concession ins Angebot) ist der handelbare, robuste Teil; die *Reversal*-Seite ist zu klein
und zu verrauscht, um Kosten + Drift-Trap-Permutation zu überleben. Spiegelbeine eines
echten Edges sind nicht automatisch selbst Edges.
