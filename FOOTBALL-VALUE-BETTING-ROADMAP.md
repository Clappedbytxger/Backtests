# Roadmap: Fußball-Value-Betting-System (Closing-Line-Value-basiert)

> Handoff für Claude Code / Robin. Ziel: ein paar hundert Euro/Monat
> Nebeneinkommen über statistisches Value Betting — kein ML nötig, sondern
> saubere Wahrscheinlichkeits-Mathematik + dieselbe Validierungs-Disziplin wie
> im `Backtests`-Repo. Stand: Juni 2026. Keine Anlage-/Glücksspielberatung;
> Glücksspiel ab 18, nur lizenzierte deutsche Anbieter.

---

## Teil 0 — Ehrliche Einordnung & Ökonomie (zuerst lesen)

Das ist ein **Nebeneinkommen mit Decke**, kein Karrierepfad. Drei strukturelle
Wände, alle hart:

1. **5,3 % Wettsteuer** auf jeden Einsatz bei deutschen Lizenz-Buchmachern. Bei
   2–5 % Edge frisst die Steuer fast alles → **nur Buchmacher nutzen, die die
   Steuer komplett übernehmen** (Stand 2026: u. a. Bet365, Winamax, Tipwin,
   Bet3000 — vor Start live verifizieren, ändert sich). Sonst ist die Edge tot,
   bevor sie beginnt.
2. **LUGAS-Limit:** anbieterübergreifend max. **1.000 €/Monat Einzahlung** (mit
   Bonitätsprüfung erhöhbar). Begrenzt das *Bankroll-Wachstum durch frische
   Einzahlungen*, nicht den Umsatz — gewonnenes Geld lässt sich im Monat
   vielfach umschlagen. Aber: eine große Bankroll aufzubauen dauert Monate.
3. **Limitierung:** Soft Books limitieren konsistente Gewinner schnell (Wochen
   bis Monate) auf Kleinsteinsätze. Das ist die eigentliche Skalierungsgrenze.

**Realistische Mathematik des Ziels:** Bei ~3 % Netto-Edge braucht 300 €/Monat
rund 10.000 € Monatsumsatz. Mit einer aufgebauten Bankroll von 2.000–3.000 €
und Geld-Recycling (wetten → gewinnen → neu setzen) ist dieser Umsatz machbar —
bis die Accounts limitiert werden. **200–500 €/Monat ist erreichbar und
gleichzeitig die Decke.** Wer das akzeptiert, hat ein sauberes +EV-Projekt; wer
mehr erwartet, wird enttäuscht.

**Warum es methodisch trotzdem wertvoll für dich ist:** Es ist deine
Validierungs-Pipeline in einem neuen Markt — mit einer Validierungsmetrik (CLV),
die *schneller* Signifikanz liefert als alles in deinem Futures-Repo.

---

## Teil 1 — Die Edge & warum sie existiert

**Kernidee:** Pinnacle ist der schärfste Buchmacher der Welt — niedrigste Marge
(2–3 % statt 6–8 % bei Soft Books), limitiert Gewinner *nicht*, akzeptiert
höchste Limits. Dadurch sind Pinnacles Quoten der beste öffentlich messbare
Schätzer fairer Wahrscheinlichkeiten. **De-viggte Pinnacle-Quoten = Orakel.**

Die Soft Books (Bet365 & Co.) bewegen ihre Quoten langsamer und bepreisen
behaviorale Verzerrungen ein (Lieblingsteams, Favoriten-Bias, träge Reaktion auf
News/Lineups). **Immer wenn ein Soft Book eine Quote anbietet, die über der
fairen Pinnacle-Quote liegt, ist das eine +EV-Wette.**

**Closing Line Value (CLV) ist der Beweis-Mechanismus:** Pinnacles *Schluss*-Linie
ist der genaueste Outcome-Prädiktor überhaupt. Wenn du systematisch zu besseren
Quoten kaufst als die (de-viggte) Schlusslinie, hast du bewiesenermaßen Skill —
*lange bevor* die Ergebnis-Varianz es zeigt. **CLV ist der Permutationstest des
Wettens:** pro Wette sofort messbar, hohe N in Wochen statt Jahren. Das ist der
entscheidende Vorteil gegenüber deinen Saison-Edges (11 Trades/Jahr) — hier hast
du tausende unabhängige CLV-Beobachtungen schnell.

**Warum Retail das kann (anders als in Aktien):** Pinnacle als Orakel ist gratis
einsehbar, die Soft-Book-Ineffizienz ist behavioral und persistent, und die
„großen Player" (Syndikate) konzentrieren sich auf hohe Liquidität — in den
Nischen-Ligen ist mehr übrig.

---

## Teil 2 — Die Mathematik

### De-Vigging (Pinnacle-Quoten → faire Wahrscheinlichkeit)
Für ein 1X2-Spiel mit Pinnacle-Dezimalquoten o_H, o_D, o_A:

- **Implizite Wahrscheinlichkeiten:** p_i = 1/o_i (summieren auf > 1, die
  „Marge"/Overround).
- **Multiplikativ (Basis):** fair_p_i = (1/o_i) / Σ(1/o_j). Einfach, leichter
  Favoriten-Longshot-Bias.
- **Shin-Methode (besser):** korrigiert für Insider-Handel/Longshot-Bias,
  schätzt z (Insider-Anteil) iterativ. Für 2-Wege-Märkte (Over/Under, AH)
  empirisch genauer.
- **Power-/Odds-Ratio-Methode:** Alternative, im Backtest gegen Shin vergleichen.

→ **Implementiere alle drei, vergleiche im Backtest per CLV/Brier, welche auf
deinen Ligen am besten kalibriert.**

### EV-Berechnung
Für eine Soft-Book-Quote o_soft auf Outcome i:
```
EV% = (fair_p_i × o_soft − 1) × 100
```
Beispiel: fair_p = 52,3 %, Soft-Book bietet 1,952 → EV = (0,523×1,952−1)×100 =
**+2,1 %**. Wetten nur wenn EV% > Schwelle (Backtest bestimmt die Schwelle,
typisch 2–4 % nach Steuer-Übernahme).

### Sizing
- **Fractional Kelly** (¼–½ Kelly wegen Schätzfehler in fair_p):
  f = edge / odds, Einsatz = bankroll × kelly_fraction × f.
- Hard-Cap pro Wette (z. B. 2 % Bankroll) gegen Tail-Risiko und
  Limitierungs-Auffälligkeit.

---

## Teil 3 — Daten

### Backtest (gratis, das Fundament)
- **football-data.co.uk** — *die* kanonische Gratisquelle: 20+ Jahre, 20+
  europäische Ligen, mit **Pinnacle Opening & Closing** (Spalten `PSH/PSD/PSA` =
  Pinnacle, `PSCH/PSCD/PSCA` = Pinnacle Closing) plus Bet365 & Co. und
  Ergebnissen. CSV pro Liga/Saison. → Damit ist das komplette System
  backtestbar, *bevor* ein Euro fließt.
- Erweiterung (optional): bettingiscool / OddsPortal-Historie für mehr Bücher.

### Live-Betrieb
- **The Odds API** — brauchbarer Gratis-Tier für Low-Frequency-CLV-Tracking und
  Odds-Vergleich; Pinnacle + viele Soft Books. Bester Startpunkt.
- **OddsPapi** — Gratis-API-Key inkl. Pinnacle + Bet365, REST (Pre-Match).
- (Pinnacle eigener API seit Juli 2025 geschlossen — Aggregatoren nötig.)
- Soft-Book-Quoten teils nur per Anzeige/Scrape (Bet365 hat keinen API) → für
  den Start manuell/halbautomatisch, später Aggregator.

---

## Teil 4 — System-Pipeline

```
value_bot/
├── data/         # football-data Loader (Backtest), Odds-API Loader (live)
├── devig/        # multiplicative / shin / power, mit Tests
├── ev/           # fair_prob → EV%, Schwellen-Logik
├── clv/          # CLV-Tracker (gewettete Quote vs de-viggte Schlusslinie)
├── stake/        # fractional-Kelly Sizing, Caps
├── backtest/     # historischer Lauf auf football-data
└── live/         # tägliches Polling, +EV-Alerts, Bet-Log
```

**Live-Loop (täglich):** Fixtures der Ziel-Ligen ziehen → Pinnacle-Quoten holen
→ de-viggen → faire Wahrscheinlichkeiten → Soft-Book-Quoten vergleichen → EV% >
Schwelle? → Einsatz nach Kelly → **Wette + de-viggte Pinnacle-Quote zum
Wettzeitpunkt loggen** (für CLV). Nach Anpfiff: Schlusslinie + Ergebnis
nachtragen.

---

## Teil 5 — Validierung = CLV (deine Pipeline, schneller)

Der Backtest auf football-data.co.uk ist der Kern. Design:

1. **Kostenmodell zuerst:** 5,3 % Steuer (0 % bei absorbierenden Büchern —
   beide Szenarien rechnen!), realistischer Quoten-Slippage (du bekommst nicht
   immer die angezeigte Quote).
2. **Regel:** Wette Outcome i wenn `o_soft,i × fair_p_i(Pinnacle) − 1 > Schwelle`.
   fair_p aus **Opening- oder Zwischenquote**, NICHT aus der Schlussquote
   (das wäre Look-ahead — die Schlusslinie nutzt du nur zur CLV-Messung).
3. **Primärmetrik CLV:** Verteilung von `o_gewettet / o_fair_close − 1`. Positiver
   Median-CLV über tausende Wetten = bewiesene Edge. Das ist dein
   Permutationstest-Äquivalent — schnell und hoch-N.
4. **Sekundär P&L:** realisierte Rendite, aber mit breitem KI (Ergebnis-Varianz
   ist hoch). **Bootstrap-KI auf ROI**, muss bei großem N > 0 ausschließen.
5. **OOS-Split:** nach Saison *und* nach Liga (generalisiert die Edge, oder ist
   sie ein Ein-Liga-Artefakt?).
6. **Schwellen-Robustheit:** EV-Schwelle als Parameter-Plateau, nicht Spitze.
7. **Liga-Heterogenität:** Top-Ligen (effizient, dünne Edge) vs. Unterligen
   (ineffizient, breitere Edge, aber Soft Books limitieren dort schneller).

**Gate für „live gehen":** Median-CLV deutlich > 0 über ≥ 2 Saisons UND ≥ 3
Ligen, ROI-Bootstrap-KI > 0, Schwellen-Plateau stabil.

---

## Teil 6 — Bankroll & Realität des Skalierens

- **Startbankroll:** 1.000–3.000 € (LUGAS-Aufbau über Monate einplanen).
- **¼-Kelly**, Cap 2 %/Wette → niedrige Ruin-Wahrscheinlichkeit, glättere Kurve.
- **Varianz ist brutal:** auch mit echter Edge sind 100–200-Wetten-Drawdowns
  normal. Nur mit CLV-Beweis durchhaltbar (du weißt, dass du richtig liegst,
  auch wenn die Kurve fällt).
- **Account-Lebenszyklus:** voll wetten, bis Limitierung greift; dann neue
  (legale, eigene) Konten bei weiteren absorbierenden Büchern. Das ist die
  Decke, nicht ein Bug.

---

## Teil 7 — Phasenplan

| Phase | Ziel | Deliverable | Gate |
| --- | --- | --- | --- |
| **0** | football-data Loader + De-Vig | `data/`, `devig/` + Tests | De-Vig reproduziert Pinnacle-Margen korrekt |
| **1** | Backtest-Engine + CLV | `backtest/`, `clv/` | Median-CLV > 0 auf ≥ 2 Saisons/≥ 3 Ligen |
| **2** | Schwellen-/Liga-Robustheit | Backtest-Report (REPORT.md-Stil) | ROI-Bootstrap-KI > 0, Plateau stabil |
| **3** | Live-Polling + +EV-Alerts (Paper) | `live/` mit Odds-API | Paper-CLV ≈ Backtest-CLV über 4–6 Wochen |
| **4** | Echtgeld-Micro | kleine Einsätze, reale Quoten | reale CLV ≈ Paper, Steuer-Absorption verifiziert |

---

## Teil 8 — Anti-Selbstbetrugs-Checkliste

- **Steuer-Absorption verifizieren** vor jedem Euro — sonst Edge tot.
- **fair_p NIE aus der Schlussquote** im Backtest (Look-ahead). Schlusslinie nur
  für CLV-Messung.
- **CLV ist der Beweis, nicht die P&L-Kurve** — die Kurve ist verrauscht, CLV
  nicht.
- **Slippage real modellieren:** angezeigte Quote ≠ erhaltene Quote.
- **Liga-Effizienz beachten:** Top-Ligen dünn, Unterligen breit aber schneller
  limitiert.
- **De-Vig-Methode validieren** (multiplicative vs Shin vs power) per Kalibrierung.
- **Limitierung einplanen** — das ist die Skalierungsdecke, kein Versagen.
- **LUGAS/Steuer/Limits machen das zum Nebeneinkommen** — Erwartung ehrlich halten.

---

## Teil 9 — Tooling

Reines Python, alles gratis: `pandas`/`numpy` (vorhanden), `requests`/`httpx`
für Odds-APIs, `scipy` für Shin-Iteration und Bootstrap. Keine ML-Abhängigkeit.
Deine bestehende Bootstrap-/Permutations-Logik aus `significance.py` ist direkt
auf CLV/ROI anwendbar.

---

*Reihenfolge wie immer: erst der Beweis (Median-CLV > 0, ROI-KI > 0 über Saisons
und Ligen), dann Kapital. Der CLV-Beweis kommt hier schneller als in jedem
Futures-Test — das ist der eigentliche methodische Reiz.*
