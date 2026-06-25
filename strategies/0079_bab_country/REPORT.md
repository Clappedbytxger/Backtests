# Strategie 0079 — Betting-Against-Beta auf Länder-Aktienindizes

> Idee **I0024** aus dem Handoff `D:\Backtest Ideas` (Quelle #s08, Frazzini/Pedersen
> 2014; Quantpedia Country-BAB).

- **Kategorie:** cross-sectional-factor (Länder-ETFs)
- **Status:** abgelehnt (Low-Beta-Prämie auf Länderebene insignifikant)
- **Datum:** 2026-06-15
- **Universum:** 21 iShares-MSCI-Länder-ETFs (EWG/EWJ/EWU/EWZ/…), Markt = S&P 500 (SPY)
- **Stichprobe:** 1997-2026, IS 1997-2012 / OOS 2013-2026

## 1. Hypothese & Regeln

Leverage-beschränkte Investoren überkaufen High-Beta → Low-Beta-Länder liefern höhere
risikoadjustierte Returns. Beta je ETF vs SPY (252d rollend), aufsteigend ranken, long
Low-Beta-Terzil / short High-Beta-Terzil, monatlich. FP-Kern: jedes Bein auf Beta=1
reskalieren (beta-neutraler Spread). Look-ahead-sicher (rollende Beta + T+1-Shift).

## 2. Ergebnisse

| Konstruktion | Sharpe | realisierte Beta | Signifikanz |
| --- | ---: | ---: | --- |
| naives Rank-L/S (EW low − EW high) | −0,34 | **−0,39** | perm p=0,658 |
| beta-neutral BAB (rolling-hedged) | −0,06 | −0,01 | α=+1,34%/J, **t=0,59** |
| long-only Low-Beta | +0,51 | — | vs Equal-Weight +0,49 |

Monats-Hedge-Return-Bootstrap-KI (beta-neutral): **[−0,23%, +0,41%] — berührt 0.**

## 3. Diagnose

- **Das naive L/S ist netto short-beta (−0,39)** und verliert daher im Aktien-Bull aus
  dem falschen Grund — der bekannte BAB-Konstruktionsfehler ohne Reskalierung.
- **Sauber beta-neutralisiert** (naives Spread − rollende Beta × Markt) ist das Alpha
  positiv (+1,34 %/J), aber **insignifikant** (t=0,59, Monats-KI mit 0). Das Gate des
  Briefs (Hedge-Return-KI ohne 0) ist NICHT bestanden.
- **Long-only Low-Beta (0,51) ≈ Equal-Weight-Universum (0,49)** → auf Länderebene gibt
  es praktisch KEINE Low-Beta-Prämie. Das ist der direkteste Beleg gegen I0024.
- IS/OOS der beta-neutralen Variante 0,17/0,58 (raw) sieht nach OOS-Stärke aus, aber die
  Voll-Stichprobe ist insignifikant (kleines, instabiles Alpha) — die OOS-„Stärke" ist
  nicht robust genug, um das KI-Gate zu drehen.

## 4. Methodik-Notiz (FP-Reskalierung instabil)

Die wörtliche FP-Regel „jedes Bein per 1/β auf Beta=1 reskalieren" ist auf einem
21-ETF-Universum **numerisch instabil**: wenn ein Bein-Ø-Beta klein wird, explodiert der
Hebel (1/β), einzelne Monate dominieren → CAGR −100 % (Blow-up). Auf Einzelaktien (FPs
Universum mit Hunderten Namen) mittelt sich das aus; auf 7 ETFs pro Bein nicht. Die
robuste Alternative (Markt-Hedge des naiven Spreads auf Residual-Beta ≈ 0) testet
dieselbe ökonomische Frage stabil — und sie ist insignifikant.

## 5. Verdict

**Abgelehnt.** Die BAB/Low-Beta-Prämie zeigt sich auf Länder-Aktienindizes NICHT
signifikant: beta-neutrales Alpha +1,34 %/J aber t=0,59 / KI mit 0, und Long-only-Low-Beta
schlägt das Equal-Weight-Universum nicht (0,51 vs 0,49). Konsistent mit der Bestand-Lehre,
dass cross-sektionale Prämien außerhalb von Einzelaktien-Universen schwach/zerfallen sind
(0047/0048), und mit der Literatur, dass Country-BAB schwächer ist als Single-Stock-BAB.
Reizvoll wäre BAB nur auf einem breiten Einzelaktien-Universum — das scheitert aber am
Survivorship-Daten-Blocker (wie I0011/I0035). Kein Lead.
