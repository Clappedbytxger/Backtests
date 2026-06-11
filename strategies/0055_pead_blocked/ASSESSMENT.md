# Strategie 0055 — PEAD (Post-Earnings Announcement Drift): DATEN-BLOCKER

- **Kategorie:** event / equities / behavioral
- **Status:** nicht getestet — Daten-Blocker (frei nicht rigoros testbar)
- **Datum:** 2026-06-10
- **Paper-Edge:** #8 der Liste (PEAD, Ball/Brown 1968 ff.).

## Hypothese (zur Vollständigkeit)

Aktien driften nach einem Earnings-**Surprise** über Wochen in dessen Richtung
(positive Surprise → weiterer Anstieg). Behavioral: systematische Under-Reaction.

## Warum hier nicht rigoros testbar

PEAD braucht zwei Dinge, die frei nicht in ausreichender Tiefe/Breite vorliegen:

1. **Historische Earnings-Surprises** (Analysten-Konsens-Schätzung vs. tatsächlicher
   EPS) — der Surprise IST das Signal. Saubere Vintages dafür liefern nur kostenpflichtige
   Quellen (I/B/E/S, Zacks, Refinitiv). yfinance `get_earnings_dates` gibt nur **~1-2 Jahre**
   Historie pro Ticker (und brauchte hier zusätzlich `lxml`), zu kurz und zu schmal.
2. **Survivorship-freies Aktien-Universum** über Jahrzehnte — ein Single-Ticker- oder
   nur-heutige-Large-Caps-Test wäre survivorship-verzerrt und unterpowert.

Ein Test auf den letzten ~1-2 Jahren einer Handvoll aktueller Mega-Caps wäre kein
valider PEAD-Test (Survivorship + Mini-Sample + nur ein Regime) — daher **bewusst nicht
gebaut**, statt ein irreführendes Ergebnis zu fabrizieren (Disziplin wie beim IC-Gate).

## Zusätzlich: passt ohnehin nicht zum Konto-Profil

PEAD ist ein **Einzelaktien-/Multi-Wochen-Effekt** über ein breites Cross-Section —
das ist ein IBKR-Aktien-Cross-Sectional-Programm, kein prop-/intraday-/index-naher
Trade. Selbst mit Daten wäre es eine eigene Programm-Schiene (Dutzende Namen, Earnings-
Kalender-Pipeline), kein Single-Instrument-Backtest.

## Empfehlung

**Deferred.** Wieder aufgreifen nur, wenn (a) eine freie/günstige Earnings-Surprise-
Historie erschlossen ist (z. B. Nasdaq Data Link Sharadar SF1/Actions, ~günstig; oder
Financial-Modeling-Prep-API) UND (b) der User ein Einzelaktien-Cross-Sectional-Programm
fahren will. Bis dahin außerhalb des Scopes.
