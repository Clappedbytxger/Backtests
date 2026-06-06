# Strategie 0014 — BTC Volumen-bestätigte Impuls-Continuation (Orderflow)

- **Kategorie:** momentum / orderflow / intraday
- **Status:** abgelehnt
- **Datum:** 2026-06-04
- **Universum:** Bitcoin (BTC/USDT, Binance-Spot-Tape als Datenquelle, gehandelt
  als Bitget USDT-M Perpetual)
- **Stichprobe:** In-Sample 2017-08 – 2022-12 / Out-of-Sample 2023-01 – 2026-06

## 1. Hypothese

Eine große Stundenkerze (|Rendite| ≥ 1,5·σ), die *gleichzeitig* von
außergewöhnlich hohem Volumen getragen wird **und** nahe ihrem Extrem in
Bewegungsrichtung schließt (Orderflow-Bestätigung), spiegelt echte einseitige
Aggression wider und **setzt sich** über die nächsten H Stunden fort — also long
auf Aufwärts-, short auf Abwärts-Impuls.

## 2. Makro-Begründung

Antwort auf die Lehren aus 0012 („Vola ≠ Richtung") und 0013 („Extrem-Moves
kontinuieren, aber zu schwach für die Kosten"). Der fehlende Baustein war ein
**Richtungs-Konvictions-Filter**, den der Orderflow liefern soll:

- **Volumen = Konviktion.** Ein großer Move auf hohem Volumen entsteht durch
  echten Informationszufluss, Stop-Runs oder erzwungene Liquidations-Kaskaden auf
  dem Perp — nicht durch dünnes-Buch-Rauschen.
- **Close-Location (CLV) = Absorptions-Test.** Schließt die Kerze nahe ihrem
  Extrem in Bewegungsrichtung, haben aggressive Taker den Preis bis zum Schluss
  getragen (keine zurückgewiesene Lunte) → die Gegenseite wurde absorbiert.
- In einem fragmentierten, 24/7-, retail-lastigen, von Momentum-Kapital
  dominierten Markt diffundiert diese Neubewertung langsam → Fortsetzung.

Das Dreifach-Gate (σ-Extrem **und** Volumen **und** CLV) feuert nur auf seltenen
Konviktionsbars → sehr niedriger Umschlag, die in 0012/0013 identifizierte
bindende Grenze.

## 3. Regeln

- `ret = pct_change`, `σ = std(ret, 168h).shift(1)`, `z = ret/σ`.
- `relvol = Volume / median(Volume, 168h).shift(1)`.
- `CLV = ((Close−Low) − (High−Close)) / (High−Low)` ∈ [−1, 1].
- **Long-Trigger:** `z ≥ 1,5` **und** `relvol ≥ V` **und** `CLV > 0`.
- **Short-Trigger:** `z ≤ −1,5` **und** `relvol ≥ V` **und** `CLV < 0`.
- Position wird H Stunden gehalten (neuester Trigger gewinnt), sonst flat.
- **Look-Ahead-Schutz:** Alle Normalisierer per `.shift(1)`; die Engine verzögert
  das Signal zusätzlich um eine Bar (Position wird erst ab t+1 gehalten).
- **Fix (nicht gesucht):** Fenster 168h, k = 1,5σ, CLV-Vorzeichen-Bestätigung.
- **Gesucht (9 Trials):** V ∈ {1,5; 2,0; 3,0} × H ∈ {3; 6; 12} h. IS wählt, OOS
  beurteilt nur die gelockte Regel.

## 4. Kosten- & Ausführungsannahmen

Gehandelt als **Bitget USDT-M Perpetual**. Bitget-Standardgebühren: Maker 0,02 %,
**Taker 0,06 %**. Eine systematische Stunden-Strategie füllt mit Market-Orders
(Taker) → 6 bps/Seite. BTC/USDT-Perp ist extrem liquide (Top-of-Book-Spread
~1 bp), daher 2 bps/Seite Slippage-Puffer.

- **Basis:** 8 bps/Seite = **16 bps Round-Trip** (auf 10 000 USDT: 16 USDT/RT).
- **Stress:** 12 bps/Seite = 24 bps RT (alte Binance-Spot-Annahme aus 0012/0013).
- **Funding** (alle 8h) ist *nicht* modelliert — bei Ø-Haltedauer von 11h kreuzt
  jeder Trade ~1 Funding-Fenster, also ein zusätzlicher, regimeabhängiger Kostenposten zulasten der Netto-Zahlen unten.

## 5. Ergebnisse (Out-of-Sample, netto nach Kosten)

| Kennzahl               |            Wert | Brutto (Ref.) |
| ---------------------- | --------------: | ------------: |
| CAGR                   |          −19,4 % |       +19,2 % |
| Sharpe                 |           −0,56 |        +0,65 |
| Sortino                |           −0,70 |        +0,83 |
| Calmar                 |           −0,29 |        +0,45 |
| Max Drawdown (Dauer)   | −66,1 % (779 T) |       −42,2 % |
| Trefferquote           |          42,3 % |             — |
| Profit-Faktor          |            0,91 |             — |
| Payoff-Ratio           |            1,24 |             — |
| Expectancy / Trade     |        −0,068 % |             — |
| Ø Haltedauer           |        11 Bars |             — |
| Trades                 |             836 |             — |

Buy & Hold BTC (OOS): CAGR **+49,4 %**, Sharpe **1,04**.
Kosten-Stress (24 bps RT): Sharpe **−1,15**, CAGR **−33,7 %**.

## 6. Signifikanz

| Test                          |            Wert |
| ----------------------------- | --------------: |
| Permutationstest p-Wert       |           0,532 |
| Bootstrap Sharpe 95%-KI       | [−1,38; +0,46] |
| Deflated Sharpe (N = 9)       |           0,000 |
| IS-bester Trial (von 9)       |  Sharpe −0,849 |

## 7. Robustheit

- **0/9 OOS-Gitterkombinationen positiv** (Bereich −2,46 … −0,56). Kein Plateau,
  reines Rot.
- Das Gitter ist **monoton**: weniger handeln (höheres V, längeres H) = weniger
  Verlust. Exakt das 0013-Muster — die Kosten/Umschlag-Grenze, nicht die
  Richtung, ist bindend.
- Schon der **beste In-Sample-Trial war negativ** (−0,849). Es gibt also nicht
  einmal eine Overfit-Illusion, an die man sich klammern könnte.

## 8. Verdict

**Ablehnen.** Der Orderflow-Filter erzeugt zwar einen **schwachen Brutto-Edge**
(OOS-Brutto-Sharpe +0,65), aber netto ist die Strategie bei *jeder* getesteten
Kostenannahme — selbst bei den günstigen Bitget-16-bps — ein stetiger Verlust
(Netto-Sharpe −0,56, Permutation p = 0,53 ≈ Zufall, DSR = 0). Der eine Grund:
Der Brutto-Edge ist zu dünn, um 836 Round-Trips zu bezahlen, und ist im
Bull-OOS zudem vermutlich teils Long-Beta statt Alpha. Bitget halbiert die
Kosten gegenüber 0012/0013, doch die Hürde bleibt höher als das Signal — die
Kosten sind zum dritten Mal in Folge die bindende Grenze für Intraday-BTC.
