> **Repo-Anker:** `src/quantlab/metrics.py`, Funktion `sharpe_ratio()`. Du hast eine
> Saison-Strategie mit 20 Trades und Sharpe 1,8. Klingt super. Diese Sitzung zeigt,
> warum das fast nichts beweist.

## 1. Stichprobe vs. Wahrheit

In Modul 0 war $\mu$ der wahre Erwartungswert. Den kennst du nie — du hast nur eine
**Stichprobe** von $n$ Returns und berechnest daraus den **Schätzer** $\hat\mu$. Schätzer
sind selbst Zufallsvariablen: eine andere Stichprobe ⇒ ein anderes $\hat\mu$.

Die Schlüsselgröße ist der **Standardfehler** des Mittelwerts:

$\text{SE}(\hat\mu) = \dfrac{\sigma}{\sqrt{n}}$.

Lies das genau: Die Unsicherheit deiner Schätzung schrumpft nur mit $\sqrt{n}$, nicht mit
$n$. Um den Fehler zu **halbieren**, brauchst du **viermal** so viele Trades. Das ist das
$\sqrt n$-Gesetz, und es ist der Grund, warum 20 Trades so wenig wert sind.

## 2. Der Sharpe ist auch nur eine Schätzung

Die Sharpe Ratio ist $\text{SR} = \mu/\sigma$ (Überschussrendite pro Risikoeinheit),
geschätzt als $\widehat{\text{SR}} = \hat\mu/\hat\sigma$. Auch sie streut. Ihr
ungefährer Standardfehler ist

$\text{SE}(\widehat{\text{SR}}) \approx \sqrt{\dfrac{1 + \tfrac12 \text{SR}^2}{n}}$.

Bei $n=20$ ist das ~0,23 **pro Periode** — riesig im Verhältnis zu kleinen Sharpes.
Die folgende Simulation macht es greifbar: Wir fixieren das *wahre* Sharpe pro Trade und
ziehen 2000-mal eine Stichprobe der Größe $n$. Schau, wie breit die geschätzten Sharpes
streuen — und wie oft die Strategie rein zufällig **negativ** aussieht:

::viz SharpeSampling

Schiebe $n$ von 20 auf 300: Die Verteilung zieht sich zusammen (genau um $1/\sqrt n$).
Das ist „mehr Trades = mehr Sicherheit" — quantitativ, nicht als Bauchgefühl.

## 3. Annualisieren — und wann es lügt

Du siehst meist *annualisierte* Sharpes. Aus einem täglichen Per-Tag-Sharpe wird

$\text{SR}_\text{ann} = \sqrt{252}\cdot \text{SR}_\text{täglich}$.

Woher das $\sqrt{252}$? Der Mittelwert skaliert mit der Zeit ($\times 252$), die
Standardabweichung aber nur mit $\sqrt{252}$ (Varianzen addieren sich, Std nicht). Also
$\mu/\sigma \to 252\mu / (\sqrt{252}\sigma) = \sqrt{252}\cdot \text{SR}$.

**Die Falle:** Diese Skalierung gilt nur, wenn die Returns **unkorreliert** sind. Bei
**Autokorrelation** (Trends, überlappende Holds) addieren sich die Varianzen *nicht*
sauber, und $\sqrt{252}$ **überschätzt** den wahren Sharpe. Genau deshalb ist ein
annualisierter Sharpe aus überlappenden 66-Tage-Holds (Katalog 0046) mit Vorsicht zu
genießen.

## 4. Konfidenzintervalle & der Bootstrap

Ein Punktwert wie „Sharpe 1,8" ohne Fehlerbalken ist unseriös. Ein **Konfidenzintervall
(KI)** gibt den Bereich an, in dem die Wahrheit plausibel liegt:

$\hat\mu \pm 1{,}96\cdot \text{SE}(\hat\mu)$  (95 %-KI unter Normalannahme).

Wenn dieses Intervall die **0 enthält**, kannst du „kein Edge" nicht ausschließen.

Was, wenn die Returns nicht normal sind (Fat Tails aus Modul 0)? Dann nutzt du den
**Bootstrap** (genau das macht `significance.py`): Ziehe aus deinen $n$ Returns $n$-mal
*mit Zurücklegen*, berechne die Kennzahl, wiederhole 10 000-mal. Die empirische Streuung
dieser 10 000 Werte **ist** dein Konfidenzintervall — ganz ohne Verteilungsannahme. Der
Bootstrap „simuliert" zusätzliche Stichproben aus der einen, die du hast.

> **Payoff:** Du kannst jetzt exakt begründen, warum deine Saison-Edges *power-limitiert*
> sind: Bei wenigen Trades ist $\text{SE}$ so groß, dass das Bootstrap-KI die 0 nicht
> ausschließt — das Phänomen kann real sein und trotzdem statistisch unbeweisbar.

**Nächstes Modul:** Wenn ein einzelnes KI schon schwierig ist — was passiert, wenn du
*hunderte* Varianten durchprobierst? Das ist Multiple Testing und der Deflated Sharpe.
