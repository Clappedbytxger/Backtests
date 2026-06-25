> **Repo-Anker:** CATALOG 0054 (VIX-Carry, brutto Sharpe 1,38) und 0056 (gehedged 0,74).
> Diese Sitzung vertieft Modul 8: von „was ist eine Option?" zu „wie verdient man
> systematisch an Volatilität — und warum ist das so gefährlich?".

## 1. Eine Vol für jeden Strike: der Smile

In Modul 8 war Volatilität *eine* Zahl. In der Realität hat **jeder Strike seine eigene
implizite Volatilität**. Trägt man sie über die Strikes auf, ergibt sich kein flacher Strich,
sondern ein **Smile** bzw. **Skew**: Out-of-the-Money-Puts (Absicherung gegen Crashs) handeln
**teurer** als die ATM-Option. Über alle Strikes *und* Laufzeiten spannt das die **Volatility
Surface** auf.

::viz VolSmile

Der Skew ist kein Marktfehler — er ist **Angebot und Nachfrage nach Versicherung**: Alle
wollen Crash-Puts, also sind sie teuer. Genau diese Asymmetrie ist die ökonomische Wurzel des
nächsten Punkts.

## 2. Die Variance Risk Premium

Hier schließt sich der Kreis zu Modul 0 und 8. Die **implizite** Vol (im Optionspreis
eingepreist, „was der Markt erwartet") ist **systematisch höher** als die später tatsächlich
**realisierte** Vol. Diese Differenz ist die **Variance Risk Premium (VRP)**:

$\text{VRP} = \sigma_\text{implizit}^2 - \sigma_\text{realisiert}^2.$

Im Chart ist sie die Fläche zwischen der blauen impliziten Kurve und der grauen realisierten
Linie. Sie ist **fast immer positiv** — Optionskäufer zahlen im Schnitt eine Prämie für
Versicherung, und Verkäufer kassieren sie als Carry. Das ist eine der robustesten
Risikoprämien der Märkte (verwandt mit Carry, Modul 10 — beides Bezahlung für übernommenes
Risiko).

## 3. Warum Short-Vol so verführerisch — und tödlich ist

Die VRP zu ernten heißt **Vol verkaufen** (Optionen schreiben, VIXY shorten). Das erklärt
0054 vollständig: Short-VIXY-im-Contango hatte einen **Brutto-Sharpe 1,38** — schöner als fast
alles im Katalog. Die Permutation bestätigte den Edge (p = 0,005), der DSR 0,993.

Aber: Vol verkaufen heißt **short Gamma** sein (Modul 8). Bei einem Crash explodiert das
Delta gegen dich — **schneller, als du nachhedgen kannst**. Der Verlust kommt als **Gap**,
bevor die realisierte Vol überhaupt ansteigt. Konkret (0054): MaxDD −63 %, **schlechtester Tag
−34 %** (>10σ). „Volmageddon" (Feb 2018) und März 2020 sind keine Ausreißer, sondern das
**eingebaute** Tail-Risiko.

> **Kern-Lehre (0054):** Sharpe und DSR **belohnen** Short-Vol, sind aber **blind für den
> Links-Tail**. Bei Short-Gamma/Short-Vol müssen MaxDD, Worst-Day und Kurtosis (Modul 0) das
> Urteil dominieren, nicht der Sharpe.

## 4. Warum Vol-Targeting hier versagt

Der naheliegende Reflex — die Position invers zur Vol skalieren (Modul 5) — **versagt bei
Short-Vol** (0056). Der Crash kommt als **Gap**, *bevor* die realisierte Vol das Target
heruntergezogen hat; am Gap-Tag ist die Position also noch **groß**. Vol-Targeting frisst die
ruhige Carry-Ernte und sieht den Gap nicht — nach Vol-Target ist der Edge zerstört
(Permutation p ≈ 0,90).

Was *funktioniert* (0056): **lineares Down-Sizing** (Skalieren erhält den Edge-Charakter exakt)
plus ein **definierter Risiko-Hedge** (VIX-Call). Das macht aus dem −34 %-Monster ein
konto-verträgliches Sleeve (Sharpe 0,55, MaxDD −11 %) — aber der Hedge kostet ~1–5 %/Jahr und
frisst die halbe Rendite. **Das ist das VRP-Dilemma: Die Tail-Versicherung kostet ungefähr so
viel wie die Prämie, die du erntest.** Kein free lunch — bezahltes Risiko.

> **Payoff:** Du liest die Vol-Surface (Smile/Skew), verstehst die VRP als
> Versicherungsprämie und weißt, warum Short-Vol risiko-definiert geerntet werden muss —
> MaxDD/Worst-Day vor Sharpe, lineares Sizing statt Vol-Targeting, Hedge als Existenzbedingung.

**Nächstes Modul:** Das letzte Stück — ML im Trading, mit allen Fallstricken, die du jetzt
benennen kannst.
