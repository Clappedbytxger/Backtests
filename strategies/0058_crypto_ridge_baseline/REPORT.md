# Strategie 0058 — Crypto-Cross-Section: Ridge-Benchmark unter CPCV (Roadmap Phase 0–2)

**Status: Messlatte etabliert — kein Edge-Claim.** Dies ist der vorab geforderte
lineare Benchmark, den jedes spätere ML (LightGBM Phase 3, CNN Track B) schlagen
muss (0057-Lehre: ohne saubere lineare Messlatte ist jeder ML-„Erfolg"
uninterpretierbar).

## Hypothese & Rationale

Cross-sektionale Crypto-Returns sind laut Literatur (Cakici et al. 2024, Liu &
Tsyvinski 2021) durch Momentum, Size, Illiquidität und Past-Alpha vorhersagbar
und überleben — anders als Commodities (0047/0048/0057) — die Kosten, primär im
Long-Leg. Ursache: junger, retail-dominierter, behavioral getriebener Markt.
Phase 2 testet die LINEARE Version dieser These unter voller Validierungs-Härte.

## Daten & Universum (Survivorship = Endgegner, Roadmap Teil 2)

- **PIT-Universum:** wöchentliche CoinMarketCap-Historical-Snapshots
  (462 Wochen, 2017-08 bis 2026-06), Top-150 je Snapshot, **inklusive aller
  später gestorbenen Coins**. Snapshot wird erst ab Folgetag verwendet
  (1-Tag-Lag gegen unbekannte Snapshot-Uhrzeit).
- **Preise/Volumen:** Binance-USDT-Spot-Klines — liefern verifiziert auch
  **delistete** Paare (BCC, VEN, SRM, ANC, LUNA). Binance-only = Top-Tier-Venue
  als Wash-Trading-Filter. 3220 Tage × 370 Spalten; **105 Paare (28%) sind
  heute tot/delistet und trotzdem historisch im Panel.**
- **Delist-Relist-Falle entschärft:** interne Lücken >4 Tage splitten eine
  Serie in unabhängige Segmente (`LUNAUSDT` = Terra bis 13.05.2022,
  `LUNAUSDT~2` = Luna 2.0 ab 31.05.2022) — sonst hätte Momentum über die Lücke
  ein Millionen-Prozent-Artefakt gebucht (Verwandte der Roll-Gap-Lehre 0048).
- Ausschlüsse: Stablecoins (inkl. UST — der Kollaps wirkt über LUNA), Wrapped/
  Staked-Duplikate, Gold-Pegs, Leveraged Tokens.
- **Pflicht-Gate bestanden:** `tests/test_crypto_universe.py` (8 Tests) —
  tote Coins nachweislich PIT-Mitglieder, kein Listing-/Mcap-Look-ahead,
  Forward-Targets können Tote nicht wiederbeleben, Hellseher-Panel unmöglich.

## Features (Phase 1, `quantlab/crypto_features.py`)

Momentum 1/2/4/8/12W, Size (log PIT-Mcap), Amihud-Illiquidität, Vol/Semivol 30d,
Volume-Trend, Max-Return-Salienz, Past-Alpha/Beta 90d vs cap-weighted
PIT-Marktfaktor — alle per Datum rang-transformiert (GKX). Target = per-Datum-
Rang des Forward-Returns (7/14/28 Kalendertage). Funding-Carry/On-Chain bewusst
auf Phase 4 verschoben.

## Methodik

- **Modell:** Ridge α=1.0 **fix vorab registriert** (kein Grid — auf
  Rang-Features mit n≫p ist Regularisierung nahezu irrelevant).
  **n_trials = 6** (3 Horizonte × 2 Portfolio-Varianten), alle berichtet.
- **CPCV:** 8 Gruppen / 2 Test-Gruppen = 28 purged Splits, Purge = Horizont+7d,
  Embargo 1%; OOS-Stitching → jede Woche exakt einmal out-of-sample.
- **Portfolio:** Long-only Top-Quintil (primär) + dollar-neutral L/S (sekundär),
  inverse-Vol-Gewichte, Wochen-Rebalance, `min_names=20` (Start eff. 2019-02).
- **Kosten:** gestaffelt je Liquiditätsklasse (21d-Median-Dollarvolumen):
  ≥100M$: 12 bps/Seite … <1M$: 100 bps/Seite (Binance-Taker 10 bps + Spread).
- Benchmarks (friktionslos): cap-weighted PIT-Markt, Equal-Weight-Universum, BTC.

## Ergebnisse (alle CPCV-OOS, 2019-02 … 2026-06)

### Prognosekraft: stark, stabil, KEIN Decay

| Horizont | OOS-IC (Spearman) | t-Stat | n Wochen |
|---|---|---|---|
| 7d | **+0.095** | 8.2 | 381 |
| 14d | **+0.113** | 9.4 | 380 |
| 28d | **+0.137** | 11.7 | 378 |

IC je Jahr (h=28): 2019: 0.12 · 2020: 0.12 · 2021: 0.10 · 2022: 0.16 ·
2023: 0.10 · 2024: 0.13 · **2025: 0.22** · 2026: 0.14 — jedes einzelne Jahr
positiv, zuletzt am stärksten. **Das ist der fundamentale Unterschied zu
0057 (Commodities: Decay → 0 post-2015): die Crypto-Cross-Section ist linear
prognostizierbar und bleibt es.**

### Portfolio-Übersetzung: hier sitzt das Problem

| Variante (h=28) | Sharpe netto | Sharpe brutto | CAGR netto | MaxDD | Turnover |
|---|---|---|---|---|---|
| Long-only Top-Q | +0.56 | +0.69 | +14.9% | −85% | 22×/J |
| Long-Short | −0.08 | +0.39 | −15.5% | −86% | 56×/J |
| Markt (cap-w.) | 0.61 | — | +21.6% | −86% | — |
| Equal-Weight | 0.37 | — | −5.4% | −94% | — |
| BTC B&H | 0.76 | — | +35.3% | −83% | — |

- **Long-only schlägt den Markt nicht:** Hedge-Differenz vs cap-weighted Markt
  Sharpe **−0.47…−0.68** (je Horizont); vs Equal-Weight-Pool ≈ 0 (−0.17…+0.07).
  Das Top-Quintil schlägt den eigenen (blutenden) Pool um +15–20pp CAGR, aber
  nicht BTC. Per-Jahr vs EW: negativ 2019–21/2023, positiv 2022/2025/2026 —
  instabil.
- **L/S brutto positiv (h28 +0.39), netto an der Kosten-Wand** (56–78×/J
  einseitiger Turnover × 12–100 bps). Per-Jahr brutto: 2022 +1.4, 2025 +1.5 —
  die Shorts (vorhersagbar blutende Small Caps) tragen viel vom IC, sind aber
  retail-seitig kaum/teuer umsetzbar.
- Der hohe IC monetarisiert sich im naiven Quintil-Portfolio also NICHT
  automatisch — die Differenz zwischen Rang-Prognosekraft und Portfolio-PnL
  (Konzentration im Short-Leg, Turnover, Vol-Gewichtung) ist die zentrale
  offene Frage für Phase 3.

## Ehrliche Vorbehalte

1. Benchmarks sind friktionslos; ein realer BTC-B&H hätte minimale Kosten.
2. Delisting-Limbo: nach dem letzten Bar wird die Position bis zum nächsten
   Rebalance mit Return 0 geführt (der Pre-Delisting-Crash IST im Panel).
3. CMC-Mcap-Qualität (Free-Tier) ungeprüft gegen Zweitquelle; Rang-Rauschen
   um Platz 150 toleriert.
4. Rename-Overlaps (MATIC/POL) können ein Asset wenige Wochen doppelt zählen
   (~0 Effekt auf 100+ Namen).
5. Frühperiode dünn (2018: ~13 handelbare Namen) — Backtest startet ehrlich
   erst 2019-02 (min_names=20).

## Verdikt & nächste Schritte (Phase 3 — NACH gemeinsamem Review)

Messlatte steht: **LightGBM muss (a) den Ridge-IC und (b) die OOS-Sharpe-
Verteilung der 28 Splits klar schlagen UND (c) eine Portfolio-Variante liefern,
die netto den cap-weighted Markt schlägt — sonst gilt die Roadmap-These als
nicht belegt.** Offene Hebel, die VOR Phase 3 zu registrieren sind (zählen als
Trials): Monats-Rebalance/Buffer-Ränge gegen Turnover, Long-Leg-Konzentration
(Dezil statt Quintil), Liquiditäts-Mindestfilter statt Kosten-Strafe.

## Artefakte

`results/metrics.json`, `results/ridge_predictions_h{7,14,28}.parquet` (für
Phase-3-Vergleich), `results/returns_h*_{long_only,long_short}.parquet`,
`results/equity_vs_benchmarks.png`, `results/ic_by_year.png`.
Daten-Fetch: `scripts/fetch_crypto_universe.py` (einmalig, Sandbox off).
