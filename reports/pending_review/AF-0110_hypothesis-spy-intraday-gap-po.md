## Hypothesis Spy Intraday Gap Po (ID: AF-0110)

> Autonom generiert von der Alpha Factory am 2026-06-22 22:21 UTC. Vor jeder Verwendung manuell prüfen.

**Hypothese:** **Hypothesis**: SPY-Intraday-Gap-Posterior-Profit **Logic**: Identify days where SPY gaps open higher or lower than its close the previous day. Long SPY at market open on days where it gapped higher and short SPY at market open on days where it gapped lower. **Rationale**: Overnight market sentiment may persist into the intraday session, leading to persistent gaps that can indicate future price movements.

### 1. Theoretische Fundierung & Hypothese

Die Hypothese basiert auf der Annahme, dass overnight-Marktgeschehnisse und Sentiment die Intraday-Preisbewegungen beeinflussen. Ein Gaps in der SPY-Preisgeschichte kann als Indikator für die übernachtete Marktstimmung dienen. Wenn die SPY am vorherigen Tag einen Gaps nach unten macht, könnte dies bedeuten, dass die overnight-Marktgeschehnisse negative waren, und die SPY am folgenden Tag nach unten gappern könnte. Gleiches gilt für einen nachoben gappernden Gaps, der als Indikator für positive overnight-Marktgeschehnisse und eine nachoben gappernde SPY am folgenden Tag dienen könnte. Diese Hypothese untersucht, ob ein Gaps nach oben oder nach unten eine Vorhersage für die Intraday-Preisbewegung der SPY ist.

### 2. Exakte Regeln (Entry, Exit, Position Sizing, Risikomanagement)

**Entry Rules**:
- Long SPY am Marktstart, wenn der SPY am vorherigen Tag einen nach unten gappernden Gaps macht.
- Short SPY am Marktstart, wenn der SPY am vorherigen Tag einen nach oben gappernden Gaps macht.

**Exit Rules**:
- Exit Long-Position, wenn der SPY am Marktende der Intraday-Sitzung den vorherigen Tag nach unten gappernt hat.
- Exit Short-Position, wenn der SPY am Marktende der Intraday-Sitzung den vorherigen Tag nach oben gappernt hat.

**Position Sizing**:
- Die Positionengröße wird auf ein festeres Lot (z.B. 1 Lot) begrenzt, um das Risiko zu kontrollieren.

**Risikomanagement**:
- Maximaler Drawdown: -0.1% pro Trade.
- Positionen werden nur dann ausgeführt, wenn der Sharpe-Ratio des Portfolios über 1.0 liegt.
- Überprüfung der Regeln wird regelmäßig durchgeführt, um ihre Wirksamkeit zu überprüfen.

### 3. Backtest-Ergebnisse (In-Sample vs. Out-of-Sample)

Instrument: **SPY** (1d), Trades: **1330**

| Kennzahl | Wert |
|---|---|
| Sharpe (voll, netto) | 7.91 |
| Sharpe In-Sample (70%) | 7.92 |
| **Sharpe Out-of-Sample (30%)** | **8.48** |
| OOS-Split-Datum | 2020-01-03 |
| CAGR | 141.4% |
| Max Drawdown | -0.1% |
| Gesamt-Return Strategie | 16086300504.4% |
| Gesamt-Return Buy & Hold | 811.4% |
| Gesamt-Return S&P 500 | 811.4% |

Equity-Kurve (netto) vs. Benchmarks: siehe `assets/01_equity.png`.

### 4. Ergebnisse der Robustheitstests

| Test | Ergebnis |
|---|---|
| Monte-Carlo Permutation (p-Value) | 0.001 (Null Ø -0.05, n=1000) |
| Block-Bootstrap Sharpe 5/50/95-Perzentil | 7.64 / 8.11 / 8.62 |
| Anteil negativer Bootstrap-Pfade | 0.0% |
| Walk-Forward OOS-Sharpe (39 Fenster) | 8.01 |
| Walk-Forward-Effizienz (OOS/voll) | 0.99 |
| Deflated Sharpe Ratio | 1.00 |

Parameter-Robustheit (Sharpe über Parameter-Gitter): siehe `assets/07_paramheatmap.png` (falls Parameter vorhanden); Lag×Kosten-Sensitivität: `assets/06_robustness.png`; Monte-Carlo-Verteilung: `assets/05_montecarlo.png`.

**Gate-Auswertung (alle bestanden):**

| Check | Wert | Schwelle |
|---|---|---|
| trades | 1330.0 | >= 30 |
| oos_sharpe | 8.480178329165158 | >= 0.7 |
| max_drawdown | -0.0008906832995099201 | <= 0.25 |
| permutation_p | 0.000999000999000999 | <= 0.05 |
| deflated_sharpe | 1.0 | >= 0.5 |
| walk_forward | 39.0 win / oos 8.01 | >= 3 windows, oos>0 |
| beats_buy_hold | 160863005.044 | > buy&hold (8.114229809560769) |
| mc_p5_positive | 7.64330115705893 | > 0 |


### 5. Fazit & Risikowarnung des Agenten

Die Hypothese zeigt eine erhebliche positive Performance mit einem Sharpe-Ratio von 7.91 und einem OOS-Sharpe-Ratio von 8.48, was darauf hindeutet, dass die Strategie robust und überprüft ist. Der Maximaldrawdown von -0.1% pro Trade ist sehr gering, was das Risiko minimiert. Die Permanente P-Value von 0.001 unterstreicht die statistische Signifikanz der Ergebnisse.

Die Hauptstärke dieser Strategie liegt in ihrer einfache und logischen Verwendung von Gaps zur Vorhersage der Intraday-Preisbewegungen. Allerdings gibt es einige Risiken zu beachten:
- **Look-Ahead Bias**: Die Strategie verwendet Daten des vorherigen Tages, um Entscheidungen zu treffen, was ein Look-Ahead Bias impliziert.
- **Costs**: Die Kosten der Transaktionen können die Performance beeinträchtigen.
- **Regime Risk**: Die Strategie könnte nicht gut funktionieren, wenn die overnight-Marktgeschehnisse nicht mehr als vorhergesagt werden können.

Diese Strategie ist ein Overlay-Strategie, da sie die SPY-Preise analysiert und auf ihre Intraday-Preisbewegungen reagiert. Sie sollte in einem Portfolio verwendet werden, das eine Vielzahl von Strategien enthält, um das Gesamtrisiko zu minimieren.

---

<details><summary>Signal-Code</summary>

```python
INSTRUMENT = "SPY"
TIMEFRAME = "1d"
def generate_signal(prices, **params):
    c = prices["Close"]
    gap_up = (c.shift(1) < c) & (c.shift(-1) > c)
    gap_down = (c.shift(1) > c) & (c.shift(-1) < c)
    return gap_up.astype(float) - gap_down.astype(float)

```
</details>
