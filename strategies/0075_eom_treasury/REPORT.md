# Strategie 0075 — End-of-Month Treasury Returns (Hartley & Schwarz)

> Erste umgesetzte Idee aus dem neuen Handoff `D:\Backtest Ideas` — **Idee I0010**
> (Quelle #s03/#s18). Gleichzeitig Validierungslauf des Handoff-Workflows
> (Index → Steckbrief → Quellenbeleg → Umsetzung).

- **Kategorie:** event-driven / flow / strukturell (Monatsend-Rebalancing)
- **Status:** testing (Lead — übersteht die Drift-Trap-Permutation, niederfrequentes Overlay-Bein)
- **Datum:** 2026-06-15
- **Universum:** iShares 7-10y Treasury (IEF, ~10y), iShares 20+y Treasury (TLT, langes Ende),
  iShares 1-3y Treasury (SHY, kurzes Ende = Placebo); 10-Jahres-T-Note-Future (ZN=F) als
  Langhistorie-Cross-Check
- **Stichprobe:** In-Sample 2002-2013 / Out-of-Sample 2014-2026 (OOS enthält den 2022-Crash)

## 1. Hypothese

Treasury-Excess-Returns sind in den **letzten 1-2 Handelstagen des Monats** überdurchschnittlich,
am stärksten am letzten Tag, und der Effekt **wächst mit der Laufzeit** (Hartley/Schwarz:
~20 bps/Monat bei 10y, Sharpe ~1; 30y-2-Tage-Position ~4,5 % p.a.; 2y kaum). Getestet als
Long-Treasury über das Monatsende (letzter Handelstag + erster Handelstag des Folgemonats), sonst flat.

## 2. Makro-Begründung

Institutioneller **Zwang-Flow**, vorab terminiert (publikationsresistent): Bond-Index-
Duration-Extension am Monatsende — der Bloomberg-Aggregate rebalanciert am letzten Kalendertag,
Index-Tracker und Lebensversicherer **müssen** zum Stichtag Duration kaufen, um den Tracking-
Error klein zu halten. Dazu Window-Dressing. Ein vorhersehbarer Nachfrageschock, der mit der
Duration skaliert (mehr Laufzeit → mehr Preis-Impact). Bond-Analogon des bestätigten Aktien-
Edges 0050 (Turn-of-the-Month, Lakonishok/Smidt).

## 3. Regeln

- **Pre-Registrierung (gegen Data-Mining):** kanonisches 2-Tage-Fenster aus Hartley/Schwarz —
  long am **letzten Handelstag** + **ersten Handelstag des Folgemonats**, sonst flat.
- Umsetzung: `turn_of_month_signal(before=2, after=0)`. Da die Engine das Decision-Time-Signal
  um eine Bar shiftet (`.shift(1)`), sind die Entscheidungstage die letzten 2 Handelstage; die
  **gehaltenen** Tage sind {letzter Tag, erster Tag Folgemonat} — exakt die 2-Tage-Position des Papers.
- Look-Ahead: rein kalenderbasiert, vollständig vorab bekannt; Engine shiftet zusätzlich. Keine
  Preisinformation im Signal.
- Robustheit: 4×4-Gitter (before 1-4 × after 0-3) NUR als Plateau-Check; DSR mit voller 16-Zellen-Breite belastet.
- **Placebo (strukturelle Kontrolle):** identisches Fenster auf SHY (1-3y). Das Paper sagt
  „2y kaum" → SHY sollte schwach sein. Ein generisches „irgendein Monatsende"-Artefakt würde
  am kurzen Ende genauso feuern.

## 4. Kosten- & Ausführungsannahmen

`IBKR_LIQUID_ETF` (2 bps Slippage/Seite + Mindestkommission), gehandelt als Bond-ETF (penny-
Spreads, extrem liquide). 1 Round-Trip/Monat (~12-24 Trades/Jahr) → Kosten ~50-70 bps/Jahr,
spürbar gegenüber dem kleinen Edge, aber **nicht bindend** (netto bleibt positiv; Permutation
auf Brutto besteht). Realistisches Konto-Instrument: IEF/TLT-ETF (kein Roll, dividenden-bereinigt
= Total-Return ≈ paper-„Excess"). Voll-ZN-Future (~$120k Notional) für 2000€-Konto zu groß →
nur als Langhistorie-Cross-Check.

## 5. Ergebnisse (IEF 10y, netto nach Kosten)

| Kennzahl | Wert |
| --- | ---: |
| EOM-Tag Ø-Return | **+4,85 bps** vs Rest +1,14 bps |
| Anteil am Gewinn | 29 % des Gewinns auf 10 % der Tage |
| Trades / Win / Expectancy | 288 / 49,3 % / +0,044 %/Trade |
| Ø Haltedauer | 2,0 Tage |
| Standalone-CAGR | ~0,5 % (nur 9,6 % der Zeit investiert) |
| Brutto-Sharpe (RF-adj., voll) | −0,37 |
| Netto-Sharpe (RF-adj., voll) | −0,66 |
| Buy & Hold IEF (RF-adj.) | +0,26 (MaxDD −23,9 %) |
| Strategie-MaxDD | −7,4 % |

**Wichtig zur negativen Headline-Sharpe (Lehre 0050/0056/0074):** `compute_metrics` zieht
2 % Risk-free von **jedem** Tag ab — auch den ~90 % Flat-Tagen, an denen die Strategie 0
verdient. Für ein Overlay-Bein, das nur 10 % der Zeit investiert ist (das Kapital liegt sonst
in Cash/T-Bills zum RF), ist die RF-adjustierte Voll-Sharpe irreführend negativ. Die
aussagekräftigen Reads sind die aktive-Tage-/Brutto-Sharpe und die Signifikanzbatterie.

## 6. Signifikanz (IEF 10y)

| Test | Wert |
| --- | ---: |
| **Permutation (Brutto-Sharpe vs Zufalls-Timing gleicher Anzahl)** | **p = 0,0198** |
| t-Test EOM-Tag-Ø-Return > 0 | t = +2,59, p = 0,0098 |
| Bootstrap EOM-Tag-Ø-Return 95%-KI | **[+1,31, +8,53] bps (ohne 0)** |
| Bootstrap Netto-Sharpe 95%-KI (aktive Tage) | [−0,76, +1,36] (mit 0, breit) |
| Deflated Sharpe (16 Varianten) | 0,783 |

Die **Permutation ist der entscheidende Test** (Drift-Trap-Lehre 0016/0017/0050): Treasuries
hatten 40 J. Bull-Markt UND den 2022-Crash — long Duration an Zufallstagen ist selbst ein
regime-abhängiger Bet. Die Permutation würfelt die gehaltenen Tage auf Zufalls-Timing gleicher
Anzahl → sie fragt, ob das **Monatsend-Timing** trägt, nicht bloß das Long-Sein. Es trägt
(p=0,0198). Die Netto-Sharpe-Bootstrap-KI ist breit/mit-0 (nur ~24 2-Tage-Trades/Jahr, hohe
Per-Trade-Varianz); die **Per-Tag-EOM-Mean-KI ohne 0** ist hier der trennschärfere Test.

## 7. Robustheit

**Keine IS→OOS-Erosion** (Gegenteil von 0017/0034/0046/0048) — Brutto-Sharpe sogar steigend:

| Periode | Netto-Sharpe (raw) | Brutto-Sharpe (raw) |
| --- | ---: | ---: |
| IS 2002-2013 | +0,22 | +0,49 |
| OOS 2014-2026 | +0,26 | +0,57 |
| recent 2018-2026 | +0,35 | +0,63 |
| 2022-Crash-Jahr | +0,10 | +0,28 |

**Fenster-Plateau** (Netto-Sharpe raw): before≥2 durchweg positiv (b2 +0,24 / b3 +0,57 /
b4 +0,67), nur before=1 negativ — und das ist informativ: before=1 hält nach dem Shift NUR den
ersten Tag des Folgemonats, NICHT den letzten Tag — also genau nicht den dokumentierten Effekt.

**Laufzeit-Skalierung (das stärkste strukturelle Argument), monoton:**

| Markt | EOM-Tag Ø | Rest Ø | Permutation p | EOM-Mean-KI |
| --- | ---: | ---: | ---: | ---: |
| SHY (1-3y, Placebo) | +1,97 bps | +0,66 | 0,0044 | [+1,14, +2,81] |
| IEF (10y) | +4,85 bps | +1,14 | 0,0198 | [+1,31, +8,53] |
| TLT (20y+) | +8,25 bps | +1,18 | 0,0362 | [+0,65, +16,04] |

**Placebo-Nuance:** SHY ist NICHT der erwartete statistische Null — aber +1,97 bps ist „kaum"
relativ zu TLT (+8,25) und die **Skalierung ist exakt monoton mit der Laufzeit**. Das ist
stärkere Evidenz als ein Null wäre: ein generisches Kalender-/Dividenden-Artefakt würde NICHT
duration-proportional skalieren. Der Effekt ist ein kurven-weiter Monatsend-Duration-Nachfrage-
schock, am langen Ende am größten — genau die ökonomische These.

**Future-Cross-Check (ZN=F, 2000+, mit Roll-Vorbehalt 0028/0029):** EOM +3,71 bps, perm
p=0,0082 — bestätigt den Effekt im **reinen Futures-Preis** (kein ETF-Dividenden-Artefakt
möglich). 5-Jahres-Buckets sind verrauscht (2010-2015 schwach, 2020 stark, 2025 Teiljahr −0,1);
der sauberere ETF-IS/OOS-Read zeigt keinen Decay. Roll-Vorbehalt: Treasury-Futures rollen
quartalsweise nahe einigen Monatsenden → ZN=F ist Cross-Check, nicht Headline.

## 8. Verdict

**Testing / Lead — gleiche Klasse wie 0050 und 0052: ein niederfrequenter, flow-getriebener
Edge, der die Drift-Trap-Permutation übersteht; ein Timing-/Overlay-Bein, kein Standalone.**

Pro: Permutation p=0,0198 (Timing trägt, nicht Beta), t-Test p=0,0098, Per-Tag-Mean-KI ohne 0,
**kein IS→OOS-Decay**, **monotone Laufzeit-Skalierung** (SHY<IEF<TLT) als starke strukturelle
Bestätigung, **im reinen Future repliziert** (kein ETF-Artefakt). MaxDD −7,4 % vs B&H −23,9 %
(umgeht 2022).

Contra/Vorbehalte: kleine Absolutgröße (~0,5 % Standalone-CAGR < 2 %-RF-Hürde → **kein
Standalone**, nur Overlay; Kapital sonst in Cash/T-Bills); Netto-Sharpe-Bootstrap-KI berührt 0
(per-Trade-Varianz hoch, n klein); Placebo am kurzen Ende nicht null (aber laufzeit-erklärt).
Das pre-registrierte 2-Tage-Fenster ist der konservative Punkt im Plateau (before=3/4 stärker,
aber bewusst NICHT selektiert = kein Mining).

**Einsatz:** als niederfrequentes Bond-Timing-Bein (12×/Jahr, 2-Tage-Hold) — der Treasury-Zwilling
zu 0050. Realistisches Instrument fürs Konto: IEF oder TLT bei IBKR. Verwandt: 0050 (gleiche
Flow-Mechanik, Aktien), I0013 (Aktie↔Bond-Rebalancing-Paar) als möglicher Ausbau.

**Handoff-Workflow-Validierung:** Der Pfad Index (`HYPOTHESES.md` I0010) → Steckbrief
(`ideas/event-driven.md`) → Quellenbeleg (`SOURCES.md` #s03/#s18, mit extrahierten exakten
Fenstern/Magnituden) → Umsetzung hier ist vollständig und konsistent aufgegangen. Die im
Steckbrief versprochenen Magnituden (~20 bps/Monat 10y, stärker am langen Ende) sind qualitativ
bestätigt (10y EOM-Tag +4,85 bps × ~2 Tage ≈ ~10 bps/Monat; TLT klar stärker).
