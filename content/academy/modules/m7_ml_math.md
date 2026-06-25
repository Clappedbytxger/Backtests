> **Repo-Anker:** Die Meta-Labeling-Phase aus `ML-EDGE-ROADMAP.md` und deine
> LightGBM-Läufe (Katalog 0057–0062). Diese Sitzung macht aus „Knöpfe raten" Verstehen.

## 1. Gradient Descent — Optimierung im Großen

In Modul 6 hast du ein Maximum gefunden, indem du die Ableitung null setztest. Bei einem
Modell mit Millionen Parametern geht das nicht analytisch. Stattdessen läufst du iterativ
**bergab** auf der Verlustfunktion (loss): Der **Gradient** $\nabla L$ zeigt in die
Richtung des steilsten Anstiegs, also gehst du dagegen:

$\theta \leftarrow \theta - \eta\,\nabla L(\theta)$.

$\eta$ ist die **Lernrate**. Probier es an einer einfachen Parabel — und dreh $\eta$ über 1:

::viz GradientDescent

Zu klein ⇒ quälend langsam. Zu groß ⇒ die Schritte **überschießen** und explodieren. Diese
eine Intuition erklärt, warum jeder Optimierer eine Lernrate hat und warum Training
divergiert. (Das ist Modul 6 weitergedacht: Ableitung als Wegweiser statt als Nullstelle.)

## 2. Von Bäumen zu Boosting

LightGBM ist kein neuronales Netz, sondern **Gradient Boosted Trees**:

- Ein **Entscheidungsbaum** teilt den Feature-Raum in Rechtecke („wenn RSI < 30 und Vol >
  X, dann …"). Allein ist er schwach und overfittet leicht.
- **Boosting** baut viele kleine Bäume **nacheinander**, jeder korrigiert die Fehler der
  bisherigen Summe — per Gradient Descent auf der Verlustfunktion (daher „gradient"
  boosting). Hunderte schwache Bäume ergeben einen starken Lerner.

Deine wichtigsten Knöpfe sind jetzt keine Magie mehr: `num_leaves` (Baumkomplexität),
`learning_rate` ($\eta$ von oben), `n_estimators` (Zahl der Bäume) — und der nächste Punkt.

## 3. Regularisierung = Bias-Variance gesteuert

Modul 4 hat es geometrisch gezeigt: Mehr Komplexität passt in-sample immer besser, aber
generalisiert schlechter. **Regularisierung** ist der Hebel, der Komplexität bestraft:
kleinere `num_leaves`, weniger Bäume, `min_child_samples` hoch, L1/L2-Strafen. Du steuerst
damit bewusst den **Bias-Variance-Trade-off**. Genau das war der Befund in 0059: Die
**kleinste** LightGBM-Konfig schlug Ridge, die größte verlor — Crypto-Nichtlinearität ist
real, aber **flach**; zu viel Kapazität lernt nur Rauschen.

## 4. Kreuzvalidierung — und warum Zeitreihen anders sind

Um Out-of-Sample-Leistung *vor* dem Live-Gang zu schätzen, nutzt du **Kreuzvalidierung**:
trainiere auf einem Teil, teste auf dem Rest, rotiere. **Standard-K-Fold ist für Zeitreihen
falsch** — es lässt das Modell aus der **Zukunft** lernen (Leakage), weil benachbarte Tage
korrelieren.

Die Korrektur (López de Prado): **Purging** (entferne Trainingspunkte, die sich zeitlich mit
dem Testfenster überlappen) und **Embargo** (eine Pufferzone nach dem Test). Genau das macht
dein `cpcv.py` (Combinatorial Purged CV). **Leakage formal:** Jede Information, die zum
Entscheidungszeitpunkt noch nicht verfügbar war, im Training zu haben, fabriziert einen
Edge, der live verdampft — die teuerste Klasse von Bugs im ganzen Katalog.

## 5. Kalibrierte Wahrscheinlichkeiten & der Brier-Score

Ein Modell, das „70 % Wahrscheinlichkeit" sagt, sollte in 70 % der Fälle recht haben — dann
ist es **kalibriert**. Gemessen wird das mit dem **Brier-Score** (mittlerer quadratischer
Abstand zwischen vorhergesagter Wahrscheinlichkeit und Eintreten). Für **Meta-Labeling** ist
das zentral: Das Meta-Modell sagt nicht *Richtung*, sondern *„soll ich diesem Signal
vertrauen?"* — und Sizing (Modul 6, Kelly) braucht **kalibrierte** Wahrscheinlichkeiten,
sonst ist $f^*$ Müll.

**SHAP** schließlich erklärt, *welches Feature* eine einzelne Vorhersage wie stark trieb —
nützlich, aber Vorsicht (0057): Stabile Feature-Importance beweist **kein** Edge, nur dass
das Modell konsistent dieselbe (womöglich nutzlose) Struktur lernt.

> **Payoff:** Du verstehst jedes Knob in LightGBM und jede Stufe deiner ML-Pipeline —
> Boosting, Regularisierung, Purged CV, Kalibrierung — statt zu raten.

**Nächstes Modul (optional, später):** Stochastische Prozesse und Derivate — woher
Black-Scholes kommt und was die Variance Risk Premium wirklich ist.
