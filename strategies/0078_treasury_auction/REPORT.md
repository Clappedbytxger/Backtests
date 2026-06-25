# Strategie 0078 — Treasury Auction Concession (Pre-Auktions-Short)

> Idee **I0009** aus dem Handoff `D:\Backtest Ideas` (Quelle #s03/#s18: Sigaux ECB
> WP2208, Somogyi FRBSF).

- **Kategorie:** event-driven / rates / Marktstruktur (Auktionszyklus)
- **Status:** testing (Lead am langen Ende — 30y/TLT; 10y zu klein)
- **Datum:** 2026-06-15
- **Universum:** 30-jährige US-Bonds (TLT ETF, ZB=F Future); 10y (IEF/ZN=F) als Vergleich
- **Stichprobe:** 2002-2026 (TLT/IEF), IS 2002-2013 / OOS 2014-2026

## 1. Hypothese

Vor US-Treasury-Auktionen fallen die Sekundärmarktpreise vorhersehbar (Primary
Dealer fordern eine Preis-Concession, um das Angebot zu absorbieren — „inverted V"),
danach Erholung. Short das laufzeitgleiche Instrument in den ~5 Tagen vor der Auktion.

## 2. Makro-Begründung

Liquiditätszwang/Marktstruktur: Dealer brauchen eine Concession zur Absorption; die
Auktionstermine sind vorab bekannt (announced ~T-7). #s18: Drift erklärt durch
Dealer-Meeting (~5 Geschäftstage vor) + Größenankündigung (2-4 Tage vor); Magnitude
**klein am 10y (~2,4 bps), größer am langen Ende** → Kosten binden den 10y-Outright.

## 3. Regeln & Daten

- Auktionskalender: TreasuryDirect-API (gratis, kein Key; 270 10y-Note- + 217 30y-Bond-
  Auktionen seit 2000, inkl. Reopenings). Lokal gecacht in `results/auctions_*.json`.
- Signal: **−1 (short) an den Tagen [T−5 … T−1] vor jeder Auktion**, sonst flat.
  Event-Study zusätzlich für [T0 … T+2] (Reversal). Look-ahead-sicher (Termine vorab
  bekannt; Engine shiftet T+1).
- Kosten: `IBKR_LIQUID_ETF` (TLT, 2 bps) / `IBKR_FUTURES` (ZB, 2 bps).

## 4. Ergebnisse (Event-Study + Pre-Window-Short)

| Markt | Pre [T−5..T−1] | Post [T0..T+2] | Short Sharpe (netto) | Permutation |
| --- | ---: | ---: | ---: | ---: |
| **TLT (30y)** | **−28,8 bps (p=0,033)** | +4,2 bps | **+0,44** | **p=0,000** |
| ZB=F (30y Fut) | −10,9 bps (p=0,27) | +3,1 bps | +0,20 | p=0,030 |
| IEF (10y) | −5,9 bps (p=0,29) | +9,3 bps (p=0,037) | −0,10 | p=0,026 |
| ZN=F (10y Fut) | −2,6 bps (p=0,58) | +6,2 bps (p=0,11) | −0,23 | p=0,52 |

**TLT-Tagespfad (sauberes Inverted-V):** T−4 −9,0 / T−3 −11,7 / T−2 −5,3 / T−1 −3,0 →
T+1 +6,1 / T+2 +2,2 bps. Genau die Concession-These: Preis fällt in die Auktion, erholt
sich danach.

## 5. Robustheit (TLT-Short)

| Periode | netto Sharpe | CAGR |
| --- | ---: | ---: |
| IS 2002-2013 | +0,38 | +2,0 % |
| OOS 2014-2026 | +0,37 | +2,5 % |
| ex-2022 | +0,33 | +2,0 % |

**Kein IS→OOS-Kollaps, kein 2022-Crash-Artefakt** (ex-2022 praktisch unverändert).
Die Permutation (p=0,000, Short-Timing vs Zufalls-Short gleicher Anzahl) kontrolliert
die generelle Short-Bond-Rentabilität — der Pre-Auktions-Short schlägt zufälliges
Shorten deutlich. ZB=F (Future, roll-behaftet) bestätigt die Richtung schwächer; TLT
(roll-frei) ist der saubere, robuste Read → der Roll-Vorbehalt (0028/0029) ist adressiert.

## 6. Signifikanz

| Test | Wert (TLT) |
| --- | ---: |
| Permutation Short-Sharpe | **p = 0,000** |
| Pre-Window-Mean t-Test | t = −2,15, p = 0,033 |
| Bootstrap Pre-Mean 95%-KI | siehe metrics.json |

## 7. Verdict

**Testing / Lead am LANGEN Ende — die Auction-Concession ist real und handelbar bei
30y/TLT, NICHT beim 10y.** Genau wie #s18 vorhersagt: der 10y-Effekt (~2,6 bps) ist
korrekt vorzeichenrichtig, aber zu klein und kosten-gefressen (net Sharpe negativ); der
30y-Effekt ist groß (−28,8 bps Concession), signifikant (perm p=0,000), IS/OOS-stabil
und kein 2022-Artefakt.

**Einsatz:** Short TLT (oder 30y-Bond-Future) in den 5 Tagen vor jeder 30y-Auktion
(~9-12×/Jahr, 5-Tage-Hold), netto Sharpe ~0,37 / CAGR ~2,2 %. Kleine Absolutgröße →
Overlay-/Timing-Bein. **Besonders wertvoll: es ist ein SHORT-Duration-Bet und damit
unkorreliert/gegenläufig zum Long-Duration-EOM-Bein 0075** — die beiden Rates-Beine
ergänzen sich (lange am Monatsende, short vor 30y-Auktionen; überlappen selten).

**Offene Punkte:** (1) RV 10y-vs-30y (IEF−TLT) war NICHT duration-gematcht (TLT ~3×
Duration) → +18,8 bps/p=0,011 ist von allgemeinen Ratenmoves dominiert, nicht
interpretierbar; ein sauberer Curve-Trade bräuchte duration-neutrale Gewichte. (2)
Post-Auktions-Reversal nur beim 10y/IEF signifikant (+9,3 bps, p=0,037) — als separates
Long-Bein denkbar. (3) Live-Forward + Bid-to-Cover-Conditioning (#s18) offen.
