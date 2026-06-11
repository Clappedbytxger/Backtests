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

## Environment

- venv at `.venv` (Python 3.13). Run: `.\.venv\Scripts\python.exe ...`.
- There is also a separate `D:\AI\Python` 3.10 install on the machine — do not
  use it for this project; always use the project `.venv`.

## Lessons Learned

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
