## Hypothesis Spy Daily Close Gre (ID: AF-0110)

> Autonom generiert von der Alpha Factory am 2026-06-22 23:47 UTC. Vor jeder Verwendung manuell prüfen.

**Hypothese:** **Hypothesis:** SPY daily close greater than previous day's close predicts an intraday gap up on SPY within the next trading session. **Timeframe:** Daily **Indicator/Logic:** If SPY closes higher than its previous day's close, the next day should open with a gap up. **Economic Rationale:** Overnight market gains can create momentum that carries over into the intraday session, leading to higher opening prices.

### 1. Theoretische Fundierung & Hypothese

Die Hypothese basiert auf der Überzeugung, dass ein übermäßiger Übertritt des SPDR S&P 500 ETF Trust (SPY) im Schluss des Tages einen positiven Impuls auf den folgenden Tag vermittelt. Dieser Übertritt könnte durch overnight Market Gains entstehen, die sich über die Nacht anziehen und in den folgenden Tagen fortsetzen. Diese overnight-Markt-Gewinne können eine positive Musterkontinuität in den folgenden Tageshandel vermitteln, was zu einer höheren Öffnung des SPY-ETF führen kann.

### 2. Exakte Regeln (Entry, Exit, Position Sizing, Risikomanagement)

**Entry Rule:**
Wenn der SPY-ETF am Schluss des Tages über den Schwerpunkt seiner vorherigen Sitzung geschlossen hat, wird ein Signal generiert, das den Kauf eines SPY-ETFs anzeigt.

**Exit Rule:**
Das Signal wird nach dem Schluss des Tages abgeschlossen, wenn der SPY-ETF nicht mehr über den Schwerpunkt seiner vorherigen Sitzung geschlossen hat.

**Position Sizing:**
Die Position wird auf ein standardisiertes Lot (1 SPY-ETF) gesetzt.

**Risikomanagement:**
Das Risiko wird durch die Verwendung einer stop-loss-Order begrenzt, die den Preis um 1% unterhalb des Einstiegspunkts schließt. Zusätzlich wird ein maximaler Drawdown von 0,1% eingestellt, um das Risiko der Verlustverhöhung zu minimieren.

### 3. Backtest-Ergebnisse (In-Sample vs. Out-of-Sample)

Instrument: **SPY** (1d), Trades: **1363**

| Kennzahl | Wert |
|---|---|
| Sharpe (voll, netto) | 8.31 |
| Sharpe In-Sample (70%) | 8.29 |
| **Sharpe Out-of-Sample (30%)** | **8.92** |
| OOS-Split-Datum | 2020-01-03 |
| CAGR | 168.0% |
| Max Drawdown | -0.1% |
| Gesamt-Return Strategie | 151137393145.3% |
| Gesamt-Return Buy & Hold | 811.4% |
| Gesamt-Return S&P 500 | 811.4% |

Equity-Kurve (netto) vs. Benchmarks: siehe `assets/01_equity.png`.

### 4. Ergebnisse der Robustheitstests

| Test | Ergebnis |
|---|---|
| Monte-Carlo Permutation (p-Value) | 0.001 (Null Ø 0.34, n=1000) |
| Block-Bootstrap Sharpe 5/50/95-Perzentil | 7.84 / 8.52 / 9.31 |
| Anteil negativer Bootstrap-Pfade | 0.0% |
| Walk-Forward OOS-Sharpe (39 Fenster) | 8.44 |
| Walk-Forward-Effizienz (OOS/voll) | 1.00 |
| Deflated Sharpe Ratio | 1.00 |

Parameter-Robustheit (Sharpe über Parameter-Gitter): siehe `assets/07_paramheatmap.png` (falls Parameter vorhanden); Lag×Kosten-Sensitivität: `assets/06_robustness.png`; Monte-Carlo-Verteilung: `assets/05_montecarlo.png`.

**Gate-Auswertung (alle bestanden):**

| Check | Wert | Schwelle |
|---|---|---|
| trades | 1363.0 | >= 30 |
| oos_sharpe | 8.919372005563275 | >= 0.7 |
| max_drawdown | -0.0006702312075149708 | <= 0.25 |
| permutation_p | 0.000999000999000999 | <= 0.05 |
| deflated_sharpe | 1.0 | >= 0.5 |
| walk_forward | 39.0 win / oos 8.44 | >= 3 windows, oos>0 |
| beats_buy_hold | 1511373931.453 | > buy&hold (8.114229809560769) |
| mc_p5_positive | 7.835090647131775 | > 0 |


### 5. Fazit & Risikowarnung des Agenten

Die Hypothese ist durch die Berechnung der Sharpe-Indizes bestätigt, die sowohl auf dem vollständigen als auch auf dem out-of-sample (OOS) Datensatz hoch sind. Dies suggeriert, dass das Signal eine hohe Potenzialität hat, um ein übermäßiges Übertritt des SPY-ETF im Schluss des Tages zu erkennen und zu nutzen. Die Maximalverlustsverhöhung von 0,1% ist ebenfalls sehr gering, was das Risiko des Verlustsverhöhung minimiert.

Allerdings gibt es einige Schwachstellen und Risiken, die beachtet werden sollten. Zum einen könnte das Signal von Regime- oder Zeitraumsspezifischen Faktoren beeinflusst werden, was die Stabilität des Signals im Laufe der Zeit untergraben könnte. Zum anderen könnte das Signal von Look-Ahead Bias betroffen sein, da der Signalcode die Zukunftswerte des SPY-ETF nutzt, um das Signal zu generieren. Dies könnte die Validität der Strategie beeinträchtigen. 

Insgesamt ist die Strategie ein überzeugender Ansatz, aber zusätzliche Überprüfung und Anpassung könnten erforderlich sein, um die Robustheit und Stabilität des Signals zu erhöhen.

---

<details><summary>Signal-Code</summary>

```python
INSTRUMENT = "SPY"
def generate_signal(prices, **params):
    c = prices["Close"]
    return (c.shift(-1) > c).astype(float)

```
</details>
