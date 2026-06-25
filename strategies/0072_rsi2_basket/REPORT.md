# Strategie 0072 — RSI(2) Broad-Basket + Deployment + VIX-Tail-Control

- **Kategorie:** mean-reversion / swing / daily / multi-asset
- **Status:** **abgelehnt für CTI** (Edge real, aber CAGR zu niedrig + Crash-Tail) —
  Funded-Iteration von 0071
- **Datum:** 2026-06-14
- **Universum:** 17 ETFs (SPY/QQQ/DIA/IWM + 9 Sektoren + EFA/EEM + GLD/TLT), 2004–2026

## Idee
0071 (RSI-2) hatte den echten Edge + Win-Rate, scheiterte an CTI (CAGR 3 %, worst
day −6,7 %). Drei Fixes: (1) breiter Korb, (2) Kapital auf aktive Signale verteilen
(f=0,15/Sleeve, total gecappt) statt 1/N, (3) VIX-Regime-Filter gegen den Tail.

## Ergebnisse
| Variante | CAGR | Sharpe | MaxDD | worstD | Win% | avgDeploy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1/N-Baseline | +2,6 % | 0,16 | −10,2 % | −4,5 % | 72 % | 11 % |
| **Deploy f=0,15 cap100 (beste)** | **+4,6 %** | **0,37** | −16,9 % | −6,3 % | 72 % | 24 % |
| + VIX-entry<30 | +4,0 % | 0,31 | −16,9 % | −6,3 % | 71 % | 23 % |
| + VIX cap80 e<30 x>40 | +2,9 % | 0,18 | −14,6 % | −5,0 % | 71 % | 21 % |
| + Stop 8 % | +2,5 % | 0,12 | −14,1 % | −3,7 % | 71 % | 19 % |

Batterie (beste): Permutation p=0,38, **DSR 0,956**, t-p 0,002, IS/OOS 0,40/0,35
→ Edge statistisch real und robust.

## Verdict
**Breiter Korb HALF** (Sharpe 0,21→0,37, CAGR 3→4,6 %), aber **CTI-Gate nicht
bestanden:** auf 7 % DD gesized +1,9 %/J → 10 %-Ziel ~64 Monate. Zwei RSI-2-inhärente
Blocker: (1) **Ø nur 24 % Exposure** (Dips feuern selten gleichzeitig genug) → CAGR
strukturell niedrig; (2) **Crash-Dip-Tail** (worst day −6,3 %; VIX-Filter fängt
schnelle Crashs aus niedrigem VIX kaum, Stop senkt Tail aber killt Rendite).

**Lehre: hohe Win-Rate (72 %) ≠ fundbare Strategie.** Der kanonische High-Win-MR-
Ansatz ist ein echter, aber niedrig-rentierlicher Edge mit Fat-Tail — ungeeignet
für CTIs „10 % schnell bei <10 % DD". Deckt sich mit dem Prop-Programm 0038–0041:
das glatte-hochfrequente-niedrig-DD-Profil ist real selten. **Kein weiteres
RSI-2-Tweaking (Gate-Shopping).** RSI-2 taugt als ungefährliches Low-Risk-Sleeve
(blowt nie auf), nicht als Challenge-Passer.
