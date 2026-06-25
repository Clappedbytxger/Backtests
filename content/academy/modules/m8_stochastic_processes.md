> **Repo-Anker:** Erst relevant, wenn Derivate/Vol-Strategien anstehen (VIX-Carry 0054,
> VRP formal). Dieses Modul liefert die Intuition hinter Black-Scholes — ohne den vollen
> Beweis, aber mit jedem Schritt sichtbar gemacht.

## 1. Brownsche Bewegung — der Grenzfall des Random Walk

In Modul 0 hast du einen Random Walk gebaut: viele kleine Zufallsschritte aufaddiert. Lässt
du die Schrittweite gegen null und die Schrittzahl gegen unendlich gehen, entsteht die
**Brownsche Bewegung** $W_t$ — der stetige Grenzfall. Ihre definierende Eigenschaft:

$\text{Var}(W_t) = t \quad\Rightarrow\quad \text{Streuung} \propto \sqrt{t}$.

Die Unsicherheit wächst mit **$\sqrt t$**, nicht mit $t$. Sieh es am Diffusionskegel — die
gestrichelte $\pm 2\sigma\sqrt t$-Hülle, in der ~95 % der Pfade bleiben:

::viz BrownianMotion

Dieses $\sqrt t$-Gesetz ist subtil und folgenreich: Über zwei Zeiteinheiten verdoppelt sich
die Varianz, aber die Streuung wächst nur um $\sqrt 2$. Genau diese Asymmetrie zwischen
$dt$ und $\sqrt{dt}$ ist der Motor der nächsten beiden Punkte.

## 2. Itō-Intuition

In der normalen Analysis ist $(dx)^2$ vernachlässigbar klein. Bei der Brownschen Bewegung
**nicht**: Weil die Streuung mit $\sqrt{dt}$ skaliert, ist $(dW)^2$ von der Größenordnung
$dt$ — also **nicht** vernachlässigbar. Das ist der ganze Inhalt von **Itōs Lemma**: Wenn du
eine Funktion $f(S)$ eines zufälligen Preises ableitest, kommt ein **Extra-Term** mit der
zweiten Ableitung hinzu:

$df = f'(S)\,dS + \tfrac12 f''(S)\,(dS)^2$,

und der $(dS)^2$-Term überlebt, weil $(dW)^2 \approx dt$. Dieser Zusatzterm — die Krümmung —
ist später **Gamma**. Mehr Beweis brauchst du an dieser Stelle nicht; die Kernidee ist:
*Zufall zweiter Ordnung zählt.*

## 3. Woher Black-Scholes kommt

Die Idee ist genial einfach: Du kannst eine Option **dynamisch hedgen**, indem du
fortlaufend $\Delta$ Einheiten des Basiswerts hältst. Wenn der Hedge perfekt ist, ist das
Paket (Option − $\Delta$·Basiswert) **risikolos** und muss daher den risikolosen Zins
verdienen — sonst gäbe es Arbitrage. Aus dieser No-Arbitrage-Bedingung plus Itō (Punkt 2)
fällt die Black-Scholes-Formel für den fairen Optionspreis heraus. Du brauchst den Beweis
nicht auswendig — du brauchst die **Greeks**, die Sensitivitäten des Preises:

::viz BlackScholesGreeks

- **Delta** $= N(d_1)$ = Steigung des Preises im Spot = die Hedge-Ratio (wie viele
  Basiswert-Einheiten neutralisieren die Option).
- **Gamma** = Krümmung (Ableitung von Delta) = wie schnell sich der Hedge ändert. **Am Geld
  maximal** — dort musst du am hektischsten nachhedgen. Optionsverkäufer sind short Gamma.
- **Vega** = Sensitivität zur Volatilität. Mehr Vol ⇒ wertvollere Option (mehr
  Optionalität = mehr bezahlte Unsicherheit).

## 4. Die Variance Risk Premium — formal

Jetzt schließt sich der Kreis zu Katalog 0054/0056. Die **implizite** Volatilität (im
Optionspreis eingepreist) ist **systematisch höher** als die später **realisierte** Vol.
Diese Differenz ist die **Variance Risk Premium (VRP)** — die Prämie, die Optionskäufer für
Versicherung gegen Crashs zahlen, und die Verkäufer als Carry einnehmen.

Das erklärt 0054 vollständig: Short-Vol (VIX-Carry) **erntet die VRP** — daher der schöne
Sharpe. Aber der Verkäufer ist **short Gamma** (Punkt 3): Bei einem Crash explodiert das
Delta gegen ihn, *schneller* als er nachhedgen kann ⇒ der −34 %-Tag aus Modul 0. Die VRP
ist real und positiv, aber sie ist **Bezahlung für genau dieses Tail-Risiko** — kein free
lunch, sondern verkaufte Versicherung. Deshalb war 0054 ein echter Edge und trotzdem nur als
risiko-gemanagtes Sleeve (0056) tragbar.

> **Payoff:** Du verstehst Derivate-Pricing strukturell — Brownsche Bewegung, Itō-Intuition,
> die Greeks und die VRP — und kannst Vol-Strategien bewerten, statt sie nur am Sharpe zu
> messen.

**Damit ist das Kernprogramm der Akademie komplett.** Von Abitur-Returns bis zur Variance
Risk Premium — jeder Baustein hängt an deinem eigenen Repo. Die Universität liefert später
Tiefe und Beweise; du hast jetzt das Quant-Gerüst, an dem sie andocken.
