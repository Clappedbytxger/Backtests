# Strategie 0101 — Prop-Challenge Batch 3 (CTI 1-Step, Ideen I0067–I0074)

> Sammel-Report für den dritten Handoff-Batch aus `D:\Backtest Ideas\ideas\
> prop-challenge.md`: acht intraday-/event-Edges, mit denen die **City-Traders-
> Imperium-1-Step-Funded-Challenge** bestanden werden soll. Alle acht auf einem
> einzelnen CTI-handelbaren Instrument (Index-/Gold-/FX-CFD bzw. BTC) getestet.

- **Kategorie:** prop-challenge (intraday-momentum / mean-reversion / event)
- **Status:** **abgelehnt** (8/8) — siehe je Idee
- **Datum:** 2026-06-15
- **Universum:** S&P-500-E-mini (ES.c.0), Nasdaq-100-E-mini (NQ.c.0), Gold
  (GC.v.0), Britisches Pfund (6B.v.0), GBP/USD-Spot, Bitcoin (BTC/USDT)
- **Stichprobe:** ES/NQ 1-Min 2010–2026, GC/6B 1-Min 2016–2026, BTC 1h 2017–2026

## 1. Hypothese

Acht publizierte/praktiker-belegte Intraday-Edges (Zarattini-OR-Breakout,
Zarattini-Noise-Area, Index-VWAP-MR, Gap-Fade, Session-Breakout, ICT-Judas-Swing,
Crypto-Trend, Post-News-Fade) liefern auf **einem** liquiden CFD-Instrument netto
nach Spread einen positiven Sharpe und ein 5 %-Trailing-konformes Drawdown-Profil.

## 2. Makro-Begründung

Behavioral (Unter-/Überreaktion → Intraday-Continuation bzw. -Reversion) +
strukturell (Eröffnungs-/Session-Auktionen bündeln Order-Imbalance,
Liquiditätszwänge). Die Begründungen sind dokumentiert — der Test entscheidet.

**Bestands-Prior (robuster Reject):** Die Richtung eines einzelnen liquiden
Marktes intraday ist netto kostenfrei ≈ 0 (0012-0015, 0038-0041, 0049 — fünf
unabhängige Bestätigungen). Der Batch ist explizit als „umgeht-Reject" mit neuen
Winkeln (Peer-Evidenz, Konditionierung, liquideres Instrument) aufgenommen; die
**CFD-Spread-Kostenwand ist das Pflicht-Gate**, nicht der Ausschlussgrund.

## 3. Regeln & 4. Kosten

Pro Idee unten. **Kostenmodell (neu, `quantlab.costs`):** `CFD_INDEX` 3 bps RT
(identisch zur MES-Wand — eine CFD-Idee bekommt keinen leichteren Maßstab als der
Future), `CFD_GOLD` 4 bps RT, `CFD_FX` 1,6 bps RT, `CFD_CRYPTO` 20 bps RT.
Decision-time-safe: Signal auf Bar i, Position frühestens auf Open von Bar i+1.

## 5. Ergebnisse je Idee (brutto zuerst — der „4-Zeilen-Killer", Lehre 0049)

### I0067 — 5-Min Opening-Range-Breakout (Zarattini, behauptet Sharpe 2,81)
Reproduktion auf ES/NQ/GC, Long+Short, Time-Exit zum Close, plus Konditionierung
(Relative-Volumen-Tercil, OR-Weite, R-Targets).

| Instrument | brutto Ø/Trade | brutto per-Trade-Sharpe | bestes konditioniert (brutto) | netto |
|---|---:|---:|---|---:|
| ES | −0,07 bps | −0,002 | hi-OR-Volumen +1,77 bps | alle < 0 |
| NQ | +1,18 bps | +0,018 | hi-OR-Volumen +2,53 bps | alle < 0 |
| GC | +0,97 bps | +0,025 | wide-OR +2,10 bps | alle < 0 |

**Stufe 2 (CTI-Adaption) abgelehnt.** Reproduziert exakt 0039 (OR-Breakout auf
einem Einzelinstrument brutto ≈ 0). Der beste konditionierte Brutto-Puls (+2,5 bps,
NQ hi-Volumen) liegt **unter** der 3-bps-CFD-Wand → netto überall negativ.

#### Stufe 1 — Faithful Querschnitts-Reproduktion (das eigentliche Original)
Die behauptete Sharpe 2,81 sitzt in einem **Aktien-Querschnitts-Portfolio**, nicht
im Einzel-Timing. Daher die Originalform nachgebaut (`e8_stocksinplay_orb.py`):
**50 liquide Nasdaq-Namen 1-Min 2018-2026** (Databento XNAS.ITCH, ~$30), täglich die
**Top-10 „stocks in play"** nach Relative-Volumen (erste 5 Min vs. 20-Tage-Baseline),
5-Min-ORB long+short, Stop = gegenüberliegende OR-Grenze, **Risikoparität** (jede
Position 0,5 % Risiko, Portfolio-Tagesrendite = Σ R-Multiples), flat zum Close.

| | ann.Sharpe | CAGR | MaxDD | meanR/Tag | Beta vs SPY |
|---|---:|---:|---:|---:|---:|
| **brutto** | **+0,62** | +18,5 % | −78 % | +0,197 | +0,03 |
| netto (IBKR 4 bps RT) | −0,77 | −32 % | −98 % | −0,244 | — |

IS 2018-22 brutto-Sh −1,07 / OOS 2023-26 −0,32 (netto). **Befund:** Im Querschnitt
existiert ein **echter, marktneutraler Brutto-Edge** (meanR +0,02/Trade, Sh 0,62) —
**den der Einzelinstrument-Test (brutto ≈0) komplett verfehlt.** ABER: (a) **weit
unter den behaupteten 2,81**, (b) **netto negativ** (winziges R/Trade × kleine OR-
Risk = hohe Kosten-in-R), (c) −78 % Brutto-MaxDD = instabil.

**Warum die Lücke zu 2,81:** das Paper nutzt ein **Universum von tausenden Aktien**;
„stocks in play" = Namen mit *abnormalem* Volumen/News an dem Tag (oft Small/Mid-Cap).
50 immer-liquide Mega-Caps können diese Selektion strukturell nicht abbilden.

**Robustheits-Sweep** (`e8b_sweep.py`, `results/stocksinplay_sweep.txt`):
- **Diversifikation = Treiber:** brutto-Sharpe steigt mit Positionszahl (TOP_K 5/10/20
  → 0,77 / 0,62 / 0,87) — genau die Paper-These (viele dekorrelierte Wetten).
- **Der „stocks in play"-Filter SCHADET auf diesem Universum:** rvol≥0 (nur Ranking)
  brutto 0,62-0,87 → rvol≥1,5 kollabiert auf 0,10-0,30 → **rvol≥2,5 wird negativ
  (−1,4 bis −1,7)**. Auf Mega-Caps sind Hoch-Relative-Volumen-Tage (News/Earnings)
  choppy/reversal statt clean continuation — der zentrale Selektions-Mechanismus des
  Papers funktioniert auf Mega-Caps INVERS. Stärkster Beleg, dass das Universum (nicht
  die Mechanik) die 2,81 trägt.
- **Regime-abhängig:** brutto-Sharpe je Jahr 2018 **+2,31** / 2019 +1,29 / 2020 −1,16
  / 2021 −0,37 / 2022 −0,03 / 2023 −1,16 / 2024 +1,43 / 2025 +2,18 / 2026 +3,85. Stark
  2018-19, **tot 2020-2023**, wiederbelebt 2024-26 — kein stabiler Edge, Regime-Switch.
- **Kostenkritisch:** netto-positiv nur bei ~1 bp RT (TOP_K20 +0,41 / TOP_K5 +0,53);
  bei realistischen 4 bps (IBKR liquide Aktie) überall netto negativ.

**Verdikt I0067:** Stufe-1-Edge **real, aber schwach (Sh 0,62 brutto, nicht 2,81),
regime-abhängig (tot 2020-2023), kosten-tot bei realistischen 4 bps** und auf dem
falschen Universum (Mega-Caps invertieren die „stocks in play"-Selektion). Stufe 2
(CTI) ohnehin nicht handelbar (keine Einzelaktien-CFDs). **Korrektur ggü. erstem
Urteil:** nicht „Signal leer", sondern „realer, aber schwacher + instabiler +
kosten-toter Querschnitts-Edge; die 2,81 hängt am breiten Tausende-Aktien-Universum,
das 50 Mega-Caps nicht abbilden — und ist retail nach Kosten nicht erreichbar".
Methodisch der Kern: Stufe 1 (Originalform) MUSS vor jedem Reject getestet werden;
ein Stufe-2-(Adaptions-)Reject ist KEIN Edge-Reject.

### I0068 — Intraday-Momentum „Noise-Area" (Zarattini, SPY-Sharpe 1,33 / 3,50 @VIX>40)
Faithful: Band = Open ± σ·Ø|Move(min)| aus den letzten 14 Sessions; long über
oberer Grenze, short unter unterer, sonst Halten; flat zum Close. **Stärkste
Einzel-Instrument-Peer-Evidenz des Batches** (SPY-Ebene, nicht Querschnitt) — daher
besonders sorgfältig reproduziert (Re-Test-Disziplin IDEAS-HANDOFF §4).

| Variante | Trades/Tag | brutto Tages-Sharpe (ann.) | netto |
|---|---:|---:|---:|
| ES σ=1,0 (reines Band) | 1,6 | **−0,68** | −1,63 |
| NQ σ=1,0 (reines Band) | 1,5 | **+0,21** | −0,51 |
| VIX>40 (ES/NQ) | — | — | netto negativ |

**Verdikt: abgelehnt.** Erste Implementierung über-tradete (12–30 Wechsel/Tag durch
per-Bar-VWAP-Flatten); nach Korrektur auf die paper-treue Niederfrequenz (~1,5
Trades/Tag) ist das **Brutto**-Signal leer: ES negativ, NQ nur +0,21 — also nicht
einmal über die beiden Indizes robust positiv, weit von der behaupteten 1,33. Das
VIX>40-Regime rettet es nicht (netto negativ). Bestätigt 0040 (Intraday-
Autokorrelation ≈ 0); die SPY-Ergebnisse des Papers reproduzieren auf ES/NQ-Futures
2010-2026 nicht in handelbarer Stärke.

### I0069 — Index Intraday Mean-Reversion (VWAP-Fade)
Fade Close > VWAP + k·σ (short) / < VWAP − k·σ (long), Stop weiter draußen, Ziel
VWAP-Rückkehr, Time-Exit zum Close. k = 1,5/2,0/2,5.

| Instrument | brutto Ø/Trade | brutto per-Trade-Sharpe | netto |
|---|---:|---:|---:|
| ES (k=1,5…2,5) | −0,63…−0,84 bps | −0,028 | −3,6…−3,8 bps |
| NQ (k=1,5…2,5) | −1,00…−1,48 bps | −0,035 | −4,0…−4,5 bps |

**Verdikt: abgelehnt.** Brutto **negativ** über alle Schwellen: Index-Intraday-
Extensions über VWAP **kontinuieren**, sie reverten nicht (bestätigt die 0013-
Messung „Extreme laufen weiter"). Das negative Vorzeichen wird NICHT umgedreht-und-
neu-gefittet (Lehre 0047: das wäre In-Sample-Overfit; das gespiegelte Signal =
Momentum ist exakt das kostenwand-gefangene I0067/I0068).

### I0070 — Gap-Fill-Fade am Open
Bei |Open/Vortages-RTH-Close − 1| ≥ thr Fade Richtung Vortages-Close (= Gap-Fill-
Ziel), Stop jenseits des Open-Extrems. thr = 0,1/0,3/0,5 %.

| Instrument | brutto Ø/Trade (thr 0,1→0,5 %) | netto |
|---|---:|---:|
| ES | −0,76 → −4,29 bps | −3,8 … −7,3 bps |
| NQ | −0,29 → −1,55 bps | −3,3 … −4,6 bps |

**Verdikt: abgelehnt.** Brutto **negativ** und mit Gap-Größe schlechter: Index-Gaps
**füllen intraday nicht** (sie kontinuieren) auf ES/NQ-Futures 2010-2026 — bestätigt
0038. Das RTH-gefilterte erste Bar ist der echte Cash-Open (Lehre 0038 erfüllt).

### I0071 — Session-Breakout (Asien-Range → London-Open, FX + Gold)
Bruch der 00–07-UTC-Range nach 07:00 UTC, Stop Gegenseite, R-Target 1/2R.

| Instrument | brutto Ø/Trade | brutto per-Trade-Sharpe | netto |
|---|---:|---:|---:|
| 6B (GBP-FX) | +0,5…0,8 bps | +0,016…0,025 | −0,8…−1,2 bps |
| GC (Gold) | +0,6…1,1 bps | +0,011…0,019 | −2,9…−3,4 bps |

**Verdikt: abgelehnt.** Kein Brutto-Edge (per-Trade-Sharpe ≈ 0,02 = Rauschen);
selbst auf engen FX-Spreads (6B) netto negativ. Session-Übergang als Trigger trägt
keine handelbare Imbalance.

### I0072 — ICT Judas-Swing / Silver-Bullet (Killzone-Sweep→BOS)
Wiederverwendung der auditierten 0069-SMC-Engine (asymmetrisches 8/4-Pivot, Sweep→
BOS→Retest) auf 5-Min-Bars, beschränkt auf London- (07–10) und NY-Killzone (12–15).

| Instrument | Killzone | Ø-R brutto | Ø-R netto | netto-Sharpe |
|---|---|---:|---:|---:|
| ES | London / NY | +0,04 / −0,03 | −0,02 / −0,07 | −0,16 / −0,33 |
| NQ | London / NY | +0,20 / +0,08 | +0,14 / +0,03 | +0,07 / −0,07 |
| GC | London / NY | −0,10 / +0,16 | −0,18 / +0,10 | −0,41 / +0,08 |

**Verdikt: abgelehnt.** Streuendes Quasi-Null, kein Killzone-Instrument mit
handelbarem netto-Edge (bestes NQ-London netto-Sharpe +0,07 = Rauschen, Win 0,33).
Bestätigt 0069: Indizes = Beta/Null, nur BTC war dort marginal.

### I0073 — Bitcoin Intraday-Trend-Continuation + Montag-Asien-Open
Donchian-Breakout (N=20/55/100) mit ATR-Trailing auf BTC 1h; L/S, Long-only-Check,
Montag-Asien-Gate. `CFD_CRYPTO` 20 bps RT.

| Variante | brutto Tages-Sharpe | netto Tages-Sharpe |
|---|---:|---:|
| Buy&Hold BTC (Benchmark) | **0,70** | 0,70 |
| Breakout N=100 ATR×3 L/S | +0,65 | +0,04 |
| Breakout N=55 ATR×3 Long-only | +0,67 | +0,08 |
| Montag-Asien-Gate | −0,02 | −1,08 |

**Verdikt: abgelehnt.** Brutto-Trend real (Sharpe ~0,6), aber die 20-bps-Krypto-CFD-
Spreadwand (härteste des Batches, 0012-0015) frisst den L/S-Edge; die einzigen
netto-Überlebenden sind **long-biased ≈ Beta-Bruchteil** und liegen klar unter
Buy&Hold (0,70). Montag-Asien-Konditionierung trägt nichts (negativ). Bestätigt
0012-0015 Kostenwand + 0015 Beta-Maskerade.

### I0074 — Post-News-Vol-Stabilisierung (FOMC-Teilmenge)
Entry T+5 Min nach der 14:00-ET-FOMC-Ankündigung, Fade des Spike-Extrems ODER
Continuation, Hold 30/60/120 Min. Auditierte FOMC-Liste (0052) + ES 1-Min, n=109
Events (2012+). NFP/CPI **daten-blockiert** (keine freie, survivorship-sichere
PIT-Konsens-Surprise-Quelle).

| Modus | brutto (Hold 30/60/120m) | per-Trade-Sharpe | bestes netto |
|---|---:|---:|---:|
| Fade | −0,46 / −2,76 / −2,66 bps | −0,03 | alle < 0 |
| Continuation | +0,46 / +2,76 / +2,66 bps | +0,04 | −0,24 bps (60m) |

**Verdikt: abgelehnt (exploratorisch).** Das **Fade**-Bein verliert brutto — die
FOMC-Reaktion **kontinuiert**, sie klingt nicht ab (gegen die Idee). Das
Continuation-Bein ist brutto winzig positiv (+2,76 bps), liegt aber **unter** der
3-bps-CFD-Wand → netto negativ; n=109, per-Trade-Sharpe 0,04 = Rauschen. Kein Edge.

## 6. Signifikanz

Keine Idee erreichte die Brutto-Hürde, ab der die volle Batterie (Permutation /
Bootstrap-KI / DSR) sinnvoll wäre — der Brutto-Edge ist überall ≈ 0 oder
kostenwand-gefangen. Die Batterie wird nur an Brutto-Überlebenden gefahren (Lehre
0049: der 4-Zeilen-Brutto-Killer spart die Schein-Präzision eines Vollreports).

## 7. Robustheit

Über alle Instrumente (ES/NQ/GC/6B/BTC), Parameter (OR-Länge, σ, N, R-Targets,
Killzonen) und Konditionierungen (Volumen, OR-Weite, VIX-Regime, Montag-Asien)
konsistent: **brutto ≈ 0 bis schwach, netto negativ.**

## 8. Verdict

**8/8 abgelehnt.** Der gesamte Prop-Challenge-Batch reproduziert den robustesten
Reject des Katalogs: die Intraday-**Richtung** eines einzelnen liquiden Marktes ist
netto nach CFD-Spread nicht handelbar. Peer-Evidenz (Zarattini 2,81 / 1,33) und
neue Konditionierungs-Winkel ändern das nicht — die starken Paper-Sharpes hängen an
**Querschnitt-Diversifikation** (I0067) bzw. einer **SPY-Periode/Mikrostruktur**
(I0068), die auf ein Einzelinstrument nicht übertragbar ist. Bleibender Gewinn:
die CFD-Kostenmodelle (`CFD_INDEX/GOLD/FX/CRYPTO`) als Schritt-0-Gate für jede
künftige CTI-Idee.
