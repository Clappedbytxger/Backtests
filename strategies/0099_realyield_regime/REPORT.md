# Strategie 0099 — Real-Yield-/Credit-Spread-Regime-Overlay (I0066)

> Batch-2-Idee **I0066** aus `D:\Backtest Ideas` (#s24 + #s19). Zweites Makro-Regime-Signal
> im lebenden 0086-Overlay-Frame (USD-Regime, p=0,002) — real-yield-/credit-getrieben.

- **Kategorie:** macro-cross-asset / Regime-Overlay
- **Status:** **abgelehnt** — schlägt B&H nicht, Timing insignifikant; niedriger DD ist Cash-Drag
- **Datum:** 2026-06-15
- **Daten:** FRED (DFII10 Realzins, BAMLH0A0HYM2 HY-OAS) + yfinance (GLD/TLT/GC=F). Alles gratis.

## 1. Hypothese

Zwei strukturelle Regime-Signale skalieren ein Ziel-Exposure (Overlay wie 0086, KEINE
Standalone-Wette): (a) Realzins-Momentum (10y-TIPS) negativ → Rückenwind für Gold/Duration;
(b) Credit-Spread-Momentum (HY-OAS) nicht weitend → Risk-On. Long Ziel, wenn beide günstig.
Beurteilung wie 0086: schlägt das regime-skalierte Ziel das ungeskalte B&H **und** eine
Drift-Trap-Permutation? Plus: niedrige Korrelation zum 0086-USD-Signal (sonst redundant).

## 2. Ergebnis

| Ziel | Combined Sharpe | B&H Sharpe | MaxDD (regime/B&H) | % long | perm p |
| --- | ---: | ---: | ---: | ---: | ---: |
| GLD | +0,51 | **+0,65** | −8 % / −46 % | 3 % | 0,121 |
| TLT | −0,24 | +0,31 | −16 % / −48 % | 3 % | 0,966 |
| GC=F | +0,47 | **+0,69** | −7 % / −44 % | 3 % | 0,137 |

Einzel-Signale (GLD): real-only +0,56, credit-only +0,43 — **beide ebenfalls < B&H +0,65.**

**Befund:**
1. **Schlägt B&H nicht.** Kein Ziel, keine Signal-Variante erreicht den simplen Buy-&-Hold-
   Sharpe. Das ist der entscheidende Unterschied zu 0086 (dessen USD-Regime B&H schlug,
   perm p=0,002).
2. **Timing insignifikant** (perm p=0,12-0,97) — das Regime-Timing schlägt zufälliges
   Same-Count-Timing nicht.
3. **Der niedrige MaxDD (−8 %) ist Cash-Drag, kein Skill:** das Combined-Regime ist nur **3 %
   der Zeit long**. Ursache ist ökonomisch echt: fallende Realzinsen (Flight-to-Quality) fallen
   meist mit **weitenden** Credit-Spreads zusammen (Risk-Off) → „Realzins fällt UND Credit eng"
   ist ein seltenes benignes Regime. Das Overlay ist also fast immer flat = umgeht die Drawdowns
   durch Nicht-Investiert-Sein, nicht durch Können.
4. **Korrelation zum 0086-USD-Regime nur +0,11** (niedrig) → es WÄRE ein echtes zweites Signal,
   wenn es trüge — tut es aber nicht.

## 3. Verdict

**Abgelehnt.** Das Real-Yield-/Credit-Regime ist unkorreliert zum lebenden 0086-USD-Overlay
(gut), aber **fügt keinen Wert hinzu**: es schlägt Buy-&-Hold von Gold/Duration auf keiner
Variante, das Timing ist insignifikant, und der scheinbare Drawdown-Vorteil ist reiner
Cash-Drag aus einem fast nie aktiven (3 %) Regime. Bestätigt die 0086-Lehre asymmetrisch:
**nicht jedes plausible Makro-Regime ist ein Overlay-Edge** — das USD-Momentum-Regime trägt
(0086), das Realzins-/Credit-Regime nicht. Der einzige lebende Makro-Overlay bleibt 0086.
