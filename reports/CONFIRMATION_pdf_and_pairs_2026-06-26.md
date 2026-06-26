# Edge-Bestätigung: GLM-PDF (Mean-Reversion CTI) + Quant-OS Pairs-Trading

**Datum:** 2026-06-26 · unabhängige Reproduktion mit dem `quantlab`-Harness (Kosten an,
Permutation, IS/OOS, DSR, Multiple-Testing). Skripte im Scratchpad, Methodik unten.

---

## 1. PDF „Mean Reversion Strategies for CTI 1-Step" (GLM 5.2)

Das PDF behauptet ein Portfolio mit Sharpe 0,93 aus drei Strategien (A/B/C). Die im PDF
**selbst berichteten** Permutations-p-Werte liegen bereits alle über 0,05 (A 0,0748, B 0,1362,
C 0,0854), und B/C zeigen eine IS≪OOS-Inversion (Edge sitzt nur in der hinteren Hälfte =
Regime-Glück). Die gelieferten `strategies/A_*/run.py … portfolio/run.py` existieren im Repo
**nicht** — es liegt nur der Report vor. Daher habe ich alle drei Regeln unabhängig nachgebaut.

| Strategie | meine Repro (netto, Kosten an) | Permutation p | Urteil |
|---|---|---|---|
| **A — RSI(2) SP500 daily** (2022-06…2026-06) | Sharpe **0,80**, IS 0,90/OOS 0,69, MaxDD −8,1 %, 81 Trades, +24,6 % | **0,23** | **NICHT bestätigt** als Edge |
| A — FULL 2005…2026 | Sharpe 0,55, IS 0,72/OOS 0,31 (Decay), 454 Trades | 0,070 | grenzwertig, nicht < 0,05 |
| **B — RSI(2) NAS100/NQ 1h** (2023…2026) | Sharpe **−1,86**, −46 %, MaxDD −48 %, 1517 Trades | 0,9995 | **widerlegt** (Kosten-Wand) |
| **C — z-Score ADF-MR ETH 1h** [PDF-4bps] | Sharpe **−0,38**, −45 %, MaxDD −55 % | 0,65 | **widerlegt** |
| C — ETH 1h [Repo-CFD_CRYPTO 20bps] | Sharpe −0,61, −58 % | 0,65 | **widerlegt** |

**Kernbefunde:**
- **A ist die einzige nicht-negative Strategie, aber kein bestätigter Edge.** Sie reproduziert
  sogar etwas besser als das PDF (0,80 vs 0,71), doch die **Permutation gegen Zufalls-Timing
  p=0,23** sagt: das Entry-Timing ist nicht von zufälligem Long-Sein auf denselben Up-Tagen zu
  unterscheiden. Der „Edge" ist **SP500-Beta** (Dip-Kaufen in einem Bullenmarkt), kein
  Mean-Reversion-Skill — exakt die Drift-Falle der Lessons 0016/0017/0050.
- **B und C sind netto klar negativ.** Intraday-RSI(2)/z-Score auf einem Einzelmarkt zahlt die
  Kosten-Wand (1517 bzw. 165 Trades) — die im ganzen Katalog dokumentierte Intraday-Richtungs-
  Kostenwand (0038-0041, 0049, Prop-Batch 0101). Das PDF-Headline-Plus (+1,44 / +0,74) war
  Regime-Glück auf einer spezifischen Daten-/Periodenwahl, kein robustes Signal.
- **Kostenannahme C unrealistisch:** Das PDF rechnet 4 bps für Crypto-CFD; das repo-kalibrierte
  Retail-Modell `CFD_CRYPTO` ist 20 bps RT. Selbst mit der optimistischen PDF-Annahme ist C tot.

**Verdikt PDF:** Keiner der drei Edges ist nach den Hard-Rules bestätigt. A = Beta-Overlay
ohne Timing-Skill; B/C = kosten-tot. Das Portfolio-Sharpe 0,93 ist ein In-Sample-Diversifikations-
Artefakt dreier nicht-signifikanter Beine (das PDF räumt selbst „Live-Haircut 30–50 %" ein).

## 2. Quant-OS Pairs-Trading / Stat-Arb

Scan über 5 Gruppen (Commodities/Energy/Tech/Banks/ETF-Index), 6 J daily. Die Engine
(`quantlab.pairs`) ist look-ahead-sauber: β nur auf In-Sample gefittet, trailing z-Score,
Position +1 geshiftet. Getestet: **237 Paare blind**, davon 18 kointegriert, **8 als `is_edge`
markiert**. Für jeden Edge eine Permutation auf den Spread-Returns + Multiple-Testing-Kontext.

| Paar | Sharpe OOS | Trades | Permutation p | < Bonferroni 0,00021 ? |
|---|---|---|---|---|
| USB/PNC (Banks) | 0,99 | 30 | **0,0145** | nein |
| MPC/PSX (Energy) | 1,33 | 26 | **0,0315** | nein |
| übrige 6 (DIA/QQQ, SLB/COP, DIA/SPY …) | 0,5–1,5 | 26–31 | 0,12–0,29 | nein |

**Kernbefunde:**
- **Nur 2 von 237 Paaren erreichen p < 0,05.** Bei 237 Tests erwartet man rein zufällig ~12
  Treffer bei p < 0,05 — 2 ist **weniger als die Zufallserwartung**. Die „Edges" überschreiten
  nicht, was Multiple-Testing ohnehin produziert.
- **Bonferroni-α = 0,05/237 = 0,00021 — kein Paar besteht** (auch keine milde FDR-Korrektur).
- Die **Lehrbuch-Paare** (KO/PEP, GLD/SLV, CVX/XOM, MA/V, EWA/EWC) sind alle `is_edge=False`
  (nicht kointegriert oder OOS negativ) — die Engine erfindet keine Edges, aber die, die sie
  markiert, sind Sektor-Zufallskorrelationen.

**Verdikt Pairs:** Die Pairs-Engine ist methodisch korrekt und look-ahead-frei, aber **kein
Pairs-Edge übersteht das Multiple-Testing, das der Scan selbst verursacht.** USB/PNC und MPC/PSX
sind bestenfalls Leads für einen vorregistrierten Forward-Test (Repo-Standard: DSR / Multiple-
Testing-Awareness), keine bestätigten Edges. Bestätigt die Katalog-Lehre „hoher IC ≠ PnL"
(0058) und den Faktor-Zerfall (0047/0048).

## 3. Alpha-Factory — Look-Ahead & Data-Mining behoben

Alle 4 „bestandenen" AF-0110-Reports waren **Look-Ahead-Artefakte** (`Close.shift(-1)` =
morgiger Kurs → Schein-Sharpe 8,31/8,77/7,91/3,47). Behoben:
1. **Harter Kausalitäts-Guard** (`quantlab.causality`): Harness rechnet das Signal auf
   abgeschnittenen Präfixen nach; ändert sich Bar t beim Anhängen der Zukunft → Reject.
2. **Data-Mining-Deflation:** DSR wird mit der echten Such-Breite (`QOS_N_TRIALS`) belastet
   statt `n_trials=1`.
3. **Sanity-Ceiling:** netto-Sharpe > 4 ⇒ Reject (Signatur von Look-Ahead/Daten-Bug).
4. **Schärferer Prompt** (explizites `shift(-n)`-Verbot + Data-Mining-Warnung) + Unit-Test
   (`tests/test_agent_causality.py`, 5/5 grün). End-to-End verifiziert: der AF-0110-Cheat wird
   jetzt vom Gate abgelehnt, ein kausales Signal passiert den Guard.

**Methodik:** `costs an` (CFD_INDEX 3bps / CFD_CRYPTO; PDF-4bps zum Vergleich), Permutation
gegen Zufalls-Timing (2000 Perm), IS/OOS 60/40, DSR mit n_trials=6 (PDF) bzw. 237 (Pairs-Scan).
Daten: SPY/^GSPC daily, NQ.c.0 1h (Databento), ETH 1h (Binance, frisch gezogen), alle aus dem Cache.
