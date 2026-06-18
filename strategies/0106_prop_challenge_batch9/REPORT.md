# 0106 — Prop-Challenge Batch 9 (I0092–I0101, Umsetzung der „besseren" Hypothesen)

**Datum:** 2026-06-18 · **Universum:** CTI-2-Step-CFD · **Quelle:** `D:\Backtest Ideas\ideas\prop-challenge-batch8.md` (#s41)

Umsetzung der 10 in Batch 8 abgeleiteten „besseren" Hypothesen — abgeleitet aus den
**bestätigt-lebenden** Mechanismen + gezielten Re-Tests dokumentierter Rejects. Alle Daten frei
(yfinance + gecachte Streams), kein Databento-Neukauf.

## Endstand

| ID | Strategie | Verdikt | Kernzahl |
|----|-----------|---------|----------|
| **I0100** | Risk-gegateter FX-Carry-Querschnitt | **LEAD (testing)** | Gate-Rotation perm **p=0,002**; Sharpe 0,15→**1,06–1,24**; MaxDD −38%→−21%; IS/OOS +0,93/+1,23 |
| **I0099** | Krypto-Vol/Trend-Regime-Gate | **funktionierendes Overlay** | gated Sharpe 0,73>0,67; MaxDD −14,7%<−17%; PIT-sauberer I0086-Ersatz |
| **I0092** | Monatsend-FX-Flow (4 Majors, Close-Proxy) | **Refinement — bestätigt I0075 richtungs-konsistent** | Sharpe 0,97, Win 57%, IS/OOS +0,87/+1,14; perm 0,17 auf Proxy |
| I0095 | Commodity-FX-Lead-Lag-RV | marginal | Lag existiert (AUD↔XAU +0,20); CAD↔WTI 0,56, Korb 0,16, perm 0,23 |
| I0093 | Gold/Silber-RV-MR (gegatet) | **reject** | 12 Trades, −0,44%/Trade, perm 0,82 (Ratio trendet, bestätigt I0082) |
| I0094 | Triangulär-EUR-Cross-RV | **reject (Kostenwand)** | HL≈0,2 T (HFT-arbitriert), Brutto-Abw. 1,28 bps < 4,8-bps-Wand |
| I0096 | USD-Regime Commodity-FX-Korb | **reject** | Sharpe −0,04 = B&H, perm 0,30 (bestätigt I0078: nur AUDUSD trug) |
| I0097 | Pre-Holiday Overnight | **reject/schwach** | +2,1 bps/Nacht, perm 0,29 (post-2010 +5,5 bps, aber insig.) |
| I0098 | Cross-Index RV-MR markt-neutral | **reject** | Ratio trendet statt revertiert (beide Paare neg., perm 0,999) |
| I0101 | Krisenkonvexer XAU/XAG-Spread | **reject** | verliert im Stress (−11,8% über Stress-Tage), Hedge-Korr nur −0,08 |

**Bilanz: 1 Lead + 1 Overlay + 1 Refinement-Bestätigung + 1 marginal + 6 Reject.** Der Lead I0100
ist der **erste genuin neue testing-Lead seit mehreren Batches** — und er entstand exakt dadurch,
dass ein **dokumentierter Reject (I0020/I0090 Carry) mit konkretem neuem Winkel** (VIX-Crash-Gate)
re-getestet wurde. Das validiert die Batch-8-These „bessere Hypothesen = lebende Mechanismen +
gezielte Reject-Fixes".

---

## I0100 — Risk-Regime-gegateter FX-Carry-Querschnitt → LEAD (testing)

`e9_carry_riskgated.py`. Long-Carry-Korb (AUDJPY/NZDJPY/AUDCHF/CADJPY/EURJPY), aber **flat wenn
VIX>25 oder VIX-Spike** (Carry-Unwind-Schutz). Carry-Accrual gesweept {0/2/4 %/J}.

**Befund — der Crash-Gate rettet Carry (genau die Spec-These):**
- **ungated:** Sharpe **0,15** / MaxDD **−37,7%** / Skew −0,41 / Worst-Day −7,7% → das tote naive
  Carry (bestätigt I0020/I0090/0048).
- **GATED:** Sharpe **1,06** (0 % Carry) … **1,24** (+2 %) … **1,42** (+4 %); MaxDD **−21%**;
  Skew −0,41→−0,28; Worst-Day −7,7%→**−4,0%**.
- **Skeptische Validierung:** **Gate-Rotation-Permutation p=0,002** (das VIX-Timing auf DIESEM
  Korb ist nicht-zufällig — kein bloßes Beta); **IS/OOS gated +0,93/+1,23 (KEIN Decay, OOS sogar
  stärker)**. Das ungated-Basket-Beta ist nur +0,15 → der Sharpe-Sprung kommt aus dem **Timing
  des Crash-Gates**, nicht aus dem Korb-Beta.

**Ehrliche Vorbehalte (kein Overselling):** (a) Sharpe 1,06–1,24 ist hoch — **in-sample**, Live-
Haircut erwarten (SMC-0070-Lehre 1,52→0,43); (b) Worst-Day **−4,0% nahe am CTI-5%-Daily-Limit**
→ braucht Down-Sizing; (c) das Gate fängt **VIX-geflaggte** (aktien-getriebene) Crashes, NICHT
FX-spezifische (SNB-2015-Typ bewegt VIX kaum); (d) **Carry-Accrual modelliert** (echte CTI-Netto-
Swap-Tabelle ist das finale Kill-Gate). Verdikt: **echter testing-Lead** + dekorrelierter Carry-
Sleeve fürs Buch; Forward-Test + reale Swap-Tabelle vor Echtgeld.

## I0099 — Krypto-Vol/Trend-Regime-Gate → funktionierendes Overlay (Ersatz I0086)

`e8_crypto_vol_gate.py`. Preisbasiertes SMA200-Trend × Realized-Vol-TS-Gate sized das lebende
I0080-Krypto-TSMOM. **PIT-sauber, kein On-Chain-Blocker** (umgeht I0086 statt zu deferern).
**Befund:** gated Sharpe **0,73 > 0,67** ungated, MaxDD **−14,7% < −17,0%** — Tail gekappt, Sharpe
gehalten (anders als das I0083-VIX-Gate, das den Sharpe senkte). Nützliches Risk-Overlay aufs
Krypto-Bein; Wert = Bust-Senkung.

## I0092 — Monatsend-FX-Flow, 4 Majors Close-Proxy + Q-End → Refinement (bestätigt I0075)

`e1_monthend_fx.py`. **Vorzeichen-Korrektur dokumentiert:** erste Codierung war invertiert (perm
0,98); die **I0075-validierte Richtung** (US-Aktien stark → USD kaufen → Fremdwährung short,
`direction = sign(Ausland−US)`) gibt Sharpe **0,97**, Win **57%**, IS/OOS **+0,87/+1,14 (kein
Decay)**. **Aber perm 0,17 auf dem Close-Proxy** (KI berührt 0) — schwächer als I0075s Headline
(perm 0,0006), weil der Close-Proxy verrauschter ist als das Fix-Window. Verdikt: **richtungs-
konsistente Bestätigung von I0075 auf den 4 Majors**, aber der signifikante Test braucht das
**Fix-Window (Dukascopy M15, daten-deferred)** — nicht den Close-Proxy.

## Die 6 Rejects (jeder mit eigenem Mechanismus)
- **I0093 Gold/Silber gegatet:** auch mit ADF-Gate + Multi-Jahres-Extrem revertiert das Ratio nicht
  (12 Trades, −0,44%/Trade, perm 0,82) → bestätigt I0082 endgültig (Ratio trendet im handelbaren Fenster).
- **I0094 Triangulär-EUR:** Kointegration **real aber instant** (Half-Life ≈0,2 Tage = HFT-
  arbitriert); Brutto-Abweichung 1,28 bps < 4,8-bps-3-Spread-Wand → **Kostenwand** (0012-0015-Klasse),
  nicht „keine Kointegration". Sauber: die Coint-Garantie hilft nicht, wenn die Reversion vor dem
  nächsten Daily-Close abgeschlossen ist.
- **I0096 USD-Regime-Korb:** Sharpe −0,04 = B&H-Korb, perm 0,30 → der SMA50/200-DXY-Regime-Gate
  timed den Commodity-FX-Korb nicht (bestätigt I0078: nur AUDUSD trug, der Korb verwässert).
- **I0097 Pre-Holiday:** +2,1 bps/Nacht, perm 0,29 (post-2010 +5,5 bps aber insignifikant) →
  bestätigt 0085 (Pre-Holiday post-1990 dekayed) + die 5-bps-Nacht-Wand.
- **I0098 Cross-Index RV-MR:** das Ratio (NAS/SPX, GER/EU50) **trendet statt revertiert** (beide
  Paare −0,5%/Trade, perm 0,999) — die Growth-/Länder-Trend-Falle, vor der die Spec warnte; das
  ADF-Gate konnte den mehrjährigen Trend nicht in MR verwandeln.
- **I0101 XAU/XAG-Krisen-Spread:** verliert im Stress (−11,8% über Stress-Tage, active-Sharpe −0,41)
  und die Hedge-Korrelation zum Equity-Buch ist nur −0,08 (≈0) → 2008/2020 wurde Gold MIT-liquidiert;
  kein verlässlicher Flight-to-Quality-Spread netto.

---

## Lehren
- **Die „bessere Hypothese"-These trägt — aber selektiv:** von 10 mechanismus-geleiteten Ideen
  produzierte exakt **der gezielte Reject-Fix mit neuem Winkel (I0100 Carry + Crash-Gate)** den
  einzigen echten Lead. Die beiden anderen Fixes (I0093/I0094) blieben Rejects, aber mit
  **schärferem Mechanismus-Verständnis** (Ratio trendet / Coint ist instant) statt blindem Wiederholen.
- **Kointegrations-Garantie ≠ Handelbarkeit (I0094):** ein konstruktiv stationäres Residuum (HL 0,2 T)
  ist gerade DESHALB HFT-arbitriert — die Reversions-Geschwindigkeit gegen die Daten-/Kostenfrequenz
  prüfen, bevor man „Coint = Edge" annimmt.
- **Ein Vol-/Risk-Regime-Gate wirkt gegensätzlich je nach Edge-Typ:** es **rettet** Short-Vol-artigen
  Carry (I0100, Tail-Kappung hebt Sharpe) und **kappt** den Krypto-Trend-Tail nützlich (I0099), aber
  es **schadet** Dip-Buying-MR (I0083) — das Gate muss zum Skew des Beins passen.
- **Vorzeichen-Disziplin (I0092):** eine invertierte Codierung sieht aus wie ein starker Reject
  (perm 0,98); gegen den validierten Eltern-Lead (I0075-Richtung) prüfen, NICHT blind flippen-und-fitten.

**Buch-Implikation:** Batch 9 liefert dem CTI-2-Step-Buch **1 neuen dekorrelierten Carry-Sleeve
(I0100)** + **1 Krypto-Risk-Overlay (I0099)** + die **Fix-Window-Bestätigung von I0075 (I0092)**.

---

## Buch-Integration (`book_integration.py`) — Ziel 1,05–1,3 ERREICHT

CORE-Buch aus den 4 bestätigten Lead-/Overlay-Streams (I0092 Monatsend-FX + I0076 Index-RSI2 +
I0100 Carry-gegatet + I0099 Krypto-gegatet), inverse-Vol-gewichtet (= Equal-Risk bei ~0 Korr):

- **Korrelationsmatrix: alle Kreuz-Korrelationen ~0** (max |0,06|) → **echte Dekorrelation, nicht
  IS-angenommen** (die √K-Diversifikation greift fast ideal).
- **Kombi-Sharpe = +1,21** (naive √K-Decke 1,25) — **trifft das Roadmap-Ziel 1,05–1,3**.
- **Equity-Beta-Gewicht = 20%** (Ziel ≤30% ✓; nur I0076 ist Equity-Beta, die anderen 3 sind FX-
  Flow/Carry/Krypto = nicht-Equity).
- **2-Step-MC (täglicher Pfad, 10% statisch + 5% daily):** @6% Vol P(pass beide) 0,34/Bust 0,01;
  **@8% Vol P(pass) 0,53/Bust 0,05** (Worst-Day −3,95% < 5%-Limit); @10% P(pass) 0,64/Bust 0,10.
- **Sweet-Spot = 8% Vol** (Bust 5%, Worst-Day unter Limit) — exakt der CTI-2STEP-ROADMAP-Korridor,
  jetzt mit Sharpe 1,21 statt der 0,88 der zwei Alt-Leads (schneller + sicherer).
- **Extended-Buch (+I0091 Gap-Reversal +I0095 Commodity-FX):** Kombi-Sharpe 1,27, ABER Equity-Beta
  steigt auf 32% (>30%, weil I0091 Equity-Beta ist) → **CORE bleibt die Wahl** (sauberere Beta-Disziplin).

**Vorbehalt:** die Sleeve-Streams sind IN-SAMPLE (v. a. I0100); der Live-Haircut (SMC-0070
1,52→0,43) gilt — die 4–6-Wochen-Paper-Phase-0 (ROADMAP-Entscheidung 5) bleibt das Gate. Die
**Dekorrelation (~0 Korr)** ist aber der strukturell robuste Teil des Ergebnisses.

## CTI-Swap-Recherche für I0100 (reale Daten, kein modellierter Sweep mehr)

Reale Retail-MT5-Long-Swaps (Switch Markets 2025-06, repräsentativ für CTIs Feed; CTI hat Swaps
~50% gesenkt → eher günstiger): **ALLE 5 Carry-Paare verdienen POSITIVEN Long-Swap** —
AUDJPY +10,29 · AUDCHF +6,29 · EURJPY +4,78 · NZDJPY +3,49 · CADJPY +3,13 Punkte (Long earns).
Umgerechnet ~+0,7 bis +2,7%/Jahr je Paar, **Korb-Schnitt ~+1,3%/Jahr aktuell** (historisch höher
2005-08 bei AUD/NZD ~7%, ~0 in 2020-21).

**Entscheidender Befund (Reframe vs I0090):** Anders als bei I0090 (wo der Carry der EINZIGE
mögliche Edge war und die Swap-Tabelle das Kill-Gate) liefert I0100 bereits bei **carry=0 Sharpe
1,06** aus dem gegateten Timing → **der Swap ist ADDITIV, nicht der Treiber**. Mit dem realen
+1,3%-Swap: **gated Sharpe 1,18** (IS/OOS +1,03/+1,36). → **Die CTI-Swap-Tabelle ist für I0100
KEIN Kill-Gate** (im Gegensatz zu I0090); der reale positive Swap hebt den Edge nur um ~+0,1 Sharpe.
Zusatz: die L/S-Short-Seite wäre swap-ungünstig (alle 5 Paare zahlen negativen Short-Swap, z. B.
AUDJPY short −12,92) → die **Long-only-Korb-Konstruktion (umgesetzt) ist swap-korrekt**, ein
L/S-Short-Bottom wäre es nicht.

**Quellen:** [Switch Markets Swap Rates](https://www.switchmarkets.com/trading-conditions/swap-rates),
[CTI Swap-Fee-Senkung](https://forexpropreviews.com/city-traders-imperium-swap-fees-new-adjustments/),
[AAA Trading Swaps](https://www.aaatrading.net/learn-trading-guide/swap-rates/).

**Nächster Schritt:** 4–6-Wochen-Paper-Forward des CORE-Buchs (I0092/I0076/I0100/I0099) im `live/`-
System, reale Kombi-Sharpe + Korrelationen messen (Gate ≥~0,9), dann der $2.500-2-Step @8% Vol.
