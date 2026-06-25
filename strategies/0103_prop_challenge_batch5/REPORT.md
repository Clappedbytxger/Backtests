# 0103 — Prop-Challenge Batch 5 (Sharpe-Hebel fürs CTI-Buch, I0080–I0085)

**Datum:** 2026-06-18 · **Quelle:** `D:\Backtest Ideas\ideas\prop-challenge-batch5.md`
**Ziel der Vorlage:** Kombi-Buch-Sharpe von ~0,88 auf ~1,5 heben über mehr
*dekorrelierte* Sleeves (Breite) + ein hoch-vol-dekorreliertes Fast-Pass-Sleeve.

## Endstand: 1 Lead, 1 Overlay-mit-Vorbehalt, 4 Reject — Buch-Sharpe bleibt ~0,68

| Idee | Sleeve | Verdikt | Brutto-Sh | Netto-Sh | Kern |
|------|--------|---------|-----------|----------|------|
| **I0080** | Krypto-TSMOM (BTC/ETH) | **LEAD** | 1,00 | **0,67** | einziger Survivor; Swap (194 bps/J) ist der Drag, nicht das Signal |
| I0081 | FX-Querschnitts-Momentum | Reject | −0,03 | −0,35 | Faktor tot (brutto ≈0), bestätigt 0047/0048/0083 |
| I0082 | Gold/Silber-Ratio-RV | Reject | 0,03 | −0,23 | Ratio *trendet*, revertet nicht @60T (2010/2020-Spikes) |
| I0083 | VIX-Vola-Gate (Overlay) | **Overlay-Vorbehalt** | — | — | senkt Worst-Day −42% ABER **senkt auch Sharpe 0,43→0,35** |
| I0084 | Index-Intraday-MR (Re-Test) | **Reject (hart)** | **−0,1 bps/T** | −4,0 bps/T | brutto NEGATIV → Extensions kontinuieren (Batch-3-Wand hält für MR) |
| I0085 | FX-RV/Kointegration | Reject | −0,15 | −0,13 | beide Cluster brutto ≈0, n niedrig |

**Buch (3 Survivors, Equal-Risk, 2017–2026):** kombinierte **Sharpe 0,676**
(vs naive √K-Erwartung 0,77) — die Dekorrelation ist **real** (alle Cross-Korrelationen
≈0), aber √K hilft kaum, weil es effektiv nur 2–3 *schwache* positive Sleeves gibt.
**Die Spec-eigene Ehrlichkeit (»Sharpe 1,5/3 ist auf Gratis-Daten nicht baubar«) ist
damit empirisch bestätigt — das Buch erreicht nicht einmal die 1,3-Untergrenze.**

---

## Sleeve-Details

### I0080 — Krypto-TSMOM (LEAD, einziger Survivor)
BTC/ETH daily, Long wenn `Close>SMA(100) ∧ Close>Close[-90]`, Vola-Targeting je Coin,
Indikator-Exit (SMA-Flip). **Long-only schlägt L/S** (Krypto-Short-Financing teurer +
2023-Short-Bein blutet).

- Long-only: brutto **0,997** → netto **0,671**; Timing-perm (Rotation) **p=0,056**.
- Per Coin (netto): BTC **0,69**, ETH **0,44**.
- **Swap ist der Drag:** 194 bps/J (1:2-CFD-Financing @8 bps/Nacht) → frisst gross 1,0→net 0,67.
- **Decay-Vorbehalt:** stark 2017–2021 (jährlich +9…+24%), zerfällt 2024–2026
  (2025 −1%, 2026 −5%) — dieselbe Krypto-Reifung wie 0058–0062/0069.
- **Wert:** echt dekorreliert zu FX/Aktien (Korr ≈0) + hoch-vol = Fast-Pass-Tauglich.

### I0081 — FX-Querschnitts-Momentum (Reject)
9 USD-Crosses (auf »Fremdwährung-in-USD« normiert), 12-1M-Rang, Long-Top-/Short-Bottom-
Tertil, monatlich. **Brutto-Sharpe −0,03 = der Faktor ist tot.** Jedes Jahr ~flach/negativ.
Reproduziert den Querschnitts-Faktor-Zerfall der 2010er (0047/0048/0079/0083).

### I0082 — Gold/Silber-Ratio-RV (Reject)
`z=(XAU/XAG − SMA60)/std60`, ±2σ-Entry, dollar-neutral. **Brutto-Sharpe 0,034 ≈ Null**,
Timing-perm p=0,49. Die Ratio ist auf 60-Tage-Sicht **nicht mean-reverting** — sie
trendet (COVID-2020 −38%, 2010 −26% Verlustjahre, als die Long-Silber-Seite überrollt
wurde). Der theoretische Langfrist-MR existiert, ist aber nicht im handelbaren Fenster.

### I0083 — VIX-Vola-Gate (Overlay, mit wichtigem Vorbehalt)
Gate (VIX t-1): <20→100%, 20–30→60%, ≥30→0%, angewandt auf das RSI-2-Equity-Buch.
**Kontraintuitives, ehrliches Ergebnis:**
- Sharpe **sinkt** 0,43 → 0,35 (raw), 0,23 → 0,15 (@10%vol).
- ABER Worst-Day **−585 → −338 bps** (−42% Tail).
- **Grund:** Connors-RSI-2 *kauft Panik-Dips* — der Sleeve verdient sein bestes Geld
  GENAU in Vola-Spikes. Das Gate schaltet die profitabelsten Entries ab. Die
  Spec-Prämisse (»MR verliert Edge in Spikes«) gilt für *Drift*-Sleeves, **nicht für
  Dip-Buying-MR.** Nur wertvoll, wenn die bindende Restriktion der Daily-DD-Tail ist
  (1-Step-5%-Trailing), nicht der Sharpe.

### I0084 — Index-Intraday-MR (Re-Test, Reject hart)
ES/NQ 15-Min RTH, VWAP-Fade (`|Close−VWAP|>1·ATR`), intraday-flat (kein Swap), 3 bps RT.
**Brutto-Mittel je Trade NEGATIV** (ES −1,0 / NQ −1,3 bps), Sign-perm p=1,0, Win 44%.
→ Index-Intraday-Extensions **kontinuieren**, reverten nicht. Bestätigt die Batch-3-
Kostenwand (0012-0015/0038-0041/0049) — sie hält **auch für die MR-Richtung**, nicht
nur Trend. Reject auf Signal, nicht nur Kosten.

### I0085 — FX-RV/Kointegration (Reject)
EURUSD~GBPUSD + AUDUSD~NZDUSD, rollende OLS-Hedge-Ratio (120T, look-ahead-frei),
z-Spread-MR. Beide Cluster brutto ≈0 (+0,10 / −0,02), kombiniert brutto −0,15, n=46/36.
Daily-FX-RV trägt nicht; die triangulare/kointegrierte Relation ist zu eng arbitriert.

---

## Buch-Integration & Monte-Carlo (Cross-Cutting-Gates 3–5)

**Survivor-Buch = I0075 (Monatsend-FX) + I0076 (RSI-2) + I0080 (Krypto-TSMOM)**,
Inverse-Vol-Gewichtung, gemeinsames Fenster 2017-11 … 2026-06:

- Kombinierte **Sharpe 0,676** (raw), **0,478 @10%vol**, MaxDD −18,5%.
- Korrelationsmatrix: alle Cross-Korrelationen ∈ [−0,07; +0,07] → **Dekorrelation real**
  (einzige Ausnahme 0,88 = RSI-2-gated vs ungated, derselbe Sleeve).
- Aber: nur 2–3 schwache positive Sleeves → √K-Hebel greift kaum (naive √K = 0,77).

**Prop-Monte-Carlo bei der erreichten Buch-Sharpe (0,68):**

| Vol | 1-Step P(pass) / P(bust) / Median | 2-Step P(pass) / P(bust) / Median |
|-----|-----------------------------------|-----------------------------------|
| 10% | 0,44 / **0,56** / 3,8 Mon | 0,79 / 0,21 / 3,8 Mon |
| 12% | 0,44 / 0,57 / 2,8 Mon | 0,70 / 0,30 / 2,6 Mon |
| 15% | 0,40 / 0,60 / 1,8 Mon | 0,61 / 0,40 / 1,8 Mon |

**Zum Vergleich, was die Spec-Zielzelle (Sharpe 1,5) bräuchte:**
2-Step @10%vol = 0,95/0,05/2,6 Mon — d.h. das »<15% Bust in ~2 Mon«-Versprechen lebt
erst bei Sharpe ~1,5, die Batch 5 **nicht liefert**.

## Fazit für die Account-/Pfad-Entscheidung
- Batch 5 liefert **genau ein** neues, echt dekorreliertes Sleeve (I0080 Krypto-TSMOM,
  net 0,67) — ein guter Diversifikator, aber kein Sharpe-Sprung.
- Die 4 Reject-Sleeves bestätigen Bestands-Lehren (Faktor-Zerfall, Intraday-Wand, FX-RV-tot).
- Das VIX-Gate ist **kein freier Sharpe-Hebel** — es tauscht Sharpe gegen Tail.
- **Realistisches Buch-Ceiling bleibt ~0,7–0,9**, nicht 1,5 — die Spec hat recht behalten.
  Konsequenz: der **2-Step-Pfad bei moderater Vola** (10%, Bust 0,21) ist der einzige
  mit vertretbarer Bust-Rate; der 1-Step-Fast-Retry ist bei Sharpe 0,68 ein Bust-Coinflip
  (0,56). Die Account-Entscheidung muss von dieser ehrlichen Decke getrieben werden.

## Dateien
- `e1_crypto_tsmom.py` (I0080) · `e2_fx_xsec_mom.py` (I0081) · `e3_goldsilver_rv.py` (I0082)
- `e4_vix_gate.py` (I0083) · `e5_index_intraday_mr.py` (I0084) · `e6_fx_rv_coint.py` (I0085)
- `book_integration.py` (Korrelation + Kombi-Sharpe + MC) · `results/*.json` · `results/streams/*.parquet`
