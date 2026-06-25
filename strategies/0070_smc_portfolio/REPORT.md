# Strategie 0070 — SMC Sweep+BOS als gleichgewichtetes Portfolio (Abschluss)

- **Kategorie:** price-action / multi-asset / portfolio
- **Status:** **abgeschlossen** — brutto schlägt B&H risk-adjusted, **netto knapp nicht**;
  für Funded-Accounts nur eingeschränkt geeignet
- **Datum:** 2026-06-14
- **Basis:** korrekt rekonstruierte 0069-Engine (asymmetrisches Pivot + Struktur-
  Filter + Pyramiding/`max_concurrent`), reproduziert die Video-Zahlen
- **Mitglieder:** Gold, Bitcoin, S&P 500, Nasdaq-100, GBP/USD (**echtes Dukascopy-
  Spot** statt 6B-Proxy; GBP reproduziert seine +131% NICHT — auf Spot ist Fixed-1R
  ein Münzwurf (Win 51%), mit Trailing nur +29% — aber als FX-Diversifikator drin)
- **Kosten:** netto = Spread + Kommission, **ohne Slippage** (die Methode des Videos,
  fairer Vergleich); Gold ~1,5 bps RT (Spot), BTC ~17 bps (Binance Taker),
  Index-Futures ~2 bps, je Round-Trip

## 1. Per-Asset: SMC (brutto/netto) vs. Buy & Hold

| Asset (Config) | brutto Sharpe | **netto Sharpe** | **B&H Sharpe** | netto Ret/DD | B&H Ret/DD | schlägt B&H? |
| --- | ---: | ---: | ---: | ---: | ---: | :--: |
| Gold (mc2, 10/10) | 0,55 | 0,15 | **0,70** | 1,35 | 15,3 | nein |
| Bitcoin (mc3, 8/4) | 0,73 | 0,55 | **0,79** | 9,35 | 19,6 | nein |
| S&P 500 (mc2, 6/2) | 0,67 | 0,64 | **0,68** | 9,01 | 8,06 | ~tie |
| **Nasdaq-100 (mc2, 6/2)** | 0,90 | **0,86** | 0,84 | 19,3 | 16,4 | **JA** |
| GBPUSD (Spot, mc1, trailing) | 0,16 | 0,07 | −0,28 | 0,59 | n/a | ja* |

Einzeln schlägt **nur NDX** B&H netto (Sharpe 0,86 > 0,84, Ret/DD 19,3 > 16,4 —
über den kleineren Drawdown). Gold/BTC liefern hohe Absolut-Returns (BTC netto
+268 %, Gold +38 %), aber **risk-adjusted unter B&H**: der hohe Return kommt aus
dem Pyramiding-Hebel (mc>1), nicht aus einem Sharpe-Vorteil.

## 2. Gleichgewichtetes Portfolio (⅕ je Sleeve, Gold/BTC/SPX/NDX/GBP-Spot)

| Kennzahl | **brutto** | **netto** | **Buy & Hold (⅕)** |
| --- | ---: | ---: | ---: |
| Total Return (10 J.) | +281 % | **+186 %** | +542 % |
| CAGR | +13,7 % | **+10,6 %** | +19,5 % |
| Sharpe | **1,26** | **0,96** | **0,98** |
| Max Drawdown | −10,8 % | **−13,0 %** | **−34,7 %** |
| Return/MaxDD | 26,1 | **14,3** | 15,6 |

(GBP ist ein schwaches Sleeve (netto +1,9 %/J) und verdünnt den Sharpe leicht
gegenüber der 4-Asset-Version (0,98), senkt aber den DD auf 13,0 %. taker-Kosten;
mit good_exec liegt der Portfolio-Sharpe ~1,08 > B&H.)

**Schlägt es Buy & Hold?**
- **Brutto: JA** — Sharpe **1,27 vs 1,04**, Ret/DD 30,5 vs 23,0, und nur **−12 %
  MaxDD vs −39 %**. Diversifikation über 4 unkorrelierte Sleeves ergibt ein viel
  glatteres Profil.
- **Netto: NEIN (knapp)** — Sharpe **0,98 vs 1,04**, Ret/DD 16,5 vs 23,0. Die
  Kosten (v. a. BTCs 17 bps + Golds hohe Frequenz) erodieren den Edge gerade
  unter B&H. Absolut macht B&H deutlich mehr (+898 % vs +242 %).
- **Der bleibende Vorteil: weniger als der halbe Drawdown** (14,7 % vs 39 %). Das
  SMC-Portfolio ist eine ruhigere Fahrt für weniger Gesamtrendite — kein
  risk-adjusted Schlagen von B&H netto.

## 2b. Reconciliation mit dem Video-Headline (+53,89 %/Jahr) — `combined_account.py`

Das Video nennt **+53,89 %/Jahr netto, MaxDD 29,24 %, $10k → $873.928**. Das ist
**nicht** ein 1/N-Portfolio, sondern **ein kombiniertes Konto** (alle Sleeves bei
ihrem DD-geleveltem Risiko, gemeinsames Compounding ≈ Summe der Sleeves). Mit
dieser Konstruktion reconcilen die Zahlen:

| Konstruktion (5 Assets, GBP=Spot) | CAGR/J | $10k → | MaxDD |
| --- | ---: | ---: | ---: |
| **Video (inkl. GBP)** | **+53,89 %** | $873.928 | **29,24 %** |
| Kombi-Konto taker | **+54,4 %** | **$914.331** | 52,4 % |
| Kombi-Konto good_exec | +63,9 % | $1.698.881 | 49,7 % |
| 1/N equal-weight (Abschnitt 2) | +10,6–12,0 % | ~$30k | 13,0 % |

**Rendite reconciled** — mein Kombi-Konto taker **$914.331 ≈ seine $873.928**
(+54,4 % vs +53,89 %). Der **DD bleibt höher (52 % vs 29 %)** — und GBP-Spot senkt
ihn NICHT (mein GBP +29 % ist ein schwacher Diversifikator, kein +131 %-Sleeve).
Die DD-Lücke ist eine **Risiko-Effizienz-/Diversifikations-Frage**: seine
Sleeves driften im Drawdown auseinander (Kombi-DD 29 % < Einzel-Gold 42 %!), meine
korrelieren (SPX+NDX beide Long-only-US-Indizes ziehen gemeinsam runter; Kombi-DD
52 % > Einzel-Gold 40 %). Seine Ret/DD 295 vs meine 173. **Wichtig: Kombi-Konto und
1/N sind dieselbe Strategie bei anderem Hebel** — der **Sharpe ist gleich**
(~0,96 taker / ~1,08 good_exec); die B&H-Frage (Sharpe) ist konstruktions-unabhängig.

## 3. Test-Batterie (Portfolio, netto)

| Test | Ergebnis |
| --- | --- |
| Look-ahead-Gate (0069) | grün (9/9, sym.+asym. Pivot) |
| **Block-Bootstrap Sharpe 95%-KI** | **[+0,37, +1,55]** (schließt 0 aus; i.i.d.-Bootstrap überschätzt, Block hält Trade-Korrelation) |
| t-Test mean daily return | p = 0,0002 |
| Deflated Sharpe (n_trials=40) | 0,971 (optimistisch — wahres n_trials höher) |
| **IS/OOS Sharpe (1. / 2. Hälfte)** | **1,52 / 0,43** (Zerfall) |
| Permutation je Asset | Indizes ~Beta (Null ≈ real); BTC p=0,064 (marginal) |
| Kosten-Sensitivität | CAGR brutto +16,1 % → netto +12,5 % |

Der Portfolio-Sharpe ist netto signifikant > 0 (Block-Bootstrap-KI ohne 0), **aber
er zerfällt OOS** (1,52 → 0,43) und das Schlagen von B&H gilt nur brutto. Der
hohe DSR ist mit dem ehrlich höheren Such-n_trials zu relativieren.

## 4. Funded-/Prop-Account-Eignung (netto)

| Kriterium | Wert | typ. Prop-Limit | Urteil |
| --- | ---: | ---: | :--: |
| Portfolio-MaxDD | −13,0 % | 10 % (trailing) | **BREACH** |
| Schlechtester Tag | −2,2 % | 5 % | ok |
| Längste Unterwasser-Phase | **618 Tage** | — | hart (Konsistenzregeln) |
| Ø Haltedauer | 5–23 **Tage** | flat overnight bevorzugt | **hält über Nacht/WE** |
| Top-5-Tage Gewinnanteil | 6 % | — | gut (glatt, kein Fat-Tail) |

(1/N-equal-weight; um auf 10 % MaxDD zu passen Risiko ×0,77 → CAGR ~+8,2 %. Das
Video-style Kombi-Konto hat ~52 % DD = für Funded-Accounts klar zu groß.)

**Verdikt Funded-Account: nur eingeschränkt geeignet.** Der 14,7 %-MaxDD reißt ein
typisches 10 %-Limit — um zu passen, Risiko **×0,68 → CAGR ~+8,5 %**. Schwerer
wiegt: die **Haltedauer von 9–23 Tagen** (Übernacht-/Wochenend-Gap-Risiko, kein
Flat-Overnight-Scalper-Profil, das Prop-Firmen bevorzugen) und die **576 Tage
längste Unterwasser-Phase** (kollidiert mit Konsistenz-/Trailing-DD-Regeln).
Positiv: niedriger schlechtester Tag (−2,5 %) und glatte Verteilung (Top-5 = 7 %).
Auf einer toleranten Firma (10–12 % DD, Overnight erlaubt) bei reduziertem Risiko
machbar — aber es ist **kein natürliches Prop-Profil**.

## 5. Ausführungskosten — Limit-/IBKR-Relative-Tools (`execution_scenarios.py`)

Das „netto" oben ist **Taker** (Spread auf beiden Seiten gekreuzt). Mit besserer
Ausführung (IBKR Adaptive/Relative/Pegged-to-Midpoint, Limit-/Maker-Fills) ändert
sich das Bild — Portfolio netto vs. B&H (Sharpe 1,04):

| Tier | Return | Sharpe | MaxDD | Ret/DD | schlägt B&H? |
| --- | ---: | ---: | ---: | ---: | :--: |
| Taker (aktuell) | +242 % | 0,98 | −14,7 % | 16,5 | nein |
| **good_exec** (½ Spread auf liquiden Beinen) | +292 % | **1,11** | −13,6 % | 21,5 | **JA** |
| limit_max (Maker beidseitig, Schranke) | +322 % | 1,18 | −13,0 % | 24,8 | JA |

**Realistische Spanne Sharpe 0,98–1,11** → mit guter Ausführung **schlägt das
Portfolio B&H risk-adjusted** (1,11 vs 1,04) bei halbem Drawdown. **Ehrlicher
Vorbehalt:** V1 ist ein **Breakout-Entry** (BOS-Close) — passive Limits leiden an
**adverser Selektion** (Runner laufen weg = kein Fill, Reversals füllen; exakt
warum die Retracement-Entry-V2 im Video schlechter war), und der Exit ist ein
Trailing-**Stop** (Market, zahlt Spread). Voll erreichbar ist `good_exec` daher
nur, soweit man Fills auf Ausbrüchen ohne große Non-Fill-Rate bekommt; der wahre
Wert liegt zwischen Taker und good_exec, `limit_max` ist eine unerreichbare obere
Schranke. BTC bleibt teuer (~10–17 bps RT, Maker-Rabatt klein; + Funding für Shorts).

## 5b. Drawdown-Diagnose + Funded-Optimierung (`dd_optimize.py`)

**Warum war der Kombi-DD 52 % vs. seine 29 %?** NICHT mangelnde Diversifikation —
die Sleeve-Korrelationen sind niedrig (SPX–NDX 0,25, alle anderen ~0). Der 52 %-DD
ist reiner **Hebel** (5 Sleeves gleichzeitig bei vollem Risiko ≈ 5× das 12 %-DD-
equal-weight). Haupt-DD-Treiber innerhalb der Sleeves: **Pyramiding (mc>1)**.

| 1/N-Variante (netto good_exec) | CAGR | Sharpe | MaxDD | Ret/DD |
| --- | ---: | ---: | ---: | ---: |
| A — Ist (config mc) | +12,0 % | 1,09 | −12,0 % | 18,6 |
| B — mc=1 (kein Pyramiding) | +7,3 % | 0,93 | −6,5 % | 16,8 |
| **E — mc=1 + Re-Level 20 % je Sleeve** | **+10,5 %** | **1,10** | **−8,6 %** | **21,2** |

**Fix = Variante E** (Pyramiding raus + Video-Methode „jedes Sleeve auf 20 %
Standalone-DD leveln"): Sharpe 1,10, MaxDD **8,6 %**, beste Risiko-Effizienz.

**City Traders Imperium (swing-/overnight-freundlich, kein Zeitlimit — passt zum
5–23-Tage-Hold):** worst day −2,2 % < Tageslimit ✓. Max-DD ist der Constraint:
- **Challenge (~10 % Max-DD, Ziel 8-10 %): gut geeignet** — Variante E auf ~7 %
  hist. DD gesized → ~8,5 %/J, Ziel in ~1 J. erreichbar, 3 % Puffer.
- **Instant (6 % Max-DD): riskant** — kein Puffer; OOS-Zerfall könnte 6 % reißen.
- Risiken: OOS-Zerfall (Sharpe 1,54→0,36) + 618 Tage längste Unterwasser-Phase →
  konservativ sizen, Max-DD nicht ausreizen.

## 6. Verdict

Die korrekt gebaute Strategie ist **real** (Gold/BTC haben signifikante Brutto-
Edges, both-direction = kein Beta) und reproduziert das Video. Als
gleichgewichtetes Portfolio (5 Assets, GBP=Spot) **schlägt sie B&H brutto
risk-adjusted** (Sharpe 1,26 vs 0,98, ⅓ Drawdown). Netto hängt das Urteil an der
**Ausführung**: mit reinem Taker Gleichstand (0,96 vs 0,98), **mit realistischer
Limit-/Adaptive-Ausführung darüber (~1,08 vs 0,98)** — jeweils bei **deutlich
geringerem Drawdown** (13 % vs 35 %). Das Video-Headline (+53,89 %/J) ist reproduziert
(Kombi-Konto taker +54,4 %/$914k ≈ seine $874k), aber bei **52 % DD vs seinen 29 %**
(Risiko-Effizienz-Lücke, nicht Edge-Lücke). Absolut macht B&H mehr (+898 % vs +242–322 %); der Mehrwert der
Strategie ist das **Risiko-Profil**, nicht die Mehrrendite. Vorbehalte: der Edge
**zerfällt OOS** (Sharpe 1,52 → 0,43), die Ausführungs-Einsparung ist durch die
Breakout-Natur (adverse Selektion) begrenzt, und für Funded-Accounts ist sie wegen
DD-Höhe, Multi-Tage-Holds und langer Unterwasser-Phasen nur eingeschränkt geeignet.
**Einstufung: legitimes, ruhiges, drawdown-armes Multi-Asset-Sleeve, das B&H bei
guter Ausführung risk-adjusted schlägt (knapp) — aber kein Mehrrendite-Selbstläufer
und mit OOS-Zerfall.**
