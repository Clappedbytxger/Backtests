# SMC Sweep+BOS — Personal-Account-Version (die „+54 %"-Strategie)

Eigenständige, handelbare Fassung der reproduzierten Video-Strategie — **nur für
eigenes Kapital mit hoher Drawdown-Toleranz**, NICHT für Funded-Accounts (DD zu
hoch). Engine: `strategies/0069_smc_sweep_bos/` (`quantlab/smc`), Portfolio-/
Konto-Logik: dieser Ordner.

## Was es ist
Liquidity-Sweep + Break-of-Structure über 5 Assets in EINEM Konto (alle Sleeves
gleichzeitig bei vollem Risiko, Pyramiding) — reproduziert das Revelio-Video
(+53,89 %/J, $10k→$874k). Asymmetrisches Swing-Pivot + Struktur-Filter +
1R-Trailing (GBP wäre Fixed-1R, bei mir Trailing).

## Config (eingefroren in `0069_smc_sweep_bos/config.yaml`)
| Asset | TF | Richtung | Exit | Risk/Trade | Pivot (back/fwd) | buffer | mc |
|---|---|---|---|---:|---|---:|---:|
| Gold (XAU spot) | M5 | both | Trailing | 0,5 % | 10/10 | 0,5 | 2 |
| Bitcoin | H1 | both | Trailing | 2,0 % | 8/4 | 1,0 | 3 |
| S&P 500 (ES) | M15 | long | Trailing | 1,5 % | 6/2 | 1,0 | 2 |
| Nasdaq (NQ) | M15 | long | Trailing | 1,5 % | 6/2 | 0,5 | 2 |
| GBP/USD spot | M15 | both | Trailing | 1,5 % | 6/2 | 0,5 | 1 |

## Ausführen
- Kombiniertes Konto (die +54 %-Zahl): `python strategies/0070_smc_portfolio/combined_account.py`
- Vol-getargete Variante (DD ~40 % statt ~52 % bei gleichem Return): `vol_target.py`
- Equal-weight (konservativer, ~12 %/J, 12 % DD): `portfolio.py`

## Risiko-Profil (ehrlich)
- **CAGR ~+54 % (taker) bis +64 % (good_exec)**, aber **MaxDD ~40–52 %** (kombiniert,
  voller Hebel). Vol-Targeting (`vol_target.py`) senkt den DD bei +54 % auf ~40 %.
- **Trefferquote nur ~26–30 %** (Trend-Profil: wenige große Gewinner), Median-Trade
  ≈ 0R, **längste Unterwasser-Phase 618 Tage**.
- **Edge ist real, aber zerfällt OOS** (Sharpe 1. Hälfte 1,54 → 2. Hälfte 0,36) —
  Crypto/Trend-Momentum reift. Live mit reduziertem Risiko starten.
- Both-direction Gold/BTC haben statistisch signifikante **Brutto**-Edges (kein
  Beta); netto kosten-/ausführungs-sensitiv.

## Verdikt
Legitime, aggressive Multi-Asset-Trend-Strategie für **Risikokapital**, das einen
40–50 %-Drawdown verkraftet. Schlägt B&H risk-adjusted nur knapp (bei guter
Ausführung). **Kein Selbstläufer, kein Funded-Profil** — Positionsgröße strikt
begrenzen, OOS-Zerfall beobachten, Live-Forward führen bevor groß skaliert wird.
