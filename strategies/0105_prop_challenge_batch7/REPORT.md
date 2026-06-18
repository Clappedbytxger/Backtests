# 0105 — Prop-Challenge Batch 7 (I0089–I0091, Multi-LLM-Review-Ernte)

**Datum:** 2026-06-18 · **Universum:** CTI-1-Step-CFD (FX/Index) · **Quelle:** `D:\Backtest Ideas\ideas\prop-challenge-batch7.md` (#s40)

Batch 7 erntet die drei genuin wertvollen, strukturell-dekorrelierten Sleeves aus
vier hochgeladenen LLM-Research-Dokumenten (~32/40 LLM-Strategien waren Intraday-
Richtung eines Einzel-CFD = die 9× bestätigte Kostenwand → vom Researcher schon
aussortiert). Getestet mit der Projekt-Batterie (Kosten-Gate, Permutation gegen
Zufalls-Timing, IS/OOS, Bootstrap-KI, Fat-Tail-/Beta-Check).

## Endstand

| ID | Strategie | Verdikt | Kernzahl |
|----|-----------|---------|----------|
| I0089 | AUDNZD-Kointegrations-MR | **rejected** (Daily) | corr(−z, fwd) ≈ 0 über alle LB/H; ADF-gated 25 Trades meanR −28 bps; M30-Original daten-blockiert |
| I0090 | FX-Carry + Momentum (Re-Test I0020) | **rejected** | Spot-Timing Sharpe −0,14; +3 %/J Carry hebt nur auf ~0; MaxDD −32 % |
| I0091 | Overnight-Gap-Reversal Index | **weak diversifier / overlay-Kandidat** | netto +15 bps/Trade, perm p 0,01–0,04, DSR 0,96 — ABER Crash-Bounce-konzentriert |

**Keine Standalone-Leads.** Ein realer, aber regime-konditionierter Diversifikator
(I0091). Bestätigt die Programm-Meta-These: Einzel-CFD-Intraday-Richtung + dünne
Faktoren tragen nicht; der einzige Puls sitzt in einer beta-nahen, niederfrequenten MR.

---

## I0089 — AUDNZD-Kointegrations-Mean-Reversion → REJECT (Daily)

USD-freier Cross, der selbst der mean-revertierende „Spread" sein soll. Faithful als
z-Score-MR gebaut (`e1_audnzd_coint_mr.py`): `z=(Close−SMA60)/std60`, Long z<−2 /
Short z>+2, Exit |z|<0,5, Stop |z|>3,5 o. 35 Pips, Time-Stop 30 T, **rollendes
ADF-/Half-Life-Gate** (handeln nur bei live bestätigter Stationarität — der klassische
RV-Fehler ist full-sample-Stationarität anzunehmen).

**Befund (sauberes Null, kein Bug):** Vor jedem Urteil die reine Reversions-Eigenschaft
exploriert (Handoff §4): **`corr(−z, fwd-Return) ≈ 0` über jedes Lookback (20–90) ×
jeden Horizont (1–20 T)**, und die bedingten Forward-Returns sind häufig *gleich*
gerichtet (E[fwd|z<−2] und E[fwd|z>2] beide positiv = Drift, **keine** Reversion). Der
z-Score hat null Prognosekraft. Backtest folgerichtig: ADF-gated 25 Trades Win 20 %,
meanR −28 bps; ungated 290 Trades meanR −16 bps; perm p 0,97. Die niedrige Win-Rate
ist NICHT Implementierung, sondern Konsequenz von Stops/Time-Stop auf einer
nicht-revertierenden Reihe.

**Vorbehalt (ehrlich):** Geminis Original war **M30**; die Halbwertszeit/Reversion
könnte intraday leben. yfinance liefert M30 nur ~60 Tage → **nicht testbar** auf freien
Daten. Daher: Daily-Form (die der Spec als robusten Test verlangte) = null; **M30-Form
daten-blockiert.** Die strukturelle Kointegrations-These hält auf Tagesbasis nicht.

## I0090 — FX-Carry + Momentum-Filter → REJECT (Re-Test I0020 bestätigt)

DeepSeek-S5-Winkel: auf dem CFD-Konto IST der Übernacht-Swap die Carry. Ehrliches
Re-Test-Design (`e2_fx_carry_mom.py`): zuerst **Spot-only** (trägt der EMA20+ADX-
Trendfilter auf AUDJPY/NZDJPY/AUDCHF auf dem Preis allein?), dann **Carry-Accrual
gesweept** {0 / +1,5 % / +3 %/J} — die CTI-Swap-Tabelle ist das Kill-Gate, also nie
angenommen.

**Befund:** Spot-Timing **negativ** (Korb-Sharpe −0,14; AUDCHF −0,37). Selbst die
optimistischen **+3 %/J Netto-Carry** (über realistischem CFD-Netto-Swap nach Broker-
Markup) heben den Korb nur auf **Sharpe +0,03 / CAGR +0,02 %** — Break-even. **MaxDD
−32 %** zeigt das Carry-Unwind-Crash-Risiko (CHF-/JPY-Spikes). Der CFD-Swap-Winkel
rettet I0020 nicht: der Trendfilter ist ein Drag, und realistischer Netto-Swap kann ihn
nicht tragen. Bestätigt 0048/0083 (Carry real-aber-schwach + crash-anfällig) und
disqualifiziert via −32 % MaxDD ohnehin fürs 10-%-CTI-Limit.

## I0091 — Overnight-Gap-Reversal Index → WEAK DIVERSIFIER / OVERLAY-KANDIDAT

ChatGPT-S8/DeepSeek-S9 (unabhängig konvergiert). Fade einer Vortages-Überreaktion:
Long wenn Tages-Ret<−1,5 % ∧ RSI(2,D)<10; Short spiegelbildlich; Entry t+1-Open, Exit
t+1-Close o. 1×ATR(10)-Ziel, Stop 1,5×ATR(10). Index-Spread 3 bps, **kein Overnight-
Swap** (Open→Close, swap-arm). `e3_overnight_gap_reversal.py`, ^GSPC/^DJI/^NDX 1995-2026.

**Real (besteht die Batterie):** netto **+14–18 bps/Trade**, Win 52–53 %, perm
(Random-Sign) **p 0,01–0,04**, **DSR 0,96** (n_trials=9), IS/OOS-Mean **15,7/16,8 bps =
stabil**, Top-5-Trades nur 18 % des PnL (**kein** Fat-Tail-Lottery), Look-ahead-frei.
Kombi-Buch ~37 Trades/J → Kosten **nicht** bindend (anders als unkonditionale Intraday-
Richtung 0012-0015/0038-0041 — dies ist konditionale MR, niederfrequent).

**Warum trotzdem kein Standalone-Lead (ehrlich):**
1. **Crash-Bounce-konzentriert:** die Jahres-PnL sitzt fast vollständig in **2002
   (+57 %), 2008 (+58 %), 2020 (+51 %)** ≈ die gesamte 189-%-Summe; ruhige/Grind-Bär-
   Jahre flach bis negativ, insb. **2022 −19 % / 2023 −9 %** + schwaches 2021-2024.
   = ein Hoch-Vol-Dip-Buy-Harvester, kein gleichmäßiger Edge.
2. **Win 53 % ≪ die im Spec geforderten >65 %** für ein RRR<1 — es überlebt nur, weil
   **970/1161 Exits Zeit-Close** sind (nicht das ATR-Ziel): der Edge ist die Open→Close-
   Reversion, nicht die RRR-Mechanik.
3. **Equity-Beta-nah** (Dip-Buying), aber **corr nur +0,29/+0,33 zum lebenden I0076/
   I0083 RSI-2-MR** → teilweise dekorreliert, kein reines Duplikat.

**Verdikt:** realer, aber vol-regime-konditionierter (Crash-Bounce) MR-Sleeve mit
jüngstem Zerfall → **schmaler Diversifikator/Overlay-Kandidat** (zahlt in Crashes, wenn
Beta-Sleeves bluten), **nicht** als Standalone-Bein fürs Buch promotbar.

---

## Querschnitt / Lehren
- **Reproduktions-Treue (Handoff §4) zahlte sich aus:** I0089s Win-20 %-Backtest sah nach
  Bug aus; der `corr(−z,fwd)`-Explore tötete die Hypothese sauber (Drift statt Reversion)
  und zeigte zugleich, dass es **kein** Bug war.
- **Re-Test-Disziplin (I0090):** Spot-Timing von der Carry-Accrual trennen + Carry sweepen
  statt annehmen — so wird sichtbar, dass weder das Timing noch realistischer Swap trägt.
- **Ein positives Ergebnis (I0091) erst nach Fat-Tail-/IS-OOS-/Beta-Batterie werten** —
  der Crash-Jahres-Breakdown ist der entscheidende Read, nicht der Headline-Sharpe.

Externe Korroboration ohne neuen Eintrag: Gold/Silber-Ratio (ChatGPT-S6) bestätigt
I0082; EURUSD/GBPUSD-Kointegration (DeepSeek-S6) bestätigt I0085.
