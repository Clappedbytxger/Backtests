# Roadmap: ML-Signalgenerierung auf der Crypto-Cross-Section (für Claude Code)

> Handoff für Claude Code. Nach dem sauberen Null von 0057 (Commodity-Faktoren
> post-2015 zerfallen) wechseln wir das Universum in den Markt, dessen Basis-
> Signale laut Forschung **nach Kosten** noch tragen: Crypto. Baut auf
> vorhandener Infra auf — `ccxt`-Loader (BTC-Tests 0012–0015), CPCV/PBO,
> ML-Portfolio-Engine, COT-/Feature-Panels (0057). Hardware: MacBook Air
> (Track A trivial; Track B kleine CNN auf MPS, Colab für Bursts).
> Stand: Juni 2026. Hypothesen zum Validieren, keine Anlageberatung.

---

## Teil 0 — Edge-These & warum hier, nicht bei Commodities

**0057-Lehre:** ML kombiniert Faktoren, erzeugt sie nicht. Commodity-Prämien
sind tot. Crypto ist anders:

- Cross-sektionale Crypto-Returns sind vorhersagbar und **überleben Kosten**
  (Cakici et al. 2024; Cong et al. 2022) — anders als Commodities.
- Alpha sitzt im **Long-Leg** und **persistiert** → long-only funktioniert
  (kein Short-Borrow-Problem, retail-tauglich).
- Stärker bei **Small-Caps** (Liu et al. 2023) — die Ineffizienz-Frontier.
- Ursache: junger, retail-dominierter, behavioral getriebener, noch nicht voll
  institutionalisierter Markt. Deine „illiquide Märkte"-These, endlich in einem
  legalen (DE/MiCA Spot), gratis-bedateten, 24/7-Markt.
- 24/7 = kein Übernacht-Gap (löst dein altes Saison-Problem). Hohe Vol = großer
  Brutto-Move/Trade → schlägt die Kostenwand, die Intraday/Commodities tötete.

**Realismus:** Stärkster Edge in kleinen Tokens → Spread beißt dort. Regime-
Instabilität ist extrem. Survivorship (tote Coins) ist die brutalste Falle
überhaupt. Auch das kann ein Null werden — aber in einem Markt mit echtem Saft.

---

## Teil 1 — Zwei Tracks

| Track | Ansatz | Was es ist |
| --- | --- | --- |
| **A — Klassisch (zuerst)** | GKX-light Cross-Section, LightGBM + Ridge-Benchmark | bekannte Crypto-Faktoren nichtlinear kombinieren |
| **B — Frontier** | CNN auf Preis-Chart-Bildern (Jiang, Kelly & Xiu 2023) | Modell *findet* Preismuster selbst — echte Signalgenerierung, nur Preis/Volumen-Daten |

Track A validiert das Universum/Setup mit geringem Risiko. Track B ist die
„größeres Modell, das wirklich hilft"-Wette — aber erst, wenn A sauber steht.

---

## Teil 2 — Universum & Daten (Survivorship ist der Endgegner)

**Universum:** Top ~100–200 Coins nach Marktkapitalisierung, **point-in-time**
zusammengestellt — d. h. zu jedem historischen Datum die *damaligen* Top-Coins,
inklusive der seither **gestorbenen** (Delistings, Rugs, Zero-Volume). Ein
Universum aus „heute existierenden Coins rückwärts" ist der klassische
Survivorship-Bias und macht jedes Backtest-Ergebnis wertlos.

| Daten | Quelle (gratis) | Zweck |
| --- | --- | --- |
| OHLCV (Spot + Perp) | **ccxt** (Binance/Bybit/OKX — Pipeline existiert) | Returns, Momentum, Vol, Illiquidität |
| Marktkapitalisierung + PIT-Universum | **CoinGecko API** (Free-Tier) bzw. historische Snapshots | Size-Faktor, Universums-Konstruktion |
| **Tote Coins / Delistings** | CoinGecko „inactive", Exchange-Delisting-Logs | Survivorship-Schutz |
| Funding Rates (Perp) | **Coinglass** / Exchange-APIs | Funding-Carry-Feature (Crypto-spezifisch!) |
| On-Chain | **DefiLlama** (TVL, gratis), Glassnode-Free, Dune, Artemis | Netzwerk-/Adoption-Features |
| Stablecoin-Supply, Exchange-Flows | DefiLlama / Dune | Liquiditäts-/Sentiment-Proxy |

**Wash-Trading-Filter:** Volumen auf kleinen Exchanges ist teils gefälscht. Nur
Top-Tier-Venues, plus Sanity-Checks (Volumen/Marktkap-Ratio-Ausreißer kappen).

**Loader (neu):** `quantlab/crypto_xsection.py` — PIT-Universum (mit Dead Coins),
Parquet-Cache, `get_universe_at(date)`, `get_panel(features, freq)`.

---

## Teil 3 — Track A: Features (theorie-/evidenzgetrieben)

Dominante Prädiktoren laut Literatur (Cakici 2024, Liu & Tsyvinski 2021):

| Feature | Definition | Warum |
| --- | --- | --- |
| **Momentum** | 1/2/4/8/12-Wochen-Return | stärkster, persistenter Crypto-Faktor |
| **Size** | log Marktkap | Small-Cap-Prämie (stark in Crypto) |
| **Illiquidität** | Amihud (\|ret\|/Volumen) | Illiquiditätsprämie, dominanter Prädiktor |
| **Short-Term-Reversal** | letzte 1-Wochen-Return | Überreaktion |
| **Past Alpha** | Alpha vs. Crypto-Market-Faktor, rollierend | dokumentiert dominant |
| **Funding-Carry** | Perp-Funding-Rate + z-Score | Crypto-spezifischer Carry (kein Pendant in Aktien) |
| **Volatilität / Downside-Risk** | realisierte Vol, Semi-Vol | Risiko-Konditionierung |
| **Volume-Trend** | Δ Volumen, Volumen-Momentum-Interaktion | Babiak et al.: Volumen × Lag-Return |
| **On-Chain (optional)** | Δ aktive Adressen, TVL-Trend, Netzwerk-Wachstum | Adoption (Liu & Tsyvinski: Netzwerk-Faktoren stark) |
| **Salience / Attention** | extreme-return-Salienz, Google-Trends-Proxy | Cai & Zhao: Salienz prognostiziert |

- **Target:** Forward-Return 1W (primär), 2W/4W (Ensemble), pro Datum rang-transformiert.
- **Portfolio:** **Long-only Top-Quintil** als Primärvariante (Alpha sitzt im
  Long-Leg!), Long-Short als Sekundärvariante. Inverse-Vol-Gewichte,
  Wochen-Rebalancing, volle Kosten (Spread pro Token-Liquiditätsklasse gestaffelt).
- **Modelle:** Ridge/OLS (Pflicht-Benchmark — in Crypto oft schwer zu schlagen!),
  LightGBM, RF. NN nur als Kontrolle.

---

## Teil 4 — Track B: CNN auf Preis-Chart-Bildern (JKX 2023)

- **Bild-Konstruktion:** pro Coin/Datum ein OHLC-Bild über 5/20/60-Tage-Fenster,
  3 Pixel/Tag (Open / High-Low-Bar / Close), Moving-Average-Linie als Mittelzeile,
  Volumen-Balken unten. Alle Preise pro Bild auf Max-High/Min-Low reskaliert
  (das implizite Scaling ist laut JKX ein Hauptgrund für die Vorhersagekraft).
- **Target:** binär, Forward-Return > 0 über das Ausgabe-Fenster.
- **Modell:** kleine CNN (2–3 Conv-Blöcke), Dropout, Batch-Norm — wie JKX, klein
  genug für MPS. Output → Wahrscheinlichkeit → Cross-Section-Ranking → gleiches
  Long-(Short-)Portfolio wie Track A.
- **Warum das echte Signalgenerierung ist:** kein hand-gecraftetes Faktor-Set;
  die CNN extrahiert Muster, die sich von Momentum/Reversal unterscheiden.
- **Mac-Air-Realität:** Bilder ~64×60 px, Datensatz im niedrigen Millionenbereich
  an Bildern → MPS trainierbar in Stunden; für größere Sweeps Colab Free (T4).

---

## Teil 5 — Validierung (0057-Infra wiederverwenden)

1. **CPCV + PBO** (deine `cpcv.py`) — purged + embargoed, Label-Horizont purgen.
2. **Survivorship-Unit-Test:** Universum zu Datum t enthält nachweislich tote
   Coins; kein Zugriff auf zukünftige Marktkap-/Listing-Info. **Pflicht-Gate.**
3. **Ridge/OLS-Gate:** GBT/CNN muss linear klar schlagen (in Crypto schwer!).
4. **Permutation (Label-Retrain)** + **DSR mit ehrlichem n_trials** (CNN-Epochs,
   Hyperparams zählen). DSR-Bug-Fix der Hauptpipeline vorausgesetzt.
5. **Subperioden-Decay:** Bull 2020–21 vs. Bear 2022 vs. 2023+ separat — Crypto-
   Regime sind extrem. Eine Edge, die nur im Bull lebt, ist Beta, kein Alpha.
6. **Kosten-Realismus:** Spread + Slippage pro Liquiditätsklasse; Small-Cap-Tokens
   konservativ (hier ist die Cost-Wall). Funding-Kosten bei Perp-Varianten.
7. **Wash-Trading-Robustheit:** Ergebnis mit/ohne verdächtige-Volumen-Coins.

**Gate für „Kandidat":** PBO < 0,5, schlägt Ridge in OOS-Sharpe-Verteilung,
Permutation p < 0,05, DSR überlebt, Edge in **mehr als einem** Regime, netto-positiv
nach gestaffeltem Spread, Survivorship-Test grün.

---

## Teil 6 — Phasenplan

| Phase | Ziel | Deliverable | Gate |
| --- | --- | --- | --- |
| **0** | PIT-Universum inkl. Dead Coins | `crypto_xsection.py` + Survivorship-Test | tote Coins nachweislich drin |
| **1** | Feature-Panel (Track A) | `crypto_features.py` (PIT) | reproduzierbar, leckfrei |
| **2** | Ridge-Benchmark | Cross-Section-L/S + Long-only | sauberer CPCV-Backtest als Messlatte |
| **3** | LightGBM (Track A) | `strategies/00XX_ml_crypto_xsection/` | schlägt Ridge in PBO + OOS-Verteilung, Edge > 1 Regime |
| **4** | On-Chain-Features dazu | erweiterter Report | inkrementeller Wert nachgewiesen |
| **5** | CNN-on-Charts (Track B) | `strategies/00XX_cnn_price_image/` | schlägt Track A *oder* ist unkorreliert genug zum Ensemblen |

---

## Teil 7 — Anti-Selbstbetrugs-Checkliste (Crypto-Edition)

- **Survivorship ist tödlich.** Dead Coins MÜSSEN ins historische Universum.
  Ohne das ist jedes Ergebnis Fiktion. Eigener Pflicht-Test.
- **Regime ≠ Edge.** 2020–21 macht fast alles gut aussehen. Pro Regime testen.
- **Wash-Trading:** gefälschtes Volumen verzerrt Illiquiditäts-/Volumen-Features.
- **Spread bei Small-Caps** ist die Cost-Wall (wo der Edge sitzt). Gestaffelt modellieren.
- **Look-ahead über Marktkap/Listing:** ein Coin „existierte" erst ab Listing;
  Marktkap-Rang ist PIT zu ziehen.
- **Ridge/OLS schlägt oft ML** in Crypto — wenn dein GBT/CNN das nicht klar
  schlägt, ist die Komplexität eingebildet (0057-Lehre).
- **n_trials ehrlich** inkl. CNN-Epochs/Architektur-Suche.
- **Long-Leg-Fokus:** Alpha sitzt long; Short-Leg in Crypto teuer/riskant.

---

## Teil 8 — Referenzen

- Cakici, Shahzad, Będowska-Sójka, Zaremba (2024) — 40 Features × 8 ML-Modelle;
  Past Alpha, Illiquidität, Momentum dominant.
- Cong et al. (2022); Liu, Tsyvinski & Wu (2022) — Crypto-Faktormodelle (Market,
  Size, Momentum).
- Liu & Tsyvinski (2021) — Netzwerk-/On-Chain-Variablen als Prädiktoren.
- „Forecasting cryptocurrency returns with ML" (J. Behav. Exp. Finance 2023) —
  Long-Leg-Alpha, profitabel nach Kosten, Komplexitätsvorteil begrenzt.
- Han, Kang & Ryu (2024) — TS/XSec-Momentum, stärker in Small-Caps.
- Jiang, Kelly & Xiu (2023, *J. Finance*) — „(Re-)Imag(in)ing Price Trends",
  CNN-on-charts (Track B).
- Gu, Kelly & Xiu (2020) — Methodik-Anker Cross-Section-ML.

---

*Reihenfolge wie immer: erst der Beweis (PBO-/Survivorship-/Regime-fest,
Ridge-schlagend, netto-positiv), dann Kapital. Crypto ist legal (DE/MiCA Spot),
24/7 (kein Gap), und der einzige getestete Markt, dessen Basis-Signale laut
Forschung nach Kosten noch leben — deshalb hier.*
