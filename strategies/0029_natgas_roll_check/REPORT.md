# Strategie 0029 — Erdgas Herbstfenster: Roll-Artefakt-Check

- **Kategorie:** seasonal (Diagnose)
- **Status:** **Roll-Artefakt BESTÄTIGT — 0028 zurückgestuft auf *suspect/abgelehnt* (auf verfügbaren Daten)**
- **Datum:** 2026-06-05
- **Universum:** `NG=F` (NYMEX-Erdgas, kontinuierlicher Front-Monat, yfinance), 2000–2026, 26 Herbste.

## 1. Auftrag & Verdacht

0028 fand ein stark signifikantes (Perm p=0,001), makro-begründetes Herbstfenster
21.9.–1.11. Offenes Risiko (schlimmer als bei Platin 0019): NG-Futures rollen
**monatlich** (Kontrakt-Ende ~3 Geschäftstage vor dem 1. des Liefermonats), also liegen
**zwei** Front-Month-Rolls im Fenster — Oktober-Kontrakt läuft ~Ende September aus,
November-Kontrakt ~Ende Oktober. Auf dem Weg in den Winter ist die Kurve in **Contango**
(Winterkontrakte teurer) → ein naiver Stitch in der Continuous-Reihe druckt am Roll-Tag eine
*künstliche positive* Rendite, genau an den Tagen, die ein Long-Herbstfenster aufblähen würden.

## 2. Methode (drei Belege, da früherer Exit hier nicht hilft)

Anders als bei Platin (Roll am Fensterende → früherer Exit umgeht ihn) liegen die NG-Rolls
*mitten* im Fenster. Daher **Roll-Tag-Ausschluss** statt früherem Exit:

1. **Konsistenz-Diskriminator** (den 0019 nicht hatte): mechanischer Stitch = *konsistent*
   (Roll-Tag-Trefferquote ≫ 50 %, kleine Streuung); Fat-Tail = wenige große Jahre
   (Trefferquote ~50 %, hohe Streuung).
2. **Zerlegung je Herbst** in Roll- vs. Nicht-Roll-Beitrag; Anteil des mittleren Trade-Gewinns
   auf Roll-Tagen.
3. **Ausschluss-Test:** Strategie an Roll-Tagen flat schalten, Signifikanz neu messen — eng
   (±1 Tag um Expiry) und weit (späte Monatshälfte).

## 3. Ergebnisse

### Konsistenz (Tagesebene, Basis-Fenster)

| Tagesklasse | Ø Rendite | Trefferquote | Std |
| --- | ---: | ---: | ---: |
| Roll-Zonen-Tage (24.–30.9. / 24.–31.10.) | **+1,50 %** | **54 %** | 5,78 % |
| Nicht-Roll-Tage | −0,06 % | 48 % | 3,38 % |

→ Die Roll-Tage tragen praktisch die **gesamte** Tagesrendite, aber mit nur **54 % Trefferquote**
und ~2× Streuung. Das ist *kein* sauberer mechanischer Contango-Stitch (der hätte Trefferquote
70–90 % bei kleiner Streuung) — eher **expiry-geclusterte Fat-Tail-Moves**. Die Preis-Levels
bestätigen das: 2018/2022 laufen glatt durch den Roll, nur Krisenjahre (2021) springen.

### Roll-Tag-Ausschluss (netto nach Kosten)

| Variante | Gehaltene Tage | Exp/Trade | Win | Sharpe | Perm p | IS-Exp | OOS-Exp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Basis (alle Tage)** | 777 | **+15,53 %** | 62 % | 0,53 | **0,002** | +18,39 % | +12,68 % |
| eng ±1 (26.–28.9. / 27.–29.10.) | 667 | **−0,27 %** | 47 % | — | **0,773** | — | — |
| Expiry 2 T (26.–27.9. / 27.–28.10.) | 702 | +2,01 % | 46 % | — | 0,192 | — | — |
| weit (24.–30.9. / 24.–31.10.) | 499 | **+0,15 %** | 48 % | −0,09 | **0,614** | +0,14 % | +0,16 % |

**Anteil des mittleren Trade-Gewinns, der auf Roll-Tagen liegt: 105 %** (die Nicht-Roll-Tage
sind in Summe leicht negativ).

## 4. Verdikt

**Der gesamte 0028-Edge sitzt auf ~6 Kalendertagen pro Jahr, die exakt mit den beiden
NG-Front-Month-Expiry-Terminen zusammenfallen.** Entfernt man nur diese ~6 Tage (enge ±1-Zone),
kollabiert die Expectancy von +15,5 % auf −0,27 %, die Trefferquote von 62 % auf 47 % und der
Permutationstest von p=0,002 auf p=0,773 — also von hochsignifikant auf reinen Zufall. Das
**Gegenteil von Platin 0019**, wo ~58 % des Edges im Dezember *vor* dem Roll akkumulierten und
der Edge einen Pre-Roll-Exit überlebte. Hier liegt 100 % *auf* dem Roll.

**Was 0028 in Wahrheit war:** Die headline-Statistiken (p=0,001, Bootstrap-KI ohne Null, Median
+5,7 %, IS≈OOS) waren alle echt — aber **alle vom selben, sich jährlich wiederholenden
Expiry-Cluster getrieben**. Genau weil das Artefakt jahrübergreifend konsistent ist, bestand es
jeden Standardtest. Erst der Roll-Check trennt „robuster Saison-Edge" von „Expiry-geclustertes
Continuous-Reihen-Artefakt".

**Warum nicht handelbar:** Ob die Expiry-Moves *echt* (Settlement-/Lagerbericht-/Saisonende-Repricing)
oder *Stitch-Kunstprodukt* sind, lässt sich auf der yfinance-Continuous-Reihe **nicht** entscheiden —
und beides taugt nicht: ein realer Trader, der einen Einzelkontrakt hält und rollt, fängt die
Continuous-Sprünge nicht 1:1 ein, und selbst wenn echt, ist es bei 54 % Trefferquote eine
Fat-Tail-Wette auf ~6 Tage, kein glatter Speicherzyklus-Edge wie die Makro-Story behauptete.

## 5. Konsequenz

- **0028 zurückgestuft:** „stärkster Lead" → **suspect/abgelehnt** auf verfügbaren Daten.
- **Nicht ins Saison-Overlay (0020) aufnehmen** — wäre die Aufnahme eines Artefakts.
- **Rettbar nur mit Kontrakt-Daten:** Einzelkontrakt-Reihen (Barchart/Norgate/Stevens) + die
  jeweils zweite Kontrakt-Notierung, um den echten Inter-Kontrakt-Gap zu rechnen und zu prüfen,
  ob an den Expiry-Tagen ein *handelbarer* Spot-Move existiert. Bis dahin kein Kapital.
- **Methoden-Lehre:** Bei monatlich rollenden Futures (NG, CL, RB, HO) ist die Roll-Frequenz so
  hoch, dass *jedes* mehrwöchige Continuous-Fenster Expiry-Tage enthält — Permutation/Bootstrap
  allein genügen NICHT; der Roll-Tag-Ausschluss muss Pflichtschritt sein, bevor ein Continuous-
  Futures-Saisonfenster überhaupt als Lead gilt.

## Artefakte

- `results/metrics.json` — Konsistenz, Zerlegung, Basis-vs-ausgeschlossen
- `results/decomposition_by_year.csv`, `results/per_calendar_day.csv`
- `results/plots/avg_seasonal_path.png`, `per_calendar_day.png`, `roll_decomposition.png`
