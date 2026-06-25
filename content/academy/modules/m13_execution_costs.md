> **Repo-Anker:** `src/quantlab/costs.py` — `CostModel` mit den IBKR-/CFD-/Crypto-Presets.
> Diese Sitzung erklärt die **Kostenwand**: die unsichtbare Schwelle, an der im Katalog die
> meisten schönen Brutto-Kurven gestorben sind (0012-0015, 0038-0041, 0049).

## 1. Kosten zerlegt

Jeder Trade kostet, lange bevor du falsch liegst. Drei Komponenten:

- **Commission:** fixe Gebühr pro Order (Broker).
- **Spread:** die Bid-Ask-Lücke (Modul 12) — du kaufst am Ask, verkaufst am Bid.
- **Slippage:** die Differenz zwischen erwartetem und tatsächlichem Fill (Market Impact,
  Latenz).

Zusammen ergeben sie die **Round-Trip-Kosten** (Ein- + Ausstieg), gemessen in **Basispunkten
(bps)**. `CostModel` modelliert das als `commission_per_share`, `slippage_bps` und
`regulatory_bps` mit fertigen Presets — `IBKR_LIQUID_ETF`, `MES_INTRADAY` (~3 bps RT),
`BITGET_PERP_TAKER` (~8 bps/Seite), CFD-Presets.

## 2. Die Kostenwand

Der entscheidende Begriff. Jeder Trade hat einen **Brutto-Edge** (erwarteter Return vor
Kosten) und zahlt eine **feste Kostenschwelle**. Netto pro Trade:

$\text{Netto/Trade} = \text{Brutto-Edge} - \text{Kosten}_\text{RT}.$

Liegt der Brutto-Edge **unter** den Kosten, ist **jeder** Trade ein Verlust — und mehr
Trading macht es nur schlimmer. Spiel mit beiden Reglern:

::viz CostWall

Die graue Linie ist der Brutto-Pfad, die farbige der Netto-Pfad. Sobald der Brutto-Edge
unter die Kostenwand fällt, dreht die Netto-Kurve nach unten. **Mehr Frequenz hilft nicht —
sie multipliziert nur das Vorzeichen.**

## 3. Frequenz × Kosten — die eigentliche Falle

Hier die Lehre, die im Katalog am häufigsten zuschlug. Ein hochfrequentes Signal hat oft
einen **echten, aber winzigen** Brutto-Edge. Genau dort ist die Wand am tödlichsten:

- **0012-0015 (Crypto-Intraday):** Brutto ≈ 0, die ~16-24 bps-RT-Krypto-Wand macht jeden
  Netto-Trade zum Verlust.
- **0038-0041 (Index-Intraday):** Richtungs-Edge eines liquiden Index ist netto ≈ 0; selbst
  die billige ~3-bps-MES-Wand bindet.
- **0049 (Intraday-Momentum):** Der einzige Brutto-Puls (12. Halbstunde, +0,34 bps) liegt
  **unter** der 3-bps-Wand → netto tot.

Das Muster (Memo aus 0040/0041): **Ein einzelner liquider Markt hat intraday keinen
handelbaren Richtungs-Edge netto der Kosten.** Die Wand ist nicht die Richtung — sie ist die
Frequenz mal die Kosten.

## 4. Die Konsequenzen für dein System

Drei praktische Schlüsse, die den ganzen Katalog prägen:

- **Kostenmodell ist Schritt 0, nicht Schritt 9.** Eine CFD-Idee bekommt dieselbe Wand wie
  der Future (CFD_INDEX 3 bps, CFD_CRYPTO 20 bps RT) — kein leichterer Maßstab, nur weil das
  Instrument bequemer ist.
- **Niedrige Frequenz umgeht die Wand.** Genau deshalb tragen die Saison-/Flow-Edges (Modul
  19, Turn-of-Month, Auktionen): ~1-12 Trades/Jahr machen die Kosten vernachlässigbar — das
  exakte Gegenteil des Intraday-Regimes.
- **Instrument-Wahl ist Edge.** Dasselbe Signal überlebt bei IC-Markets-Gold (halbe Kosten),
  stirbt bei Bitget-Taker. Die Wahl des billigsten handelbaren Instruments ist Teil der
  Strategie, nicht Buchhaltung.

> **Payoff:** Du modellierst Kosten als Schritt-0-Gate, rechnest jeden Brutto-Edge gegen die
> Kostenwand und erkennst die Frequenz-Kosten-Falle, bevor du eine schöne Brutto-Kurve baust.

**Damit ist der Mikrostruktur-Track komplett.** Du weißt jetzt, *wie* gehandelt wird und
*was es kostet* — die Realitätsprüfung für jeden Alpha-Baustein.
