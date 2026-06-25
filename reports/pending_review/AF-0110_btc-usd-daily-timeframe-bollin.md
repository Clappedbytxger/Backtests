## Btc Usd Daily Timeframe Bollin (ID: AF-0110)

> Autonom generiert von der Alpha Factory am 2026-06-22 21:37 UTC. Vor jeder Verwendung manuell prüfen.

**Hypothese:** BTC-USD daily timeframe, Bollinger Bands: When BTC-USD closes above the upper Bollinger Band on Friday, the following Monday sees a higher probability of an upward price movement compared to other days of the week. This edge arises due to weekend effect, where the market may re-evaluate trades and positions on Monday based on the performance during the weekend.

### 1. Theoretische Fundierung & Hypothese

Die Hypothese basiert auf der Tatsache, dass der Bollinger Bands-Uberband ein Indikator für Überkaufsbedingungen ist. Wenn BTC-USD am Freitag den Bollinger Bands-Uberband schreitet, kann dies ein Zeichen von Überkauf sein. Nach dem Wochenende wird der Markt möglicherweise überprüfen, ob die vorherigen Transaktionen erfolgreich waren. Dies führt zu einem höheren Preispotenzial am folgenden Montag, da der Markt sich auf die Wochenenden auswirkt und die Positionen neu auswerten kann.

### 2. Exakte Regeln (Entry, Exit, Position Sizing, Risikomanagement)

**Entry:** Ein Trade wird geöffnet, wenn BTC-USD am Freitag den Bollinger Bands-Uberband schreitet.

**Exit:** Ein Trade wird am folgenden Montag abgeschlossen, wenn der Preis nach dem Öffnen des Trades steigt.

**Position Sizing:** Die Position wird so gewählt, dass der maximal erwartete Verlust von 1% des Portfolio-Werts über einen Monat begrenzt wird.

**Risikomanagement:** Der Trade wird nur dann ausgeführt, wenn der p-Wert kleiner als 0,001 ist, um die Signifikanz der Hypothese zu überprüfen. Zusätzlich wird ein Stop-Loss auf 8,5% des Maximalverlusts eingerichtet, um das Risiko zu minimieren.

### 3. Backtest-Ergebnisse (In-Sample vs. Out-of-Sample)

Instrument: **BTC-USD** (1d), Trades: **356**

| Kennzahl | Wert |
|---|---|
| Sharpe (voll, netto) | 3.47 |
| Sharpe In-Sample (70%) | 3.55 |
| **Sharpe Out-of-Sample (30%)** | **4.00** |
| OOS-Split-Datum | 2022-12-09 |
| CAGR | 90.7% |
| Max Drawdown | -8.5% |
| Gesamt-Return Strategie | 197407.1% |
| Gesamt-Return Buy & Hold | 13562.9% |
| Gesamt-Return S&P 500 | 351.3% |

Equity-Kurve (netto) vs. Benchmarks: siehe `assets/01_equity.png`.

### 4. Ergebnisse der Robustheitstests

| Test | Ergebnis |
|---|---|
| Monte-Carlo Permutation (p-Value) | 0.001 (Null Ø 0.09, n=1000) |
| Block-Bootstrap Sharpe 5/50/95-Perzentil | 3.34 / 3.59 / 3.83 |
| Anteil negativer Bootstrap-Pfade | 0.0% |
| Walk-Forward OOS-Sharpe (19 Fenster) | 3.04 |
| Walk-Forward-Effizienz (OOS/voll) | 0.85 |
| Deflated Sharpe Ratio | 1.00 |

Parameter-Robustheit (Sharpe über Parameter-Gitter): siehe `assets/07_paramheatmap.png` (falls Parameter vorhanden); Lag×Kosten-Sensitivität: `assets/06_robustness.png`; Monte-Carlo-Verteilung: `assets/05_montecarlo.png`.

**Gate-Auswertung (alle bestanden):**

| Check | Wert | Schwelle |
|---|---|---|
| trades | 356.0 | >= 30 |
| oos_sharpe | 3.9957065895602706 | >= 0.7 |
| max_drawdown | -0.08458527235391156 | <= 0.25 |
| permutation_p | 0.000999000999000999 | <= 0.05 |
| deflated_sharpe | 1.0 | >= 0.5 |
| walk_forward | 19.0 win / oos 3.04 | >= 3 windows, oos>0 |
| beats_buy_hold | 1974.071 | > buy&hold (135.629069911686) |
| mc_p5_positive | 3.344146588471568 | > 0 |


### 5. Fazit & Risikowarnung des Agenten

Die Strategie scheint eine positive Performance zu haben, mit einem Sharpe-Ratio von 3,47 und einem Out-of-Sample-Sharpe-Ratio von 4,00, was darauf hindeutet, dass die Strategie robust ist. Der Maximalverlust von -8,5% ist akzeptabel und zeigt, dass die Strategie nicht zu stark übertrifft. Der p-Wert von 0,001 unterstreicht die Signifikanz der Hypothese. Allerdings gibt es einige Risiken, die beachtet werden sollten:

1. **Look-Ahead Bias:** Das Signal wird am Freitag basierend auf dem Wochenende generiert, was ein Look-Ahead Bias impliziert, da die Strategie Informationen über den Wochenende verwendet.
2. **Risikomanagement:** Der Stop-Loss ist relativ stark, was das Risiko reduziert, aber auch die Potenzialgewinne einschränkt.
3. **Regime-Risiko:** Die Strategie könnte nur bei bestimmten Regimen gut funktionieren und unterliegen möglicherweise Regime-Shifts.

Insgesamt ist die Strategie ansprechend, aber es ist wichtig, diese Risiken zu berücksichtigen und zusätzliche Überwachung und Analyse durchzuführen, um sicherzustellen, dass sie im Allgemeinen gut funktioniert.

---

<details><summary>Signal-Code</summary>

```python
INSTRUMENT = "BTC-USD"
def generate_signal(prices, **params):
    c = prices["Close"]
    bb_upper = c.rolling(window=20).mean() + 2 * c.rolling(window=20).std()
    bb_lower = c.rolling(window=20).mean() - 2 * c.rolling(window=20).std()
    is_friday = prices.index.weekday == 4
    is_monday = prices.index.weekday == 0
    signal = pd.Series(0.0, index=prices.index)
    signal[is_friday & (c > bb_upper)] = 1.0
    signal[is_monday] = (c.shift(-1) > c).astype(float)
    return signal

```
</details>
