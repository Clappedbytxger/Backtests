> **Repo-Anker:** `src/quantlab/seasonal.py` und die `live/engine.py`-Trigger. Hier ist die
> Edge-Klasse, die im Katalog am zuverlässigsten getragen hat — niederfrequenter,
> institutionell erzwungener Flow (0006, 0032, 0050, 0052, 0078).

## 1. Warum niederfrequenter Flow trägt

Erinnere dich an die Kostenwand (Modul 13): hohe Frequenz × kleine Kosten tötet Intraday-
Edges. Die **Umkehrung** ist die ganze These dieses Tracks: Bei ~1–12 Trades pro Jahr sind
die Kosten **vernachlässigbar**. Ein Edge von wenigen bps pro Trade, der intraday tot wäre,
ist hier handelbar — weil er so selten zuschlägt.

Und es gibt einen ökonomischen Grund, warum diese Edges existieren: **erzwungener Flow**.
Index-Fonds müssen am Monatsende rebalancen, Primärhändler müssen vor einer Treasury-Auktion
Platz schaffen, die Fed kündigt zu festen Terminen an. Das ist kein verrauschtes Verhalten,
sondern **institutioneller Zwang** — die robusteste Quelle struktureller Prämien.

## 2. Kalender- und Event-Fenster

Zwei Familien:

- **Kalender-Effekte:** Turn-of-Month (0050 — letzter + erste Handelstage, long Aktien;
  perm p = 0,035), Saison-Fenster (0006 — Benzin KW9; 0032 — Mais-WASDE 8.–18.12.).
- **Event-Fenster:** um einen geplanten Termin (0052 — Pre-FOMC-Overnight, +16 bps/Nacht;
  0078 — Auction-Concession, short Duration vor 30y-Auktionen).

Der `live/engine.py`-Trigger übersetzt solche Regeln backtest-treu in Order-Tickets
(`month_turn`, `fomc`, `date_window`, T+1-Konvention).

## 3. Die wichtigste Methoden-Lehre: die richtige Null

Hier der Punkt, der über echt vs. Schein entscheidet (0050/0052). Aktien driften nach oben.
Wenn du also „long am Monatsende" testest und gegen **0** vergleichst, bestehst du fast
immer — aber du misst nur die allgemeine Aktien-Drift, nicht den Kalender-Effekt.

Die **richtige Permutations-Null** ist **Zufalls-Timing**: gleiche Anzahl Trades, gleiche
Haltedauer, nur die **Tage zufällig** gewürfelt. Bestehst du *die*, trägt das **Timing**, nicht
das Long-Sein. Spiel mit der Event-Studie — der Effekt sitzt in einem schmalen Fenster:

::viz EventDrift

Schieb die Event-Zahl hoch: Mit wenigen Events ragen zufällige Offsets heraus (Rauschen),
erst mit genug Events tritt das wahre Fenster (−1/0) klar hervor. Das ist die Power-Falle aus
Modul 1 — und der Grund, warum 0052 erst in der **richtig gemessenen** Variante (Nacht in die
Ankündigung, gegen Zufalls-Nächte) bestand, während der naive „Vortag gegen 0" nicht sig war.

## 4. Die Roll-Day-Falle

Bei Continuous-Futures lauert die Falle aus Modul 10 erneut (0028/0029/0080). Eine Saison
über mehrere Wochen enthält zwangsläufig **Roll-Tage**, und der künstliche Roll-Sprung kann
den ganzen „Edge" fabrizieren:

- Erdgas-Herbst sah aus wie der stärkste Lead je (perm p = 0,001) — **105 %** der Trade-PnL
  saßen auf ~6 Roll-Tagen/Jahr. Nach Ausschluss einer ±1-Tag-Zone um jeden Verfall: p = 0,773.
- Getreide-Sommer-Short (0080): +5,6 % headline, aber 41 % auf Roll-Tagen.

**Pflicht-Vorabschritt:** Bevor ein Continuous-Futures-Saison-Edge als Lead zählt, ein
**Roll-Tag-Ausschlusstest** — der Edge muss überleben, wenn man eine enge Zone um jeden
Verfall entfernt (Modul 10).

## 5. Power: genug Trades

Letzte Hürde (Modul 1): Eine Saison gibt vielleicht ~11 Trades in 11 Jahren. Selbst ein
echter Effekt ist dann **power-limitiert** — der Bootstrap-KI schließt die Null oft nicht aus.
Deshalb sind diese Edges fast immer **Overlay-Beine** (Modul 17), kein Standalone: einzeln
schwach, aber unkorreliert und kostenwand-fest, also wertvoll im Verbund.

> **Payoff:** Du testest Kalender-/Event-Edges mit der **richtigen Null** (Zufalls-Timing),
> fängst die Roll-Day-Falle vor dem Urteil ab und ordnest sie als niederfrequente,
> kostenwand-feste Overlay-Beine ein.

**Damit ist der Alpha-Quellen-Track komplett.** Regime sagt dir *wann*, Event/Saison sagt dir
*wann genau* — beides niederfrequent, beides Overlay.
