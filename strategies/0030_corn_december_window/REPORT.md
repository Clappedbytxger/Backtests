# Strategie 0030 — Mais Dezemberfenster (1.–31.12.)

- **Kategorie:** seasonal
- **Status:** **testing / echter Lead mit Konzentrations-Vorbehalt** (KEIN Roll-Artefakt — anders als NG 0028 — aber ~60 % des Edges in einem ~5-Tage-Cluster Mitte Dez.)
- **Datum:** 2026-06-05
- **Universum:** CBOT-Mais-Future (`ZC=F`, kontinuierlicher Front-Monat, yfinance). Sauber: 2000–2026, min 76 distinkte Kurse/Jahr, 2,8 % Null-Returns.
- **Stichprobe:** Gesamt 2000–2026. IS 2000–2012 / OOS 2013–2026 (Schnitt 1. Jan., zerschneidet kein Dezemberfenster).

## 1. Hypothese

Mais zeigt laut Seasonax-Lead Stärke vom **1. bis 31. Dezember**: jeden Dezember long
(sonst flat) soll B&H risikoadjustiert schlagen. ~21 Handelstage. Vorab via Monatsrendite-
Screen begründet (Dez Ø +5,5 %, 85 % Monats-Trefferquote — höchste im Universum).

## 2. Makro-Begründung

Das **Harvest-Low** (US-Ernte überschwemmt das Angebot Sep/Okt) ist im Dezember durch;
Preise festigen sich ins Jahresende auf Nachfrage, Exporttempo und die **südamerikanische
Wetterprämie** (Brasilien/Argentinien-Sommerkultur startet). **Vorbehalt:** Mais ist *der*
überforschte Ag-Seasonal — ein echter Edge lebt oft nur im **Kalenderspread**, nicht im
Flat-Price-Front-Month. Permutation + Roll-/Konzentrations-Check tragen daher extra Gewicht.

## 3. Regeln

- Long (1.0) an allen Handelstagen [1. Dez., 31. Dez.] jedes Jahres, sonst flat. Ein Trade/Jahr.
- Look-Ahead-Schutz: datumsbasiert, Engine verzögert um einen Bar.
- Daten-Guards 0005 (nicht-positiv) + 0025 (frozen feed) bestanden.

## 4. Ergebnisse (gesamt 2000–2026, netto)

| Kennzahl | Wert | IS 2000–12 | OOS 2013–26 |
| --- | ---: | ---: | ---: |
| CAGR | 5,06 % | 6,80 % | 3,57 % |
| Sharpe | **0,47** | 0,61 | 0,31 |
| Max Drawdown | −11,8 % | −11,8 % | −8,7 % |
| Trefferquote | 77 % (20/26) | 69 % | **85 %** |
| Profit-Faktor | 8,21 | 7,57 | 11,97 |
| Expectancy/Trade | +5,26 % | +6,80 % | +3,78 % |
| Median/Trade | +3,87 % | +5,30 % | +2,97 % |
| Trades | 26 | 13 | 13 |
| Exposure | 8,2 % | | |

Buy & Hold (Front-Month): CAGR 3,51 %, **Sharpe 0,19** (driftarm → keine Drift-Falle), MaxDD −63,7 %.

## 5. Signifikanz (gesamte Stichprobe — Seasonax-gemined)

- **Permutation p = 0,000** ✓ — Timing schlägt den Zufall klar, auf driftarmem Asset doppelt aussagekräftig.
- **Bootstrap-Sharpe-KI [0,10; 0,82]** ✓ — **schließt die Null aus** (wie NG, Palladium 0021, sonst selten).
- **t-Test p = 0,000** ✓. **IS ≈ OOS** beide positiv (Sharpe 0,61/0,31; Win 69 %/**85 %**; Median +5,30/+2,97 %).
- **Robustheit 121/121** Fenster-Verschiebungen positiv. **DSR/PSR = 0** (Standard-Such-Strafe n_trials=121).

## 6. Roll-/Konzentrations-Check (Pflicht seit 0029) — und warum Mais KEIN NG ist

**Kein Roll-Artefakt im Fenster.** Mais-Liefermonate sind Mär/Mai/Jul/Sep/Dez; der
Dez-Kontrakt-First-Notice liegt **Ende November** → die Continuous-Reihe handelt ab dem
1. Dezember bereits den **März**-Kontrakt. Es liegt also **kein Future-Roll im Fenster**
(der einzige Roll, Dez→März, ist Ende Nov, außerhalb). Die **Preis-Levels laufen Mitte
Dezember glatt durch** (kein diskreter Stitch-Sprung wie bei NG) — bestätigt: kein
mechanisches Klebestellen-Artefakt.

**Aber: der Edge ist mittel-Dezember-konzentriert.** Entfernt man die ~5 Tage 11.–16. Dez.
(stärkster Tag **15.12.: +2,36 %**, fällt mit dem **Dezember-WASDE-Bericht** ~9.–12. Dez. +
Rohstoffindex-Roll zusammen):

| Variante | Exp/Trade | Win | Sharpe | Perm p | IS-Exp | OOS-Exp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Basis (alle Tage)** | +5,26 % | 77 % | 0,47 | **0,000** | +6,80 % | +3,78 % |
| 11.–16. Dez. ausgeschlossen | +1,15 % | 61 % | 0,06 | 0,093 | +1,57 % | +0,79 % |

~60 % des mittleren Trade-Gewinns sitzt in diesem Cluster. Der Rest-Edge bleibt **positiv**
(+1,15 %, 61 % Win), verliert aber die Signifikanz (p=0,093). Das ist ein **Konzentrations-
Vorbehalt**, kein Artefakt-Verdikt: anders als NG (105 % auf Expiry-Tagen, p kippt auf 0,77,
nicht handelbar) ist hier (a) kein Stitch, (b) der Treiber real und benennbar (WASDE/Index-Roll),
(c) der Effekt auch außerhalb des Clusters positiv.

## 7. Bewertung & nächste Schritte

**Echter Lead, klar über NG, aber ein Stück unter Platin (0018).** Stärken: p=0,000, Bootstrap-KI
ohne Null, beide Hälften positiv, driftarmes Asset, kein Roll-Artefakt, plausibler Treiber.
Schwächen: Edge zu ~60 % in 5 Tagen Mitte Dez. (WASDE/Index-Roll = bekannt, also evtl.
arbitragiert), Rest-Monat insignifikant; Mais überforscht → evtl. nur im Spread voll real.

- **Kein echtes zeitliches OOS** (Seasonax-gemined) → Live-Forward Dez 2026 vorab registrieren.
- **Verfeinerung prüfen:** ein engeres Fenster um die WASDE-/Roll-Tage (~8.–18. Dez.) könnte den
  Kern isolieren — aber das wäre erneutes Mining, daher nur als separat vorab fixierte Hypothese.
- **Cross-Check** auf Mais-ETF (`CORN`, physisch-nah) bzw. Weizen/Soja (Ag-Geschwister) ohne Re-Fitting.
- Rang: ~Zink 0025 / Charter 0016 — echtes Timing, moderate Fragilität.

## Artefakte

- `results/metrics.json` (inkl. `roll_check`), `results/trades.csv`, `results/equity.csv`
- `results/plots/equity_vs_bh.png`, `per_year_trades.png`, `robustness_heatmap.png`
