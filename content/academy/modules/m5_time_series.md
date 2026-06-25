> **Repo-Anker:** Vol-Targeting fürs Overlay — der größte fehlende Baustein deines
> Systems. Und die nachträgliche Antwort auf „warum war der Intraday-Brutto 0?" (0040).

## 1. Märkte haben Gedächtnis: Autokorrelation

Bisher behandelten wir Returns als unabhängig. Stimmt das? Die **Autokorrelation**
$\rho_k = \text{Corr}(r_t, r_{t-k})$ misst, wie stark der heutige Return mit dem von vor
$k$ Tagen zusammenhängt:

- $\rho_1 > 0$ ⇒ **Momentum** (Aufwärtstage folgen auf Aufwärtstage).
- $\rho_1 < 0$ ⇒ **Mean Reversion** (Bewegungen kehren um).
- $\rho_1 \approx 0$ ⇒ **Random Walk** (keine Richtungs-Prognose möglich).

**Dein 0040-Befund:** Die Intraday-Return-Autokorrelation von ES war ≈ 0 ⇒ kein
vorhersagbares Richtungssignal ⇒ Brutto-Edge 0. Das war keine Pleite, sondern eine saubere
Messung: An liquiden Indizes ist die Richtungs-Autokorrelation wegarbitriert.

## 2. Stationarität

Die meisten Zeitreihen-Werkzeuge verlangen **Stationarität**: Mittelwert und Varianz
ändern sich nicht über die Zeit. **Preise sind nicht stationär** (sie wandern), **Returns
meist schon** — noch ein Grund, mit Returns zu arbeiten (Modul 0). Der **ADF-Test** prüft
das formal; intuitiv fragt er: „Zieht die Reihe zu einem festen Mittel zurück (stationär)
oder läuft sie davon (Random Walk)?"

## 3. AR und MA — Minimalmodelle

Zwei Bausteine modellieren Gedächtnis:

- **AR(1)** (autoregressiv): $r_t = \phi\, r_{t-1} + \varepsilon_t$. Der heutige Wert hängt
  am gestrigen. $|\phi| < 1$ ⇒ stationär; $\phi$ nahe 1 ⇒ langes Gedächtnis.
- **MA(1)** (moving average): $r_t = \varepsilon_t + \theta\,\varepsilon_{t-1}$. Der heutige
  Wert hängt am gestrigen *Schock*.

Für **Returns** sind diese Effekte klein (Autokorrelation ≈ 0). Der interessante Teil
steckt woanders.

## 4. Der eigentliche Schatz: Vol-Clustering

Returns sind kaum autokorreliert — aber ihre **Beträge** sehr wohl. Große Tage folgen auf
große Tage, ruhige auf ruhige. „Volatility clustering". Modelliert wird das mit **GARCH**:
die heutige Varianz hängt am gestrigen Schock und an der gestrigen Varianz. Sieh es dir an
— blau die Returns (richtungslos), gelb die EWMA-Vol-Hülle (clustert klar):

::viz VolClustering

Unten stehen die zwei Autokorrelationen: die der Returns ≈ 0 (Richtung unvorhersagbar),
die der **Beträge** deutlich positiv (**Vol ist vorhersagbar**). Das ist die wichtigste
handelbare Regelmäßigkeit der Märkte — nicht *wohin*, sondern *wie heftig*.

## 5. Vol-Targeting — Carvers Kern

Wenn Vol vorhersagbar ist, kannst du sie steuern. **Vol-Targeting** skaliert deine Position
invers zur erwarteten Vol:

$\text{Position}_t = \dfrac{\sigma_\text{Ziel}}{\hat\sigma_t}\cdot \text{Basis-Position}$.

In ruhigen Phasen ($\hat\sigma_t$ klein) gehst du größer, in stürmischen kleiner. Resultat:
ein **konstantes Risiko** über die Zeit statt wild schwankender Drawdowns. $\hat\sigma_t$
schätzt du per **EWMA** (exponentiell gewichteter gleitender Durchschnitt der quadrierten
Returns) — jüngere Tage zählen mehr. Das ist der fehlende Baustein, um dein Overlay auf ein
festes Vol-Ziel zu bringen.

> **Vorsicht (aus Katalog 0056):** Vol-Targeting versagt bei **Short-Vol/Short-Gamma**-
> Strategien — der Crash kommt als Gap, *bevor* die realisierte Vol das Ziel heruntergezogen
> hat. Für richtungslose Carry/Trend-Beine ist es ideal, für Short-Optionalität gefährlich.

## 6. Kointegration light

Zwei nicht-stationäre Preise können eine **stationäre Linearkombination** haben — sie sind
**kointegriert** (z. B. ES und NQ). Dann ist der *Spread* mean-reverting, auch wenn die
Einzelpreise wandern. Das ist die Mathe hinter Pairs-/Stat-Arb (0041-RV): Nicht die
Richtung handeln, sondern die Rückkehr des Spreads zum Gleichgewicht.

> **Payoff:** Du kannst dein Overlay vol-targeten und verstehst, warum Richtungs-Edges an
> liquiden Märkten verschwinden, während Vol- und Spread-Struktur bleiben.

**Nächstes Modul:** Du weißt jetzt *was* du handelst. Wie **groß**? Das ist Optimierung,
Kelly und Sizing.
