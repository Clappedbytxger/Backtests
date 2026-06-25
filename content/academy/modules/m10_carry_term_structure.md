> **Repo-Anker:** `src/quantlab/futures_curve.py` — `carry_signal()` und
> `roll_adjusted_front_panel()`. Carry ist der Edge, der nicht aus der Preisbewegung kommt,
> sondern aus der **Form der Terminkurve** — und der dich die teuerste Roll-Falle lehrt.

## 1. Die Terminstruktur

Ein Future hat nicht einen Preis, sondern eine ganze **Kurve**: denselben Rohstoff für
Lieferung in 1, 2, 3 … Monaten. Zwei Formen:

- **Contango:** ferne Kontrakte **teurer** als nahe (aufsteigende Kurve). Normal bei lager-
  baren Gütern (Lagerkosten, Zins).
- **Backwardation:** ferne Kontrakte **billiger** als nahe (absteigende Kurve). Typisch bei
  Knappheit/hoher Spot-Nachfrage.

Verschieb die Kurvenform und sieh, wie sich der Roll-Yield dreht:

::viz RollYieldCurve

## 2. Roll-Yield = Carry

Warum ist die Form handelbar? Ein Future konvergiert bei Verfall zum Spot. Hältst du eine
Long-Position und „rollst" sie vor Verfall in den nächsten Kontrakt, **verdienst oder
verlierst** du an dieser Konvergenz — den **Roll-Yield**:

$\text{Roll-Yield} \approx \frac{P_\text{front} - P_\text{second}}{P_\text{front}} \times \frac{12}{\text{Monate Abstand}}$.

- **Backwardation** (front > second): Du kaufst den billigeren fernen Kontrakt, er rollt
  **hoch** zum Spot → **positiver** Carry für den Long.
- **Contango** (front < second): Der ferne Kontrakt rollt **runter** → **negativer** Carry.

Das ist eine **strukturelle Risikoprämie**, kein Preis-Timing: Du wirst dafür bezahlt, dass
du Lagerhalter/Produzenten Absicherung abnimmst. Das Cross-Sectional-Carry-Portfolio (0048,
Modul 9) rankt genau danach: **long die stärkste Backwardation, short das tiefste Contango**.

## 3. Die teuerste Falle des Katalogs: Roll-Artefakte

Jetzt der Teil, der im Katalog (0048, 0028/0029) bares Geld kostete. Um Carry zu *messen*,
brauchst du eine durchgehende Preisreihe. Anbieter liefern „continuous" Front-Month-Reihen —
und die haben einen **Sprung an jedem Roll-Tag**, weil zwei verschiedene Kontrakte
aneinandergeklebt werden.

Rechnest du naiv `front.pct_change()`, **buchst du diesen Sprung als Return**. Bei tiefem
Contango (Erdgas −24,7 %/Jahr) springt die Reihe an jedem Monatsroll hoch; eine Strategie,
die Contango shortet, „verdient" diesen Sprung — den ein echter Roller **nie** zahlt. In
0048 ergab das einen Schein-Sharpe von **−1,57** (perfekt invertiert), zu 100 % Artefakt:
**−39 bps/Tag an Roll-Tagen** vs. −1,1 bps sonst.

Die Korrektur:

- **Roll-Tage exakt aus dem `instrument_id`-Wechsel** bestimmen (nicht heuristisch — die
  Heuristik unter-/überzählte je nach Rohstoff).
- Am Roll-Tag den **Gap nullen** (`roll_adjusted_front_panel`): die Intra-Kontrakt-
  Konvergenz (= echter Carry) bleibt, der künstliche Klebe-Sprung verschwindet.

Korrigiert fiel der Schein-Sharpe von −1,57 auf −0,40 (kein Edge) — die ehrliche Antwort.

> **Meta-Lehre:** Ein Sharpe, der **zu schlecht** ist (≤ −1,5, p gegen 1,0), ist genauso
> verdächtig wie einer, der zu gut ist — beides schreit nach Artefakt. Bei Continuous-Futures
> **immer zuerst roll-adjustieren**, bevor irgendein Carry-/Return-Urteil zählt.

## 4. Carry ist real, aber zerfallen

Ehrlich bleiben (0047/0048): Nach der Index-Welle 2004–2014 ist die cross-sektionale
Rohstoff-Carry-Prämie 2010–2026 weitgehend **zerfallen** (IS +0,31 → OOS −0,40). Der
*Mechanismus* (Roll-Yield = Carry) ist lehrbuch-korrekt und in einzelnen Märkten/Perioden
lebendig — die *breite Faktor-Prämie* ist arbitriert. Carry bleibt ein Baustein, kein
Standalone.

> **Payoff:** Du verstehst Roll-Yield als strukturelle Prämie, erkennst Roll-Artefakte am
> instrument_id-Sprung und roll-adjustierst, bevor du Carry überhaupt misst.

**Nächstes Modul:** Statt eines Faktors über viele Märkte — zwei eng verwandte Märkte
gegeneinander: Pairs Trading & Kointegration.
