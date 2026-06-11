# Strategie 0061 — Phase 4: Funding-Carry + On-Chain-TVL als inkrementelle Features

**Status: abgelehnt (kein inkrementeller Wert).** Die Roadmap-Phase-4-Frage —
bringen die crypto-spezifischen Quellen (Perp-Funding, On-Chain-TVL) etwas
ÜBER die 0058/0059-Basis-Features hinaus? — ist sauber mit **nein**
beantwortet: der knappe CPCV-Gate-Pass der TVL-Variante überlebt den
Walk-Forward nicht.

## Daten (neue, wiederverwendbare Infra)

- **Perp-Funding:** Binance fapi `fundingRate`, 8h-Events seit 2019-09,
  **verifiziert inkl. delisteter Perps** (SRM, ANC, FTT, Alt-LUNA, XEM) —
  survivorship-sicher. 294 Paare mit Historie (39 Namen 2020 → 244 in 2025).
  `crypto_xsection.get_binance_funding` / `get_funding_panel`, Parquet-Cache.
- **Chain-TVL:** DefiLlama `historicalChainTvl` (gratis, **tote Chains
  historisch vorhanden** — Terra Classic komplett), Symbol→Chain-Map über
  `/v2/chains`. 102 Paare mappbar (nur L1/L2-Gas-Token). `get_chain_map` /
  `get_chain_tvl`.

## Features & Design (vorab registriert, 2 neue Trials)

`funding_7` (7d-Funding-Summe = Crowding-Level), `funding_z` (vs 90d),
`tvl_chg_28` (28d-log-TVL-Trend der eigenen Chain, 1d-Lag). PIT: 8h-Funding
des UTC-Tages ist zum Close bekannt; Perp-Existenz selbst ist historische
Information. Identische CPCV-Splits/Zeilenmengen wie 0059 (h=28, Phase-4-NaNs
droppen keine Zeilen, LightGBM behandelt NaN nativ), Modell LGBM0 fix, KEIN
neues Grid. Portfolio-Messung mit der eingefrorenen Live-Regel (min_k=12).

## Ergebnisse

| Set | CPCV-IC | schlägt BASE (Splits) | Portfolio vs Markt (CPCV) | Gate |
|---|---|---|---|---|
| BASE (11 Features) | +0.1505 | — | +0.45 | — |
| +FUNDING | +0.1526 | **68%** | +0.36 | **FAIL** (Portfolio schlechter) |
| +FUNDING+TVL | +0.1529 | 57% | +0.50 | pass (knapp) → WF-Check |

**Walk-Forward-Check (0060-Protokoll, der entscheidende Test):**

| | BASE | +FUNDING+TVL |
|---|---|---|
| netto Sharpe | +0.59 | +0.51 |
| vs Markt | **+0.64** | **+0.42** |
| Bootstrap-KI | [−0.24, +1.11] | [−0.44, +0.91] |
| je Jahr | 21:+1.9 22:+1.8 23:−0.8 24:−0.3 25:+0.1 26:+0.1 | in JEDEM Jahr ≤ BASE |

## Interpretation

1. **Funding verbessert den IC konsistent** (68% Split-Siege — das Signal
   existiert), aber er konzentriert sich offenbar in Namen/Phasen, die das
   konzentrierte 12er-Dezil-Buch nicht besser machen — Rang-Information ≠
   Portfolio-Wert (dieselbe IC→PnL-Lektion wie 0058, diesmal als Feature).
2. **Der CPCV-Gate-Pass der TVL-Variante (+0.05) war Rauschen** — out-of-time
   kehrt er sich um (−0.22). Der zweistufige Check (CPCV-Gate → WF-Check) hat
   genau die Sorte knappen Schein-Fortschritt abgefangen, die sonst als
   „Phase 4 erfolgreich" in die Regel gewandert wäre.
3. **Konsequenz: die Live-Regel bleibt bei den 11 Basis-Features.** Jede
   spätere Feature-Erweiterung muss denselben zweistufigen Check bestehen.

## Vorbehalte

- Funding-Coverage beginnt erst 2020/21 für Alts — in der frühen Hälfte des
  Panels ist das Feature NaN-dominiert; ein reiner Post-2021-Test hätte mehr
  Power, wäre aber ein NEUES Design (nicht nachgeschoben).
- TVL nur für 102 Gas-Token; Protokoll-Token (UNI, AAVE, …) bräuchten
  Protokoll-TVL-Mapping — bewusst nicht nachgelegt (Trial-Disziplin).
- Funding als KOSTEN-Term (bei Perp-Ausführung) ist eine andere Frage als
  Funding als SIGNAL — hier nur Letzteres getestet (Spot-Ausführung).

## Artefakte

`results/metrics.json`, `results/walkforward_check.json`,
`predictions_{base,funding,funding_tvl}.parquet`;
Daten-Fetch: `scripts/fetch_crypto_phase4.py`.
