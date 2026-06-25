> **Repo-Anker:** Deine 3-%-Risk-Regel und die Prop-Pass-Monte-Carlos. Diese Sitzung
> macht aus „Sizing nach Gefühl" eine Rechnung.

## 1. Ableitungen als Optimierungswerkzeug

Aus dem Abitur: An einem **Maximum** einer glatten Funktion ist die **Ableitung null**
($f'(x) = 0$), und die zweite Ableitung negativ ($f''(x) < 0$). Das ist das ganze Werkzeug
der Optimierung: Stell die Zielfunktion auf, leite ab, setze null, löse. Genau das machen
wir gleich mit dem Kapitalwachstum.

## 2. Warum log-Wachstum?

Naiv würdest du den **erwarteten Gewinn** maximieren. Das führt in den Ruin: Eine Strategie
mit positivem Erwartungswert, aber Totalverlust-Risiko, maximiert $\mathbb{E}[\text{Gewinn}]$
und geht trotzdem irgendwann pleite (ein einziger −100 %-Tag löscht alles, und Produkte sind
nicht kommutativ mit der Null).

Der Ausweg: Kapital **multipliziert** sich über die Zeit ($V_T = V_0\prod_t(1+r_t)$). Wegen
$\ln(\prod) = \sum\ln$ (Modul 0!) ist die richtige Zielgröße das **erwartete logarithmische
Wachstum** $g = \mathbb{E}[\ln(1 + r)]$. Wer $g$ maximiert, wächst langfristig mit
Wahrscheinlichkeit 1 schneller als jede andere Strategie.

## 3. Das Kelly-Kriterium

Für eine binäre Wette (Trefferquote $p$, Gewinnverhältnis $b:1$) ist das erwartete
log-Wachstum bei Einsatz-Anteil $f$:

$g(f) = p\,\ln(1 + b f) + (1-p)\,\ln(1 - f)$.

Ableiten und null setzen ($g'(f)=0$) gibt den **Kelly-Anteil**:

$f^* = p - \dfrac{1-p}{b} = \dfrac{\text{Edge}}{\text{Odds}}$.

Sieh dir die Wachstumskurve an — sie hat ein klares Maximum bei $f^*$ und fällt danach
steil:

::viz KellyCurve

Beachte zwei Dinge: (1) Das Maximum ist **flach** nach links, aber **steil** nach rechts —
Untersetzen kostet wenig Wachstum, **Übersetzen ruiniert**. (2) Jenseits eines Punktes wird
$g$ **negativ**: Du verlierst Kapital trotz positivem Edge, nur durch zu große Einsätze.

## 4. Warum Fractional Kelly

Volles Kelly ist in der Praxis **zu aggressiv**, aus genau dem Grund aus Modul 1: $p$ und
$b$ sind nur **geschätzt**. Überschätzt du den Edge, sitzt dein „optimales" $f^*$ schon im
steilen, ruinösen Bereich. Außerdem sind die Drawdowns bei vollem Kelly brutal
(typisch −50 %). Profis handeln daher **½·Kelly** oder weniger: Das opfert nur ~25 % des
Wachstums, halbiert aber die Vol und macht die Schätzfehler verkraftbar. Deine 3-%-Risk-
Regel ist faktisch ein konservatives Fractional-Kelly mit Sicherheitsmarge.

## 5. Drawdown, Ruin & Monte-Carlo

Zwei Risikobegriffe, die Sharpe nicht erfasst:

- **Maximum Drawdown** = größter Peak-to-Trough-Verlust. Bestimmt, ob du ein Prop-Limit
  reißt — und ob du psychologisch dabei bleibst.
- **Ruin-Wahrscheinlichkeit** = Chance, eine kritische Schwelle (z. B. −10 % Prop-Limit) zu
  unterschreiten, **bevor** du das Ziel erreichst.

Beide haben selten geschlossene Formeln — deshalb **Monte-Carlo**: Simuliere tausende
Pfade aus deiner Return-Verteilung (mit den Fat Tails aus Modul 0, nicht naiv normal!) und
zähle, in wie vielen das Limit reißt. **Sauber aufgesetzt** heißt: realistische Verteilung,
Autokorrelation/Vol-Clustering (Modul 5) berücksichtigt, und die Pass-Rate als
*Wahrscheinlichkeit* lesen, nicht als Garantie. Genau so sind deine CTI-Pass-Monte-Carlos
(72–81 %) zu interpretieren.

> **Payoff:** Sizing ist jetzt eine Optimierungsrechnung mit ehrlicher Schätzfehler- und
> Drawdown-Behandlung statt eines Bauchgefühls.

**Nächstes Modul:** Die Optimierung von hier (Ableitung null setzen) skaliert auf
Millionen Parameter — das ist Gradient Descent und der Kern des Machine Learning.
