# Strategie 0017 — Nasdaq, Inc. Sommerfenster (11.6.–1.9.)

- **Kategorie:** seasonal
- **Status:** **abgelehnt** (Timing nicht signifikant, IS/OOS instabil, schlägt B&H nicht)
- **Datum:** 2026-06-04
- **Universum:** Nasdaq, Inc. (NASDAQ: NDAQ, ISIN US6311031081 — der Börsenbetreiber)
- **Stichprobe:** Gesamt 2002–2026 (NDAQ-Notierung ab Juli 2002).
  In-Sample 2002–2014 / Out-of-Sample 2015–2026.

## 1. Hypothese

Nasdaq, Inc. zeigt laut Seasonax-Testversion eine wiederkehrende Stärke von
**11. Juni bis 1. September**: jedes Jahr long in diesem ~58-Handelstage-Fenster,
sonst flat, soll Buy & Hold risikoadjustiert schlagen.

## 2. Makro-Begründung

**Schwach bis kontraproduktiv.** Ein Börsenbetreiber verdient an Handelsvolumen,
Listings und Datenfeeds. Der Sommer ist traditionell die volumen- und
volatilitätsärmste Phase („Summer doldrums") — das spricht eher *gegen* als für
eine sommerliche Outperformance der NDAQ-Aktie. Keine plausible Angebots-/
Nachfrage-Ursache. Nach Hausregel: data-gemint.

## 3. Regeln

- Long (Gewicht 1.0) an allen Handelstagen mit Datum im Intervall
  [11. Juni, 1. September] jedes Jahres; sonst flat. Ein Trade pro Jahr,
  ~58 Handelstage Haltedauer.
- **Look-Ahead-Schutz:** datumsbasiertes Signal, Engine verzögert um einen Bar
  (`shift(1)`). Keine Same-Bar-/Zukunftsinformation.

## 4. Kosten- & Ausführungsannahmen

IBKR-Standardmodell für US-Einzelaktien (`IBKR_DEFAULT`): ~3–4 bps/Seite,
~7 bps Round-Trip. Alle Zahlen **netto**. Ausführung am Folgetag (Close-to-Close).

## 5. Ergebnisse (gesamt 2002–2026, netto nach Kosten)

| Kennzahl                |             Wert |
| ----------------------- | ---------------: |
| CAGR                    |            4,57% |
| Sharpe                  |         **0,23** |
| Sortino                 |             0,34 |
| Calmar                  |             0,11 |
| Max Drawdown            |          −40,34% |
| Trefferquote            |     67% (16/24)  |
| Profit-Faktor           |             2,90 |
| Payoff-Ratio            |             1,45 |
| Expectancy/Trade        |           +5,49% |
| Ø Haltedauer            |     57,3 Tage    |
| Trades                  |              24  |
| Exposure                |           22,8%  |

**Vergleich Buy & Hold:** CAGR **13,74%**, Sharpe **0,48**, MaxDD −68,5%. Anders
als bei 0016 (Charter) schlägt das Fenster B&H hier **weder** bei der Rendite
**noch** beim Sharpe — B&H ist klar überlegen.

### In-Sample vs. Out-of-Sample — **massive Instabilität**

| Periode             | Trades | Win | Expectancy/Trade | Sharpe |
| ------------------- | -----: | --: | ---------------: | -----: |
| In-Sample 2002–2014 |     13 | 54% |           +1,69% |   0,03 |
| OOS 2015–2026       |     11 | 82% |           +9,91% |   0,82 |

Die erste Hälfte ist ein **Münzwurf** (Sharpe 0,03, Win 54%, Expectancy 1,7%) —
der gesamte gute Eindruck stammt allein aus 2015–2026. Die Equity-Kurve zeigt es
unmissverständlich: bis 2014 flach um 1,0, erst danach steigend. Ein Effekt, der
nur in der jüngeren Hälfte existiert, ist typisch für „Fenster hat zufällig den
2015–2021-Bullenmarkt eingefangen", nicht für eine stabile Saison.

## 6. Signifikanz (gesamte Stichprobe)

| Test                              |             Wert |
| --------------------------------- | ---------------: |
| Permutationstest p-Wert           |     **0,307** ✗  |
| Bootstrap Sharpe 95%-KI           |  [−0,16, 0,64] ✗ |
| t-Test mittlere Rendite p         |        0,087 ✗   |
| Deflated Sharpe (n_trials = 121)  |       0,00 (PSR) |

**Alle drei Signifikanztests fallen durch.** Der entscheidende Permutationstest
(p = 0,307) sagt: das Juni–September-Timing ist **nicht von einem zufällig
platzierten gleich langen Fenster zu unterscheiden**. Das Bootstrap-KI schließt
Null ein, der t-Test verfehlt 5%.

## 7. Robustheit

- **Fenster-Verschiebung:** 121/121 Kombinationen positiv — sieht stark aus, **ist
  hier aber wertlos**: Bei einem langfristig steigenden Titel und einem langen
  Fenster (~23% des Jahres) ist *jede* Platzierung im Schnitt positiv, einfach
  durch die Aufwärtsdrift. Da der Permutationstest (p = 0,31) zeigt, dass das
  konkrete Timing nichts schlägt, ist das grüne Feld reine Drift, kein Edge.
  → **Methodenlehre:** Robustheit gegen Fenster-Verschiebung allein beweist nichts,
  wenn das Asset driftet; erst der Permutationstest trennt Timing von Drift.
- **Teilperioden:** stark inkonsistent (§5) — disqualifizierend.

## 8. Verdict

**Abgelehnt.** Im direkten Kontrast zu 0016 (Charter), das den Permutationstest
mit p = 0,004 bestand und über beide Hälften konsistent war, **scheitert Nasdaq an
genau diesem Kontrolltest** (p = 0,31), liegt unter Buy & Hold und hat seine ganze
Performance nur in der zweiten Hälfte. Kein Edge, nur eingefangene Drift eines
guten jüngeren Laufs — bei fehlender Makro-Ursache erwartbar.

**Wertvolle Lehre:** Seasonax markiert mehrere Aktien als „starkes Sommerfenster",
aber das ist überwiegend Aufwärtsdrift + Rückschau-Selektion. Der **Permutationstest
ist der Filter**, der Charter (echtes Timing) von Nasdaq (nur Drift) trennt. Künftige
Seasonax-Leads zuerst gegen die Permutation prüfen, bevor Robustheit/Equity
beeindrucken.
