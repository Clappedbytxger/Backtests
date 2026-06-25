# Spezifikation: SMC Liquidity-Sweep + Break-of-Structure (für Claude Code)

> Objektive Implementierungs- und Test-Anleitung. Ziel: die Strategie (V1) aus
> dem Referenzmaterial im Repo-Stil umsetzen und durch die Standard-Pipeline
> laufen lassen. Die Validierungs-Gates sind dieselben wie für jede andere
> Strategie im Repo. Stand: Juni 2026. Keine Anlageberatung.

---

## Teil 1 — Strategie-Spezifikation (V1)

### Entry-Logik

**Bullishes Setup (Long):**
1. **Confirmed Swing Low** identifizieren: Pivot-Tief mit `N` Bars höherem Low auf
   jeder Seite. Gilt erst zum Zeitpunkt `t = Bildung + N` als bestätigt.
2. **Liquidity Sweep:** eine Bar handelt mit dem Low unter das bestätigte Swing
   Low (Wick darunter), und innerhalb von `K` Bars schließt der Kurs wieder über
   dem gesweepten Level. Der tiefste Punkt des Sweeps = `sweep_low` (Wick).
3. **Break of Structure (BOS):** nach dem Sweep schließt eine Bar über dem
   jüngsten bestätigten Swing High. → BOS bestätigt.
4. **Entry:** zum Close der BOS-Bar (Variante A) ODER Open der Folge-Bar
   (Variante B). **Eine Variante vorab fixieren.**
5. **Stop:** `sweep_low − buffer` (Buffer z. B. 0.1×ATR oder fix in Ticks).
6. **R := entry − stop.**

**Bearishes Setup (Short):** spiegelbildlich (Sweep eines Swing High, BOS unter
jüngstes Swing Low, Stop = `sweep_high + buffer`).

### Exit-Logik

**Trailing Stop (Default, alle Assets außer GBPUSD):**
- Bei Erreichen von `entry + 1R` (Long): Stop → `entry` (Break-Even).
- Bei `entry + nR` (n ≥ 1): Stop → `entry + (n−1)·R`.
- Kein Teilgewinn, kein Take-Profit. Exit nur, wenn der (nachgezogene) Stop
  getroffen wird.
- **Intrabar-Konvention (Look-ahead-frei):** werden in derselben Bar sowohl das
  nächste R-Level als auch der aktuelle Stop berührt, gilt der Stop als zuerst
  getroffen (konservativ).

**Fixed 1R (nur GBPUSD):** Take-Profit bei `entry + 1R`, voller Exit; Stop fix
auf Initial-Stop.

### Per-Asset-Konfiguration (vorab fixiert)

| Asset | Proxy (Daten) | Richtung | Timeframe | Session-Filter | Exit | Risk/Trade |
|-------|---------------|----------|-----------|----------------|------|-----------:|
| XAUUSD | Gold (GC / XAUUSD-Spot) | Long + Short | M5 | keiner | Trailing | 0.5% |
| BTCUSD | BTC (ccxt Binance) | Long + Short | H1 | keiner | Trailing | 2.0% |
| SPX | ES-Future (Databento) | **nur Long** | M15 | Asset-Session (RTH) | Trailing | 1.5% |
| NDX | NQ-Future (Databento) | **nur Long** | M15 | Asset-Session (RTH) | Trailing | 1.5% |
| GBPUSD | GBPUSD-Spot | Long + Short | M15 | Asset-Session (London/NY) | Fixed 1R | 1.5% |

- **Risk/Trade** ist im Referenzmaterial so gesetzt, dass jedes Asset isoliert
  ~20% Max-Drawdown anstrebt. → Im Test als **vorab fixierter Parameter**
  übernehmen (nicht nach Ergebnis nachjustieren).
- **Testzeitraum:** 2016-01 bis 2026-05 (10 Jahre), pro Asset und kombiniert.

---

## Teil 2 — Objektive Definitionen der diskretionären Parameter

Die SMC-Begriffe müssen für systematisches Testen parametrisiert und **vor dem
Lauf eingefroren** werden (sonst kein reproduzierbarer Test). Default-Vorschläge:

| Parameter | Symbol | Default | Bedeutung |
|-----------|--------|--------:|-----------|
| Swing-Lookback | `N` | 2 | Bars je Seite für Pivot-Bestätigung |
| Sweep-Reversal-Fenster | `K` | 3 | Bars, in denen der Kurs zurück über/unter das Level schließen muss |
| Strukturreferenz BOS | — | jüngstes bestätigtes Gegen-Swing | welcher Swing für den Break zählt |
| Stop-Buffer | — | 0.1×ATR(14) | Abstand jenseits des Sweep-Wicks |
| Entry-Timing | — | Variante A (BOS-Close) | fix |

**Robustheits-Check (Teil 8):** das System auf einem kleinen Gitter um diese
Defaults laufen lassen (`N∈{2,3}`, `K∈{2,3,5}`), um Parameter-Plateau vs. -Spitze
zu prüfen. Alle getesteten Kombinationen zählen in `n_trials` (DSR).

---

## Teil 3 — Daten (frei / vorhandene Infra)

| Asset | Quelle | Hinweis |
|-------|--------|---------|
| Gold M5 | Databento (GC) **oder** Dukascopy/HistData (XAUUSD M1→M5) | 10 J. M5 |
| BTC H1 | ccxt Binance (vorhanden, 0012–0015) | direkt |
| SPX/NDX M15 | Databento ES/NQ (vorhanden, 0039–0041) | RTH-Filter aus `futures_intraday` |
| GBPUSD M15 | Dukascopy/HistData (M1→M15) | frei |

**Hinweis zur Daten-Äquivalenz:** Das Referenzmaterial nutzte CFD-Daten
(IC Markets). Futures-/Spot-Proxies haben abweichende Spreads/Sessions → im
Kostenmodell (Teil 6) asset-spezifisch parametrisieren. Roll-Behandlung für
ES/NQ/GC via vorhandener `roll`-Infra.

---

## Teil 4 — Implementierung (Modulstruktur)

```
strategies/00XX_smc_sweep_bos/
  run.py
  config.yaml            # alle Parameter aus Teil 1+2, eingefroren
quantlab/smc/
  structure.py           # Swing-Detektion (kausal), BOS
  sweep.py               # Liquidity-Sweep-Erkennung
  signals.py             # Setup-Assembly → Entry/Stop/Richtung
  exits.py               # Trailing-Stop + Fixed-1R-Engine
  smc_backtest.py        # Event-Loop, Sizing, Kosten
  tests/
    test_causality.py    # Look-ahead-Guard (Pflicht)
    test_trailing.py     # Trailing-Logik-Invarianten
```

### Implementierungsschritte
1. **`structure.py`:** Pivot-Swings (`N`-Bar-Fraktale). Funktion gibt je Bar nur
   die zu diesem Zeitpunkt **bestätigten** Swings zurück (Bildung + `N`).
2. **`sweep.py`:** prüft je Bar, ob ein bestätigtes Level gesweept wurde
   (Wick jenseits + Re-Close innerhalb `K`).
3. **`signals.py`:** kombiniert Sweep + nachfolgendes BOS → Setup-Objekt
   (Richtung, Entry-Zeit, Entry-Preis, Stop, R). Richtungsfilter je Asset
   (SPX/NDX nur Long).
4. **`exits.py`:** verwaltet offene Position bar-für-bar; implementiert
   Trailing-Schema bzw. Fixed-1R; Intrabar-Konvention aus Teil 1.
5. **`smc_backtest.py`:** Event-Loop, Position-Sizing nach `Risk/Trade` und
   Stop-Distanz (`size = risk·equity / |entry−stop|`), Kostenabzug, Equity-Kurve.
6. **`run.py`:** lädt `config.yaml`, läuft je Asset, dann kombiniert.

---

## Teil 5 — Kausale Konstruktion (Engineering-Pflicht)

Standard für jede Strategie im Repo: **jede Entscheidung in Bar `t` nutzt
ausschließlich Information bis einschließlich `t`.**
- Ein Swing-Punkt fließt erst ab seiner Bestätigung (`Bildung + N`) in
  Sweep-/BOS-Logik ein.
- Entry-Preis = Close(BOS-Bar) bzw. Open(t+1) — nie ein späterer Preis.
- Trailing-Updates nutzen nur abgeschlossene Bars; Intrabar-Konvention konservativ.
- **`tests/test_causality.py`:** füttert das System mit bis `t` gekürzten Daten
  und verifiziert, dass Signale/Exits identisch zu denen aus dem Volllauf bis `t`
  sind (kein Repainting). Gleiche Vorlage wie der bestehende Look-ahead-Test.

---

## Teil 6 — Kostenmodell

Pro Asset: **Spread + Kommission + Slippage.**
- Spread/Kommission asset-spezifisch (Futures: Tick-Wert + Broker-Commission;
  Spot/FX: typischer Spread).
- **Slippage:** da der Entry direkt nach einem Sweep (Volatilitäts-Spike) liegt,
  Slippage als Funktion der Entry-Bar-Range modellieren (z. B.
  `slip = c · range(entry_bar)`, `c` als Parameter), plus fixe Mindest-Slippage.
- **Kosten-Sensitivität (Teil 8):** Lauf bei {0, realistisch, 2×realistisch}
  Slippage; Ergebnis je Stufe berichten.

---

## Teil 7 — Backtest-Läufe

1. **Pro Asset einzeln** (eingefrorene Config): Equity, CAGR, Sharpe, MaxDD,
   #Trades, Return/MaxDD.
2. **Kombiniert** (5 Assets, je `Risk/Trade`): aggregierte Equity, Sharpe, MaxDD,
   Beitrag je Asset.
3. **Benchmarks:** Buy-&-Hold je Asset (Long-only, gleiche Periode) und ein
   einfaches Fast-Trend-Following-Baseline (z. B. Donchian-Breakout) auf
   denselben Assets/Timeframes — als Vergleichsmaßstab.

---

## Teil 8 — Validierungs-Batterie (Repo-Standard, identisch für alle Strategien)

1. **Look-ahead-Test** (Teil 5) — Pflicht-Gate, grün vor allem Weiteren.
2. **In-Sample/Out-of-Sample-Split über die Konstruktion:** Asset-/TF-/Exit-Wahl
   auf der ersten Hälfte fixieren, auf der zweiten ungesehenen Hälfte testen
   (nicht nur die ML-Schicht splitten).
3. **Walk-Forward:** rollierendes/expandierendes Fenster über den Zeitraum.
4. **Permutationstest:** Trade-Timing/Labels permutieren → schlägt das reale
   Ergebnis die Zufallsverteilung?
5. **Bootstrap-KI** auf Sharpe/Return-pro-Trade (Block-Bootstrap wegen
   Autokorrelation).
6. **DSR** mit **ehrlichem `n_trials`** = alle getesteten Asset × TF × Session ×
   Exit × Parameter-Gitter-Kombinationen.
7. **Verteilungs-Kennzahlen (deskriptiv):** Median-Trade, Mittelwert-Trade,
   Beitrag der Top-5/Top-10-Trades zum Gesamtgewinn, Trade-Return-Histogramm,
   längste Verlust-/Flat-Strecke.
8. **Kosten-Sensitivität** (Teil 6).
9. **Parameter-Plateau** (Teil 2-Gitter): Spitze vs. Plateau.

Alle Kennzahlen out-of-sample, netto nach Kosten, in `REPORT.md` im
Standard-Format.

---

## Teil 9 — Optional: ML-Meta-Labeling-Schicht (Phase 2)

Nach dem Basistest (Phase 1) die Random-Forest-Schicht aus dem Referenzmaterial:
- **Features (nur Pre-Trade-Info):** realisierte Vol, Session/Stunde, Wochentag,
  Trend-Zustand (z. B. Lage zu MA), Range der Sweep-Bar, R-Distanz, Richtung,
  Verhalten post-Sweep/post-BOS.
- **Label:** Trade-Erfolg (Triple-Barrier oder realisiertes R > 0).
- **Modell:** Random Forest / LightGBM.
- **Validierung:** **Purged & Embargoed CV** (kein einfaches k-Fold —
  Repo-Standard gegen Leakage), DSR mit `n_trials` inkl. aller Feature-/
  Konfig-Versuche.
- **Gate:** Meta-Labeling muss die Basisversion in OOS-Sharpe-Verteilung
  schlagen.

---

## Teil 10 — Phasenplan

| Phase | Deliverable | Gate |
|-------|-------------|------|
| 0 | Daten-Loader (5 Assets, kausal, roll-bereinigt) | Look-ahead-Test grün |
| 1 | SMC-Engine + Einzel-Asset-Backtests + REPORT | volle Batterie Teil 8 berichtet |
| 2 | Kombiniertes Portfolio + Benchmarks | Beitrag/Asset, vs B&H + Trend-Baseline |
| 3 | ML-Meta-Labeling (optional) | Purged-CV, schlägt Basis OOS |

---

*Methodik identisch zu allen Repo-Strategien: kausale Konstruktion, volle
Validierungs-Batterie, ehrliches `n_trials`, Kennzahlen out-of-sample netto. Die
Tests bestimmen das Ergebnis.*
