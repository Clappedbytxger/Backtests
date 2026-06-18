# 0107 — Marubozu-Kerzen-Studie (Robins Idee; reine Edge-Forschung, NICHT CTI)

**Datum:** 2026-06-18 · **Status:** exploratorisch (nicht für das CTI-Buch)

Robins Hypothese: eine **große rote wick-lose Kerze** (Low≈Close, High≈Open), deren Body deutlich
größer als die letzten Kerzen ist, signalisiert **Fortsetzung → short**. Varianten: eine vs. zwei
solcher Kerzen; Exits inkl. 1:1 RR; intraday + daily; mehrere Märkte. Getestet wurde SHORT
(die Hypothese = rote Fortsetzung), LONG (grüne Marubozu-Fortsetzung) UND die Inverse (rote → FADE/
Long-Bounce), brutto-zuerst dann netto.

**Definition:** rot = Close<Open; Body=Open−Close; body/range ≥ 0,92 (fast keine Wicks); Body >
1,5× SMA(|Open−Close|,10) (deutlich größer als zuletzt). Entry nächste Bar-Open, R=Signal-Body,
1:1 (Stop=Entry+R, Ziel=Entry−R für Short), Auflösung über Folge-Bar-High/Low (Stop zuerst bei
Doppeltreffer), Time-Cap 20 Bars.

## Kern-Ergebnis: die Hypothese ist **asset-abhängig — und für Aktien FALSCH**

| Markt | rote→SHORT (Hypothese) | rote→FADE/Long (Inverse) | Verdikt |
|-------|------------------------|--------------------------|---------|
| QQQ daily | Win **36,5%** (verliert) | Win **63,5%**, netto **+0,28R** | **Bounce — Hypothese invers** |
| SPY daily | 43,1% | 53,4%, +0,07R | Bounce |
| GLD daily | 46,9% | 53,1%, +0,06R | Bounce |
| EURUSD daily | 37,5% (n=16) | 62,5%, +0,23R | Bounce |
| **BTC daily** | **57,4%, netto +0,15R** | 40,4% (verliert) | **Momentum — Hypothese richtig** |
| ES=F daily | 55,6% (n=27), +0,13R | 44,4% | (schwach) Momentum |
| ES/NQ 15m·1h | ~46–52% | ~46–52%, **netto NEGATIV** | Kostenwand |

**Synthese (ehrlich):**
1. **Auf Aktien & FX ist Robins „rot→short" die VERLIERER-Seite** — eine große rote wick-lose
   Kerze ist dort **kurzfristige Kapitulation, die zurück-bounct** (mean-reversion). Das **FADEN
   (long) gewinnt** (QQQ 63,5% Win, +0,28R netto auf Daily). Das ist die klassische Aktien-
   Asymmetrie („Treppe hoch, Aufzug runter — dann Bounce").
2. **Nur auf BTC funktioniert die Fortsetzungs-These** (rot→short 57%, netto +0,15R) — große rote
   Kerzen LAUFEN WEITER (Krypto-Momentum). Das ist aber kein Kerzen-Form-Edge, sondern der bereits
   bekannte Krypto-Trend (I0080/0069); das Faden verliert dort spiegelbildlich (40%).
3. **Intraday (15m/1h) ist netto kostentot** in beide Richtungen (3-bps-Wand × kleines R aus den
   kleinen Intraday-Bodies), selbst wo brutto ~52% — exakt die mehrfach bestätigte Kostenwand
   (0012-0015/0038-0041/0049). Daily überlebt netto, wo der Brutto-Edge real ist.
4. **Grüne Marubozu → long (Fortsetzung up) ist STÄRKER als rot → short** (SPY 55%, GLD 53%, BTC
   65%, EURUSD 69%) — bestätigt die Asymmetrie: Aufwärts-Marubozu kontinuieren, Abwärts-Marubozu bouncen.
5. **Zwei-Kerzen-Variante:** zu wenige Vorkommen (n=5–11) für eine belastbare Aussage (einzelne
   100%-Win-Zellen sind Rauschen) — nicht überinterpretieren.

## Lehre
Eine **Kerzen-FORM ist kein universelles Signal** — ihr Vorzeichen kippt mit dem Momentum-/
Reversions-Charakter des Assets: Aktien/FX bouncen nach dem roten Marubozu (faden = +EV), Krypto
kontinuiert (Hypothese korrekt). Robins konkrete „rot→short"-Form ist genau die **Verlierer-Seite
auf Aktien**; die handelbare (aber schwache, ~+0,07–0,28R/Trade daily) Version ist das **Faden auf
Aktien/FX-Daily** oder die **Fortsetzung auf BTC**. Beide sind dünn (n=30–80/Markt), nicht
standalone, und intraday netto tot. 1:1-RR ist sinnvoll; bindend ist die Win-Rate, nicht das RRR.

Daten frei (yfinance daily + gecachte Databento-Intraday ES/NQ), kein Neukauf. `results/marubozu_results.json`.
