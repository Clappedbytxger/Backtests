# Strategie 0080 — Getreide-Sommer-Short (Mais/Weizen, Mitte Juni–Mitte Juli)

> Idee **I0044** aus dem Handoff `D:\Backtest Ideas` (Quelle #s16, eigener Seasonax-Lauf).

- **Kategorie:** seasonal (short) / commodities
- **Status:** abgelehnt (überwiegend Roll-Artefakt; generalisiert nicht)
- **Datum:** 2026-06-15
- **Universum:** Mais (ZC=F), Weizen Chicago (ZW=F) & Kansas (KE=F), Soja (ZS=F) Cross-Check
- **Stichprobe:** 2000-2026, Fenster vorab fixiert 14.6.–19.7. (#s16, kein Re-Fit)

## 1. Hypothese & Makro

Getreide-Sommerschwäche: nach der kritischen Pollinationsphase löst sich die
Wetter-/Risikoprämie auf, gute Ernteerwartung + Erntedruck drücken die Preise. Short
der Front 14.6.–19.7. (#s16: Mais −8,3 %/10 % Win). Spiegel der Dezember-Stärke (0030/0032).

## 2. Pflichtchecks (0017/0029)

- **Permutation** gegen Zufalls-Short-Fenster (kontrolliert die Down-Drift der
  Continuous-Reihe via Contango).
- **Roll-Exclusion** (Mais rollt Jul→Sep Ende Juni/Anfang Juli — IM Fenster).

## 3. Ergebnisse

| Markt | Trades | Win | Expectancy/Trade | net Sharpe | Permutation |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Mais (ZC=F)** | 26 | 62 % | **+5,60 %** | +0,25 | **p=0,001** |
| Weizen Chicago (ZW=F) | 26 | 38 % | −2,81 % | −0,44 | p=0,806 |
| Weizen Kansas (KE=F) | 25 | 56 % | −0,68 % | −0,28 | p=0,455 |
| Soja (ZS=F) | 25 | 48 % | +1,06 % | −0,10 | p=0,109 |

(Expectancy/Win sind für die SHORT-Seite: positiv = Short verdient = Preis fiel.)

**Roll-Check Mais (entscheidend):** base perm p=0,001 / Expectancy +5,60 % → nach
Roll-Ausschluss **p=0,024 / Expectancy +0,74 %**; **41 % des Gewinns sitzt auf
Roll-Tagen**. IS/OOS Mais +0,18 / +0,57.

## 4. Verdict

**Abgelehnt — überwiegend Roll-Artefakt, generalisiert nicht (genau das NG-Muster
0028/0029).** Der headline-starke Mais-Short (+5,60 %, p=0,001) verliert nach
Roll-Ausschluss 87 % seiner Expectancy (+0,74 %), 41 % des Gewinns liegt auf den
Jul→Sep-Roll-Tagen — die Continuous-Reihe springt am Roll nach unten (neue Ernte
billiger = normale Carry-Struktur), und der Short bucht diesen Sprung, den ein echter
Roller nie verdient. Der Resteffekt nach Ausschluss ist winzig (perm p=0,024, aber
Trade-Mean-KI berührt 0). **Zusätzlich kein Komplex-Effekt:** nur Mais zeigt überhaupt
etwas; Weizen (Chicago/Kansas) shorts VERLIEREN (p=0,81/0,46), Soja flat (p=0,11). Die
#s16-„10 % Win"-Behauptung wird auf der Front nicht reproduziert (62 % Short-Win).

**Konsequenz:** Die ökonomisch reale Old-Crop/New-Crop-Dynamik gehört in den
**roll-sauberen Kalender-Spread (I0001, Jul/Dez-Mais)** — genau die Handoff-Variante 4.
Der Outright-Short auf der Continuous-Front ist nicht handelbar (Roll-kontaminiert).
Dies verschiebt das Gewicht hin zur Spread-Gruppe I0001/I0002 (benötigt
Einzelkontrakt-Ketten / Databento).
