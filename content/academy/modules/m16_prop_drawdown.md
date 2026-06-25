> **Repo-Anker:** `src/quantlab/robustness/monte_carlo.py` und der Funded-Account-Test aus
> 0070. Hier hört die Strategie auf, eine abstrakte Renditeverteilung zu sein, und wird an
> den harten Regeln eines echten Prop-Kontos gemessen.

## 1. Sharpe ist nicht genug

Modul 1 hat dich gelehrt, den Sharpe zu lesen. Aber ein Prop-Konto stirbt nicht am Sharpe —
es stirbt an **einem** schlechten Pfad. Zwei Regeln entscheiden über Leben und Tod, die der
Sharpe nicht sieht:

- **Trailing Maximum Drawdown:** der größte Verlust vom **bisherigen Höchststand** (Peak)
  bis zum Tief. Reißt er das Limit (z. B. 10 %), ist das Konto **sofort** weg — egal wie gut
  der Rest aussah.
- **Daily-Drawdown-Limit:** ein Verlust an **einem** Tag (z. B. 5 %) beendet die Challenge,
  selbst wenn der Gesamtstand positiv ist.

Dazu kommt oft eine **Konsistenzregel:** kein einzelner Tag darf mehr als X % des
Gesamtgewinns ausmachen — ein einziger Glückstreffer zählt nicht.

## 2. Warum der Mittelwert irreführt

Eine Strategie mit **positivem Erwartungswert** kann trotzdem fast sicher scheitern, wenn ihr
Pfad-Risiko hoch ist. Das ist der Kern (Prop-Edge-Framework):

> Eine Edge mit positivem EV, aber 40 % Ruin-Wahrscheinlichkeit pro Pfad, ist nutzlos.

Der Mittelwert mittelt über die Pfade, die das Limit reißen, einfach hinweg — aber die gibt
es real nicht mehr. Die richtige Frage ist nicht „was ist die erwartete Rendite?", sondern
**„welcher Anteil der Pfade überlebt die Regeln?"**.

## 3. Pass-Wahrscheinlichkeit per Monte-Carlo

Das beantwortet man simulativ. Du ziehst tausende Equity-Pfade aus deiner Return-Verteilung
(mit den **Fat Tails** aus Modul 0 — nicht naiv normal!) und zählst, wie viele das Limit
**nie** reißen. Probier es aus — grün besteht, rot reißt das Limit:

::viz DrawdownPaths

Schieb die Vol hoch oder das Limit runter: Die mittlere Rendite ändert sich kaum, aber die
**Pass-Wahrscheinlichkeit** bricht ein. Genau das macht `monte_carlo.py` mit
`block_bootstrap_paths()` — und zwar als **Block**-Bootstrap, damit die Autokorrelation und
das Vol-Clustering (Modul 5) erhalten bleiben; sonst unterschätzt du die Drawdowns.

## 4. Risikomaße jenseits des Sharpe

Zwei Kennzahlen, die das Pfad-Risiko direkt messen:

- **Recovery Factor** $= \dfrac{\text{Gesamtgewinn}}{\text{Max Drawdown}}$. Wie viel Rendite
  pro Einheit schlimmsten Verlusts — die eigentliche Prop-relevante Effizienz.
- **Ulcer Index:** die Wurzel des mittleren *quadrierten* Drawdowns. Anders als der Max-DD
  (ein einzelner Punkt) bestraft er **tiefe und lange** Unterwasserphasen — wie schmerzhaft
  das Halten wirklich war.

## 5. Der reale Befund (0070)

Konkret aus dem Katalog: Das SMC-Portfolio (0070) hatte ein Bootstrap-Sharpe-KI [+0,37,
+1,55] ohne Null — statistisch echt. **Trotzdem** im Funded-Account-Test problematisch:
Ø-Haltedauer 9–23 Tage, Max-DD 14,7 % — das **reißt** ein 10-%-Limit. Eine Strategie kann
also signifikant *und* prop-untauglich sein. Der Fix (Variante E): Pyramiding aus, jedes Bein
auf 20 % Standalone-DD re-leveln, equal-weight → Max-DD 8,6 %, Ret/DD 21 = fundbares Profil.
**Risikomanagement hat den Edge nicht erzeugt — es hat ihn handelbar gemacht.**

> **Payoff:** Du bewertest eine Strategie unter echten Prop-Regeln (Trailing-/Daily-DD,
> Konsistenz), schätzt ihre Pass-Wahrscheinlichkeit per Block-Bootstrap-Monte-Carlo und
> liest Recovery Factor und Ulcer Index statt nur den Sharpe.

**Nächstes Modul:** Ein einzelnes Bein ist riskant — wie kombiniert man mehrere zu einem
robusten Buch? Portfolio-Konstruktion.
