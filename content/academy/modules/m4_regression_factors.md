> **Repo-Anker:** Die 0015-Frage — „Ist mein Overlay nur verstecktes Long-Beta?" Eine
> Regression deiner Returns gegen den Markt beantwortet das sauber.

## 1. Von der Abitur-Geraden zu OLS

Du kennst $y = mx + b$. Die **lineare Regression** sucht genau diese Gerade durch eine
Punktwolke — aber datengetrieben: Welche Steigung und welcher Achsenabschnitt passen am
besten? „Am besten" = **kleinste Summe der quadrierten Abstände** (Ordinary Least
Squares, OLS). Im Trading-Kontext schreiben wir

$r_\text{strat} = \alpha + \beta\, r_\text{markt} + \varepsilon$.

- $\beta$ (Steigung) = **Marktexposure**: Wie stark bewegt sich deine Strategie mit dem
  Markt? $\beta = 1$ heißt „voll wie der Markt", $\beta = 0$ heißt marktneutral.
- $\alpha$ (Achsenabschnitt) = **Skill**: der Teil deiner Rendite, der **nicht** vom Markt
  kommt. Das ist echtes Alpha.
- $\varepsilon$ = **Residuum**: der unerklärte Rest pro Tag.

## 2. Die Formel — und ihr Bezug zu Modul 3

Die OLS-Steigung ist

$\hat\beta = \dfrac{\text{Cov}(r_\text{strat}, r_\text{markt})}{\text{Var}(r_\text{markt})}$.

Das ist exakt Kovarianz durch Varianz — dieselben Bausteine wie $\Sigma$ aus Modul 3, nur
jetzt *gerichtet* verwendet. Der Achsenabschnitt folgt aus den Mittelwerten:
$\hat\alpha = \bar r_\text{strat} - \hat\beta\,\bar r_\text{markt}$.

Spiel mit den wahren Werten und sieh, wie OLS sie aus verrauschten Daten zurückgewinnt:

::viz RegressionFit

Setz $\alpha = 0$: Die Strategie ist **reines Beta** — alle Rendite kommt vom Markt, kein
Skill. Erhöh das Rauschen: $\hat\alpha$ wird unschärfer (zurück zu Modul 1 — auch
$\hat\alpha$ hat einen Standardfehler).

## 3. R² und die t-Statistik

Zwei Kennzahlen lesen die Regression aus:

- **R²** ∈ [0, 1] = Anteil der Varianz deiner Strategie, den der Markt erklärt. R² = 0,8
  heißt „80 % deiner Schwankung ist nur Markt" — wenig eigenständig.
- **t-Statistik von $\hat\alpha$** = $\hat\alpha / \text{SE}(\hat\alpha)$. Das ist die
  Brücke zu Modul 1+2: Ist dein Alpha **signifikant** von 0 verschieden, oder im Rauschen?
  Faustregel |t| > 2 für 95 %.

So beantwortest du die 0015-Frage endgültig: Regressiere die Overlay-Returns gegen den
Markt. Ist $\hat\beta \approx 0$ **und** $\hat\alpha$ signifikant positiv ⇒ echtes,
marktneutrales Alpha. Ist $\hat\beta$ groß und $\hat\alpha \approx 0$ ⇒ du hast nur die
Aktien-Risikoprämie in Verkleidung verkauft.

## 4. Faktormodelle

Statt nur „den Markt" kannst du gegen **mehrere Faktoren** regressieren (Markt, Size,
Value, Momentum — Fama-French). Das ist dieselbe Mathe in Matrixform:

$r = \alpha + \beta_1 f_1 + \beta_2 f_2 + \dots + \varepsilon$.

Jedes $\beta_k$ misst die Exposure zu einem bekannten, bezahlten Risiko. Was nach Abzug
*aller* bekannten Faktoren als $\alpha$ übrig bleibt, ist dein echter, neuartiger Edge —
der Rest ist umverpackte Risikoprämie.

## 5. Overfitting geometrisch: Bias-Variance

Warnung, die Modul 7 vorbereitet: Je **mehr Features** du in eine Regression wirfst, desto
besser passt sie *in-sample* — irgendwann legt sie sich durch jeden Rauschpunkt. Das ist
**Overfitting**: niedriger Bias, aber hohe Varianz ⇒ out-of-sample wertlos. Mit $n$
Punkten und $n$ Parametern ist R² = 1 und der Edge eine Illusion. Mehr Komplexität ist
*nicht* gratis — sie kostet Generalisierung.

> **Payoff:** Du kannst jede Strategie gegen Marktfaktoren regressieren und echtes Alpha
> von Beta trennen — die zentrale Disziplin des ganzen Katalogs.

**Nächstes Modul:** Regression behandelt Tage als unabhängig. Aber Märkte haben Gedächtnis
— Autokorrelation, Vol-Clustering. Das ist Zeitreihenanalyse.
