> **Repo-Anker:** `src/quantlab/robustness/walk_forward.py`. Hier wird aus „mein Modell
> ist gut" das ehrlichere „mein Modell wäre live gut gewesen" — die Methode, die 0060
> (Crypto) und 0021 (Platin Cross-Asset) vom Schein-Edge getrennt hat.

## 1. Warum CPCV nicht reicht

Modul 14 hat es gezeigt: CPCV beweist **Skill** (Modell A schlägt B), aber jeder Test-Pfad
ist von Daten der Zukunft mitgeprägt. Walk-Forward erzwingt die **kausale Reihenfolge**:
trainiere nur auf Vergangenheit, teste auf der unmittelbar folgenden Zukunft, dann ein
Schritt weiter. Jeder grüne Test im Diagramm liegt strikt nach seinem Train:

::viz WalkForwardSplits

## 2. Rolling vs. Expanding

Zwei Fenster-Strategien:

- **Rolling:** Das Trainingsfenster hat eine **feste Länge** und gleitet mit. Gut, wenn sich
  die Marktstruktur ändert (alte Daten sollen „vergessen" werden) — passt zur Decay-These
  vieler Edges (0058–0062).
- **Expanding:** Das Training nutzt **die gesamte Historie bis jetzt**. Gut, wenn der Prozess
  stabil ist und mehr Daten immer helfen.

Beides toggelst du oben. Welches richtig ist, ist eine Annahme über Stationarität (Modul 5)
— und selbst eine Designentscheidung, die als Trial zählt (Modul 2).

## 3. Parameter-Pfad & Stabilität

Walk-Forward wählt die Parameter **in jedem Fenster neu** (auf dem IS-Teil) und wertet sie
OOS aus. Das liefert nebenbei einen **Parameter-Pfad**: Springt die optimale Lookback-Länge
von Fenster zu Fenster wild (5 → 60 → 12 → 90), ist die Strategie **instabil** — sie fittet
Rauschen. Bleibt der Parameter über die Fenster ruhig, ist das ein starkes Robustheits-
Signal. **Ein stabiler Parameter-Pfad ist oft aussagekräftiger als der OOS-Sharpe selbst.**

## 4. Der Haircut — und warum er gesund ist

Hier die zentrale, in echtem Geld bezahlte Zahl (0060): Dieselbe Regel, dieselben Daten —

$\text{CPCV-Stitch} \approx +0{,}81 \quad\longrightarrow\quad \text{echter Walk-Forward} \approx +0{,}38.$

Der Unterschied ist **kein Bug**, sondern der herausgerechnete Optimismus aus dem Regel-
Selektions-Kanal, den nur die kausale Reihenfolge entfernt. Erwarte diesen **Haircut** immer
— eine Strategie, deren CPCV- und WF-Zahl identisch sind, ist verdächtig (vermutlich kein
echter Selektionsdruck modelliert). Bei 0060 überlebte der Modell-Vorsprung den Haircut
(LGBM > Ridge auch OOT) — das machte ihn glaubwürdig.

## 5. Live-Forward — der einzige unbestechliche Test

Walk-Forward ist die beste *Backtest*-Approximation. Der wirklich unbestechliche Beweis ist
der **registrierte Live-Forward**: Du frierst die Regel ein, schreibst die Erfolgskriterien
**vorab** auf (z. B. „Median-CLV ≥ +1 % bei ≥150 Alerts in 4–6 Wochen"), und lässt sie auf
**ungesehenen** Daten laufen. Zwei Muster aus dem Katalog:

- **0021 (Platin):** Die auf einem Instrument gefittete Saison-Regel wurde **ohne Re-Fit**
  auf zwei nie berührten Instrumenten (PPLT, PA=F) getestet — Cross-Asset-OOS bestanden
  (p = 0,003–0,004). Das ist Walk-Forward im Querschnitt.
- **0060 (Crypto):** Die eingefrorene Regel läuft seit der Registrierung als monatliches
  Live-Buch — der finale, kanal-freie Test.

> **Payoff:** Du trennst CPCV-Skill vom handelbaren Pfad, liest den Parameter-Pfad als
> Stabilitätssignal, erwartest den Haircut und registrierst Forward-Tests mit vorab fixierten
> Kriterien — die Disziplin, die im Katalog Schein-Edges von echten getrennt hat.

**Damit ist der Validierungs-Track komplett.** Jeder folgende Alpha-Baustein (Cross-Sectional,
Carry, Pairs, Regime, Event) wird mit genau dieser Maschinerie geprüft.
