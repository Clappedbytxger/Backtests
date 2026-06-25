> **Repo-Anker:** `src/quantlab/cpcv.py` — `make_cpcv_splits()` mit Purging + Embargo
> und die PBO-Schätzung via CSCV. Diese Sitzung erklärt, warum dein ML-Vergleich (0057,
> 0061) ohne diese Maschinerie systematisch lügt.

## 1. Das Problem: Leakage in Zeitreihen

In Modul 2 hast du Multiple Testing kennengelernt: Wer genug Varianten probiert, findet
„Signifikanz" rein zufällig. Bei ML kommt ein zweites, subtileres Gift dazu — **Leakage**.

Standard-Kreuzvalidierung (K-Fold) mischt die Daten und teilt sie in $K$ Blöcke. Bei
unabhängigen Beobachtungen ist das korrekt. Bei **Zeitreihen ist es falsch**: benachbarte
Tage korrelieren (Modul 5, Vol-Clustering), und viele Labels überlappen — ein 5-Tage-
Forward-Return von heute teilt sich vier Tage mit dem von morgen. Trainiert das Modell auf
morgen und testet auf heute, hat es die **Zukunft mitgelernt**. Der OOS-Score ist
optimistisch, der Edge verdampft live.

## 2. Purging & Embargo

Die Korrektur (López de Prado) entfernt die kontaminierten Trainingspunkte rund um das
Testfenster:

- **Purging:** Lösche jeden Trainingspunkt, dessen Label-Fenster sich **zeitlich mit dem
  Testfenster überlappt**. Bei einem Label-Horizont von $h$ Tagen heißt das: ein Puffer von
  $h$ Tagen vor dem Test fällt weg.
- **Embargo:** Sperre zusätzlich eine kleine Zone **nach** dem Test, weil Autokorrelation
  auch vorwärts wirkt (typisch ~1 % der Beobachtungen).

Genau das macht `make_cpcv_splits()` über den Parameter `purge_days`. Im Gitter unten ist
die gelbe Bande diese gesperrte Zone:

::viz CPCVMatrix

## 3. Combinatorial Purged CV (CPCV)

Normale Walk-Forward-Validierung (Modul 15) liefert **einen** OOS-Pfad. CPCV liefert
**viele**: Die Zeit wird in $N$ Gruppen geteilt, und für **jede** Wahl von $k$ Testgruppen
trainiert man auf dem Rest (purged). Das ergibt

$\binom{N}{k}$ Splits

— im Gitter oben siehst du, wie die Zahl mit $k$ wächst. Aus diesen vielen überlappenden
Test-Pfaden bekommst du nicht nur einen Punktschätzer, sondern eine **Verteilung** der
OOS-Performance. Das ist der Stoff für den nächsten, entscheidenden Schritt.

## 4. PBO — die Wahrscheinlichkeit für Backtest-Overfitting

Die **Probability of Backtest Overfitting (PBO)** beantwortet die Frage, die Modul 2
aufwarf, jetzt quantitativ: *Wie wahrscheinlich ist es, dass meine in-sample beste Konfig
out-of-sample unterdurchschnittlich ist?*

Die CSCV-Logik: Für jeden Split bestimmst du die **IS-beste** Konfiguration und schaust
ihren **OOS-Rang** an. Landet die IS-Siegerin OOS regelmäßig in der unteren Hälfte, war die
IS-Selektion Glück. Formal: PBO = Anteil der Splits, in denen die IS-Beste OOS unter dem
Median liegt.

$\text{PBO} = \frac{1}{S}\sum_{s=1}^{S} \mathbf{1}\!\left[\,\text{rank}_\text{OOS}(\text{IS-Beste}_s) < \tfrac{1}{2}\,\right]$.

PBO nahe **0,5** = reines Rauschen (die IS-Auswahl sagt nichts über OOS). PBO nahe **0** =
robuste Selektion. **Vorsicht (aus 0057):** Auf reinem Rauschen ist PBO nur *im Mittel über
viele Datensätze* ≈ 0,5 — pro Einzeldatensatz ist sie hochvariabel; nicht überinterpretieren.

## 5. Die teure Lehre: CPCV ist kein handelbarer Pfad

Hier der Punkt, der im Katalog Geld gespart hat (0059): **CPCV beweist Modell-Skill, nicht
einen handelbaren Pfad.** Ein Modell, das in einem CPCV-Split „2020 vorhersagt", ist —
purged, aber doch — auch auf 2021–2026 trainiert. Es beantwortet „ist Modell A besser als
B?", nicht „hätte ich das 2020 live gehabt?". Den **Pfad** beweist nur Walk-Forward (Modul
15) oder ein echter Live-Forward. Deshalb bestand 0061 das CPCV-Gate — und kippte erst im
Walk-Forward-Check.

> **Payoff:** Du validierst Modellvergleiche leakage-frei (Purge + Embargo), liest die PBO
> richtig und weißt, warum ein bestandenes CPCV-Gate noch keinen handelbaren Edge beweist.

**Nächstes Modul:** Der ehrliche, handelbare Pfad — Walk-Forward und der registrierte
Live-Forward.
