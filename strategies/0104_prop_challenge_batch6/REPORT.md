# 0104 — Prop-Challenge Batch 6 (I0086–I0088, Robin-Images + dekorrelierte CTI-Sleeves)

**Datum:** 2026-06-18 · **Universum:** CTI-1-Step-CFD · **Quelle:** `D:\Backtest Ideas\ideas\prop-challenge-batch6.md` (#s37–#s39)

Batch 6 entstand aus Robins drei Hypothesen-Images (ORB, NQ-Long-Bias, Bitcoin
MVRV-Z) + der Batch-5-Direktive „Kombi-Sharpe Richtung 1,3–1,6 über dekorrelierte
Breite". ORB (= reject I0067/0039) und NQ-Long-Bias (= Beta-Maskerade) führten zu
keinem Eintrag. Drei abgeleitete Sleeves getestet.

## Endstand

| ID | Strategie | Verdikt | Kernzahl |
|----|-----------|---------|----------|
| I0086 | Krypto-On-Chain-Regime-Gate (MVRV-Z) | **deferred (Daten-Blocker)** | PIT-On-Chain (Realized-Cap-Revision) nicht frei verfügbar; Overlay, kein Standalone |
| I0087 | Index-Rebalance-FX-Flow (MSCI) | **deferred (Daten-Blocker)** | Stage-1-Gewichte blockiert; Stage-2-Proxy am Quartals-Trigger null (perm p 0,51–0,86) |
| I0088 | Krypto-Cross-Sectional-Momentum | **rejected** | CS-neutral netto −0,80; IS/OOS-Kollaps; CS schlechter als TS (contra #s35) |

**Keine Leads.** Zwei daten-blockierte Defer (kein Pseudo-Test), ein sauberer Reject.

---

## I0086 — MVRV-Z-Regime-Gate → DEFERRED (Daten-Blocker, bewusst nicht gebaut)

Sizing-/Regime-Overlay (analog VIX-Gate I0083): Z<0 → Krypto-BTC/ETH-Risiko ×1,25;
0–5 → ×1,0; Z>5 → ×0,4. **Kein eigener Entry-Edge.**

**Warum nicht gebaut:** Der MVRV-Z-Score hängt an der **Realized Cap**, die laufend
**revidiert** wird (späte On-Chain-Coin-Bewegungen ändern historische Werte) = echtes
**PIT-Problem**. Eine PIT-treue Reihe gibt es nur kostenpflichtig (Glassnode); die
Gratis-Charts (bitcoinmagazinepro/bgeometrics) ohne PIT-Garantie → jeder Backtest darauf
ist look-ahead-verseucht. **Disziplin-Entscheid (wie 0055 PEAD / IC-Gate): kein
Pseudo-Test auf look-ahead-kontaminierten Daten.** Zudem wirkt das Gate nur auf das
Krypto-Sleeve (I0080/I0088) — und das ist nach 0058-0062/I0080/I0088 selbst tot/zerfallen,
also gibt es derzeit kein lebendes Krypto-Bein zum Gaten. Defer bis (a) PIT-MVRV
beschaffbar UND (b) ein tragendes Krypto-Sleeve existiert.

## I0087 — Index-Rebalance-FX-Flow (MSCI) → DEFERRED (Daten-Blocker)

Mandatsgetriebener FX-Hedge-Flow am MSCI-Review-Effektivtag (letzter Geschäftstag
Feb/Mai/Aug/Nov), distinkter Kalender-Trigger neben dem I0075-Monatsende.

**Stage-1 (faithful)** braucht die **announced weight changes je Währung** → nicht frei
PIT-verfügbar = **Daten-Blocker**. Getestet wurde nur der **Stage-2-Proxy**
(`e2_msci_fx_flow_proxy.py`): relative Regionen-Equity-Performance (EWJ/EWU/EWG/EWA/EWL →
JPY/GBP/EUR/AUD/CHF) als Richtungs-Proxy, dollar-neutral, Hold ums Effektivtag-Fenster.

**Befund:** Am **faithful Quartals-Trigger null** — hold 1/2/3 T: meanR ≈ 0,
perm p 0,51–0,86, Bootstrap-KI um 0. Nur die **Monats-Variante** marginal (hold=2
meanR +8,4 bps, perm p 0,028) — aber **KI berührt 0** und das ist generisches
FX-Risk-on-Momentum (outperformende Region kontinuiert 2 Tage), **nicht** der MSCI-
Flow-Mechanismus. **Per Repro-Treue (`RESEARCH-PROCESS.md`): ein Stage-2-Null ist KEIN
Edge-Reject des Flow-Edges** — die faithful Form ist daten-blockiert, nicht widerlegt.
Verdikt: **deferred** bis MSCI-Gewichtsdaten (PIT). Der vom Researcher erwartete dünne
DM-Edge (wegarbitragiert) ist konsistent mit dem null Proxy.

## I0088 — Krypto-Cross-Sectional-Momentum → REJECT

5 CTI-Coins (BTC/ETH/XRP/LTC/ADA), Ranking, wöchentliches Rebalance, Long-Top-2/
Short-Bottom-2 (neutral) bzw. Long-only; Benchmark = TS-Momentum (I0080-Form).
`e1_crypto_xsec_mom.py`, 2018-2026. Kostenwand: 20 bps RT Spread + 8 bps/Nacht
1:2-Financing (das Kill-Gate, #s35).

**Befund (Reject auf allen Achsen):**
- **Kostenwand bindend:** TS brutto Sharpe +0,55 → **netto +0,25**; neutral brutto +0,17 →
  **netto −0,80** (Short-Bein + Financing zerstören es), MaxDD −94 %.
- **CS schlechter als TS** — widerlegt die #s35-Andeutung „CS schlägt TS bei Krypto"
  direkt auf den CTI-Coins; bestätigt die #s39-Disclosure (gemischt) + den „5 Coins zu
  dünn"-Vorbehalt.
- **IS/OOS-Kollaps** in allen Varianten (TS 0,54→−0,17; long-only 0,39→−0,14) = der
  Sharpe lebt im 2018-21-Bull, zerfällt im Bär (bestätigt 0058-0062/I0080).
- **Schlägt EW-Buy&Hold der 5 Coins netto nicht** (B&H Sharpe +0,39 > jede aktive Variante).

Kein Dekorrelator, kein Fast-Pass — der dünne Querschnitt + die Krypto-CFD-Kostenwand
töten den Edge.

---

## Querschnitt / Lehren
- **Daten-Blocker ehrlich tragen statt Pseudo-Test:** I0086 (PIT-MVRV) und I0087-Stage-1
  (MSCI-Gewichte) bleiben `deferred` — ein look-ahead-verseuchter Backtest wäre wertlos
  (0055-Disziplin). Stage-2-Null ≠ Edge-Reject.
- **#s35-CS-These auf CTI-Coins widerlegt:** Cross-Sectional ist hier schlechter als
  Time-Series; 5 Coins sind kein Querschnitt (Bestätigung 0058 „hoher IC ≠ PnL" + dünnes
  Universum).
- **Ehrliche Decke bleibt ~1,3–1,6** (Batch-5-`sim_sharpe_needed`): Batch 6 liefert weder
  Breite noch Risk-Senkung, die handelbar wäre — der Hebel bleibt die Account-/Fast-Retry-
  Entscheidung, nicht „Sharpe grinden".
