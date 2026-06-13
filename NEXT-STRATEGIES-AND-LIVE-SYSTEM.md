# Nächste Strategien, technische Edges & Live-Trading-System

> Handoff für Claude Code + Entscheidungsgrundlage für Robin. Aufbauend auf dem
> 62-Strategien-Bestand. Recherchiert Juni 2026. Keine Anlageberatung.

---

## Teil 0 — Was noch zu finden ist (und wo nicht)

Dein Bestand ist fast eine einzige Familie: Kalender-/Saison-/Flow-Effekte +
ein Crypto-Bein. Drei Sackgassen sind **bewiesen** und brauchen keinen weiteren
Versuch: Intraday-Richtung liquider Märkte (kostengebunden), Fundamental-Inputs
(eingepreist), cross-sektionale Rohstoff-Prämien (zerfallen). Das
yfinance-Saison-Universum ist erschöpft (0011). **Die Suche muss eine
strukturell unkorrelierte zweite Edge-Familie liefern** — nicht noch ein
Outright-Saison-Fenster. Zwei Richtungen tragen, eine ist nett-aber-nachrangig.

---

## Idee A — Calendar Spreads: deine Saisonalität, sauber gemacht (TOP-PRIORITÄT)

**Die Erkenntnis:** Deine Outright-Saison-Trades haben zwei Schwächen, die du
selbst diagnostiziert hast — (1) sie tragen volle **Richtungs-/Beta-Wette**
(du gibst Marktrendite auf für einen kleinen Saison-Kick), (2) auf
Continuous-Reihen das **Roll-Artefakt-Risiko** (0028/0029 NatGas tot). **Calendar
Spreads lösen beides gleichzeitig:** Long Nahmonat / Short Fernmonat desselben
Rohstoffs isoliert die Saison-Angebots-/Nachfrage-Dynamik, ist innerhalb des
Rohstoffs marktneutral, und die Roll-/Expiry-Dynamik *ist das Signal statt ein
Artefakt*.

**Evidenz, dass das real ist:** Es gibt einen systematischen Fonds (Aquantum
Commodity Spread), der genau das seit 15 Jahren handelt — Return/Risk ~0,81–0,85
über die Indizes. Die Ursachen sind **strukturell, nicht behavioral, also
decay-resistent:** Hedging-Prämie der Farmer um die Ernte (sie zahlen Prämie,
um Produktion abzusichern → Nahmonat outperformt), Lagerkosten, Convenience
Yield, Wetter (Hurricane-Saison → Front outperformt). Dazu praktisch: **20–40%
der Outright-Margin, deutlich niedrigere Vola, reduziertes Tail-Risiko.**

**Konkreter Plan:** Drücke deine *bereits validierten* Saison-Effekte als Spreads
aus, statt neue Fenster zu suchen:
- Mais Dezember (0030/0032) → Long Dez / Short Juli (alte vs neue Ernte).
- Benzin Driving-Season (0006) → Front/Deferred-Spread um KW9.
- Erdgas Winter (0028 — als Outright tot wegen Roll!) → als Spread **könnte der
  Effekt echt sein**, weil der Spread genau die Injection-/Withdrawal-Dynamik
  abbildet, die das Roll-Artefakt verursacht hat.
- Plus die klassischen Ag-Spreads (Soja-Crush-Saison, Weizen-Carry).

**Daten:** Databento GLBX (hast du, aus 0048) liefert alle Kontrakte → Front-
und Deferred-Settlement, daraus die Spread-Zeitreihe. **Kein Back-Adjust nötig**
(der Spread ist per Konstruktion roll-bereinigt — der Hauptvorteil).

**Validierung:** deine volle Batterie, plus ein **Spread-spezifischer
Roll-Check** (Verfallswochen der beiden Beine sauber behandeln) und
Liquiditäts-Check (Deferred-Kontrakte sind dünner → Spread-Spread-Kosten).

**Warum top-Priorität:** Es ist die einzige Idee, die (a) deine bestehende,
bewiesene Saison-Forschung direkt veredelt, (b) das Beta-Problem deines Overlays
löst, (c) eine echte Fonds-Erfolgsbilanz hat, (d) mit deiner vorhandenen
Databento-Infra baubar ist.

---

## Idee B — Trend-Following: der belegte Diversifikator (ZWEITE PRIORITÄT)

**Ehrliche Einordnung:** Time-Series-Momentum (Moskowitz/Ooi/Pedersen 2012;
„a century of evidence" Hurst et al. 2017) ist die **eine technische Strategie
mit echter, struktureller, jahrhundertelanger Evidenz** — und ohne
signifikante Kapazitätsgrenze (Baltas/Kosowski). ABER: **kein Geheim-Alpha.**
Post-2009 war die Performance schwach, und der Horizont entscheidet — aktuelle
Forschung (2025) zeigt: **schnelle (~20d) und langsame (~500d) Sleeves tragen,
die mittleren (60–125d) whipsawen** und underperformen seit 2022. Kurzfrist-
Momentum (täglich) mean-reverted nach Mikrostruktur-Kosten (= exakt deine
Intraday-Kostenwand, von der Literatur bestätigt).

**Der Wert für dich ist Diversifikation, nicht Rendite:** Trend-Following ist
**niedrig/negativ korreliert** zu deinem Saison-/Mean-Reversion-Buch und liefert
**Krisen-Konvexität** (Long-Vol-Charakter — gut 2008, 2022). Als eigenständige
Edge mittelmäßig; als **zweites unkorreliertes Bein** in einem Multi-Strategie-
Portfolio lehrbuchmäßig sinnvoll. **Carver (hast du) ist die Bauanleitung.**

**Konkreter Plan:** Vol-getargetetes Multi-Future-Trend über ~15–20 liquide
Kontrakte (Indizes, Bonds, FX, Rohstoffe), **nur schneller + langsamer Sleeve**
(den mittleren Whipsaw-Bereich meiden), Risk-Parity-Gewichtung. Databento +
yfinance reichen. Validierung: Walk-Forward, Subperioden (2009–2022 war hart —
das muss überlebt werden), Korrelation zu deinem bestehenden Buch messen (der
eigentliche Test: senkt es Portfolio-Vola/MaxDD?).

---

## Idee C — Mehr Seasonalitäten (Seasonax): nachrangig

Das yfinance-Outright-Saison-Universum ist erschöpft (0011: 18/19 kollabieren
OOS, Kontrollen sauber → Methode validiert, Universum leer). **Weitere
Seasonax-Outright-Fenster zu minen ist negativ-erwartungswertig** — du würdest
nur die 0017-Drift-Falle neu produzieren. Die *richtige* Weiterführung der
Saisonalität ist Idee A (Spreads), nicht mehr Fenster. Falls überhaupt neue
Outright-Märkte: Rates-/FX-Saisonalität (Treasury-Auktionszyklen,
Quartalsende-FX-Flows) sind die einzigen unberührten mit struktureller Ursache —
aber erst nach Spreads + Trend.

---

## Idee D — PEAD: real, aber datengemauert und off-focus (NACHRANGIG)

PEAD (Post-Earnings Announcement Drift) ist eine der robustesten Anomalien
überhaupt und **funktioniert noch — aber dekayed**, v.a. in Large Caps; lebendig
bleibt sie im **kleinen/illiquiden Segment** (genau dort, wo Execution für dich
schwer ist, s. Small-Cap-Diskussion). Dein 0055-Verdikt war richtig: Der
Blocker sind **survivorship-freie Earnings-Surprises (Ist vs. Konsens) über
Jahrzehnte** — frei nur 1–2 Jahre/Ticker (Finnhub hast du, FMP-Free, yfinance),
die Tiefe braucht Sharadar/I-B-E-S (kostenpflichtig). Dazu ist es ein
**Einzelaktien-Programm**, das nicht zu deinem Index-/Prop-Fokus passt.
**Verdikt: legitim, aber erst wenn eine freie Tiefendaten-Quelle erschlossen ist
und nach Spreads/Trend.** Kein Pseudo-Test auf heutigen Mega-Caps (wäre
survivorship-verzerrt — deine eigene Disziplin).

---

## Idee E — ML: erst den Live-Forward abwarten

Dein Crypto-ML-Lead (0059/0060) ist im 24-Monats-Live-Forward. **Bevor der nicht
resolved, kein neues ML** — sonst Multiple-Testing über Programme hinweg. Die
*eine* additive ML-Anwendung, die du noch nicht gebaut hast und die zu deinem
Bestand passt: **Meta-Labeling auf dem Quint-Overlay** (LightGBM lernt
regime-abhängig „Bein nehmen / verkleinern / auslassen"). Kleiner
Hypothesenraum, setzt auf bewiesene Signale auf, kann nur Sizing verbessern.
Niedrige Priorität, aber sauberster ML-Next-Step. CNN/Deep Learning ist
abgehakt (0062 Null, wie vorhergesagt).

---

## Teil 2 — Technische Strategien: Verdikt

Deine eigene Evidenz ist eindeutig: **standalone TA auf einem liquiden
Einzelmarkt ist tot** (0012–0015, 0038–0041, 0049 — Intraday-Richtung ≈ 0 netto;
0013 Fade kontinuiert statt umzukehren; Opening-Range/Time-of-Day leer). Das ist
keine Meinung, das sind 9 sauber gemessene Nullen, und die Literatur bestätigt
es (Kurzfrist-Momentum mean-reverted nach Mikrostruktur-Kosten).

**Was als technische Strategie Sinn ergibt:**
- **Trend-Following (Idee B)** — die einzige TA-Klasse mit struktureller Evidenz,
  als *Komplement/Diversifikator*, nicht standalone-Alpha.
- **Technische Muster als ML-Features** — abgehakt (0062 CNN-Null auf Crypto).
- **Volatilitäts-Breakout auf trendstarken Märkten** — könnte als Teil des
  Trend-Sleeves getestet werden, nicht separat.

**Was keinen Sinn ergibt:** Oszillatoren/Indikatoren (RSI/MACD/Bollinger) als
eigenständige Edge auf liquiden Märkten — das ist der gecrowdetste, leerste Raum,
und deine Intraday-Nullen sind der Beweis. **Verdikt: TA nur als Trend-Komplement,
nie als alleinige Edge.**

---

## Teil 3 — Live-Trading-System mit Claude-Routinen

Du hast jetzt mehrere live/live-nahe Strategien mit verschiedenen Auslösern —
das schreit nach Automatisierung der *Signalerzeugung + Benachrichtigung +
Protokollierung* (Ausführung bleibt human-in-the-loop, aus Engineering-Gründen,
nicht aus Vorsicht).

### Architektur
```
live/
├── calendar.yaml         # jede Live-Strategie + Trigger-Regel
├── signals/              # ein Signal-Skript je Strategie
│   ├── overlay_signal.py       # Quint-Overlay-Beine (Datums-getriggert)
│   ├── tom_signal.py           # Turn-of-Month (Monatsultimo)
│   ├── prefomc_signal.py       # Pre-FOMC (FOMC-Kalender)
│   └── crypto_live_signal.py   # (existiert) Crypto-Monatsbuch
├── run_daily.py          # Orchestrator: prüft Kalender, ruft fällige Signale
├── notify.py             # Telegram/E-Mail-Alert mit Order-Ticket
└── ledger.py             # Live-Forward-Log: erwartete vs reale Fills
```

### `calendar.yaml` (Beispiel)
```yaml
- id: benzin_kw9
  trigger: {type: isoweek, week: 9, day: monday}
  signal: overlay_signal.py --leg gasoline
- id: turn_of_month
  trigger: {type: month_end, offset_days: -1}
  signal: tom_signal.py
- id: pre_fomc
  trigger: {type: fomc_calendar, when: day_before}
  signal: prefomc_signal.py
- id: crypto_rebalance
  trigger: {type: month_end, offset_days: 0}
  signal: crypto_live_signal.py
```

### Die Claude-Routinen (der eigentliche Hebel)
1. **Wöchentlicher „Trading-Desk"-Lauf** (GitHub Action, cron, gratis; oder
   lokal). Claude Code führt `run_daily.py` aus, das den Kalender prüft. Bei
   fälligem Trigger: Signal-Skript laufen lassen → **menschenlesbares
   Order-Ticket** generieren (Instrument, Richtung, Size nach deiner
   Risk-Regel, Stop, Begründung + Backtest-Erwartung) → per `notify.py` an dich.
2. **„Was soll ich diese Woche traden?"** — du fragst Claude Code, eine Routine
   konsolidiert alle fälligen Signale zu einem Wochenplan. Claude eignet sich
   dafür besser als ein starres Skript, weil es Sonderfälle erklärt
   (Überlappungen, ausgefallene Beine, Daten-Lücken) und das Ticket in Prosa
   kommentiert.
3. **Post-Trade-Logger** — nach jedem Fill trägst du Einstand/Size ein;
   `ledger.py` vergleicht gegen die Backtest-Expectancy und führt das
   **Live-Forward-Protokoll** automatisch (das du für Platin/Mais/Crypto eh
   registriert hast). Claude erstellt monatlich einen kurzen Live-vs-Backtest-
   Report.

### Automatisierungsgrad (bewusst gewählt)
- **Automatisiert:** Kalender-Check, Signalerzeugung, Alert, Logging,
  Live-Forward-Tracking.
- **Human-in-the-loop:** die eigentliche Orderplatzierung. Bei echtem Geld ist
  Bestätigung-vor-Ausführung solides Engineering. Optional später: IBKR-API mit
  **verpflichtender Bestätigung** (kein Blind-Auto-Trade).
- **Tools, alle gratis:** Python, GitHub Actions (cron), Telegram-Bot oder
  SMTP-E-Mail, deine bestehenden Signal-Skripte. Claude Code als Orchestrator
  und Wartung.

---

## Teil 4 — Priorisierte Reihenfolge

| Prio | Was | Warum |
|------|-----|-------|
| **1** | **Live-System bauen** (Teil 3) | Du hast handelbare Edges + Leads — sie zuverlässig live zu führen ist mehr wert als die 63. Strategie. |
| **2** | **Calendar Spreads** (Idee A) | Veredelt bewiesene Saison-Forschung, löst Beta+Roll, Fonds-belegt, Databento-baubar. |
| **3** | **Trend-Following** (Idee B) | Echter, unkorrelierter Diversifikator — die fehlende zweite Edge-Familie. |
| **4** | **Crypto-Live-Forward beobachten** | Läuft schon; nicht anfassen, nur tracken. |
| **5** | Meta-Labeling-Overlay (Idee E) / PEAD (Idee D) | Nachrangig; PEAD erst bei freier Datenquelle. |

*Reihenfolge wie immer: erst der Beweis, dann Kapital — und diesmal zuerst die
Infrastruktur, die deine bewiesenen Edges zuverlässig an den Markt bringt.*
