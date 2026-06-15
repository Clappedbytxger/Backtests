# Strategie 0094 — Month-End FX-Rebalancing-Flow (WMR 4pm Fix)

> Batch-2-Idee **I0058** aus `D:\Backtest Ideas` (Quelle #s20: Melvin & Prins 2015,
> „Equity hedging and exchange rates at the London 4pm fix", J. Financial Markets; BIS).
> Hoch-Prio: gleicher Monatsend-Flow-Mechanismus wie Gewinner 0075, aber im FX-Universum.

- **Kategorie:** microstructure-flow / FX / Monatsend-Rebalancing
- **Status:** **abgelehnt** — Hedging-Flow-Richtung falsifiziert; Gegenrichtung nur schwaches Risk-on-Beta
- **Datum:** 2026-06-15
- **Universum:** 6E/6B/6J/6A/6C (CME-FX-Futures); Signal SPY vs EAFE (EFA) / währungs-spezifischer Index
- **Stichprobe:** 2001-2026, Sub-Split pre/post 2015

## 1. Hypothese (pre-registriert)

Real-Money-Hedger (Pensions/AM mit Hedge-Mandat) auf ausländischen Aktien passen ihre
USD-Hedges am Monatsende an. **Outperformen ausländische Aktien im Monat → ihr Fremdwährungs-
Exposure wächst → sie verkaufen Fremdwährung / kaufen USD am WMR-4pm-Fix** → vorhersehbarer
USD-Flow. Regel: `signal = foreign_monthret − US_monthret`; foreign outperformt → **short
FX-Future** (long USD). Position auf den letzten 2 Handelstagen, Exit erster Tag Folgemonat.

## 2. Ergebnis — die Richtung ist falsch

| Paar (EAFE-Signal) | Event-Ø (Hedge-Richtung) | Hedge net Sharpe / perm | Reverse net Sharpe / perm |
| --- | ---: | ---: | ---: |
| 6E (EUR) | −8,73 bps (t=−1,88, p=0,061) | −0,56 / p=0,95 | +0,09 / p=0,051 |
| 6B (GBP) | **−11,50 bps (t=−2,37, p=0,018)** | −0,60 / p=0,96 | +0,17 / p=0,019 |
| 6J (JPY) | −2,45 bps (p=0,64) | −0,18 / p=0,48 | −0,22 / p=0,54 |
| 6A (AUD) | −9,99 bps (p=0,083) | −0,44 / p=0,93 | +0,07 / p=0,141 |
| 6C (CAD) | −7,56 bps (p=0,085) | −0,55 / p=0,93 | +0,08 / p=0,044 |

**Die pre-registrierte Hedging-Richtung verliert systematisch** (alle net Sharpe negativ,
Permutation p≈0,93-0,96 = schlechter als 95 % zufälliger Timings). Das **Vorzeichen ist
durchgängig umgekehrt**: ausländische Aktien-Outperformance fällt mit **Aufwertung der
Fremdwährung** am Monatsende zusammen (6E/6B steigen) — das Gegenteil des USD-Kauf-Flows.
G3-Korb (EUR/GBP/JPY) net Sharpe −0,57.

## 3. Warum — Intraday-Effekt × Risk-on-Beta

1. **Der WMR-Flow ist ein INTRADAY-Effekt** (konzentriert in den Minuten um 16:00 London).
   Tages-Close-to-Close-Futures fangen das Fixing-Fenster nicht und werden vom dominanten
   **Risk-on-Zusammenhang** überlagert: steigt der ausländische Aktienmarkt, fließt Kapital
   in das Land → Währung wertet auf (Equity-FX-Momentum). Dieser Beta-Effekt läuft GENAU
   GEGEN den Hedging-Flow und ist auf Tagesbasis größer.
2. Die **Gegenrichtung** (Momentum) ist zwar in-sample schwach signifikant (6B perm p=0,019,
   Boot-KI ohne 0), aber **net Sharpe nur ~0,1-0,17** = kosten-marginal, und sie ist das
   FALSCHE Vorzeichen gegenüber der Hypothese. Die Richtung umzudrehen, um Signifikanz zu
   behaupten, ist In-Sample-Fitting (Lehre 0047: negatives Vorzeichen ist ein Hinweis, kein
   Refit-Anlass). Währungs-spezifische Signale (ccy) sind durchgängig tot.

## 4. Verdict

**Abgelehnt.** Der Melvin-Prins-Hedging-Flow ist auf täglichen FX-Futures **nicht
handelbar** — er ist ein Intraday-Fixing-Phänomen, und auf Tagesbasis dominiert der
gegenläufige Equity-FX-Risk-on-Zusammenhang, sodass das pre-registrierte Signal sogar
kontraproduktiv ist. Die Gegenrichtung ist nur schwaches Momentum-Beta (net Sharpe ~0,1),
kein Lead.

**Lehre:** Ein Top-Journal-Mikrostruktur-Effekt mit **Intraday-Fixing-Mechanik** braucht
Intraday-Daten am Fixing-Fenster — Tages-Close-Daten messen den falschen Zeitraum und werden
vom Beta überlagert (verwandt 0049/0058: Paper-Name + Flow-Story ≠ handelbar auf unseren
Daten/Frequenz). Der lebende Monatsend-Flow bleibt im Rates-Segment (0075), nicht in FX.
Offener Pfad: Dukascopy-FX-Tick um 16:00 London (wie 0070-GBP), niedrige Prior.
