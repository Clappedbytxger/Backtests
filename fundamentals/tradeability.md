# Phase 0 — Tradeability Audit (Alt-Data Fundamentals Framework)

> Markt-Screening vor jeder Strategiearbeit. Ein gefundener Edge überlebt nur,
> wenn er die Spread-Kosten des Zielmarktes netto übersteht. Diese Tabelle ist
> der erste Filter — bevor irgendein Feature berechnet wird.
>
> Aktualisierungsdatum: 2026-06-07. Notional auf aktuellen ca.-Preisen.

---

## Kostenmethodik

- **Cost class**: Abgeleitet aus `CostModel`-Presets in `quantlab/costs.py`.
- **RT bps** = Round-trip Kosten in Basispunkten des Nominalwerts (ein Entry +
  ein Exit). Enthält halben Bid-Ask-Spread + Market-Impact + IBKR-Kommission.
- **Min. netto Edge/Trade**: Was ein Trade verdienen muss, damit nach Kosten
  etwas übrig bleibt. Als Faustregel: RT bps × 1.5 Safety-Margin.
- **Roll-Typ**: Monatlich rollende Kontrakte erfordern `roll.py`-Check; quartals-
  rollende sind sicherer (weniger Expiry-Cluster im Saisontest).

---

## Universum-Tabelle

| # | Future | Ticker | Börse | Kontrakt-Größe | ca. Nominal (USD) | RT bps | Cost-Klasse | Roll | IBKR-DE | Verdict |
|---|--------|--------|-------|---------------|-------------------|--------|-------------|------|---------|---------|
| 1 | **Zucker #11** | SB | ICE | 112,000 lbs | ~24,000 | 8 | `IBKR_SOFTS` | monatl. | ✅ | **PRIO 1** |
| 2 | **Kaffee** | KC | ICE | 37,500 lbs | ~75,000 | 8 | `IBKR_SOFTS` | monatl. | ✅ | **PRIO 1** |
| 3 | **Kakao** | CC | ICE | 10 t | ~80,000 | 8 | `IBKR_SOFTS` | monatl. | ✅ | **PRIO 1** |
| 4 | **Baumwolle** | CT | ICE | 50,000 lbs | ~40,000 | 8 | `IBKR_SOFTS` | monatl. | ✅ | **PRIO 1** |
| 5 | **Mais** | ZC | CME | 5,000 bu | ~25,000 | 5 | `IBKR_FUTURES` | monatl. | ✅ | **PRIO 1** |
| 6 | **Kupfer** | HG | CME | 25,000 lbs | ~112,500 | 4 | `IBKR_METALS_LIQUID` | monatl. | ✅ | **PRIO 1** |
| 7 | **Platin** | PL | CME | 50 oz | ~50,000 | 6 | `IBKR_METALS_PGM` | quartl. | ✅ | **PRIO 1** (0021 Saison-Lead vorhanden) |
| 8 | **Palladium** | PA | CME | 100 oz | ~100,000 | 6 | `IBKR_METALS_PGM` | quartl. | ✅ | **PRIO 1** |
| 9 | **Live Cattle** | LE | CME | 40,000 lbs | ~64,000 | 8 | `IBKR_SOFTS` | monatl. | ✅ | **PRIO 1** |
| 10 | **Feeder Cattle** | GF | CME | 50,000 lbs | ~110,000 | 8 | `IBKR_SOFTS` | quartl. | ✅ | **PRIO 1** (0009 Lead vorhanden) |
| 11 | **Lean Hogs** | HE | CME | 40,000 lbs | ~35,000 | 10 | `IBKR_SOFTS` | monatl. | ✅ | **PRIO 2** |
| 12 | **Orangensaft** | OJ | ICE | 15,000 lbs | ~22,500 | 40 | `IBKR_SOFTS_THIN` | monatl. | ✅ | ⚠️ Spread tötet Edge — nur wenn ≥40 bps/Trade netto |
| 13 | **Hafer** | ZO | CME | 5,000 bu | ~15,000 | 35 | `IBKR_SOFTS_THIN` | monatl. | ✅ | ⚠️ Dünn |
| 14 | **Rough Rice** | ZR | CME | 2,000 cwt | ~28,000 | 40 | `IBKR_SOFTS_THIN` | monatl. | ✅ | ⚠️ Sehr dünn |
| 15 | **Milch Kl. III** | DC | CME | 200,000 lbs | ~35,000 | 60+ | `IBKR_SOFTS_THIN` | monatl. | ✅ | ❌ Spread prohibitiv |
| 16 | **Butter** | CB | CME | 20,000 lbs | ~56,000 | 60+ | `IBKR_SOFTS_THIN` | monatl. | ✅ | ❌ Spread prohibitiv |
| 17 | **Käse** | CSC | CME | 20,000 lbs | ~38,000 | 60+ | `IBKR_SOFTS_THIN` | monatl. | ✅ | ❌ Spread prohibitiv |
| 18 | **Raps/Canola** | RS | ICE CA | 20 t | ~11,000 CAD | 12 | `IBKR_SOFTS` | monatl. | ⚠️ ICE Canada — IBKR DE möglich, prüfen | **PRIO 2** |
| 19 | **Palmöl** | FCPO | Bursa | 25 t | ~14,000 MYR | — | — | monatl. | ❌ Bursa Malaysia — IBKR DE nicht unterstützt | **SKIP** |
| 20 | **Naturkautschuk** | — | TOCOM/SGX | — | — | — | — | monatl. | ❌ Asiatische Börsen — nicht über IBKR DE | **SKIP** |
| 21 | **Lumber** | LBR | CME | 27,500 board ft | ~110,000 | 25 | `IBKR_SOFTS_THIN` | monatl. | ✅ (neuer LBR-Kontrakt 2023) | ⚠️ Dünn, alter LBS eingestellt (`0011`) |

---

## Priorisierung für Phase 3+

**Gruppe A — Sofort testbar (liquide, klare Kausalkette):**
SB, KC, CT (erste 3 Märkte per Roadmap), dann CC, ZC, HG, PL, LE/GF

**Gruppe B — Testbar aber Spread-Warnung:**
HE, ZO, ZR, RS, OJ, LBR → Kostentest ist hier der primäre Gate

**Gruppe C — Skip:**
Milch/Butter/Käse (Spread prohibitiv), Palmöl/Kautschuk (Börse nicht zugänglich)

---

## Roll-Behandlung (Reminder)

- **Monatlich rollende** Kontrakte (SB, KC, CC, CT, NG, CL, LE, HE, ...):
  Pflicht: `roll.py` Roll-Exclusion-Test für jede Saisonhypothese.
- **Quartals-rollende** (PL, PA, GF, GC, SI, HG meist):
  Sicherer, weil ein Fenster das einzige Roll-Event oft ganz vermeidet.
- Continuous-Reihe: yfinance `=F`-Symbole oder Databento `*.c.0` (für Intraday).
  Bei Datenbasis-Wechsel Lückencheck via `close.groupby(year).nunique()` (Lektion 0025).

---

## Nächste Schritte

- [ ] IBKR-Konditionen für Canola (ICE Canada) von IBKR DE-Kontoseite verifizieren
- [ ] Kontraktspezifikationen für LBR (neuer Lumber-Kontrakt) prüfen
- [ ] Für jede PRIO-1-Gruppe: Continuous-Reihe laden + 0-Return-Tage-Screen
