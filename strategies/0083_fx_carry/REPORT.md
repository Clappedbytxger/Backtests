# Strategie 0083 — FX Carry (G10) mit Vol-/Crash-Filter

> Idee **I0020** aus dem Handoff `D:\Backtest Ideas` (#s11; Quantpedia/Menkhoff/Sarno).
> umgeht-Reject 0048 (andere Asset-Klasse als toter Commodity-Carry).

- **Kategorie:** carry-term-structure (cross-sectional FX)
- **Status:** abgelehnt als Standalone (echt-aber-schwach, Crash-Skew)
- **Datum:** 2026-06-15
- **Universum:** 9 G10-Währungen vs USD (EUR/JPY/GBP/AUD/CAD/CHF/NZD/SEK/NOK)
- **Stichprobe:** 2004-2026 (monatlich), IS 2004-2014 / OOS 2015-2026

## 1. Regeln & Daten

Long Top-3 / Short Bottom-3 Währungen nach 3-Monats-Zins (FRED OECD Interbank,
monatlich), USD-Funding, monatliches Rebalance. Carry-Total-Return = Spot-Return
(XXX/USD) + Zins-Akkrual (rate/12), Zins decision-time (shift 1). FX-Spot yfinance.
~8 bps/Monat Kosten-Drag. Vol-Filter: risk-off (globale Korb-Vola > Median) → flat.

## 2. Ergebnisse

| Variante | Sharpe | CAGR | MaxDD | Skew | Permutation | Monats-KI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Carry L/S (netto) | +0,19 | +1,1 % | −28 % | **−0,72** | p=0,043 | [−0,14 %, +0,36 %] (mit 0) |
| + Vol-Filter | **+0,31** | — | −14 % | — | — | — |

IS/OOS: IS +0,26 / OOS **+0,11** (Zerfall).

## 3. Verdict

**Abgelehnt als Standalone — echte, aber zu schwache Prämie.** Die Carry-Richtung
stimmt (Permutation p=0,043, Vol-Filter hebt Sharpe 0,19→0,31 und halbiert den MaxDD
auf −14 % — genau wie #s11/der Brief vorhersagt), und die **negative Skew (−0,72)
bestätigt das dokumentierte Crash-Risiko**. Aber das Lead-Gate scheitert: Monats-Return-
KI berührt 0, Sharpe nur 0,19 (0,31 gefiltert), und der OOS zerfällt auf +0,11.

**Wichtige Abgrenzung zu 0048:** anders als der tote Commodity-Carry (IS→OOS-Kollaps auf
negativ, p=0,77) ist die FX-Carry-Prämie *real und richtungsstabil* (perm p<0,05, beide
Hälften positiv, Vol-Filter wirkt) — nur eben klein und crash-behaftet. Damit ist I0020
das, was die Literatur sagt: eine echte Risikoprämie mit negativer Skew, kein
risikofreies Alpha. Bestenfalls ein **kleines diversifizierendes Bein mit Vol-Filter**,
kein Standalone-Lead. Ein EM-FX-Ausbau (höhere Carry-Spreads) könnte mehr Magnitude
bringen, trägt aber mehr Crash-Risiko — bewusst nicht verfolgt (Disziplin).
