# 0102 — Prop-Challenge Batch 4 (Ideen I0075–I0079, CTI 1-Step)

**Datum:** 2026-06-17 · **Quelle:** `D:\Backtest Ideas\ideas\prop-challenge-batch4.md`

## Kontext & warum dieser Batch anders ist

Batch 3 (0101, I0067–I0074) war **8/8 Reject**: die Intraday-*Richtung* eines einzelnen
liquiden CFD ist netto nach Spread tot (5× bestätigt). Batch 4 zieht die Konsequenz und
mint **nicht** denselben toten Raum neu, sondern testet (a) **lebende Katalog-Edges** auf
CTI-handelbare CFDs portiert und (b) das **niederfrequente Daily-Swing-Profil**, das
`BATCH-3-RESULTS.md` selbst als CTI-Pfad benennt. **Ergebnis: 2 Leads, 1 Diversifikator,
1 Overlay, 1 Reject** — der erste produktive Batch der Prop-Schiene.

| ID | Strategie | Verdikt | Kernzahl |
|----|-----------|---------|----------|
| **I0075** | Monatsend-FX-Flow (WMR-Fix) | **LEAD (testing)** | Korb netto **+7,6 bps/Event**, perm **p=0,0006**, Boot-CI [4,1;14,4] ohne 0 |
| **I0076** | Daily-Index-MR (Connors RSI-2) | **LEAD (testing)** | Win **70 %**, netto **+22 bps/Trade**, perm-Random-Entry **p=0,002–0,026** (3/4) |
| **I0077** | Cross-Asset TSMOM | **Diversifikator (Originalform)** | Spec-Form über-tradet (brutto 0,15); klassisch 12M/monatl. brutto **0,74**, netto 0,23 |
| **I0078** | USD-Regime-Overlay | **Overlay (Originalform)** | 0086 repro **p=0,0025**; Batch-4-Gold/Index-Reframe = Drift-Falle (p>0,26) |
| **I0079** | Overnight-Ernte | **REJECT** | Brutto reproduziert 0051, aber CFD 5 bps/Nacht > Prämie → netto Sh −0,24 |

Kosten-Gate (Schritt 0, `quantlab.costs`): CFD-Spread RT FX 1,6 / Index 3 / Gold 4 bps
**plus Overnight-Swap** (Index/Gold ~2 bps/Nacht, FX ~0,5) für die gehaltenen Edges —
für I0077/I0079 ist der Swap so entscheidend wie der Spread für Intraday.

---

## I0075 — Monatsend-FX-Rebalancing-Flow (WMR 4pm-Fix) — **LEAD**

**Mechanik (Melvin & Prins 2015):** Ausländische Real-Money-Hedger stellen am Monatsende
(LBD, 16:00-London-Fix) ihre USD-Hedge-Ratio wieder her. Aktien im Monat gestiegen →
unter-gehedged → **USD-Verkaufsdruck**. Signal = `sign(Aktien-Monatsreturn bis LBD−1)`,
Korb = long EURUSD/GBPUSD/AUDUSD + short USDCHF/USDJPY (= short USD bei Aktien-up).

Zwei Reads (Stage-1-Reproduktion auf freien Daten):
- **Tages-Korb (5 Majors, 2003–2026, n=281 Events):** brutto **+9,2 bps/Event**, netto
  nach FX-Spread **+7,6 bps**, Win 59 %, Sharpe/Event 0,21 (≈ ann. ~0,72). **Drift-Trap-
  Permutation gegen Zufalls-Vorzeichen p=0,0006**, Bootstrap-Mean-CI **[+4,1;+14,4] bps
  ohne 0**. Der Edge sitzt im *Vorzeichen* (Aktien-Richtung), nicht im Beta.
- **GBPUSD M15 Fix-Fenster (15:00→16:30 London, 2016–2026, n=125):** brutto +4,6 bps,
  netto +3,0 bps, perm p=0,032 — **richtungs-konsistent und netto positiv**, aber die
  Bootstrap-CI [−0,2;+9,5] **berührt 0** (nur ein Paar, kürzere Historie). Der präzise
  Mikrostruktur-Read ist schwächer als der Tages-Korb, widerspricht ihm aber nicht.

**Verdikt LEAD:** Lebende, **decay-resistente** Flow-Edge (Mandats-Hedge-Zwang, kein
Crowding-Verfall) auf dem **billigsten CTI-Instrument** (FX 1,6 bps). Netto-positiv,
hoch-signifikant, dekorreliert zum Aktien-/Trend-Buch. Stärkster Batch-4-Kandidat.
**Vorbehalt:** Der Tages-Korb-Read enthält den ganzen LBD-Tag, nicht nur das Fix-Fenster;
für Live ist das exakte 15:00→16:30-Fenster + Vorzeichen die heikle Stelle (GBP-Fix-Test
positiv-aber-CI-grenzwertig). Nächster Schritt: M15-Daten für die restlichen 4 Paare
beschaffen, um den Korb auf Fix-Fenster-Ebene zu bestätigen.

## I0076 — Daily-Index-Mean-Reversion (Connors RSI-2 + SMA-200) — **LEAD**

Long-only auf US500/US30/NAS100/GER40 (Index-CFD): `Close>SMA200 ∧ RSI(2)<10 ∧
Close>0,9×Close[-5]` → Long am Close; Exit `RSI(2)>65 ∨ Close>SMA5`; Stop 2,5×ATR(14);
Time-Stop 10 Tage. Kosten: CFD-Index-Spread 3 bps RT + 2 bps/Nacht Swap (Ø 3 Nächte).

**Ergebnis (1995–2026, 1001 Trades gepoolt):** Win **70 %**, brutto +31 bps/Trade,
**netto +22 bps/Trade**, Sharpe/Trade 0,10 (≈ ann. ~0,69), Bootstrap-Netto-Mean-CI
**[+8,5;+34,9] bps ohne 0**. **Drift-Trap (Random-Entry-Permutation auf Uptrend-Tagen,
gleiche Exit-Mechanik):** US500 p=0,002, US30 p=0,004, NAS100 p=0,026 — das **RSI-2-
Überverkauft-Timing schlägt zufälliges Long-im-Aufwärtstrend**; nur GER40 p=0,156 (schwach).

**Verdikt LEAD:** High-Win/smooth — genau das Profil fürs enge 5 %-Trailing + Konsistenz-
Gate. Überlebt CFD-Spread **und** Overnight-Swap. **Vorbehalte (ehrlich):** (a) der Index-
Level-Edge ist schwächer als die ursprüngliche Aktien-Querschnitts-Version (lebt von
Kurzfrist-Reversion + ERP-Drift, nicht idiosynkratischer Überreaktion); (b) **alle 4 Beine
sind Equity-Beta → im Crash verlieren sie gleichzeitig** (keine echte Diversifikation,
anders als ein Aktien-Korb); (c) GER40 statistisch nicht signifikant. Standalone schmal,
aber als hoch-trefferquoten-Bein im Buch wertvoll.

## I0077 — Cross-Asset Daily TSMOM — **Diversifikator (Originalform), Spec-Form REJECT**

Spec: Dual-Sleeve `S=0,5·sign(Δ50)+0,5·sign(Δ200)`, vol-skaliert (10 %/Leg, Buch 6 %),
**wöchentlicher** Rebalance, 11-Asset-CFD-Korb (Index/Metall/Öl/FX).

- **Faithful Spec-Form:** brutto-Sharpe **nur 0,154** (< Einzel-Leg-Schnitt 0,20!), netto
  **−0,31**. Die **wöchentliche** Rebalance + 50/200-Dual-Sleeve **über-tradet** und mischt
  Signal mit Whipsaw-Kosten (Wiederholung der Turnover-Kalibrierungs-Lehre 0069/I0068).
- **Reject-not-final / Stage-1 (Originalevidenz #s04):** klassisches **12M-Signal,
  monatlicher** Rebalance → brutto-Sharpe **0,741** (= Jahrhundert-Evidenz reproduziert!),
  netto **0,232** nach Overnight-Swap. Krisen-konvex (2008 **+12,8 %** netto).

**Verdikt:** Die TSMOM-Edge **existiert** — die Spec-Form (wöchentlich, Dual-Sleeve) hat sie
durch Über-Rebalancing zerstört. In der **Originalform (monatlich/12M)** ist sie ein
**realer, swap-gedünnter, krisen-konvexer Diversifikator** (≙ Katalog 0068-Trend-Bein),
**kein Standalone-Lead** (netto-Sharpe 0,23 < die zwei echten Leads). **Methodik-Lehre
bestätigt: vor der Reproduktion den Turnover gegen das Paper kalibrieren** — die
Jahrhundert-Evidenz ist monatlich/12M, nicht wöchentlich/50-200.

## I0078 — USD-Regime-Richtungs-Overlay — **Overlay (Originalform), Reframe REJECT**

Port des lebenden 0086-Gewinners. Batch-4-Definition: `USD_down=(DXY<SMA200 ∧ DXY<DXY[-63])`
→ long XAUUSD/US500/NAS100/AUDUSD.

- **0086-Original reproduziert:** DXY-63d-Momentum<0 → Commodity/EM-Korb, **timed-Sharpe
  0,862 vs B&H 0,336, Drift-Trap-perm p=0,0025** — der lebende Edge bestätigt sich.
- **Batch-4-Reframe auf Gold/Index:** XAUUSD timed 0,13 vs B&H **0,69** (Filter *schadet*),
  US500 0,48<0,58, NAS100 0,54<0,76 — alle perm **p>0,26 = Drift-Falle** (das Regime gatet
  nur das Eigen-Beta/-Drift dieser Instrumente weg, kein Timing-Skill). **Einzige Ausnahme
  AUDUSD** (Commodity-FX ohne Eigendrift): timed 0,55 vs B&H 0,03, **perm p=0,004**.

**Verdikt:** Der Edge ist real, aber **nur in seiner Originalform** (Commodity-/Risk-FX-
Ausdruck: 0086-Korb + AUDUSD). Gold/Index als Ziel ist die klassische **Beta-Maskerade/
Drift-Falle** (Lehre 0016/0017/0076-GER40). Bestätigt 0086 als **Overlay-Kandidat** auf
Commodity-FX; der Batch-4-Gold/Index-Reframe wird abgelehnt.

## I0079 — Overnight-Risikoprämien-Ernte — **REJECT** (Re-Test 0051)

Long am Cash-Close, Exit nächster Open; konditioniert K1 (Uptrend) / K2 (Low-Vol).
Kosten ehrlich: 1 Spread-RT/Nacht (3 bps) **+** Overnight-Swap (2 bps) = **5 bps/Nacht**.

**Ergebnis (1995–2026):** US500 brutto **+3,95 bps/Nacht (Sharpe 0,92** = reproduziert
0051), aber netto **−1,05 bps (Sharpe −0,24)**; NAS100 brutto +2,95 → netto −2,05; US30
brutto leer. **Konditionierung K1/K2 rettet nichts** (netto-Sharpe überall negativ),
B&H schlägt alle (0,55–0,65).

**Verdikt REJECT:** Die Brutto-Overnight-Prämie ist real und reproduziert 0051 — aber die
**CFD-Kostenwand (Spread + Swap) übersteigt die Prämie**. Genau das vom Spec selbst
benannte ehrliche Gate: anders als beim physischen ETF zahlt man beim Cash-CFD die
Overnight-Finanzierung, die die Prämie spiegelt. Bestätigt 0051 + die Swap-Drag-These.

---

## Meta-Lehren des Batches

1. **Die richtige Schiene zahlt sich aus:** Batch 3 (Intraday-Richtung) 8/8 Reject; Batch 4
   (lebende/strukturelle Flow-Edges auf billigen Instrumenten) liefert 2 Leads + Diversifikator
   + Overlay. **Niederfrequenter, erzwungener Flow trägt** (Monatsend-FX), wo Intraday-Timing
   stirbt — die Programm-These des ganzen Katalogs erneut bestätigt.
2. **Reject-not-final wirkte zweimal:** I0077 (Spec-Form tot, Originalform brutto 0,74) und
   I0078 (Gold/Index-Reframe tot, Originalform p=0,0025) wären bei blindem Spec-Test
   fälschlich verworfen worden. **Turnover gegen das Paper kalibrieren; den Edge in der
   Originalform testen, bevor die Adaption zählt.**
3. **Der Overnight-Swap ist das Gate der gehaltenen CFD-Edges** — er killt I0079 direkt und
   dünnt I0077 (0,74→0,23). Für Trend/Carry auf CFD ist Financing so bindend wie der Spread
   für Intraday.
4. **Bestes gemeinsames Buch:** I0075 (FX-Flow, dekorreliert) + I0076 (Index-MR, high-win) +
   I0077-Originalform (krisen-konvex) + I0078 als Commodity-FX-Overlay — die Aggregat-Kurve
   passt zum engen 5 %-Trailing (FX-Flow und Trend dekorrelieren zum equity-beta-MR-Bein).

## Dateien
- `e1_monthend_fx.py` … `e5_overnight.py` — je eine Idee, eigenständig lauffähig.
- `_common.py` — CFD-Kosten (Spread + Swap), Wilder-RSI/ATR, Permutations-/Bootstrap-Helfer.
- `results/*.json` — Roh-Metriken je Idee + `summary.json` (Verdikte).
