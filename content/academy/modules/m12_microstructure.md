> **Repo-Anker:** `src/quantlab/footprint.py` und das Charts-Terminal. Hier zoomst du unter
> die Tagesbar: Wie kommt ein Preis überhaupt zustande — und was verrät das Volumen darüber,
> wer aggressiv war?

## 1. Das Order Book

Ein Preis ist kein Punkt, sondern das Ergebnis eines **Order Books**: einer Liste von Kauf-
(Bid) und Verkaufs-Aufträgen (Ask) auf verschiedenen Preis-Levels.

- **Best Bid:** der höchste Preis, zu dem jemand kaufen will.
- **Best Ask:** der niedrigste Preis, zu dem jemand verkaufen will.
- **Spread:** die Lücke dazwischen — die unmittelbarste Handelskostenquelle (Modul 13).
- **Tiefe:** wie viel Volumen auf den Levels liegt.

Zwei Order-Typen treiben alles: Eine **Limit-Order** *stellt* Liquidität ins Buch (passiv,
wartet). Eine **Market-Order** *nimmt* Liquidität (aggressiv, führt sofort gegen die beste
Gegenseite aus). Wer eine Market-Order schickt, **zahlt den Spread** und ist der „Aggressor".

## 2. Market Impact

Eine große Market-Order frisst nicht nur das beste Level, sondern arbeitet sich durch das
Buch — jedes weitere Level ist schlechter. Das ist **Market Impact**: der Preis bewegt sich
*gegen* dich, je größer deine Order relativ zur Tiefe. Impact ist der Grund, warum eine
Strategie, die im Backtest mit dem Schlusskurs rechnet, live schlechter abschneidet — und
warum Liquidität (Modul 9, der $5-M-Floor) ein hartes Vorab-Kriterium ist, kein Detail.

## 3. Footprint & Delta

Aus jedem Trade lässt sich ableiten, ob ein **Käufer** den Ask gehoben oder ein **Verkäufer**
den Bid getroffen hat. Aggregiert pro Preis-Level ergibt das den **Footprint**:

- **Ask-Volumen** (Käufer-aggressiv) vs. **Bid-Volumen** (Verkäufer-aggressiv) je Level.
- **Delta** $= \text{Ask} - \text{Bid}$: positives Delta = Käufer waren aggressiver.
- **POC (Point of Control):** das Level mit dem meisten Volumen — der „faire Preis" der Bar.

Schieb den Aggressor-Bias und beobachte Delta und POC:

::viz FootprintDelta

Diese Lesart — *wo* wurde aggressiv gehandelt, kehrt das Delta an einem Extrem um — ist, was
Order-Flow-Trader verfolgen. Im Repo rekonstruiert `footprint.py` genau das aus den Bars.

## 4. Die ehrliche Einschränkung: Tick-Rule-Approximation

Hier ein wichtiger Vorbehalt (Charts-Memo): Aus reinen **OHLCV-Bars** kennst du die
Aggressor-Seite **nicht** — du kennst nur Preis und Gesamtvolumen. `footprint.py` nutzt
deshalb die **Tick-Rule**: ein Trade über dem vorherigen Preis gilt als käufer-initiiert,
darunter als verkäufer-initiiert. Das ist eine **Näherung** (`approx=True,
delta_method="tick-rule"`), kein echtes Bid/Ask-Tagging.

Echtes Order-Flow-Delta braucht **Trade-Daten mit Aggressor-Flag** (Databento `trades`-Schema)
— und das ist bewusst opt-in, weil es Kredit-Kosten verursacht. **Lehre:** Bevor du auf eine
Footprint-Strategie baust, frag, ob dein Delta echt oder approximiert ist — die Näherung
genügt für Kontext, nicht für ein Edge, das vom exakten Aggressor abhängt.

> **Payoff:** Du verstehst Order Book, Spread, Market Impact und liest einen Footprint
> (Bid/Ask-Delta, POC) — und weißt, wann dein Delta nur eine Tick-Rule-Näherung ist.

**Nächstes Modul:** Der Spread aus Punkt 1 ist nur der Anfang der Kosten. Die volle
Kostenwand — und warum sie die meisten Intraday-Edges tötet.
