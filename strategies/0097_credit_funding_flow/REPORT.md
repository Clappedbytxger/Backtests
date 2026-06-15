# Strategie 0097 — Month-End Credit-ETF-Flow (I0059) + Turn-of-Quarter-Funding (I0057)

> Batch-2-Ideen aus `D:\Backtest Ideas` (#s10 / #s23). Beide erweitern den lebenden
> 0075-Monatsend-/Quartalsend-Flow auf neue Instrumente (Credit bzw. Front-End-Funding).

- **Kategorie:** microstructure-flow / Credit + Geldmarkt
- **Status:** **beide abgelehnt** — I0059 = nur der 0075-Rates-Flow; I0057-Spike real, aber nicht handelbar
- **Datum:** 2026-06-15
- **Daten:** yfinance (LQD/HYG/JNK/VCIT/IEF/SHY/ZT=F) + FRED (SOFR/EFFR). Alles gratis.

## 1. I0059 — Month-End Credit-ETF-Flow (die Isolations-Frage)

Long LQD/HYG über das Monatsende (letzte 2 Handelstage). **Entscheidender Kontroll-Test:**
der EXCESS-Return über ein duration-Proxy (IEF) — nur er isoliert einen echten *Credit*-Flow
vom bereits bekannten 0075-*Rates*-Flow.

| ETF | RAW Monatsend | RAW perm p | **EXCESS über IEF** | EXCESS p | Boot-95%-KI |
| --- | ---: | ---: | ---: | ---: | --- |
| LQD (IG) | +15,94 bps (p=0,003) | 0,003 | **+6,15 bps** | **0,202** | [−2,0; +16,9] |
| HYG (HY) | +11,25 bps (p=0,087) | 0,169 | +1,01 bps | 0,904 | [−14,7; +18,2] |
| JNK (HY) | +11,98 bps (p=0,038) | 0,159 | +2,02 bps | 0,799 | [−13,2; +17,5] |
| VCIT (IG) | +12,07 bps (p=0,001) | 0,013 | +3,60 bps | 0,134 | [−1,2; +8,2] |

**Befund:** Der RAW-Monatsend-Effekt ist bei den IG-ETFs signifikant (LQD perm p=0,003) — aber
**er verschwindet im Excess über IEF** (alle p>0,13, alle Boot-KI berühren die 0). D. h. die
Monatsend-Rendite der Credit-ETFs ist **schlicht der 0075-Duration-Flow**, durch die
Zinskomponente der Corporates gemessen — **kein eigenständiger Credit-spezifischer Flow.**
HY (HYG/JNK, kurze Duration) zeigt entsprechend kaum RAW-Effekt und null Excess.

**Verdict I0059: abgelehnt** — redundant zu 0075 (genau das vom Idee-Text befürchtete
Beta-Konfunding). Long-Credit über das Monatsende = Long-Duration über das Monatsende.

## 2. I0057 — Turn-of-Quarter-Funding-Squeeze (Front-End)

**(a) Der Funding-Spike ist REAL** (FRED, 2018+): SOFR−EFFR-Basis am Quartalsultimo
**+6,79 bp vs +(−0,34) bp** an Normaltagen. Das Window-Dressing der Dealer (Basel-/G-SIB-
Leverage-Stichtage) erzeugt die dokumentierte Repo-Spitze über das Quartalsende.

**(b) Der Spike ist aber nicht über Front-End-Futures handelbar:**

| Instrument | Quartalsende-Long | t / p | Netto-Sharpe |
| --- | ---: | ---: | ---: |
| SHY (1-3y) | +1,68 bps | t=1,20 / 0,233 | −0,51 (kosten-gefressen) |
| ZT=F (2y) | −11,83 bps | t=−4,74 / 0,000 | −1,24 |

**Befund:** SHY ist insignifikant und netto kosten-gefressen (Geldmarkt-Magnituden, exakt der
Idee-Caveat „Kostenwand im Geldmarkt"). Der große, „signifikante" ZT-Wert (−11,8 bps) ist
**kein Funding-Signal**, sondern **Zins-Drift-Konfunding** — ein 1-2-Tage-Repo-Spike ist
Basispunkte wert, keine 12 bps auf einer 2y-Note; das Sampling fängt die 2022-Zinswende an
Quartalsenden ein (kein Drift-kontrollierter Permutationstest interpretierbar). Der Spike lebt
im **Repo/SOFR**, nicht im handelbaren 2y-Future-Preis.

**Verdict I0057: abgelehnt** — der Squeeze ist real, aber ein Geldmarkt-/Repo-Phänomen; das
handelbare Front-End-Instrument (SOFR-Future) hat zu kurze Historie (ab 2018) und der Effekt
ist sub-Kostenwand. Kein Aktien-/Future-Preis-Edge.

## 3. Gesamt-Verdict

Beide abgelehnt. **Wichtige Bestätigung der Batch-1-Meta-Lehre:** der lebende Monatsend-Flow
ist **spezifisch der Treasury-Duration-Kanal (0075)** — er generalisiert NICHT auf Credit
(dort nur als verkapptes Duration-Beta) und NICHT auf das Front-End-Funding (dort real, aber
im Repo gefangen, nicht im handelbaren Future). Der Flow trägt nur dort, wo er groß und im
liquiden Instrument direkt abgreifbar ist (langes Treasury-Ende).
