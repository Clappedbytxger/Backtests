> **Repo-Anker:** `significance.py` — `permutation_test()` und
> `deflated_sharpe_ratio()`. Inklusive der Herleitung, warum dein alter DSR-Bug
> (er gab mechanisch 1,0 oder 0,0 aus) ein echter Bug war.

## 1. Die Nullhypothese und der p-Wert

Ein Hypothesentest stellt eine **Nullhypothese** $H_0$ auf — „es gibt keinen Edge, das
Ergebnis ist Zufall" — und fragt: *Wie wahrscheinlich wäre mein beobachtetes Resultat
(oder ein extremeres), wenn $H_0$ stimmt?* Diese Wahrscheinlichkeit ist der **p-Wert**.

- Kleiner p-Wert (z. B. < 0,05): Das Ergebnis wäre unter reinem Zufall selten ⇒ Indiz
  gegen $H_0$.
- **Wichtig:** Der p-Wert ist **nicht** die Wahrscheinlichkeit, dass deine Strategie
  funktioniert. Er ist die Wahrscheinlichkeit der *Daten unter $H_0$*. Diese Verwechslung
  ist der häufigste Statistik-Fehler überhaupt.

## 2. Der Permutationstest — die Null selbst bauen

Statt eine Verteilung anzunehmen, *erzeugen* wir $H_0$ direkt aus den Daten. Idee: Wenn
das **Timing** deiner Strategie keinen Edge hat, dann ist es egal, in welcher Reihenfolge
(oder mit welchem Vorzeichen) die Returns stehen. Also:

1. Miss die Kennzahl (z. B. Sharpe) der echten Strategie → **beobachteter Wert**.
2. **Mische** die Returns/Signale viele Male zufällig und miss jedes Mal die Kennzahl →
   das ist die Verteilung *unter $H_0$* (Zufalls-Timing).
3. Der p-Wert = Anteil der gemischten Läufe, die mindestens so gut sind wie dein echter.

Spiel damit: Stell den wahren Edge ein und beobachte, wie die graue Null-Verteilung liegt
und wo dein beobachteter Sharpe (grün) landet:

::viz PermutationNull

Setz den Edge auf 0 — der grüne Strich wandert in die Mitte, p ≈ 0,5. Das ist die
ehrliche Antwort „kein Signal". Genau dieser Test rettete Katalog 0069 (SMC) vor einem
Fehlurteil und tötete dutzende Schein-Edges.

## 3. Multiple Testing — das eigentliche Gift

Jetzt der Kern. Ein einzelner Test bei $\alpha=0{,}05$ irrt sich in 5 % der Fälle. Aber
was, wenn du **100 Varianten** durchprobierst? Selbst wenn *keine* einen Edge hat, ist die
Wahrscheinlichkeit, dass mindestens eine zufällig p < 0,05 erreicht, riesig:

$P(\text{mind. 1 Treffer}) = 1 - (1-0{,}05)^{100} \approx 99{,}4\%$.

Du **wirst** also „Signifikanz" finden, wenn du nur genug suchst. Das ist Data-Mining /
Backtest-Overfitting — die größte Gefahr im Quant-Research.

Die Mathe dahinter: Das **erwartete Maximum** von $N$ unabhängigen Zufalls-Sharpes wächst
mit $N$. Für Standardnormale gilt näherungsweise

$\mathbb{E}[\max_N] \approx \sqrt{2\ln N}$.

Bei $N=100$ sind das ~3,0 Standardfehler — ein „3-Sigma-Ergebnis" ist bei 100 Versuchen
**erwartbar**, nicht beeindruckend.

## 4. Der Deflated Sharpe Ratio (DSR)

Der DSR (López de Prado) zieht genau diese Erwartung ab. Er fragt: *Ist mein bester
Sharpe höher als das, was ich bei so vielen Versuchen ohnehin zufällig erwartet hätte?*

Vereinfacht: Er bildet einen **erwarteten Maximal-Sharpe** $\text{SR}^*$ aus (a) der Zahl
der Versuche $N$ und (b) der Streuung der Versuchs-Sharpes, und berechnet dann die
Wahrscheinlichkeit, dass dein wahrer Sharpe **über** $\text{SR}^*$ liegt — unter
Korrektur für Skew und Kurtosis (Modul 0 zahlt sich aus).

> **Dein Bug, jetzt verständlich:** Der alte Code übergab teils $N=1$ (⇒ $\text{SR}^*$
> kollabierte, DSR mechanisch 1,0) und hatte die Versuchs-Varianz hartkodiert auf falscher
> Skala (⇒ DSR mechanisch ~0). Beide Defekte machten die Metrik binär. Der Fix schätzt
> $\text{SR}^*$ aus der echten Trial-Streuung und behandelt $N=1$ separat als PSR-gegen-0.

## 5. Einheiten-Disziplin: warum $\sqrt{n-1}$

Eine letzte, unterschätzte Quelle von Bugs: **Einheiten**. Die PSR/DSR-Formeln erwarten
einen **Per-Period-Sharpe** (nicht annualisiert), weil sie intern mit $\sqrt{n-1}$
skalieren. Übergibst du versehentlich den annualisierten Sharpe, zählst du $\sqrt{252}$
doppelt. Regel: Immer prüfen, in welcher Einheit eine Formel ihren Sharpe erwartet.

> **Payoff:** Du kannst den DSR selbst korrekt implementieren, die Zahl der Versuche
> ehrlich zählen und Data-Mining von echtem Signal trennen.

**Nächstes Modul:** Bisher eine Strategie. Jetzt mehrere gleichzeitig — und dafür brauchst
du lineare Algebra: die Kovarianzmatrix und $w^\top\Sigma w$.
