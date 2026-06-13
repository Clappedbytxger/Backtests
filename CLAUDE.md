# CLAUDE.md — Backtests (Quant Research)

Project-specific instructions. The global `CLAUDE.md` also applies (German
communication, English code/commits, Conventional Commits, etc.).

## Goal

Build a real, statistically validated trading edge — datadriven, not vibes.
Every strategy must survive cost, look-ahead and significance scrutiny.

## Workflow for a new strategy

1. Copy `strategies/REPORT_TEMPLATE.md` into a new `strategies/NNNN_name/` folder.
2. Write `run.py` using `quantlab` (never re-implement metrics/engine).
3. Split in-sample / out-of-sample; only trust out-of-sample numbers.
4. Always run: costs on, permutation test, bootstrap CI, Deflated Sharpe.
5. Write `REPORT.md`, save plots + `metrics.json` + `trades.csv` to `results/`.
6. Append a row to `CATALOG.md`.

## Hard rules (non-negotiable)

- **No look-ahead.** Signals are decision-time; the engine shifts them. Never
  use same-bar or future data in a signal.
- **Costs always modeled** (IBKR). Report net, not gross.
- **Macro rationale required.** No economic cause => mark as suspect/data-mined.
- **Enough trades.** Aim for >30, prefer >100, for statistical meaning.
- **Multiple-testing awareness.** Track how many variants were tried; use the
  Deflated Sharpe Ratio.
- Use **adjusted close** (yfinance `auto_adjust=True`, already default in `data.py`).

## Library map (`src/quantlab`)

- `data.py` — cached yfinance loader (Parquet)
- `metrics.py` — `compute_metrics`, `trade_stats`
- `costs.py` — `CostModel`, IBKR presets
- `backtest.py` — `run_backtest` (vectorized, look-ahead safe, trade log)
- `significance.py` — permutation, bootstrap, Deflated Sharpe, t-test
- `seasonal.py` — calendar features, bucket analysis, signal builders
- `cross_sectional.py` — panel ranking engine (`run_cross_sectional`,
  `momentum_signal`, `cross_sectional_permutation_test`); look-ahead-safe,
  dollar-neutral L/S, turnover costs
- `futures_curve.py` — Databento term-structure loader (`.c.0`/`.c.1` daily,
  `get_carry_panel`, `carry_signal`); `roll_adjusted_close`/`roll_adjusted_front_panel`
  back-adjust via `instrument_id` roll dates (artifact-free returns)
- `plotting.py` — equity, drawdown, monthly heatmap, bucket bars
- `cot_data.py` — CFTC-COT-Loader (Socrata, gratis), Hedging Pressure,
  PIT-Release-Logik (Di-Daten, Fr-Release, +1-Handelstag-Shift)
- `commodity_features.py` — theoriegetriebene Feature-Panels (Carry,
  Basis-Momentum, Momentum, HP, Skew, Vol, FRED-Makro), Rang-Transform,
  Forward-Targets, Design-Matrix; Kalender gefiltert auf ≥50% beobachtete Bars
- `cpcv.py` — Combinatorial Purged CV (Purge+Embargo), OOS-Stitching,
  PBO via CSCV
- `ml_portfolio.py` — Prediction-Panel → Quintil-L/S, inverse-Vol-Legs,
  Turnover-Kosten
- `football_data.py` — football-data.co.uk-Loader (Parquet-Cache; PS*/PSC* =
  Pinnacle Collection/Closing, B365* = Bet365; Closing ab Saison 2019/20)
- `devig.py` — Quoten → faire Wahrscheinlichkeiten (multiplicative/Shin/power;
  Shin am besten kalibriert, Tests in `tests/test_devig.py`)
- `clv.py` — Closing Line Value je Wette + Bootstrap-KI auf den Median
- `odds_live.py` — The Odds API-Client (Quota-Tracking, Key `.oddsapi.key`) +
  eingefrorene Live-Alert-Logik (`find_value_bets`, `fair_close_prob`);
  täglicher Paper-Tick: `scripts/football_live_paper.py` (0065)

## Live-System (`live/`)

Signalerzeugung + Alert + Forward-Ledger für alle live-nahen Strategien
(siehe `live/README.md`). `calendar.yaml` definiert die Trigger, `engine.py`
übersetzt sie backtest-treu (T+1-Konvention) in Order-Tickets, `run_daily.py`
läuft täglich 08:00 via Task-Scheduler („Backtests Trading Desk"),
Telegram-Key optional in `.telegram.key`. FOMC-Termine in `engine.py`
jährlich pflegen (Test erzwingt 8/Jahr). Fills via
`live/ledger.py fill <ticket>` loggen; Ausführung bleibt human-in-the-loop.

## Environment

- venv at `.venv` (Python 3.13). Run: `.\.venv\Scripts\python.exe ...`.
- There is also a separate `D:\AI\Python` 3.10 install on the machine — do not
  use it for this project; always use the project `.venv`.

## Lessons Learned

- **2026-06-12 (0066, Extra-Ligen-Eignungstest — dieselbe Gate-n-Falle
  ZWEIMAL in einem Programm):** football-data-Extra-Dateien (`/new/{LAND}.csv`)
  haben NUR Schlussquoten (kein 0064-Replikat), B365-Close erst ab Saison
  2025/26, AvgC voll seit 2012, Pinnacle-Close fehlt jüngst in ARG/USA —
  **Spaltenexistenz ≠ Coverage, immer non-null je Saison prüfen** (0025-
  Verwandte). Methodisch: Gate „n≥50 B365-Close-Value-Wetten" war mit
  maximal ~41 verfügbaren unerreichbar (Lauf 1), und das Amendment auf das
  ~9× seltenere AvgC-Maß behielt die 50 bei (Lauf 2) → 0/14 PASS trotz klar
  positiver Strukturbefunde (Orakel 14/14 sane, Bias-Rate 13/14 ≥ Benchmark,
  Sanity-ROI +12%). **Die 0064-Lehre (erreichbares n VOR der Schwellen-
  Registrierung gegen die Datenquelle rechnen) gilt für JEDE Schwelle, auch
  nach Amendments — ein geändertes Maß braucht eine neu gerechnete Schwelle.**
  Disziplin gehalten: kein dritter Gate-Umbau (= Gate-Shopping); Entscheid
  transparent auf Strukturbasis — 8 Ligen in den NICHT-Gate-relevanten
  Extension-Tier (der nie backtest-pflichtig war), 0065-Gate unangetastet,
  Budget-Schutz via Tier-Lookahead 24h/48h.

- **2026-06-12 (0064, Football Phase 2 — Cross-Liga-OOS PASS, ROI-Gate als
  Kriterium beerdigt):** Eingefrorene 0063-Regel (shin@2%) ohne Re-Fit auf 11
  nie berührte Ligen: **Median-CLV +1,44%, KI [+0,97%,+1,90%] ohne 0, 11/11
  Ligen + 7/7 Saisons positiv** (OOS > IS — Nischen-Ligen ineffizienter);
  Plateau über alle 12 Schwellen; Edge sitzt im Quote-Bucket [2,5;4) (77%
  Draws = Soft-Book-Draw-Bias), NICHT in Longshots. **Lehre 1 (Gate-Design):
  ein ROI-Bootstrap-KI-Gate ist bei Wett-Strategien strukturell unerreichbar**
  — wahrer Erwartungswert je Wette = mittlerer CLV (+1,09%), Streuung
  1,98/Wette → KI-Ausschluss bräuchte ~126k Wetten (verfügbar 1.849). Vor dem
  Registrieren eines Gates die benötigte Stichprobe gegen die verfügbare
  rechnen — sonst registriert man einen garantierten FAIL. CLV ist die
  korrekte Beweis-Metrik (per-Wette, sofort, hoch-N). **Lehre 2 (Ökonomie):
  EV gegen die Opening-Linie überschätzt den Edge massiv** — +4,2% mean EV
  (vs Open) schmilzt an der Schlusslinie auf +1,1%; nach 1% Slippage ~+0,2%,
  nach 5,3% Steuer tot (Stress-ROI −3%) → Steuer-Absorption ist
  Existenzbedingung, und die Roadmap-Annahme „2-4% Edge" hält am
  Freitag-Snapshot nicht. Flow-Zerfall real: 5,9→1,6 Wetten/Woche bis 25/26.
  Offen: nur Phase 3 (Live-Polling-Paper-CLV, Gate vorab: Median ≥+1% bei
  ≥150 Alerts/4-6 Wochen) kann zeigen, ob Intraday-Divergenzen mehr tragen
  als der Snapshot.

- **2026-06-12 (0063, Football-Value-Betting Phase 0+1 — Selbstreferenz-Bias
  in der CLV-Messung gefangen):** Neues Programm (FOOTBALL-VALUE-BETTING-
  ROADMAP.md): de-viggte Pinnacle-Quoten als Orakel, Bet365-Quoten darüber =
  +EV, Beweis-Metrik = CLV gegen die de-viggte Pinnacle-Schlusslinie.
  **Kern-Lehre: Selektions- und Mess-Maßstab müssen entkoppelt sein** — wird
  der CLV jeder De-Vig-Methode gegen ihre EIGENE Schlusslinie gemessen,
  bestätigt sich die Methode selbst: multiplicative (inflationiert Longshot-
  Probs) wählte Longshots und zeigte Median-CLV +2,7% mit KI ohne 0; gegen
  die bestkalibrierte Shin-Schlusslinie gemessen wurde daraus **−0,7%**
  (Verwandter der „richtige Permutations-Null"-Lehre 0052/0057). Standard
  jetzt: CLV IMMER an der Shin-Close messen, egal welche Methode selektiert.
  Zweite Lehre: das +EV-Wettbuch ist longshot-lastig (Median-Quote 4,75,
  Top-5-Gewinner = 95% des PnL) → ROI-KIs nutzlos breit, **nur der CLV ist
  beweisfähig** — exakt der Grund, warum die Roadmap CLV als Primärmetrik
  registriert. Stand: Phase 0 PASS (Margen plausibel, Shin > power > mult per
  Brier, 15/15 Tests), Phase-1-Gate shin@3% FAIL (KI mit 0), Lead shin@2%
  (Median-CLV +1,01%, KI [+0,2%,+2,2%], 5/7 Ligen, von Zweitligen getragen);
  Vorbehalt Flow-Zerfall 90→20 Wetten/Saison bis 25/26. Entscheid mit Robin:
  2%-Headline registrieren + Phase 2 vs direkt Phase 3 (Live-Paper-CLV).

- **2026-06-12 (0062, Phase 5 / CNN-on-Charts — Track B sauberes Null,
  Crypto-Roadmap 0-5 KOMPLETT):** JKX-2023-CNN (20d-OHLC-Bilder, 3px/Tag,
  per Bild skaliert — Skalierungs-Invarianz per Unit-Test bewiesen) auf
  exakt den 35.428 Track-A-Zeilen unter identischen 28 CPCV-Splits:
  **CNN gewinnt 0/28 Splits** (Stitched-IC +0.012 vs LGBM +0.151), fixe
  Architektur/Seed, bewusst KEINE Architektur-Iteration gegen ein
  0/28-Ergebnis (wäre Trial-Mining). **Lehre 1: „unkorreliert" ist KEIN
  Ensemble-Argument ohne eigenes Signal** — Rank-Korrelation 0.044 sah
  nach Diversifikation aus, aber das Ensemble verwässerte nur (IC
  0.151→0.109, vs Markt +0.45→+0.04, 0/28 Splits): erst Signal nachweisen,
  DANN über Korrelation reden. **Lehre 2: Deep-Learning-Paper brauchen die
  Datenskala des Papers** — JKX trainieren auf Millionen täglicher
  US-Aktien-Bilder; ~25k wöchentliche Crypto-Bilder/Split reichen für
  „Modell findet Muster selbst" nicht, und Crypto-Einzelcharts tragen
  v.a. den gemeinsamen Marktmove, der im Querschnitt nichts rankt.
  Infra wiederverwendbar: `quantlab/price_images.py` (+ 4 Guards inkl.
  Look-ahead-Test), OHLC-Panels in `get_price_panels`, torch-CPU im venv.
  **Programm-Stand: Roadmap 0-5 fertig; einziger offener Faden = der
  registrierte Live-Forward der Track-A-Regel (0060).**

- **2026-06-12 (0060/0061, Walk-Forward + Konzentrations-Fix + Phase 4 —
  drei Lehren, eine davon teuer-fast):** **Lehre 1 (Stablecoin-Falle, im
  LIVE-Buch gefangen, nicht im Backtest):** Das Live-Signal der eingefrorenen
  Regel hielt 95% in RLUSD („Ripple USD") + „U" („United Stables") — zwei
  Stablecoins, die 2025/26 neu in die CMC-Top-150 kamen und in der
  Namens-Exclusion fehlten; **inverse-Vol-Gewichtung lässt ein
  Quasi-Null-Vol-Asset das Buch schlucken** (verstecktes Cash, schmeichelt
  in Chop-Phasen). Fix: Namensliste IMMER nur als zweite Schicht hinter
  einem strukturellen Guard (Mitglied nur bei trailing 60d-Vol ≥ 10% p.a.,
  PIT-safe; `tests/test_crypto_pegged_guard.py`). Effekt ehrlich beziffert:
  WF-12er-Buch +0.78→+0.64 vs Markt. **Statische Ausschlusslisten veralten
  — jeder Universums-Filter braucht ein datengetriebenes Gegenstück.**
  **Lehre 2 (CPCV→Walk-Forward-Haircut quantifiziert):** identische Regel,
  identische Daten: CPCV-Stitch +0.81 → echter monatl. Expanding-Walk-Forward
  +0.38 (8er-Buch) — der Rest des Optimismus ist der Regel-Selektions-Kanal,
  den nur Live cleant. ABER der LGBM-vs-Ridge-Abstand überlebt OOT (+0.38/
  +0.64 vs Ridge −0.15 bei identischer Regel; Ridge verdient OOT NICHTS) —
  Gate A war kein CPCV-Artefakt. Konzentrations-Fix min_k=12 (1 Trial):
  2023 −2.3→−0.8, +0.64 vs Markt, t-p 0.14 = Richtung klar, Beweis offen →
  **Live-Forward registriert 2026-06-11** (`scripts/crypto_live_signal.py`,
  Kriterien in 0060-REPORT). **Lehre 3 (0061, zweistufiger Feature-Check
  fängt Schein-Fortschritt):** Funding verbessert den IC konsistent (68%
  Split-Siege) aber macht das konzentrierte Portfolio SCHLECHTER (Rang-Info
  ≠ Portfolio-Wert — die 0058-Lektion als Feature-Variante); Funding+TVL
  bestand das CPCV-Gate knapp (+0.05) und **drehte im Walk-Forward um**
  (+0.42 vs +0.64, jedes Jahr ≤ Basis) → Phase 4 abgelehnt, Live-Regel
  bleibt bei 11 Basis-Features. **Knappe CPCV-Verbesserungen sind Rauschen,
  bis der WF-Check sie bestätigt — Feature-Adds brauchen beide Stufen.**
  Daten-Infra-Gewinn: Binance-fapi-Funding inkl. DELISTETER Perps (294
  Paare ab 2019-09) + DefiLlama-Chain-TVL inkl. toter Chains (102
  Gas-Token) — beide survivorship-sicher, gecacht, wiederverwendbar.

- **2026-06-11 (0059, Crypto-ML-Roadmap Phase 3 — ERSTES bestandenes
  Ridge-Gate des Katalogs, trotzdem kein validierter Edge):** LightGBM gegen
  die 0058-Messlatte unter identischen 28 CPCV-Splits. **Lehre 1: das
  Ridge-Gate diskriminiert wirklich** — die KLEINSTE Konfig (15 Blätter,
  lr 0.05, 100 Bäume) schlägt Ridge in 68-82% der Splits, während die
  größte (31×300) in 0-11% gewinnt; Crypto-Nichtlinearität ist real aber
  FLACH, Kapazität muss klein bleiben (Gegenstück zu 0057, wo gar nichts
  gewann). **Lehre 2: die 0058-IC→PnL-Lücke war eine Kosten-/Konstruktions-
  frage, kein Signalproblem** — vorregistrierte Hebel (Liquiditäts-Floor
  $5M VOR dem Ranking statt Kosten-Strafe danach, Dezil-Konzentration,
  Hold-Band-Buffer 2×, Monats-Rebalance) senken Turnover 22→6×/J und drehen
  die Marktrelative von −0.56 auf +0.78; der stärkste Einzelhebel ist der
  Liquiditäts-Floor. Plateau monoton = Mechanismus, kein Zell-Glück; Ridge
  in identischer Zelle nur +0.40 → der GBT-Vorsprung überlebt die
  Portfolio-Übersetzung. Wiederverwendbar: `ml_portfolio.
  run_buffered_long_portfolio`. **Lehre 3: Batterie-Dissens ernst nehmen —
  Permutation p<0.005 + PBO 0.003 und TROTZDEM kein Kandidat,** weil (a)
  Bootstrap-KI der Hedge-Returns [−0.12,+1.16] die 0 berührt (der einzige
  echte „Edge>0"-Test, Permutations-Null ist kosten-verseucht, Mittel
  −0.30), (b) DSR 0.32 bei ehrlichen n_trials=62, (c) 2023 ein −3.2-Jahr
  vs Markt (BTC-Dominanz-Ära; 6/7 Jahre positiv, aber ~2J Alpha-Unterwasser
  — Faktor-Crash-Risiko, das IC/Sharpe nicht zeigen), (d) Dezil×Floor-Buch
  = Median 8 Namen (min 2!) = kaum noch Querschnitt. **Lehre 4 (Methodik):
  der CPCV-Stitch ist KEIN handelbarer Pfad** — Modelle, die 2020
  vorhersagen, sind (purged) auch auf 2021-26 trainiert; CPCV beantwortet
  Modellvergleich/Skill, den Pfad beweist nur Walk-Forward/Live. Eingefrorene
  Regel (LGBM0 h28, ME, Dezil, Buffer 2×, Liq≥$5M) für Live-Forward
  registriert 2026-06-11.

- **2026-06-11 (0058, Crypto-ML-Roadmap Phasen 0-2 — Survivorship-freies
  Universum gebaut, Ridge-Messlatte steht):** Neue Infra `crypto_xsection` +
  `crypto_features` + `tests/test_crypto_universe.py` (8/8 grün).
  **Daten-Durchbruch: CMCs Web-API (`api.coinmarketcap.com/data-api/v3/...
  /listings/historical?date=`) liefert die wöchentlichen historischen
  Top-200-Snapshots gratis** (462 Wochen 2017-2026, PIT-Marktkap-Ränge inkl.
  aller toten Coins), und **Binance `/api/v3/klines` liefert auch DELISTETE
  Paare voll** (BCC/VEN/SRM/ANC verifiziert; data.binance.vision-S3 listet
  alle je existierenden Symbole) → 105/370 Panel-Spalten (28%) sind heute tot
  = echtes Graveyard. **Lehre 1 (Daten-Falle, vor dem ersten Lauf gefangen):
  Delist-Relist unter GLEICHEM Ticker** — Binance delistete LUNAUSDT (Terra,
  →0) am 13.05.2022 und vergab dasselbe Symbol ab 31.05.2022 an Luna 2.0;
  `pct_change`/Momentum über die Lücke hätte ein Millionen-Prozent-Artefakt
  gebucht (Verwandter der Roll-Gap-Lehre 0048). Fix: interne Lücken >4 Tage
  splitten die Serie in unabhängige Segment-Spalten (`LUNAUSDT~2`). Außerdem:
  CMC-Symbol→Binance-Ticker braucht Alias-Kandidaten (BCH↔BCC 2018, VET↔VEN);
  alle Kandidaten werden Mitglied, die Bars-Schnittmenge wählt das damals
  handelbare Paar. 1 Symbol ist non-ASCII (`币安人生USDT`) → URLs quoten.
  **Lehre 2 (Kern-Befund): hoher IC ≠ Portfolio-PnL.** Ridge-OOS-IC unter 28
  purged CPCV-Splits stark und OHNE Decay (h28 +0.137, t=11.7, JEDES Jahr
  2019-2026 positiv — Gegenteil der toten Commodity-XSection 0057), aber das
  naive inverse-Vol-Top-Quintil monetarisiert ihn nicht: Long-only netto 0.56
  < Markt 0.61 < BTC 0.76 (Hedge vs Markt -0.47..-0.68); L/S brutto +0.39 →
  netto -0.08 (Turnover 56-78×/J × gestaffelte 12-100bps/Seite). Viel IC
  sitzt im Short-Leg (vorhersagbar blutende Small Caps) — retail kaum
  handelbar. Die Lücke IC→PnL (Rebalance-Frequenz, Leg-Konzentration,
  Buffer-Ränge) ist DIE Phase-3-Frage; jeder Hebel zählt als Trial.
  Equal-Weight-Universum hat CAGR -5.4% (der mittlere Top-150-Coin VERLIERT)
  — Long-only-Crypto-Claims immer gegen cap-weighted Markt UND den eigenen
  Pool benchmarken, sonst verkauft man Beta-Differenzen als Alpha.

- **2026-06-11 (0057, ML-Commodity-Roadmap Phasen 0-5 komplett — sauberes Null
  + drei Methodik-Lehren):** Komplette ML-Pipeline gebaut (`cot_data` CFTC-COT-
  PIT-Loader, `commodity_features` 14 Feature-Panels, `cpcv` CPCV+PBO,
  `ml_portfolio` Quintil-L/S) und LightGBM gegen Ridge unter 28 purged CPCV-
  Splits getestet. **ERGEBNIS: Ridge-Gate verfehlt** (LGBM gewinnt nur 25-46%
  der Splits je Horizont), DSR 0.233, Label-Retrain-Permutation p=0.065, Decay
  +0.93 (vor 2015) → ~0 (danach) — ML kombiniert die zerfallenen Faktoren aus
  0047/0048 zu einem zerfallenen Faktor. Die Roadmap-These „weniger
  institutionalisierter Markt" gilt post-2015 nicht mehr. **Lehre 1 (Daten,
  teuer gefangen): Databento-Tagesbars sind UTC-datiert → Globex-
  Sonntagssessions erzeugen dünne „Sonntags"-Zeilen, und `to_period('W')` legt
  den Wochen-Rebalance EXAKT darauf** — der Querschnitt kollabierte auf ~5/17
  Namen (und als die Grain-Sonntagssessions 2014 endeten, starb das Portfolio
  still). Der erste Lauf zeigte Permutation p=0.032 auf einem nach 2015 fast
  positionslosen Buch = Schein-Signifikanz aus der dünnen Frühperiode. Fix:
  Kalender auf Tage mit ≥50% beobachteten Bars filtern (`price_panels`).
  **Immer Zeilen-pro-Datum über die ZEIT prüfen, nicht nur Spalten-Coverage.**
  **Lehre 2: bei Turnover-behafteten Strategien ist die Rank-Shuffle-
  Permutations-Null KOSTEN-verseucht** — zufällige Rankings zahlen volle
  Kosten (Null-Mittel -0.56), also misst p=0.002 nur „besser als zufällig
  NACH Kosten", nicht „Edge > 0". Ehrliche Tests: Label-Shuffle MIT Komplett-
  Retrain (p=0.065) und t-Test gegen 0 (p=0.29). Die richtige Null wählen —
  Gegenstück zur 0052-Lehre (dort half die passende Baseline dem Signal, hier
  entlarvt sie es). **Lehre 3: Feature-Importance-Stabilität ≠ Edge** — das
  LGBM lernte über alle Splits dieselbe Struktur (Spearman 0.92: Term-Spread,
  Skew, Realzins, Basis-Momentum), die OOS nichts prognostiziert; Konsistenz
  des Modells beweist keine Prognosekraft. Nebenbefunde: MLP schlägt GBT
  nicht (Phase-5 wie erwartet); h5/h21 an der Kosten-Wand, nur h63 mit
  Brutto-Puls (+0.52) = Niederfrequenz-Regime bestätigt; statt Optuna ein
  vorab fixiertes 8er-Gitter = zählbare n_trials. COT-PIT: Freitag-15:30-ET-
  Release liegt NACH dem Futures-Settlement → +1-Handelstag-Shift nötig
  (strenger als die übliche „+3 Tage"-Konvention). CFTC-Socrata-API frei und
  vollständig (888 Wochen × 17 Märkte); Marktnamen heißen jetzt
  „WTI-PHYSICAL"/„NAT GAS NYME". Wiederverwendbar: CPCV/PBO für JEDES
  künftige Multi-Konfigurations-Screening (PBO auf Noise ≈ 0.5 nur im Mittel
  über Datensätze — pro Datensatz hochvariant, nicht überinterpretieren).

- **2026-06-10 (0056, Risk-Managing des 0054-VIX-Carry — zwei wichtige Sizing-Lehren):**
  Aus dem 0054-Outright-Reject (echter Edge, −34 %-Tail) per Risk-Management ein konto-
  verträgliches Sleeve gemacht. **Lehre 1 (kontraintuitiv): Vol-Targeting versagt bei
  Short-Vol/Short-Gamma.** Exposure ∝ 1/realisierte-Vol senkte den Sharpe (0.74→0.32)
  STÄRKER als den Tail und erhöhte die Kurtosis (6→12) — weil der Short-Vol-Tail GAP-
  getrieben ist: der Crash kommt, BEVOR die realisierte Vol das Target herunterzieht,
  also ist die Position am Gap-Tag noch groß. Vol-Targeting frisst die ruhige Carry-Ernte
  und sieht den Gap nicht → nach Vol-Target+Puffer Permutation p≈0.90 (Edge zerstört). Bei
  gap-lastigen Strategien ist Vol-Targeting das FALSCHE Werkzeug. **Lehre 2: pures lineares
  Down-Sizing erhält den Edge exakt** — Skalieren eines Return-Streams ist linear, also
  bleiben Sharpe-Charakter/Permutation/DSR invariant, nur die Absolutgröße schrumpft. Faktor
  0.149 (schlimmster historischer Tag = −5 %) → Sharpe 0.55, CAGR 6.6 %, MaxDD −11 %,
  Permutation p=0.012, DSR 0.972 = legitimes signifikantes Sleeve. **Aber 2 Vorbehalte:**
  (a) „−5 %-Tag" ist deskriptiv für die HISTORIE, kappt keinen künftig schlimmeren Gap
  (echtes Cap braucht VIX-Call-Hedge); (b) der VIX-Call-Hedge kostet ~1-5 %/Jahr und frisst
  auf 6.6 % CAGR die halbe bis ganze Rendite = das VRP-Dilemma (Tail-Versicherung ≈ Prämie).
  **Nebenbei bestätigt: der Sharpe sinkt beim Down-Sizing 0.74→0.55, weil die 2 %-Risk-free-
  Hürde bei kleiner CAGR proportional mehr frisst — ehrlicher Effekt, kein Bug.** Verdikt:
  kleines optionales Satellit-Sleeve, Priorität unter den niederfrequenten Leads 0050/0052.

- **2026-06-10 (0051-0055, Rest der „Paper-Edge"-Liste — 1 Treffer, 4 Reject mit je
  eigener Lehre):** Komplette Restliste durchgetestet. **Bilanz Paper-Edges gesamt:
  2 testing-Leads (0050 Turn-of-Month, 0052 Pre-FOMC), 4 abgelehnt (0049/0051/0053/0054),
  1 Daten-Blocker (0055 PEAD).** Vier verschiedene Reject-MECHANISMEN sauber getrennt —
  das ist die eigentliche Lehre:
  **(1) 0051 Overnight Drift = Phänomen REAL, Turnover tötet es.** Overnight Brutto-Sharpe
  0.94 (t-p=5e-08, ES-1h-Peak 02:00 ET EU-Open bestätigt NY-Fed), aber 252 RT/Jahr × 3bps
  ≈ 7.6%/J → netto Sharpe 0.23 (p=0.182), und **Buy&Hold (0.64) schlägt die Netto-Strategie**.
  Anders als 0049 (Signal leer): hier ist das Signal STARK, nur die Frequenz unbezahlbar.
  **(2) 0052 Pre-FOMC = TREFFER, aber nur in der richtig gemessenen Variante.** Der strikte
  „Vortag"-Drift (Lucca-Moench-Schlagzeile) ist NICHT sig (p=0.36); der Drift sitzt in der
  **Nacht IN die Ankündigung** (Close[A-1]→Open[A], handelbar vor 14 Uhr): +16.18 bps = 5×
  gewöhnliche Nacht, Win 67.6%, Permutation gegen ZUFÄLLIGE NÄCHTE (nicht gegen 0 — kontrolliert
  die Overnight-Baseline aus 0051!) p=0.0034, DSR 0.995, KEIN Decay (2000-14 +16.16 / 2015-26
  +16.20 identisch). **Lehre: die a-priori-korrekte Fenster-Definition + die richtige Permutations-
  NULL (gegen die passende Baseline) entscheiden — gegen 0 testen hätte das Overnight-Ergebnis
  überverkauft.** Klein (~1%/J, 8 Nächte) → Overlay-Bein wie 0050.
  **(3) 0053 Monetary Momentum = Signal leer** (beta≈0, corr 0.04, Permutation p=0.276). Richtung
  stimmt (dovish>hawkish) aber winzig. Vorbehalt: 2J-Yield-Surprise-Proxy verrauschter als
  Fed-Funds-Futures-Kuttner.
  **(4) 0054 VRP/VIX-Carry = ECHTER Edge, abgelehnt auf RISIKO nicht Signal.** Short-VIXY-im-Contango
  Sharpe 0.74, Permutation p=0.005, DSR 0.993 — aber MaxDD -63%, **schlechtester Tag -34%** (>10σ).
  **Kern-Lehre: Sharpe & DSR BELOHNEN Short-Vol, sind aber blind für den Links-Tail — bei Short-
  Gamma/Short-Vol müssen MaxDD/Worst-Day/Kurtosis das Urteil dominieren, nicht Sharpe.** Wieder nur
  mit Defined-Risk-Hedge.
  **(5) 0055 PEAD = bewusst NICHT gebaut** (Daten-Blocker: historische Earnings-Surprises survivorship-
  frei nur kostenpflichtig; yfinance ~1-2J/Ticker). Kein Pseudo-Test auf heutigen Mega-Caps (Disziplin
  wie IC-Gate). **Daten-Infra-Gewinn: FOMC-Termine — der FRED-„FOMC Press Release"-Release-Feed (rid=101)
  ist UNTAUGLICH (liefert jeden Geschäftstag, nicht Sitzungstage); Web-Extraktion fehlerhaft (2023-Glitch).
  Lösung: verifizierte hartkodierte Liste 2000-2026 (2021-26 gegen Fed gegengeprüft) + strikte 8/Jahr-
  Assertion. FRED-API via PowerShell + dangerouslyDisableSandbox für DGS2.** Übergreifend: die 2 Treffer
  sind BEIDE niederfrequent + flow/struktur-getrieben (Turn-of-Month, Pre-FOMC-Overnight) und BEIDE
  Overlay-/Timing-Beine, kein Standalone — bestätigt die Programm-These (niederfrequent trägt).

- **2026-06-10 (0050, Turn-of-the-Month — ERSTER Paper-Edge mit echtem Puls):**
  Paper-Edge #5 (Lakonishok/Smidt 1988): letzter 1 + erste 3 Handelstage je Monat
  long. **Bestes IS/OOS-Profil im ganzen Katalog und erster nicht-PGM-Lead, der die
  volle Batterie besteht.** Kanonisches Fenster VORAB fixiert (`turn_of_month_signal`,
  schon in seasonal.py — nicht neu bauen). **Kosten-Frage (User trade IBKR) sauber
  beantwortet: NICHT bindend** — Brutto-Sharpe 0.32 → netto MES 0.27 → netto SPY-ETF
  0.25; beide IBKR-Modelle (MES `MES_INTRADAY` 3bps RT als kapitaleffizientes Instrument
  fürs ~2000€-Konto + `IBKR_LIQUID_ETF`) ändern nichts, weil ~12 Trades/Jahr × 4d-Hold
  (Gegenteil von 0049/Intraday, wo 1 Trade/Tag die Kosten bindend machte). **Permutation
  ist DER Filter (Drift-Falle, Lehre 0016/0017): Aktien driften → beweisen, dass das
  TIMING trägt, nicht bloß das Long-Sein** — SPY p=0.035, ^GSPC 1927-2026 p=0.0002
  bestehen; Bootstrap-Sharpe-KI aktive Tage [+0.24,+1.66] OHNE 0; t-Test TOM-Tag
  p=0.0075; **DSR 0.916** (höchster je — Robustheits-Plateau + Langhistorie; bestätigt
  nebenbei, dass der DSR-Fix funktioniert, der Wert ist nicht mehr mechanisch 0).
  IS/OOS/recent 0.53/0.50/0.43 = stabil, **kein IS→OOS-Kollaps**; 4×4-Gitter alle 16
  Zellen positiv. **Zwei ehrliche Vorbehalte, die das Ergebnis NICHT überverkaufen:**
  (1) **Post-Publikations-Decay** — TOM-Tag-Prämie je Dekade ^GSPC fiel von +16-24bps
  (vor 2000) auf +3.7-7.3bps (nach 2000, ~halbiert, aber nicht tot); (2) **kein
  Standalone-Index-Schläger** — Voll-Tagesreihe-Sharpe 0.27 < B&H 0.54, weil 81% der
  Zeit flat (Drift entgeht) → der Edge ist ein **Timing-/Overlay-Bein** (Kapital nur am
  Wechsel, aktive-Tage-Sharpe ~0.9), nicht ein B&H-Ersatz. **Meta-Lehre: die Saison-/
  Flow-Schiene trägt, wo die Intraday-/Cross-Sectional-Schienen scheiterten — niedrige
  Frequenz macht Kosten vernachlässigbar; genau das vom Intraday-Programm vorhergesagte
  Regime.** Nächst (registriert): Cross-Index-OOS (Nasdaq/DAX/Russell, kein Re-Fit, wie
  Platin→Palladium 0021), Live-Forward Juli 2026, als 12×/Jahr-Bein in Overlay 0036.

- **2026-06-10 (0049, Start der „Paper-Edge"-Liste):** **Neues Programm:
  publizierte Anomalien mit struktureller Ursache** (aus Claude.ai-Recherche:
  Market Intraday Momentum, Overnight Drift, Pre-FOMC, Turn-of-the-Month, Carry,
  VRP, PEAD). Auswahl-Logik des Vorschlags: nur Effekte mit (a) Top-Journal/Large-
  Sample-Beleg, (b) struktureller/behavioraler Ursache, (c) mit unserer Pipeline +
  gratis/billig-Daten testbar. **0049 (Market Intraday Momentum, Gao/Han/Li/Zhou
  2018 JFE) ABGELEHNT — und es bestätigt unseren eigenen Befund 0040/0041 hart:**
  Die Paper-Behauptung „erste 30 min (+ Overnight-Gap) sagen die letzten 30 min
  voraus" ist auf ES.c.0 2010-2026 **leer**: beta(first30→last30)=**−0,007**,
  corr −0,007, Sign-Strategie-Brutto-Sharpe **−0,05**. Die im Paper zentrale
  Intraday-Autokorrelation EXISTIERT HIER NICHT — exakt wie 0040 (corr Morgen→
  Nachmittag +0,02) und 0041 (ES-Autokorr ≈0). **Disziplin-Gewinn: ein 4-Zeilen-
  `explore.py` (Regression beta + Sign-Sharpe je Prädiktor) tötete die Hypothese,
  BEVOR der volle Report gebaut wurde** — gleiche Vorab-Disziplin wie der IC-Gate
  bei den Fundamentals. Einziger echter Brutto-Puls = die **12. Halbstunde**
  (15:00-15:30 → 15:30-16:00, Momentum-Continuation in den Close): Brutto-Sharpe
  +0,34/+0,63 bps — aber **netto −2,27 bps an der 3-bps-MES-Wand**. Magnitude-
  Conditioning (nur Top-Tercil |Signal|) rettet nichts; einzig `h12 |top3|`
  erreicht **Netto-Breakeven (−0,03 bps, Win 51,3%)** — aber als 1 von 8
  gescannten Zellen mit **DSR 0,450 <0,5 = Selektions-Glück**, Permutation
  p=0,091, Bootstrap-KI [−0,59,+0,41] über 0, t-Test NETTO signifikant negativ.
  **Meta-Lehre: ein publizierter Name + plausible Flow-Story (Gamma/LETF-Hedging)
  ist KEINE Garantie — der Effekt muss auf UNSEREN Daten und nach UNSERER Kosten-
  Wand überleben; 30-50% Paper-Decay erwarten und die eigene Batterie entscheiden
  lassen, nicht das Paper. Liquider-Index-Intraday-Richtung bleibt tot (0012-0015/
  0038-0041/0049), egal wie gut die Theorie klingt.** ES 1-Min lag bereits gecacht
  → kein Databento-Neukauf. Nächste Paper-Edges: #5 Turn-of-the-Month (Saison-
  Engine, umgeht die Kosten-Wand, höchste Erfolgswahrscheinlichkeit) und #2
  Overnight Drift (gleiche ES-Daten).

- **2026-06-09 (0048 Carry + Terminstruktur-Daten + Roll-Artefakt auf BEZAHLTEN
  Daten):** **Freie Futures-Terminstruktur erschlossen:** Databento Continuous
  `.c.0` (Front) + `.c.1` (2. Kontrakt), täglich, GLBX.MDP3 (CME/NYMEX/COMEX/CBOT,
  16-17 Rohstoffe, KEINE ICE-Softs), 2010-06 ff., ~$1.56 vom Gratis-Kredit
  (`quantlab.futures_curve`, Parquet-Cache). EIA publiziert die Energie-Kurve
  (WTI/NG/HO/RB Kontrakt 1-4) komplett gratis als Alternativ-/Cross-Check. **IBKR
  ist für den BACKTEST untauglich** (löscht abgelaufene Kontrakte → keine tiefe
  Historie), aber gratis fürs LIVE-Carry-Signal (volle aktuelle Kette, delayed,
  Paper-Account). **0048 (Cross-Sectional Commodity Carry) ABGELEHNT — wichtigste
  Roll-Lehre des Katalogs:** Der NAIVE Test (`Front.pct_change()`) gab OOS-Sharpe
  **-1.57**, t-p=0.000-NEGATIV, Permutation p=1.000 → sah aus wie katastrophal
  invertierter Faktor. **War zu 100% ein Roll-Artefakt (Lehre 0028/0029, aber
  diesmal auf BEZAHLTEN Premium-Daten und VOR jedem Report gefangen):** Databentos
  `.c.0`-Continuous ist NICHT back-adjusted → `pct_change` bucht den Roll-Sprung
  mit. Zerlegung: **-39 bps/Tag an Roll-Tagen vs -1.1 bps sonst.** Bei tiefem
  Contango (Erdgas -24.7%/Jahr) springt die Reihe an jedem Monatsroll hoch; die
  Strategie shortet Contango und frisst den Sprung — den ein echter Roller nie
  zahlt. **Fix: exakte Roll-Tage aus `instrument_id`-Wechsel** (NG = exakt 12/Jahr;
  die Heuristik „Front_t≈2._{t-1}" unterzählte NG/überzählte Getreide → unbrauchbar,
  instrument_id ist Pflicht), dann Gap-Tag nullen (`roll_adjusted_close`; Intra-
  Kontrakt-Konvergenz = echter Carry bleibt). Korrigiert: OOS -1.57→**-0.40**, IS
  **+0.31**/OOS -0.40 = IS→OOS-Kollaps (wie 0017/0034), Perm p=0.77, DSR 0.006 →
  kein Edge. **Carry + Momentum (0047) beide im 2010er-Jahrzehnt zerfallen** —
  cross-sektionale Rohstoff-Klasse 2010-2026 vorerst erschöpft. **Meta-Lehre: ein
  Sharpe, der zu schlecht ist (≤-1.5, p gegen 1.0), ist genauso verdächtig wie einer,
  der zu gut ist — beides schreit nach Artefakt; bei Continuous-Futures IMMER zuerst
  roll-korrigieren (back-adjust via instrument_id), BEVOR irgendein Carry/Return-
  Urteil zählt.** Tests in `tests/test_futures_curve.py`.

- **2026-06-08 (DSR-Fix + Cross-Sectional-Paradigma gestartet):** **Zwei
  Defekte im Deflated Sharpe gefixt** (significance.py), beide machten die Metrik
  faktisch binär (1.0 bei n_trials=1, ~0.0 sonst): (a) `n_trials=1` ergab
  `z(1-1/1)=z(0)=-inf` → DSR mechanisch 1.0 für JEDEN Forward-Test → jetzt
  separat als PSR-gegen-0 (`expected_max_sharpe=0`); (b) `sharpe_variance_across_
  trials=1.0` hartkodiert war auf falscher Skala — per-period-Sharpes sind ~0.05,
  V=1.0 blies SR* auf ~2.6 und zerquetschte jeden Screen-Effekt auf DSR≈0 →
  jetzt aus echter Trial-Streuung (`trial_sharpes`) oder analytischem Fallback
  `1/(n_obs-1)` geschätzt. Auch Kurtosis-Default `returns=None` von 0.0→3.0
  korrigiert (PSR-Nenner). **WICHTIG: die Behauptung „du übergibst annualisierten
  Sharpe → √252-Doppelzählung" war FALSCH** — die Caller (0006/0008/0009) rechnen
  bereits `sp = mean/std` (per-period), genau wie der Docstring verlangt. Immer
  den Code prüfen, nicht der Diagnose von außen trauen. Die alten Ablehnungen
  hingen ohnehin an Permutation+OOS, nicht am DSR. Regressionstests in
  `tests/test_significance.py`. **Neues Paradigma gestartet (cross_sectional.py):**
  raus aus der Frequenz-Zwickmühle (saisonal=zu wenig Trades / intraday=Brutto≈
  Kosten). **0047 (Cross-Sectional Commodity Momentum 12-1) ABGELEHNT, aber
  lehrreich:** L/S-Quartile über 21 Rohstoff-Futures, **Brutto-Sharpe -0.51 →
  Signal vor Kosten genuin negativ** (Kosten-Drag nur 0.8%/Jahr — KEIN Kosten-
  problem wie intraday), jede Lookback×Rebalance-Zelle negativ, IS -0.89/OOS
  -0.41, Permutation p=0.75, korrigierte DSR=0.003 (sauber abgestuft!). Rohstoff-
  Momentum ist nach der Index-Welle 2004-2014 zerfallen. **Das negative Vorzeichen
  ist ein Hinweis (Laggards schlugen Winner → Mean-Reversion/Carry), NICHT zum
  Umdrehen-und-Neufitten** (= In-Sample-Overfit). Nächster Schritt: vorab-
  registrierte Carry-Hypothese (Term-Struktur long Backwardation/short Contango,
  strukturell) — **braucht Mehrkontrakt-Daten, yfinance liefert nur Front-Month;
  das ist die eigentliche offene Hürde, nicht das Konzept.** Engine ist look-ahead-
  sicher (gepflanzter Hellseher-Test) + exakt dollar-neutral (Netto 5.5e-17).

- **2026-06-07 (0045-0046 + Daten-Zugang, Fundamental-Programm Phase 4):** **Der
  USDA/EIA-„Geo-Block" war die Sandbox, nicht Geo.** Mit `dangerouslyDisableSandbox:
  true` (Bash/PowerShell) sind FRED/EIA/NASS/FAS alle vom Rechner erreichbar (gaben
  vorher in der Sandbox 403/timeout). Keys liegen gitignored als `.fred.key`/`.eia.key`/
  `.nass.key`/`.fas.key` (`*.key`-Regel deckt sie); `read_api_key(service)` in
  fundamental_data.py löst Env-Var→Keyfile auf (alle Loader jetzt `api_key=None`).
  **Workflow: Fundamental-Daten EINMAL mit Sandbox-off ziehen → Parquet-Cache → danach
  Backtests normal.** Status der freien Quellen: **FRED/EIA/NASS = 200 (live)**; **FAS
  PSD/WASDE = HTTP 500** (deren OpenData-API ist serverseitig flakey; `API_KEY`-Header
  korrekt erkannt, aber 500 — WASDE alternativ via Cornell-Mann-CSV). **2 NASS-Loader-
  Bugs gefixt** (fielen in 0042 nie auf, weil geblockt): `unit_desc='PCT AREA'` ist
  ungültig (→400, entfernt); Condition-Stufe steht bei Baumwolle in `short_desc`
  ("...PCT GOOD"), NICHT in `class_desc` (=„UPLAND") → Parsing auf short_desc-Suffix.
  **0045 (Baumwolle Crop-Condition Δ, H-CT-01) ABGELEHNT:** IC(22d)=-0.037 (p=0.42),
  Event-Study 41 Events Δ<-5pp Median +0.10%/Win 51% = Münzwurf. **Lehre: die
  Report-Surprise-Klasse trägt nur Edge bei DISKRETER Info-Konzentration (monatl. WASDE
  0032, 78% auf 6 Tagen) — eine WÖCHENTLICHE, meistbeobachtete Reihe (Crop-Condition) ist
  laufend eingepreist, eher Preis als Report.** **0046 (Kupfer/China-IP-Surprise, H-HG-01)
  ABGELEHNT — aber lehrreichster Fundamental-Test:** ERSTES Feature, das den IC-Screen
  passierte (IC(66d)=+0.12, naive p=0.046), von der vollen Batterie gekillt. **DIE
  methodische Kern-Lehre: bei ÜBERLAPPENDEN Forward-Returns (66d-Hold, monatl. Feature)
  ist die naive IC-t-Statistik wertlos — sie war p=0.046, die überlapp-korrekte Permutation
  auf der Position gab p=0.099.** Dazu IS 0.64→OOS 0.07 (Superzyklus-Drift-Falle wie
  0017/0034), Sharpe 0.39≈B&H 0.35 (Beta bei 65% Exposure), nicht lag-robust, und der
  US-INDPRO-Cross-Check mit ECHTEN ALFRED-Vintages leer (p=0.79). Verteidigung-in-der-Tiefe
  hinter dem IC-Gate funktioniert exakt wie vorgesehen. **China-IP-FRED-Reihe hat KEINE
  Vintages** (1 Print/Monat) → PIT nur via Publikations-Lag; nur US-Makro (INDPRO: 15
  Vintages/Punkt) ist echt vintaged. **Gesamt: Fundamental-Programm 5/5 abgelehnt
  (0042-0046)** — freie, breit-beobachtete Quellen (Wetter/Ethanol/Frost/Crop-Condition/
  Makro) tragen keinen 1-3M-Edge; einziger offener Pfad = diskreter WASDE-Surprise, sobald
  FAS erreichbar.

- **2026-06-07 (0042-0044, Fundamental-Programm Phase 1-3):** **Das Alt-Data-/
  Fundamental-Framework ist gebaut** (`quantlab.fundamental_data` PIT-Loader,
  `quantlab.features` Anomalie/Surprise/Δ, `quantlab.ic` IC-Decay+Permutation,
  `fundamentals/HYPOTHESES.md` Vorab-Register, `tests/test_pit.py` Look-ahead-Guard).
  Drei Hypothesen getestet, **alle abgelehnt** — mit drei reusablen Lehren: **(a)
  US-Behörden-APIs sind in dieser Umgebung geoblockt** (USDA FAS PSD + EIA beide
  HTTP 403/timeout, schon auf dem Root ohne Key). Open-Meteo (keyless) + yfinance
  gehen durch. → WASDE-/EIA-Hypothesen (H-SB-03, H-CT-02, H-LE-02, Crop-Condition)
  hier nicht testbar, müssen aus Heimnetz nachgeholt werden. **(b) ERA5-Grid-Daten
  sehen keinen Frost.** Die ~25-km-Zelle glättet lokale Tal-Kältesenken weg: bei
  (-19.5,-43.5) ist die kälteste Nacht je 2.3 °C, der 2021er Frost zeigt nur 3.7 °C.
  Absoluter Temp-Threshold untauglich → **Anomalie-z-Score** (robust gegen Warm-Bias)
  + **Koordinaten-Validierung gegen bekannte Events VOR dem Test**: Sul de Minas
  (-21.5,-45.5) rankt 1994/2000/2021 als kälteste Anomalien = genau die bekannten
  Frostjahre; die Nord-Koordinate nicht. **(c) Die Frostprämie ist real aber
  nicht-timebar** — verstärkt 0027 mit echten Daten: selbst *nach* einem z<-2σ
  Kälte-Event ist der Median-Forward-Return negativ (22d -14%, 66d -12%, nur 2/5
  Events positiv), weil z<-2σ ≠ pflanzentötender Frost (3/5 waren harmlose
  Kältenächte, Erntedruck dominierte). **Placebo-Methodik bewährt (0043):** RBOB/Zucker
  zeigte kein Signal, aber der RBOB/Gold-Placebo leuchtete (IC(66d)=-0.27, p=0.000) →
  hätte Zucker ein Signal gezeigt, wäre es als generische Energie-Beta entlarvt worden.
  **Gesamt-Muster: die meistbeobachteten Soft-Commodity-Fundamentaldaten (Wetter,
  Energie-Parität, Frost) tragen keinen 1-3M-Edge** — voll eingepreist oder
  nicht-timebares Fat-Tail. Die einzige je funktionierende Klasse im Katalog bleibt
  der **Report-Surprise** (Mais-WASDE 0032: 78% der Edge auf 6 Tagen) — und genau die
  ist hier geoblockt. **Disziplin-Gewinn:** Der IC-Gate (kein Backtest bei IC≈0) hat
  bei 0042/0043 zwei sinnlose Backtests verhindert; bei 0044 (Sparse-Event) war die
  Event-Study der primäre Test, nicht der IC.

- **2026-06-06 (0038, Prop-Programm):** **Free intraday-data inventory** for the
  prop research program (Prop-Edge-Framework.md). yfinance daily OHLC is deep and
  clean (SPY 1993+, QQQ 1999+, ES=F/NQ=F 2000+, ^GSPC 1927+). Real intraday is the
  bottleneck: yfinance gives `1h` only ~2.4y (ES=F/MES=F since 2024-01, SPY 1h since
  2023-07), `5m/30m` only 60 days. Stooq's keyless CSV is now behind a JS
  proof-of-work challenge (dead). Consequence: **gap / open-to-close studies are
  fully testable on daily OHLC with decades of history** (gap = `Open_t/Close_(t-1)`,
  trade PnL = `Close_t/Open_t`, flat overnight) — that is the natural first prop
  hypothesis; true intraday hypotheses (opening-range, time-of-day) only have ~2.4y
  of 1h ES and must be treated as thin/exploratory until a deeper source (Databento
  free credit / Alpha Vantage month-param) is wired up. **For gap studies use the
  ETF (SPY/QQQ): its daily `Open` is the real RTH auction open. The futures
  continuous `Open` is the Globex session open (18:00 ET) — NOT a gap instrument**
  (ES/NQ show gross-negative "gap fade" = continuation, an artifact of this).
- **2026-06-07 (0039, Databento wired):** **Real intraday futures data is now
  available** via Databento (`quantlab.futures_intraday`, GLBX.MDP3, Parquet cache,
  cost-guarded; key in gitignored `.databento.key`). Cached: ES.c.0 + NQ.c.0 `ohlcv-1h`
  full (2010-2026, ~$0.94 each) and **ES.c.0 `ohlcv-1m` full (5.5M bars, ~$20.2)** —
  ~$22 of the $125 free credit spent, ~$103 left. Gotchas: continuous symbology
  (`ES.c.0`, `stype_in="continuous"`) **fails to resolve when `end` is omitted** —
  always pass an explicit end (loader defaults to today). Bars are timestamped at the
  interval START; CME RTH = 09:30-16:00 ET (filter on `tz_convert("US/Eastern")`).
  ES intraday returns == MES, so backtest ES.c.0 and apply `MES_INTRADAY` cost. On
  this data the opening-range fade (#1) was a clean cost-gate reject: breakout fade
  AND continuation have gross ~0 / win ~49% across every OR window x holding horizon
  x OR-width tercile — the liquid-index intraday directional edge is ~0 and cost is
  binding, same wall as BTC 0012-0015 and gap 0038 (no look-ahead this time, the
  engine is clean, the signal is simply empty). **Pattern across 0012-0015/0038/0039:
  a single liquid market's intraday DIRECTION is not exploitable net of cost; the
  remaining prop-viable class is relational/market-neutral (ES<->NQ lead-lag) or
  structural time-of-day, not a directional bet on one series.**
- **2026-06-07 (0040/0041, prop intraday list complete):** The framework's whole
  intraday hypothesis list is now tested and **all rejected on cost**: #1 opening-range
  fade (0039), #2 gap fade (0038), #3 time-of-day (0040), #4 breakout continuation
  (in 0039), #5 ES<->NQ lead-lag/RV (0041). Findings worth keeping: (a) **the
  "last-hour / close-auction drift" is empirically ABSENT** on ES 2010-2026 — intraday
  equity gains are spread across the session, not concentrated into the close (NQ 1h
  confirms ET-15:00 hour Sharpe -0.06); the famous equity drift is *overnight*, which
  prop rules forbid holding. (b) **Intraday autocorrelation ~0** (ES morning->afternoon
  +0.02, like BTC 0015) — no time-conditioned directional structure. (c) **ES<->NQ
  lead-lag is fully HFT-arbitraged** (corr(ES[t],NQ[t+1])=+0.001) but the **beta-hedged
  RV spread genuinely reverts** (1-min autocorr -0.107, win rate rises monotonically to
  58% at z=2.5) — the ONLY real intraday signal found, yet only 0.3-0.5 bps/trade vs a
  ~6 bps two-leg cost (needs maker-rebate HFT to clear). **Strategic conclusion: a
  retail/prop cost structure cannot access liquid-index intraday alpha — direction is
  empty, RV is real-but-sub-cost. The confirmed path for this account stays the
  LOW-FREQUENCY seasonal track (Platin 0021 etc.), where ~1 trade/year makes cost
  negligible — the exact opposite regime.** Do not re-litigate intraday index direction
  without a fundamentally cheaper execution (maker fills + rebates), which is out of
  scope for a 2000-EUR prop account.
- **2026-06-06 (0038):** **Look-ahead via a same-bar trend filter** — the framework's
  #1 intraday trap, caught live. A "buy the dip in an uptrend" gap-fade scored
  Sharpe 2.82 (+12.5 bps/trade) only because the trend filter used `Close_t > MA_t`,
  and `Close_t` is unknown at the open. `Close_t > MA` is mechanically correlated
  with a positive open->close (a day closing high vs its average usually rose from
  the open), so the long secretly pre-selected up-days. Lagging the filter to
  open-time info (`Close_(t-1) > MA_(t-1)`) collapsed it to Sharpe −0.22. **Rule: any
  intraday filter/feature must be built from data available at the decision instant;
  a feature that contains the current bar's close while the PnL is also driven by
  that close fabricates the edge.** Also reconfirmed: tiny gross edges (~1-2 bps) on
  liquid index gaps never clear even the cheap ~3 bps MES round-trip (cost gate), and
  a positive-mean cell whose top-5 days are >100% of profit is a fat-tail lottery —
  doubly disqualifying under prop rules (consistency + daily-DD breach risk).
- **2026-06-03:** On Windows, `python -m pip install --upgrade pip` chained in
  the same command that then installs packages can corrupt pip (`WinError 32`
  file lock + leftover `~ip` dist). Fix: don't self-upgrade pip mid-install; if
  pip breaks, recreate the venv and run `ensurepip --upgrade`.
- **2026-06-03 (0005):** Continuous front-month futures can print a *non-positive*
  price — WTI (`CL=F`) settled at -$37.63 on 2020-04-20. Simple `pct_change`
  returns are undefined across a zero crossing and produce nonsense (CAGR -100%,
  MaxDD -264%). Guard any futures backtest with `if (close <= 0).any(): skip`,
  or use a ratio-adjusted continuous series. "Futures are cleaner than ETFs" is
  only half true — they have their own artifacts (negative prints, roll gaps).
- **2026-06-05 (0025):** yfinance has **no reliable LME base-metal series**. The
  zinc front-month `ZNC=F` looks alive (price ~2300, positive) but is a *dead
  symbol*: it froze around 2018–2019 and from 2020 on returns a single repeated
  print — **1 distinct close per year**, ~100% zero-return days. A whole backtest
  ran "fine" and produced numbers (Sharpe −0.54, OOS-"Sharpe" −59) that were pure
  cost-on-zero-movement artifacts. Before any seasonal test on an exotic future,
  **screen data quality first**: `close.groupby(year).nunique()` and the
  zero-return fraction expose a frozen feed in seconds, before a backtest is even
  worth running. This check is now a guard in `0025/run.py`.
  **Free LME workaround found:** westmetall.com publishes daily LME official
  Cash-Settlement (spot, no roll) for Zn/Cu/Al/Pb/Ni/Sn back to 2008, scrapeable —
  wrapped in `src/quantlab/lme_data.py` (`get_lme_zinc`). On that clean series the
  zinc July window actually passes the permutation test (p=0.031) — so the original
  "untestable" verdict was a *data* failure, not a strategy failure. For the full
  35y series Seasonax uses (Bloomberg `BCOMZS`, a futures-TR index), the only free
  route is a manual CSV export from Investing.com/MacroMicro. Stooq and Nasdaq Data
  Link now both require API keys.
- **2026-06-03 (0005):** In-sample optimization Sharpes are meaningless alone.
  Picking the best of 156 weekly windows in-sample gave Sharpes of 4-8 that
  collapsed to ~0 OOS for 7/8 assets. Always charge the Deflated Sharpe the full
  search width (`n_trials` = configs scanned), and treat a single OOS survivor
  among many as a lead needing a pre-registered forward test, not an edge.
- **2026-06-05 (0028/0029):** On **monthly-rolling futures** (`NG=F`, `CL=F`,
  `RB=F`, `HO=F`) every multi-week continuous-series window necessarily contains
  futures-expiry days, and a continuous front-month stitch can fabricate returns
  there (gas autumn 21.9.–1.11. looked like the strongest lead ever: perm p=0.001,
  bootstrap CI excluding zero, median +5.7%, IS≈OOS — *all real but all driven by
  the same yearly expiry cluster*). **105% of the mean trade PnL sat on ~6
  expiry-days/year**; excluding just a tight ±1-day zone around each expiry
  (26–28 Sep / 27–29 Oct) flipped expectancy +15.5%→−0.27% and permutation
  p 0.002→0.773. Permutation + bootstrap + IS/OOS + median **all pass** when the
  artifact is year-over-year consistent, so they are *not enough*. **Mandatory
  pre-step before a continuous-futures seasonal counts as a lead: a roll-day
  exclusion test** — the edge must survive removing a tight zone around every
  in-window expiry. Quarterly rollers (platinum Jan/Apr/Jul/Oct, 0019) are safer
  because a window can exit before its single roll; monthly rollers cannot. The
  54% roll-day hit rate (vs a clean mechanical stitch's 70–90%) also says: this
  was expiry-clustered fat-tails, not a fixed contango gap — but neither is a
  tradable seasonal. Reusable harness: `0029_natgas_roll_check/run.py`.
