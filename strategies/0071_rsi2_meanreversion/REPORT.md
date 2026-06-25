# Strategie 0071 — Connors RSI(2) Short-Term Mean Reversion

- **Kategorie:** mean-reversion / swing / daily
- **Status:** **testing** — echter Edge + Ziel-Win-Rate, aber Vanilla-Version
  nicht CTI-tauglich (CAGR zu niedrig, worst day > 5 %-Tageslimit)
- **Datum:** 2026-06-14
- **Universum:** SPY, QQQ, DIA, IWM (US-Indizes) + GLD; 1999–2026
- **Motivation:** Funded-Account-Profil (City Traders Imperium) — hohe Trefferquote,
  viele kleine Gewinne, glatte Equity, kurze Swing-Holds. Daily-Bars umgehen die
  Kostenwand, an der jeder Intraday-MR-Test starb (0012-0015, 0038-0041).

## 1. Regeln (look-ahead-safe via run_backtest-Shift)
- Trendfilter: Close > SMA(200) (nur Dips im Aufwärtstrend), long-only
- Entry: RSI(2) < 10 (oversold)
- Exit: Close > SMA(5) [Alt.: RSI(2)>70 / max-hold / Stop]
- Entscheidung am Close t, gehalten ab t+1.

## 2. Ergebnisse (netto, ~2 bps/Seite ETF)

| Asset | Trades | Win% | PF | Payoff | ØHold | CAGR | Sharpe | MaxDD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SPY | 198 | 74 % | 2,42 | 0,84 | 3,5 | +3,5 % | 0,27 | −14,8 % |
| QQQ | 208 | 69 % | 2,16 | 0,96 | 3,7 | +4,2 % | 0,29 | −15,4 % |
| DIA | 209 | 72 % | 1,55 | 0,59 | 3,6 | +1,8 % | 0,00 | −13,0 % |
| IWM | 189 | 72 % | 1,68 | 0,64 | 3,8 | +2,6 % | 0,11 | −21,1 % |
| GLD | 140 | 73 % | 1,59 | 0,59 | 4,3 | +2,1 % | 0,05 | −14,7 % |

**Equal-Weight-Portfolio (Indizes):** CAGR +3,1 %, Sharpe 0,21, Sortino 0,30,
MaxDD −14,8 %, worst day −6,7 %, längste Unterwasser-Phase 846 Tage, ~10 % Marktzeit.

## 3. Signifikanz (Portfolio)
- Permutation p = **0,024** (Timing schlägt Zufalls-Exposure)
- t-Test mean p = 0,0034 · Deflated Sharpe = **0,892** (n_trials=12)
- Bootstrap Sharpe 95%-KI [−0,17, +0,59] · IS/OOS Sharpe 0,15 / 0,28
→ **Der Edge ist statistisch real** (sauberer als SMC auf der Permutations-/DSR-Achse).

## 4. Robustheit + Tail (SPY)
Win-Rate 72–80 % über alle Entry-Schwellen (5/10/15) = stabiles Plateau. Tail:
worst trade −10 % ohne Stop; Stop −5 % → −8 % (zähmt etwas), max-hold 10d → −14 %
(schlechter, falscher Exit-Zeitpunkt). Der Crash-Dip-Tail ist dem Dip-Kauf inhärent.

## 5. Verdict / CTI-Eignung
**Form richtig (74 % Win, kurze Holds, signifikanter Edge), Zahlen für CTI noch
nicht:** (a) CAGR ~3 % → auf 7 % DD gesized +1,5 %/J → 10 %-Ziel erst ~82 Monate;
(b) **worst day −6,7 % > CTI 5 %-Tageslimit** = K.O.-Kriterium; (c) Sharpe nur 0,21
(Tail-Verluste drücken trotz hoher Win-Rate; Payoff < 1).

**Kern-Problem:** kapital-effizient aber niedrig-exponiert (90 % Cash) → zu wenig
Rendite, und die Marktzeit fällt auf Crash-Dips. Die hohe Win-Rate täuscht.

**Fix-Pfad (→ 0072):** (1) breiter ETF-Korb (Sektoren/Regionen/TLT/GLD) +
Kapital auf aktive Signale verteilen (statt 1/N) → CAGR zweistellig bei moderatem
DD; (2) Tail-Kontrolle (Vol-Sizing / VIX-Regime-Filter) → worst day < 5 %. Damit
könnte RSI-2 CTI-tauglich werden. Engine + Batterie stehen wiederverwendbar in
`run.py`.
