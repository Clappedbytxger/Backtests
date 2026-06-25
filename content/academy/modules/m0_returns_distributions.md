> **Repo-Anker:** Öffne `src/quantlab/backtest.py`. Dort wird mit *Returns*
> gerechnet, nie mit *Preisen*. Warum? Diese Sitzung beantwortet das von Grund auf —
> nur mit Abitur-Mathe als Startpunkt.

## 1. Von Preisen zu Returns

Ein Preis allein sagt nichts über Erfolg. Ob eine Aktie von 10 € auf 11 € oder von
100 € auf 110 € steigt — der *Gewinn in Prozent* ist identisch: 10 %. Genau diese
**relative Veränderung** nennen wir Return.

Der **einfache Return** von Tag $t-1$ auf Tag $t$ ist

$r_t = \frac{P_t - P_{t-1}}{P_{t-1}} = \frac{P_t}{P_{t-1}} - 1$.

Beispiel: $P_{t-1}=100$, $P_t=110$ ⇒ $r_t = 110/100 - 1 = 0{,}10 = 10\%$.

### Warum Quants stattdessen Log-Returns nehmen

Der **logarithmische Return** ist $\ell_t = \ln\!\big(P_t / P_{t-1}\big)$.

Das ist kein Selbstzweck. Aus der Abitur-Logarithmusregel $\ln(a\cdot b) = \ln a + \ln b$
folgt die entscheidende Eigenschaft: **Log-Returns addieren sich über die Zeit.**
Der Return über zwei Tage ist

$\ln\!\frac{P_t}{P_{t-2}} = \ln\!\frac{P_t}{P_{t-1}} + \ln\!\frac{P_{t-1}}{P_{t-2}} = \ell_t + \ell_{t-1}$.

Einfache Returns müsstest du dagegen **multiplizieren** ($1+r$ verketten —
„Compounding"). Addieren ist mathematisch viel angenehmer: Mittelwerte, Varianzen
und die Normalverteilung (gleich) funktionieren mit Summen sauber. Für kleine
Bewegungen gilt zudem $\ell_t \approx r_t$ (z. B. 1 % vs. 0{,995} %), also verlierst du
fast nichts an Interpretierbarkeit.

> **Merksatz:** Preise sind Niveaus, Returns sind Veränderungen. Strategien
> verdienen an *Veränderungen* — deshalb rechnet `backtest.py` mit Returns.

## 2. Returns sind Zufallsvariablen

Den morgigen Return kennst du heute nicht. In der Sprache der Stochastik ist $r_t$
eine **Zufallsvariable**: eine Größe, deren Wert vom Zufall abhängt und die eine
*Verteilung* möglicher Werte besitzt.

Aus dem Abitur kennst du drei Kennzahlen einer Verteilung — hier ihre Bedeutung im Trading:

- **Erwartungswert** $\mu = \mathbb{E}[r]$ — der „mittlere" Return, dein
  langfristiger Edge pro Trade. Geschätzt durch den Durchschnitt:
  $\hat\mu = \frac{1}{n}\sum_{t} r_t$.
- **Varianz** $\sigma^2 = \mathbb{E}\big[(r-\mu)^2\big]$ — die mittlere quadratische
  Abweichung vom Mittel.
- **Standardabweichung** $\sigma = \sqrt{\sigma^2}$ — die Streuung in denselben
  Einheiten wie der Return. **Das ist die „Volatilität".**

Risiko ist also nicht abstrakt — es ist buchstäblich $\sigma$, die Breite der
Return-Verteilung.

## 3. Die Normalverteilung — das erste Modell

Das einfachste Modell für Returns ist die **Normalverteilung** (Gauß'sche
Glockenkurve). Sie wird vollständig durch $\mu$ (Lage) und $\sigma$ (Breite)
beschrieben. Verschiebe unten die Regler und beobachte, wie $\mu$ die Glocke
verschiebt und $\sigma$ sie verbreitert:

::viz NormalDistribution

Die blaue Fläche ist das **±1σ-Intervall** und enthält ca. **68 %** der
Wahrscheinlichkeitsmasse; ±2σ ca. 95 %. Genau diese Faustregeln stecken später in
deinen Konfidenzintervallen (Modul 1) und in der Sharpe Ratio.

## 4. Wo die Normalverteilung lügt: Fat Tails

Echte Finanz-Returns sind **nicht** normalverteilt. Sie haben zwei Eigenschaften,
die die Glocke nicht abbildet:

- **Fat Tails (Kurtosis):** Extreme Tage (Crashs, Rallyes) treten **viel häufiger**
  auf, als eine Normalverteilung mit demselben $\sigma$ erlaubt. Die **Kurtosis**
  misst, wie „dick" die Enden sind (Normal = 3; Returns oft 5–10+).
- **Skew (Schiefe):** Die Verteilung ist oft **asymmetrisch** — bei Aktien hängt der
  linke (Verlust-)Tail tiefer: Crashs sind schneller und brutaler als Rallyes.

Im folgenden Chart simulieren wir Returns mit einstellbar dicken Tails (über die
Freiheitsgrade einer Student-t-Verteilung) und legen die Normalverteilung mit
*gleichem σ* darüber. Schiebe `df` nach unten:

::viz ReturnsHistogram

Sieh, wie die roten Balken an den Rändern weit über die blaue Kurve hinausragen.
**Das ist der Grund, warum `metrics.py` neben dem Sharpe auch Skew und Kurtosis
ausweist** — und warum eine Strategie wie der VIX-Carry (Katalog 0054) trotz tollem
Sharpe an *einem* Tag −34 % machen kann. Ein reines σ-Maß sieht diesen Tail nicht.

## 5. Random Walk: Warum ein „Trend" Zufall sein kann

Letzter Baustein. Wenn du Returns Tag für Tag zu einem Preis aufaddierst (bzw.
aufmultiplizierst), entsteht ein **Random Walk** — die zeitdiskrete Form der
*Brownschen Bewegung*. Das Standardmodell für Preise ist die **geometrische
Brownsche Bewegung**:

$P_t = P_{t-1}\cdot \exp\!\Big(\tfrac{\mu}{N} + \tfrac{\sigma}{\sqrt{N}}\,Z_t\Big)$,

wobei $Z_t$ eine Standard-Normal-Zufallszahl ist und $N$ die Anzahl Schritte pro Jahr.

Unten starten **fünf Pfade mit identischer Drift und Vol** am selben Punkt. Würfle neu:

::viz RandomWalk

Manche Pfade „trenden" überzeugend nach oben, andere fallen — obwohl **kein Pfad mehr
Information besitzt als die anderen**. Dein Auge sieht Muster, wo nur Rauschen ist.

> **Das ist die teuerste Lektion der ganzen Akademie:** Ein hübscher Aufwärts-Backtest
> ist als Erstes *zufallsverdächtig*. Genau deshalb gibt es `significance.py` mit
> Permutationstest, Bootstrap und Deflated Sharpe — die Werkzeuge, mit denen du
> echtes Signal von solchen Zufalls-Trends trennst (Modul 1 und 2).

## Payoff dieser Sitzung

Du kannst jetzt:

- begründen, warum mit Returns (speziell Log-Returns) statt Preisen gerechnet wird,
- $\mu$, $\sigma^2$, $\sigma$ als Edge bzw. Risiko einordnen,
- die Normalverteilung lesen und sagen, **wo sie bei Returns versagt** (Fat Tails, Skew),
- einen Random Walk als Nullhypothese gegen jeden schönen Backtest stellen.

Damit verstehst du den Kopfteil von `src/quantlab/metrics.py` Zeile für Zeile.

**Nächstes Modul:** *Schätzfehler & der Sharpe* — warum 20 Saison-Trades „nicht
reichen" und wie der Standardfehler $\sigma/\sqrt{n}$ das exakt quantifiziert.
