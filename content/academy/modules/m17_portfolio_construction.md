> **Repo-Anker:** das Live-Overlay und CATALOG 0036 (Triple-Season-Overlay), 0050/0078
> (unkorrelierte Rates-Flow-Beine), 0106 (CTI CORE-Buch, Sharpe 1,21). Hier kommt alles
> zusammen: aus mehreren schwachen Beinen wird ein robustes Buch.

## 1. Das Versprechen aus Modul 3, eingelöst

In Modul 3 hast du die Mathe gesehen: $N$ unkorrelierte Beine mit je Vol $\sigma$ ergeben ein
Portfolio mit Vol $\sigma/\sqrt N$. Jetzt machst du daraus eine handelbare Strategie. Die
Schlüsselgröße ist der **Blend-Sharpe**:

$\text{Sharpe}_\text{Blend} = \text{Sharpe}_\text{Bein}\cdot \sqrt{\dfrac{N}{1 + (N-1)\rho}}$,

mit der mittleren Paar-Korrelation $\rho$. Bei $\rho = 0$ wird daraus $\text{Sharpe}\cdot\sqrt
N$ — fünf Beine mit Sharpe 0,5 ergeben ein Buch mit Sharpe ~1,1. Spiel damit:

::viz SharpeBlending

Stell $\rho$ auf 0 und erhöhe $N$: Die grüne Blend-Kurve wird glatt, während das einzelne
blaue Bein zappelt — **bei gleicher Rendite**. Das ist der eigentliche Hebel deines Systems:
nicht ein starkes Bein finden, sondern viele schwache, **unkorrelierte** kombinieren. Genau
deshalb erreicht das Quint-Overlay (0036) Sharpe 1,25, obwohl kein einzelnes Bein für sich
signifikant ist (Modul 3).

## 2. Korrelation ist der ganze Hebel

Der Term $\sqrt{N/(1+(N-1)\rho)}$ sagt alles: Bei hoher Korrelation bringt mehr $N$ fast
nichts (du handelst denselben Trade mehrfach), bei niedriger Korrelation skaliert der Sharpe
mit $\sqrt N$. Deshalb sind die wertvollsten Beine im Katalog die **gegenläufigen**: 0050
(Turn-of-Month, long Duration) und 0078 (Auction-Concession, short Duration) sind
unkorreliert/gegenläufig — zusammen tragen sie mehr als die Summe ihrer Teile.

**Konsequenz:** Ein neues Bein bewertest du nicht nur nach seinem eigenen Sharpe, sondern
nach seiner **Korrelation zum bestehenden Buch**. Ein mittelmäßiges, aber unkorreliertes Bein
ist wertvoller als ein gutes, das mit dem Bestand korreliert.

## 3. Wie gewichten?

Die Allokation über die Beine:

- **Inverse-Vol / Risk-Parity:** jedes Bein trägt **gleich viel Risiko** bei (Position ∝
  1/Vol, Modul 5). Verhindert, dass das wildeste Bein das Buch dominiert.
- **Regime-bedingt:** manche Beine tragen nur in bestimmten Regimes (Modul 18) — dort höher
  gewichten, sonst flach.
- **Overlay statt Standalone:** viele Edges (Saison/Flow) sind nur ~10 % der Zeit aktiv. Als
  **Overlay** liegt das Kapital nur am Trigger im Markt, sonst flat — so kombinierst du
  Dutzende seltener Beine ohne Kapitalkonflikt.

## 4. Wann ein Bein nichts beiträgt

Ehrlich bleiben (0077): Nicht jede Hinzunahme verbessert das Buch. Ein Bein, das mit dem
Bestand korreliert oder dessen Edge schon abgedeckt ist, hebt den Sharpe nur durch
**Konzentration** (mehr Kapital auf denselben Trade), nicht durch Diversifikation — und das
fliegt im Walk-Forward (Modul 15) auf. Der Test ist immer: **Steigt der Blend-Sharpe nach
Kosten und out-of-sample?** Wenn nicht, lass das Bein weg.

## 5. Das fertige Buch

So entsteht ein CORE-Buch wie 0106 (CTI, Sharpe 1,21): mehrere niederfrequente, gegenläufige
Flow-/Saison-/Carry-Beine, inverse-Vol gewichtet, als Overlay, unter den Prop-Regeln aus
Modul 16 re-geleveled. Kein einzelnes Bein ist spektakulär — das Buch ist es, weil die
Korrelationen niedrig sind.

> **Payoff:** Du verschmilzt mehrere schwache, dekorrelierte Edges zu einem robusten Buch,
> bewertest neue Beine nach Korrelation statt Solo-Sharpe und weißt, wann ein Bein nur
> Konzentration vortäuscht.

**Damit ist der Risiko-Track komplett.** Du kannst eine Strategie sizen (Modul 6), unter
Prop-Regeln prüfen (Modul 16) und zu einem Buch kombinieren (Modul 17) — die volle
Risikomanagement-Säule.
