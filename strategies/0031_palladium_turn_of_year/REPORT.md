# Strategie 0031 — Palladium Jahreswechsel-Fenster (6.12.–25.1.)

- **Kategorie:** seasonal
- **Status:** **testing / echter Lead, bestärkt die PGM-Jahreswechsel-Saison (0018/0021)** — KEIN Roll-Artefakt, aber OOS-Hälfte dünn + korrelierte (nicht unabhängige) Evidenz.
- **Datum:** 2026-06-05
- **Universum:** NYMEX-Palladium-Future (`PA=F`, kontinuierlicher Front-Monat). Sauber: 2000–2026, min 97 distinkte Kurse/Jahr, 0,7 % Null-Returns.
- **Stichprobe:** Gesamt 2000–2026. IS bis 2013-07 / OOS ab 2013-07 (Schnitt 1. Juli, zerschneidet kein Dez→Jan-Fenster).

## 1. Hypothese

Palladium zeigt laut Seasonax-Lead Stärke vom **6. Dez. bis 25. Jan.** (jahresübergreifend,
~35 Handelstage): jeden Jahreswechsel long (sonst flat) soll B&H risikoadjustiert schlagen.

## 2. Makro-Begründung

**PGM-Schwester zu Platin (0018/0021)** — gleicher Jahreswechsel-Treiber: Auto-Katalysator-
**Restocking zum Jahresstart** + Schmuck-/Industrienachfrage in den Vorlauf des **chinesischen
Neujahrs**. **Wichtig (Evidenz-Status):** teilt damit den Treiber mit 0018/0021/0023 → das ist
**korrelierte, nicht unabhängige** Evidenz; Palladium war in 0021 bereits das Cross-Asset-OOS-Bein
(Platin-Fenster 18.12.–10.1. auf PA=F: 93 % Win, p=0,004). 0031 testet nun Palladiums *eigenes*
Seasonax-Fenster.

## 3. Regeln

- Long (1.0) [6. Dez. → 25. Jan.] jeden Winter (wrap-aware), sonst flat. Ein Trade/Winter.
- Look-Ahead-Schutz: datumsbasiert, Engine verzögert um einen Bar. Daten-Guards 0005/0025 bestanden.

## 4. Ergebnisse (gesamt 2000–2026, netto)

| Kennzahl | Wert | IS –2013 | OOS 2013– |
| --- | ---: | ---: | ---: |
| CAGR | 8,70 % | 11,84 % | 5,94 % |
| Sharpe | **0,42** | 0,51 | 0,32 |
| Max Drawdown | −27,8 % | −22,8 % | −27,8 % |
| Trefferquote | 67 % (18/27) | **79 %** | **54 %** |
| Profit-Faktor | 7,06 | 12,85 | 4,31 |
| Expectancy/Trade | +9,02 % | +10,97 % | +6,92 % |
| Median/Trade | +6,31 % | +6,73 % | **+0,29 %** |
| Trades | 27 | 14 | 13 |
| Exposure | 13,4 % | | |

Buy & Hold: CAGR 4,58 %, **Sharpe 0,26** (driftarm → keine Drift-Falle), MaxDD −86,3 %.

## 5. Signifikanz (gesamte Stichprobe — Seasonax-gemined)

- **Permutation p = 0,005** ✓ — Timing schlägt den Zufall klar; driftarmes PGM → doppelt aussagekräftig.
- **Bootstrap-Sharpe-KI [0,08; 0,74]** ✓ — **schließt die Null aus**.
- **t-Test p = 0,009** ✓. **Robustheit 121/121**. DSR/PSR = 0 (Standard-Such-Strafe).
- **Schwäche OOS:** zweite Hälfte deutlich dünner — **Win nur 54 %, Median +0,29 % ≈ Null**;
  die positive OOS-Expectancy (+6,92 %) wird allein vom Mittelwert (wenige große Gewinner) getragen
  = Fat-Tail-Tendenz im OOS. IS war breit (79 % Win, Median +6,73 %).

## 6. Roll-Tag-Check (Pflicht seit 0029) — bestanden, KEIN Artefakt

Palladium-Liefermonate Mär/Jun/Sep/Dez; der Dez-Kontrakt verfällt **Ende Dezember** → ein
Dez→März-Roll fällt **ins Fenster** (gleiche Struktur wie Platin 0019). Der Check ist also scharf:

| Variante | Exp/Trade | Win | Sharpe | Perm p | IS-Exp | OOS-Exp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **Basis (alle Tage)** | +9,02 % | 67 % | 0,42 | 0,005 | +10,97 % | +6,92 % |
| 24.–31. Dez. ausgeschlossen | +3,02 % | 55 % | 0,33 | **0,017** | +2,02 % | +3,97 % |

**Nur 17 % des mittleren Trade-Gewinns liegt auf den Roll-Tagen** (NG: 105 %). Nach Ausschluss
bleibt der Edge **signifikant (p=0,017 < 0,05)**, Sharpe fällt kaum (0,42→0,33), Expectancy
positiv in IS *und* OOS. → Der Edge ist **echte Jahreswechsel-Stärke, kein Roll-Gap** — exakt
wie bei Platin 0019, das Gegenteil von NG 0028.

## 7. Bewertung & nächste Schritte

**Echter Lead, klar über NG, bestärkt die PGM-Jahreswechsel-Saison.** Stärken: p=0,005,
Bootstrap-KI ohne Null, driftarm, roll-sauber, benennbarer Makro-Treiber. Schwächen: (1) **OOS
dünn** (Median ~0, Win 54 %, fat-tail-getragen) → risikoadjustiert fragiler als die Basis suggeriert;
(2) **korrelierte Evidenz** — selber Treiber wie 0018/0021/0023, Palladium schon in 0021 verwendet
→ 0031 ist *Bestärkung* der PGM-Saison, kein unabhängiger neuer Edge.

- **Kein zeitlicher Forward** (Seasonax-gemined; teilt Jahre + Treiber mit 0018/0021) → Live-Forward
  Winter 2026/27 vorab registrieren (gemeinsam mit dem 0021-Platin-Forward).
- **Einordnung Overlay 0020:** Palladium-Bein würde dem bestehenden Platin-Bein (Dez/Jan) stark
  korrelieren → kein echter Diversifikationsgewinn, eher Klumpung der PGM-Jahreswechsel-Wette.
- Rang: ~Platin 0018 auf Basis-Stats, aber OOS-schwächer; als *Bestätigung* der PGM-Saison wertvoll,
  als eigenständiger Edge nachrangig.

## Artefakte

- `results/metrics.json` (inkl. `roll_check`), `results/trades.csv`, `results/equity.csv`
- `results/plots/equity_vs_bh.png`, `per_year_trades.png`, `robustness_heatmap.png`
