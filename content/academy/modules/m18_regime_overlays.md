> **Repo-Anker:** `live/signals/dxy_regime_signal.py` und `vix_signal.py` — zwei live
> laufende Gates. Hier lernst du, einen Edge **kontextabhängig** an- und auszuschalten,
> statt ihn blind immer zu handeln.

## 1. Was ist ein Regime?

Ein **Regime** ist ein Marktzustand, in dem sich die Spielregeln ändern: Bullen- vs.
Bärenmarkt, ruhige vs. panische Vol, expansive vs. restriktive Geldpolitik. Viele Edges sind
**regime-abhängig** — sie verdienen im einen Zustand und verlieren im anderen. Ein Filter,
der den Zustand erkennt und nur im günstigen handelt, kann aus einem mittelmäßigen Bein ein
gutes machen.

## 2. Gating-Signale

Ein **Gate** ist eine simple, PIT-saubere (Modul 14) Bedingung, die das Bein scharf schaltet.
Zwei reale Beispiele aus dem Repo:

- **DXY-Regime** (`dxy_regime_signal.py`): Ist das 63-Tage-Momentum des US-Dollar-Index
  **negativ**, geh long einen Rohstoff-Korb (Gold, Kupfer, Öl, EM), sonst flat. Logik: ein
  schwacher Dollar treibt Rohstoffpreise (sie sind in USD notiert).
- **VIX-Carry-Gate** (`vix_signal.py`): Ist VIX3M/VIX > 1,03 (**Contango**, Modul 10), short
  VIXY (ernte die VRP, Modul 20), sonst flat. Das Gate hält dich aus der invertierten
  Backwardation-Phase, in der Short-Vol blutet.

Spiel mit einem Gate — grün ist die gegatete Strategie, grau Buy & Hold:

::viz RegimeGate

Das Gate (entschieden auf der **gestrigen** Indikator-Lesung — kein Look-ahead, Modul 14)
umgeht die Bär-Phasen und glättet die Equity. Schieb die Schwelle: zu locker → du hältst auch
im Bären, zu streng → du verpasst zu viel.

## 3. Overlay, nicht Standalone

Wichtige Einordnung (Modul 17): Ein Regime-Gate ist ein **Overlay**, kein eigener Edge. Es
*verbessert* ein bestehendes Bein (Timing/Risiko), erzeugt aber selbst keine Rendite — ohne
ein Asset, das es gated, ist es wertlos. Das USD-Regime (0086) hob den Sharpe eines
Rohstoff-Korbs von B&H 0,34 auf getimt 0,86 (Permutation p = 0,002) — aber der Korb liefert
die Rendite, das Gate nur das Timing.

## 4. Die Falle: Regime-Instabilität

Hier der ehrliche Vorbehalt, der Regime-Strategien gefährlich macht (0086). Ein Gate, das auf
**wenige** Regimewechsel reagiert, hat effektiv eine **winzige Stichprobe** — auch wenn es
über tausende Tage läuft. Wenn der DXY in 16 Jahren nur ~5 echte Momentum-Regimes hatte, dann
beruht dein „signifikanter" Backtest auf 5 Beobachtungen, nicht auf 4000 Tagen. Das ist die
Power-Falle aus Modul 1 in Verkleidung:

- **Wenig-Episoden-Risiko:** Der Sharpe sieht hoch aus, weil das Gate ein paar große Regimes
  richtig traf — das nächste Regime kann anders aussehen.
- **Regime-Definitionen veralten:** Was 2008–2015 ein Regime war (ZIRP), gilt 2022+ nicht
  mehr. Statische Schwellen driften (verwandt 0060, Stablecoin-Falle).

**Konsequenz:** Ein Regime-Overlay immer mit der **richtigen Null** prüfen (Modul 19, gegen
Zufalls-Timing, nicht gegen 0) und die **Zahl der Episoden** zählen, nicht die Zahl der Tage.

> **Payoff:** Du baust ein PIT-sauberes Regime-Gate als Overlay, verstehst, dass es ein
> Bein verbessert statt selbst Edge zu sein, und misst seine Fragilität an der Episoden-Zahl,
> nicht der Tageszahl.

**Nächstes Modul:** Die niederfrequenteste, kostenwand-festeste Edge-Klasse überhaupt —
Event-Driven & Saisonalität.
