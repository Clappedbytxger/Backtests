> **Repo-Anker:** `overlay.py` — warum dein Quint-Overlay Sharpe 1,25 erreicht, obwohl
> kein einzelnes Bein für sich signifikant ist. Die Antwort ist ein Matrixprodukt.

## 1. Vektoren und Matrizen — in Trader-Sprache

Vergiss abstrakte Pfeile. Im Portfolio-Kontext sind die Objekte konkret:

- Ein **Vektor** $w = (w_1, \dots, w_n)^\top$ = deine **Positionsgewichte** (wie viel
  Kapital in jedem Asset). Long-only summiert zu 1; dollar-neutral zu 0.
- Eine **Matrix** = eine Tabelle. Deine Return-Historie ist eine Matrix $R$ (Zeilen = Tage,
  Spalten = Assets).

Der Portfolio-Return an einem Tag ist das **Skalarprodukt** $w^\top r = \sum_i w_i r_i$ —
gewichtete Summe der Asset-Returns. Das ist die ganze Magie: Matrixalgebra ist nur
„viele gewichtete Summen auf einmal".

## 2. Die Kovarianzmatrix Σ

In Modul 0 war die Varianz $\sigma^2$ die Streuung *eines* Assets. Bei mehreren Assets
brauchst du auch, **wie sie zusammen** schwanken. Das fasst die **Kovarianzmatrix** $\Sigma$
zusammen:

- Diagonale $\Sigma_{ii} = \sigma_i^2$ — die Varianz von Asset $i$.
- Off-Diagonale $\Sigma_{ij} = \text{Cov}(r_i, r_j) = \rho_{ij}\,\sigma_i\,\sigma_j$ — wie
  Asset $i$ und $j$ gemeinsam schwanken.

Die **Korrelation** $\rho_{ij} \in [-1, 1]$ ist die normierte Kovarianz: Vorzeichen +
Stärke des Zusammenhangs, einheitenfrei.

## 3. Das wichtigste Produkt deines Quant-Lebens: wᵀΣw

Die **Varianz eines ganzen Portfolios** ist

$\sigma_p^2 = w^\top \Sigma\, w = \sum_i \sum_j w_i w_j\,\Sigma_{ij}$.

Diese eine Formel steckt hinter jeder Portfolio-Konstruktion. Für zwei Assets ausgeschrieben:

$\sigma_p^2 = w_1^2\sigma_1^2 + w_2^2\sigma_2^2 + 2w_1 w_2\,\rho_{12}\,\sigma_1\sigma_2$.

Der entscheidende Term ist der letzte: Wenn $\rho_{12} < 1$, ist die Portfolio-Vol
**kleiner** als der gewichtete Durchschnitt der Einzel-Vols. Probier es aus — links die
gemeinsame Punktwolke, rechts die Portfolio-Vol über dem Gewicht:

::viz CovarianceEllipse

Stell $\rho$ auf 1 (Punkte auf einer Linie): Die Mulde rechts verschwindet — keine
Diversifikation. Stell $\rho$ niedrig oder negativ: Die Mulde wird tief — die
Portfolio-Vol fällt unter beide Einzel-Vols. **Das ist „der einzige free lunch" der
Finanzwelt**, und es ist reine lineare Algebra.

## 4. Diversifikation: warum √N

Spezialfall: $N$ Assets, jedes mit Vol $\sigma$, **alle unkorreliert**, gleich gewichtet
($w_i = 1/N$). Dann ist

$\sigma_p^2 = \sum_i \frac{1}{N^2}\sigma^2 = \frac{\sigma^2}{N} \;\Rightarrow\; \sigma_p = \frac{\sigma}{\sqrt N}$.

Die Portfolio-Vol fällt mit $\sqrt N$. **Genau das passiert in deinem Overlay:** Jedes
einzelne Bein hat ein schwaches, verrauschtes Signal (großer SE aus Modul 1), aber die
Beine sind nahezu unkorreliert. Ihre Summe hat dieselbe erwartete Rendite bei drastisch
kleinerer Vol ⇒ der Portfolio-Sharpe steigt auf 1,25, obwohl kein Bein allein besteht.

## 5. Eigenwerte light: Wie viele Risiken handelst du wirklich?

Wenn deine Assets stark korrelieren, sind 10 Positionen vielleicht nur **2–3 echte
Risikofaktoren**. Die **Hauptkomponentenanalyse (PCA)** zerlegt $\Sigma$ in
**Eigenvektoren** (unkorrelierte Risiko-Richtungen) und **Eigenwerte** (wie viel Varianz
jede Richtung trägt). Ein großer erster Eigenwert = „ein Faktor dominiert alles" (oft der
Markt selbst). Für dich praktisch: PCA auf deine Futures-Returns sagt dir, ob deine
„Diversifikation" echt ist oder nur derselbe Trade in Verkleidung.

> **Payoff:** Carvers Portfolio-Konstruktion und die Diversifikations-Mathe deines
> Overlays sind jetzt lesbar — du siehst $w^\top\Sigma w$ in jeder Risikozahl.

**Nächstes Modul:** $\Sigma$ misst Zusammenhang symmetrisch. Aber „erklärt der Markt meine
Strategie?" ist *gerichtet* — das ist Regression.
