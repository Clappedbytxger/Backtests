# Strategie 0096 — Strukturelle RV-Mean-Reversion: Brent/WTI, Inter-Grain, Re-Test 0081

> Batch-2-Ideen **I0060** (Brent/WTI, Hoch-Prio), **I0061** (Inter-Grain-Substitution),
> **I0063** (Re-Test der 0081-Spreads als z-Score-MR) aus `D:\Backtest Ideas` (#s22/#s19).
> Alle replizieren das lebende 0087-Muster (kointegrierter Anker + z-Score-MR statt
> Richtungs-Saison).

- **Kategorie:** RV-Mean-Reversion (kointegrierte Paare/Spreads)
- **Status:** **alle abgelehnt** — I0063 war ein Roll-Artefakt (4. Fang), I0060/I0061 zu schwach
- **Datum:** 2026-06-15
- **Daten:** yfinance (BZ=F/CL=F/ZC=F/ZW=F/ZS=F) + gecachte Databento-Chains (0081, $0 Neukosten)
- **Engine:** z-Score-MR (win 60, Entry |z|>2, Exit z→0, Stop 3,5), ADF-Gate + Half-Life, Permutation

## 1. I0063 — Re-Test 0081-Spreads: der wichtigste Befund (Roll-Artefakt, 4. Fang)

Die Idee: 0081 lehnte die Calendar-Spreads als *Richtungs*-Saison ab — vielleicht tragen sie
einen **MR**-Edge, den der Richtungs-Frame verdeckte. Re-Test als z-Score-MR.

**Erster (naiver) Lauf — spektakulär, aber falsch:**

| Spread | netto Sharpe (naiv) | Half-Life | perm p |
| --- | ---: | ---: | ---: |
| Mais Jul/Dez | +1,69 | 2,7 d | 0,000 |
| NatGas Mär/Apr | +1,51 | 2,4 d | 0,000 |
| RBOB Jul/Nov | +1,03 | 13 d | 0,000 |

Sharpe >1,5 mit 2,4-Tage-Half-Life und perm p=0,000 = **klassischer Too-good-to-be-true-Alarm.**
Ursache: mein erster Spread-„Level" wurde über den **jährlichen Kontrakt-Roll hinweg
differenziert** (Jahr-y-Spread vs Jahr-y+1-Spread sind verschiedene Preis-Niveaus) → der
Roll-Sprung fabrizierte die „Reversion" (Lehre 0028/0029/0048 — **4. Fang derselben Falle**,
genau die im Handoff geforderte Pflicht-Roll-Prüfung).

**Roll-saubere Korrektur (MR NUR innerhalb jedes Einzeljahr-Paars, nie über den Roll halten):**

| Spread | netto Sharpe (sauber) | ADF p | IS/OOS |
| --- | ---: | ---: | ---: |
| Mais Jul/Dez | **+0,41** | 0,42 | +0,82 / +0,17 |
| NatGas Mär/Apr | **−0,02** | 0,80 | +0,39 / −0,20 |
| RBOB Jul/Nov | **−0,15** | 0,65 | +0,31 / −0,34 |

**Vollständiger Kollaps.** Innerhalb eines Paars sind die Spreads **nicht einmal kointegriert**
(ADF p=0,42-0,80), und die MR ist null/negativ. → **0081s Ablehnung war strukturell, nicht
Frame-bedingt.** Die Idee „MR-Edge vom Richtungs-Frame verdeckt" ist **falsifiziert** — der
scheinbare Edge war ausschließlich der Roll-Sprung. (RESEARCH-PROCESS „Reject ist vorläufige
Evidenz" sauber abgearbeitet: reproduziert, Roll-geprüft, dann erst verworfen.)

## 2. I0060 — Brent/WTI-Spread-MR

$-Spread BZ−CL, z-Score-MR. **ADF p=0,020 (kointegriert, Half-Life 22 d — sauber)**, aber
**netto Sharpe +0,19, perm p=0,191** = das MR-Timing schlägt Zufall nicht. Der Spread ist
zwar arbitrage-gebunden (Pipeline-/Transportkosten als Band), aber das Band ist breit und die
Bewegungen sind regime-getrieben (2011-14 Cushing-Glut-Blowout) → kein handelbarer MR-Edge.

## 3. I0061 — Inter-Grain-Substitution-Ratios

| Ratio | ADF p | netto Sharpe | perm p | IS/OOS | Half-Life |
| --- | ---: | ---: | ---: | ---: | ---: |
| Corn/Wheat | 0,000 | +0,16 | 0,131 | +0,06 / +0,24 | 108 d |
| Soy/Corn | 0,000 | +0,27 | **0,044** | +0,38 / +0,15 | 95 d |

Beide Ratios sind **kointegriert** (ADF p=0,000 — die Substitutions-These hält ökonomisch),
aber die MR ist **zu schwach zum Traden**: Corn/Wheat insignifikant (perm p=0,13); Soy/Corn
**grenzwertig** (perm p=0,044) aber Sharpe nur 0,27, **OOS-Decay** (+0,38→+0,15) und
Half-Life 95 Tage (sehr langsam → wenige unabhängige Trades). Kein Lead.

## 4. Gesamt-Verdict

**Alle abgelehnt.** Das einzige lebende RV-MR-Bein bleibt **0087 (Weizen CHI/KC)** — und der
Grund ist jetzt scharf: 0087 ist **dasselbe Gut an verschiedenen Börsen** (Chicago vs Kansas
Wheat) = nahezu perfekte Kointegration mit engem, schnellem Band. Die hier getesteten
**Cross-Commodity-Substitutions** (Corn/Wheat, Soy/Corn) sind zwar kointegriert, aber das Band
ist zu breit/langsam (Half-Life 95-108 d), und die **Calendar-Spreads** (I0063) sind innerhalb
des Paars gar nicht kointegriert — ihr scheinbarer Edge war reiner Roll-Sprung.

**Lehre:** „Kointegriert" (ADF signifikant) ist NOTWENDIG, aber nicht HINREICHEND — ein
handelbarer RV-MR-Edge braucht zusätzlich ein **enges, schnelles Band** (kurze Half-Life,
geringe Regime-Drift). Same-commodity-cross-venue (0087) erfüllt das; Cross-Commodity-
Substitution und arbitrage-breite Energie-Spreads nicht. Und: der Roll-Check bleibt bei
Einzelkontrakt-Spreads Pflicht — die Falle schnappt sonst zum 4. Mal zu.
