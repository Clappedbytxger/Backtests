> **Repo-Anker:** `live/signals/wheat_rv_signal.py` — der Z-Score-Spread zwischen Chicago-
> und Kansas-Weizen (ZW − KE). Hier handelst du nicht die Richtung eines Marktes, sondern
> die **Rückkehr eines Spreads** zum Gleichgewicht — die reinste Form von Markt-Neutralität.

## 1. Die Idee: zwei verwandte Märkte

Zwei eng verwandte Assets (Chicago- vs. Kansas-Weizen, ES vs. NQ, zwei Aktien derselben
Branche) bewegen sich meist gemeinsam — getrieben vom selben Faktor. Ihre Preise **wandern**
(sind nicht-stationär, Modul 5), aber ihr **Abstand** schwankt um einen stabilen Mittelwert.
Wird der Abstand zu groß, ist die Wahrscheinlichkeit hoch, dass er zurückkehrt. Das ist die
Wette: **nicht wohin der Markt geht, sondern dass die beiden wieder zusammenfinden.**

## 2. Kointegration

Formal heißen zwei nicht-stationäre Reihen **kointegriert**, wenn eine **Linearkombination**
von ihnen **stationär** ist. Für ein Paar baust du den **Spread**

$s_t = \ln P^A_t - \beta\,\ln P^B_t$,

wobei $\beta$ das Hedge-Verhältnis ist (oft 1 für sehr ähnliche Märkte, sonst per Regression
aus Modul 4 geschätzt). Der **Engle-Granger-Test** prüft, ob dieser Spread stationär ist
(ADF-Test aus Modul 5 auf $s_t$). Ist er es, hast du ein handelbares Paar — die Preise dürfen
davonlaufen, der Spread nicht.

## 3. Z-Score Entry/Exit

Den Spread normierst du zu einem **Z-Score** über ein rollendes Fenster:

$z_t = \frac{s_t - \mu_t}{\sigma_t}$,

mit rollendem Mittel $\mu_t$ und Std $\sigma_t$. Die Regel:

- $z_t \geq +2$: Spread ist „zu hoch" → **short A, long B** (auf Rückkehr setzen).
- $z_t \leq -2$: Spread ist „zu tief" → **long A, short B**.
- $z_t \to 0$: Gleichgewicht erreicht → **schließen**.

Spiel mit der Halbwertszeit der Rückkehr:

::viz SpreadZScore

Weil du in **gleicher Höhe** long und short bist, ist die Position **markt-neutral** — fällt
der ganze Sektor, verlierst du auf einem Bein, was du auf dem anderen gewinnst. Genau das
zeigt 0087 (Weizen-RV): netto markt-neutral innerhalb Weizen, Permutation p = 0,000, Sharpe
0,31.

## 4. Das eigentliche Risiko: der Regime-Bruch

Pairs Trading sieht risikolos aus — ist es nicht. Die Gefahr ist **kein** großer Drawdown im
Normalbetrieb, sondern dass die **Kointegration reißt**: ein struktureller Bruch (ein
Unternehmen geht pleite, ein Markt ändert sein Regime), nach dem die beiden **nie wieder**
zusammenfinden. Dann läuft dein Z-Score immer weiter weg, und die „Mean Reversion", auf die
du wettest, existiert nicht mehr.

Verwandt ist die Delist-Relist-Falle (0058): LUNA fiel auf 0 und der Ticker wurde neu
vergeben — ein Spread über diese Lücke ist sinnlos. **Konsequenz:** Ein Pairs-Trade braucht
ein **Stop-/Monitoring-Regime** (maximaler Z-Score, Zeit-Stop, regelmäßiger Re-Test der
Kointegration), nicht nur die Entry/Exit-Bänder. Stabilität ist hier wichtiger als der
Entry.

## 5. Verwandtschaft zur Mikrostruktur

Der schnellste Cousin (0041): der **ES↔NQ-Relative-Value-Spread** auf Minutenbasis revertiert
echt (1-Min-Autokorr −0,107, Trefferquote steigt monoton bis 58 % bei z = 2,5) — aber er
liefert nur ~0,3–0,5 bps/Trade gegen ~6 bps Zwei-Bein-Kosten. Das ist die perfekte Brücke zu
Track C: das Signal ist real, aber die **Kostenwand** (Modul 13) entscheidet, ob es handelbar
ist.

> **Payoff:** Du baust einen markt-neutralen Spread-Trade (Kointegration → Z-Score → Bänder),
> verstehst, dass der Regime-Bruch das wahre Risiko ist, und überwachst Stabilität statt nur
> Entries.

**Nächstes Modul:** Was Spread-Profitabilität letztlich entscheidet — die Mikrostruktur und
die Kostenwand.
