# 0108 — CTI CORE-Buch, eingefrorene Live-Spezifikation

**Freeze-Datum:** 2026-06-19 · **Quelle:** 0106 CORE-Buch (`book_integration.py`,
Kombi-Sharpe 1,21, in-sample) · **Status:** eingefroren für Forward-Test auf IBKR Paper

> **Zweck des Freeze:** Diese Regeln + Parameter sind ab dem Freeze-Datum **unveränderlich**.
> Jede spätere Anpassung an den Regeln macht den Forward-Test ungültig (= wieder in-sample-Fitting).
> Der Git-Commit dieses Ordners ist der Zeitstempel. Out-of-Sample-Fenster = ab Freeze-Datum.
> Einzige zur Laufzeit erlaubte Stellschraube: das **Konto-Ziel-Vol** (Sizing), nicht die Logik.

## Ausführungs-Konvention (für alle Sleeves identisch)

- **Datenquelle Signale:** yfinance Tagesschluss (dieselben Ticker wie im Backtest).
- **Entscheidung:** nach dem **Tagesschluss** berechnet (Signal nutzt nur Daten bis Close[t]).
- **Ausführung:** Position wird zur **nächsten Session gehalten** (T+1, entspricht `.shift(1)`
  in jedem Sleeve-Code). Keine Intraday-Logik — reine End-of-Day-Strategie.
- **Broker (Forward-Test):** IBKR Paper, volles Buch, korrekte Sizing (kein Echtgeld).

---

## Sleeve 1 — I0092 Monatsend-FX-Flow

| | |
|---|---|
| Paare (Vorzeichen = long Fremdwährung ggü. USD) | EUR `EURUSD=X` +1 · JPY `USDJPY=X` −1 · AUD `AUDUSD=X` +1 · CHF `USDCHF=X` −1 |
| Signal | Monats-Relativperf. `EFA_monatsret − ^GSPC_monatsret` des **gerade abgeschlossenen** Monats (bekannt am letzten Handelstag/Close) |
| Richtung | `sign(Signal)`: US stark (Signal<0) → **short** Fremdwährungskorb; US schwach (>0) → long |
| Trade | Eintritt am **letzten Handelstag (LBD)** zum Close, Halten bis Close des **1. Handelstags** des Folgemonats; Korb = Mittel der 4 Paar-Returns × Richtung |
| Sizing | Quartalsende-Monate (Mär/Jun/Sep/Dez) **2×**, sonst 1× |
| Kosten | 1,6 bps Spread × Size |
| Frequenz | ~12 Events/Jahr |
| Normierung Stream | `scale_to_vol(0,10)` |

**Vorbehalt:** Close-Proxy (perm p=0,17) ist schwächer als das daten-deferte Fix-Window
(Dukascopy M15, perm p=0,0006). Richtungs-konsistent mit dem validierten I0075.

## Sleeve 2 — I0076 Index-RSI-2-Mean-Reversion (long-only)

| | |
|---|---|
| Indizes (1 Position/Index gleichzeitig) | US500 `^GSPC` · US30 `^DJI` · NAS100 `^NDX` · GER40 `^GDAXI` |
| Entry (am Close, ALLE Bedingungen) | `Close > SMA200` **und** `RSI(2) < 10` (Wilder) **und** `Close > 0,90·Close[t−5]` |
| Exit (am Close) | `RSI(2) > 65` **oder** `Close > SMA5` |
| Initial-Stop | `Entry − 2,5·ATR(14)` (intraday) |
| Zeit-Stop | 10 Handelstage |
| Kosten | 3 bps RT + 2 bps/Nacht Swap |

**Stream-Provenienz:** Buch nutzt `0103/results/streams/i0076_rsi2_ungated.parquet`;
Referenz-Implementierung `0102/e2_index_rsi2.py`. **Vor Engine-Bau verifizieren, dass der
Stream bit-genau diese Regeln erzeugt** (Provenienz-Check).

## Sleeve 3 — I0100 Risk-gegateter FX-Carry-Korb (long-only)

| | |
|---|---|
| Paare (alle long, +1) | `AUDJPY=X` `NZDJPY=X` `AUDCHF=X` `CADJPY=X` `EURJPY=X` |
| Korb | Gleichgewicht der long-ccy-Tagesreturns |
| Risk-Gate (auf `^VIX`) | `risk_on = (VIX < SMA50(VIX)) und (VIX < 25) und (VIX/VIX[t−5] < 1,3)`, dann `.shift(1)` |
| Position | risk_on → Korb halten; sonst **flat** |
| Carry-Accrual | **+1,3 %/Jahr** (`0,013/252` pro gehaltenem Tag) — real gemessener Netto-Swap |
| Kosten | 2,2 bps auf Turnover (bei Gate-Wechsel) |
| Normierung Stream | `scale_to_vol(0,10)` |

**Vorbehalt:** brandneuer Lead, **nie live**; Sharpe 1,06–1,24 ist in-sample → größter
Haircut-Kandidat. Gate fängt VIX-getriebene Crashes, NICHT FX-spezifische (SNB-2015-Typ).

## Sleeve 4 — I0099 Krypto-Vol/Trend-Gate (skaliert I0080)

| | |
|---|---|
| Basis | I0080-Krypto-TSMOM-Stream (siehe unten) |
| Gate (auf `BTC-USD`) | `trend_mult = 1,0 wenn Close>SMA200 sonst 0,4` · `vol_mult = 0,5 wenn rv>1,5 sonst 1,0`, `rv = std20(ret)/std100(ret)` |
| Multiplikator | `mult = trend_mult · vol_mult`, dann `.shift(1)` |
| Stream | `gated = I0080 · mult` (keine zusätzliche Vol-Normierung; Buch re-skaliert via Inverse-Vol) |

### Basis-Bein I0080 — Krypto-TSMOM (long-only)
| | |
|---|---|
| Coins (gleichgewichtet) | `BTC-USD` (ab 2015) · `ETH-USD` (ab 2017) |
| Signal je Coin | long wenn `Close > SMA100` **und** `Close − Close[t−90] > 0`; sonst flat |
| Gewicht | `w = (0,10 / sigma)`, `sigma = 20d-Realized-Vol × √252`; `.shift(1)` |
| Kosten | 10 bps/Seite Spread auf Turnover + 8 bps/Nacht Swap auf Brutto-Exposure |
| Variante | **long-only** (CTI-Krypto-Short-Financing ungünstig) |

---

## Buch-Konstruktion (Inverse-Vol / Equal-Risk)

1. Streams: `i0092_monthend_fx` (→10 % Vol), `i0076_rsi2_ungated`, `i0100_carry_riskgated`
   (→10 % Vol), `i0099_crypto_gated`.
2. Auf Datums-Union ausrichten ab dem Tag, an dem **alle 4** live sind; fehlende Tage = 0.
3. Gewichte: `w_i = (1/vol_i) / Σ(1/vol_j)`, `vol_i = std_i × √252`.
4. `book = Σ w_i · stream_i`.

**Eigenschaften (in-sample, …2026-06-17):** Kombi-Sharpe **1,21**, alle Kreuz-Korrelationen
~0 (max |0,06|), Equity-Beta-Gewicht **20 %** (nur I0076), Worst-Day @8 %-Vol −3,95 %.

## Live-Sizing (Forward-Test)

- **Ziel-Konto-Vol = 6 % p.a.** (konservativ; entspricht dem 1-Step-Sweet-Spot:
  in-sample P(pass) 0,72 / P(bust) 0,28, Worst-Day ~−3,0 %). **Einzige tunbare Größe.**
- Buch auf 6 % Jahres-Vol skalieren, dann Inverse-Vol-Gewichte je Sleeve in reale
  Instrument-Notionals übersetzen (Engine-Schritt).

## Was eingefroren ist

- **Unveränderlich:** alle Regeln, Parameter, Ticker, Kosten-Annahmen, Buch-Gewichtungsmethode.
- **Tunbar (nur Sizing):** Ziel-Konto-Vol (Default 6 %).
- **Erfolgs-Gate Forward-Test:** Live-Kombi-Sharpe ≥ ~0,9 über das Fenster (Haircut-Toleranz
  gegen die 1,21 in-sample) → erst dann CTI-Echtgeld.

## Offene Engineering-Punkte (nächste Schritte, NICHT Teil des Freeze)

1. Signal-Engine (deterministisch: Regeln → tägliche Ziel-Positionen).
2. Provenienz-Check I0076-Stream.
3. IBKR-Paper-Adapter (`ib_async`/TWS-API) + Instrument-Mapping (FX-Spot, Index-CFD/ETF,
   Krypto, Carry-Paare) — Verfügbarkeit der Symbole prüfen.
4. Trailing-DD-Notaus + 60-Sek-SL-Logik (für die spätere CTI-MT5-Variante).
