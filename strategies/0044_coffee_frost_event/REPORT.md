# Strategie 0044 — Kaffee (KC) Fundamental: Realisierte-Frost-Event-Study (H-KC-01)

- **Kategorie:** fundamental / alt-data / event-study
- **Status:** rejected
- **Datum:** 2026-06-07
- **Universum:** Arabica-Kaffee-Future (KC=F, ICE)
- **Stichprobe:** 2000–2026 (KC-Futures-Historie)
- **Getestete Hypothese:** H-KC-01 (aus `fundamentals/HYPOTHESES.md`)

---

## 1. Hypothese

Ein Frost-/Extremkälte-Ereignis im brasilianischen Arabica-Gürtel (Minas Gerais,
Jun–Aug) schädigt die Pflanzen physisch → Ertragsausfall → Preis steigt. Wir
*sagen den Frost nicht voraus* (Lektion 0027: man kann eine Überraschung nicht
timen), sondern **positionieren nach einem realisierten Kälte-Event** und reiten die
langsame Diffusion über 1–3 Monate.

---

## 2. Abgrenzung zu Strategie 0027 (bereits abgelehnt)

0027 nutzte ein **festes Kalenderfenster** (15.7.–28.8.) jedes Jahr — long sitzen
in einem volatilen Fenster und hoffen, dass ein Schock hineinfällt. **Diese**
Strategie nutzt **echte ERA5-Temperaturdaten**, um realisierte Kälte-Anomalien zu
erkennen, und positioniert *nur nach* einem solchen Event. Das ist die gezielte,
event-konditionierte Version derselben Idee — der bestmögliche Test der Frostprämie.

---

## 3. Koordinaten-Validierung (vor dem Test durchgeführt)

Die ursprünglich in HYPOTHESES.md registrierte Koordinate (−19.5, −43.5) hat einen
**ERA5-Warm-Bias** — die kälteste Nacht im Datensatz ist 2.3 °C, **nie unter 2 °C**,
und der schwere Frost 2021 zeigt dort nur 3.7 °C. Grid-Zellen (~25 km) glätten die
lokalen Tal-Kältesenken weg, in denen Frost entsteht.

Ich habe stattdessen den realen Frostgürtel **Sul de Minas (−21.5, −45.5)** gewählt
(Herz der heutigen Arabica-Produktion). Dort sind die kältesten Jahres-Anomalien:

| Rang | Jahr | z-Score | Realität |
|------|------|--------:|----------|
| 1 | **2021** | −3.00 | schwerer Frost ("schlimmster seit 1994") |
| 2 | **2000** | −2.52 | moderater Kälteeinbruch |
| 3 | 2024 | −2.49 | Kälte (kein großer Schaden bekannt) |

In der Vollhistorie (ab 1990) ranken **1994 (z−2.4), 2021 (z−2.3), 2000 (z−1.8)** als
Top-3 — exakt die bekannten schweren Frostjahre. **Die ERA5-Anomalie trackt hier also
echten Frostschaden** (anders als die registrierte Nord-Koordinate). Konsequenz:
absoluter Temperatur-Threshold mit ERA5 untauglich → **Anomalie-Ansatz** (robust gegen
Warm-Bias).

---

## 4. Regeln (vorab registriert)

- **Feature:** monatliche Kältenacht-Anomalie = z-Score der *kältesten Nacht des
  Monats* (`agg=min`) vs. rollierende 20-Jahres-Klimatologie (shift(1), rein
  vergangenheitsbasiert, PIT-korrekt). Nur Jun/Jul/Aug.
- **Frost-Event:** Anomalie < −2.0 σ.
- **Signal:** Long KC=F ab `release_date` (Monatsende + 1, Kältenacht voll bekannt),
  Haltedauer 66 Handelstage (3M-Diffusion).
- **Look-Ahead-Schutz:** rollierende Klimatologie + Engine-Shift (+1 Tag).
- **Strenge Schwellen (Lektion 0027):** Median-Trade muss positiv sein (kein Fat-Tail);
  bei so wenigen Events p < 0.01 gefordert.

---

## 5. Kosten- & Ausführungsannahmen

`IBKR_SOFTS` (4 bps/Seite = 8 bps Round-Trip). KC=F ~37.500 lbs à ~200 ¢/lb. EOD-Einstieg.

---

## 6. Ergebnisse

### 6a. Kontinuierlicher IC-Screen (alle Jun–Aug-Monate, 78 Obs.)

| Horizont | IC | Perm-p |
|----------|-----:|-------:|
| 5 Tage   | **−0.183** | 0.124 |
| 22 Tage  | **−0.137** | 0.220 |
| 66 Tage  | +0.080 | 0.470 |

Der IC ist bei kurzen Horizonten **negativ** — ein kälterer Wintermonat sagt eher
*fallende* Kaffeepreise voraus. Das bestätigt 0027: Jun–Aug ist vom **Erntedruck**
(bärisch) dominiert; generische Kälte ist kein Frostschaden. Bei 66d dreht der IC leicht
positiv, aber insignifikant (p=0.47). **Kein kontinuierliches Signal.**

### 6b. Event-Study (der eigentliche Test — nach realisiertem Frost positionieren)

| Event | z | 22d | 66d | 132d |
|-------|------:|------:|------:|------:|
| 2000-07 | −2.52 | −13.7% | −14.0% | −27.4% |
| 2011-08 | −2.15 | −22.1% | −19.9% | −36.2% |
| 2020-08 | −2.29 | −17.4% | −12.5% | +0.4% |
| 2021-07 | −3.00 | +11.8% | +21.1% | +44.1% |
| 2024-08 | −2.49 | +2.1% | +28.0% | +58.3% |
| **mean** | | −7.8% | +0.5% | +7.8% |
| **median** | | **−13.7%** | **−12.5%** | +0.4% |
| **win** | | 40% | 40% | 60% |

**Der Median ist bei 22d und 66d klar NEGATIV.** Nur 2 von 5 „Frost"-Events (2021, 2024)
führten zu steigenden Preisen. Die anderen drei (2000, 2011, 2020) waren harmlose
Kältenächte (z < −2σ, aber kein pflanzentötender Frost), bei denen der Erntedruck dominierte
und der Preis um −12 bis −22 % fiel. Der positive Mean bei langen Horizonten kommt **rein aus
2021/2024** = klassische Fat-Tail-Lotterie.

### 6c. Netto-Backtest (long 66d nach jedem Event) — UNTERPOWERT (n=5)

| Kennzahl | Wert |
|----------|-----:|
| Sharpe | −0.23 |
| CAGR | −0.2 % |
| Max Drawdown | −49.6 % |
| Trefferquote | 40 % (2/5) |
| Expectancy/Trade | +1.40 % (mean) |
| **Median/Trade** | **−11.41 %** |
| Trades | 5 |
| Exposure | 5 % |

## 7. Signifikanz

| Test | Wert |
|------|-----:|
| Permutationstest p | 0.560 ✗ |
| Bootstrap Sharpe 95%-KI | [−0.62, 0.14] ✗ |
| t-Test mittlere Rendite p | 0.928 ✗ |
| Deflated Sharpe (PSR) | 0.00 |

Alle Tests klar insignifikant. Bei n=5 Trades ohnehin keine statistische Aussagekraft.

---

## 8. Verdict

**ABGELEHNT** auf zwei unabhängigen Wegen:
1. **Kein kontinuierliches IC-Signal** (IC bei kurzen Horizonten sogar negativ — Erntedruck dominiert).
2. **Event-Median negativ** bei 22d und 66d (−14 % / −12 %) → Fat-Tail-Verbot (Lektion 0027) verletzt.

**Die Pointe — und der wissenschaftliche Mehrwert gegenüber 0027:**
Selbst mit *echten Temperaturdaten* und der *richtigen* Frostgürtel-Koordinate (die nachweislich
1994/2000/2021 erkennt) ist die Frostprämie **nicht handelbar**. Der Grund liegt in der Auflösung
des Signals: eine z < −2σ Kälte-Anomalie im ERA5-Grid ist **nicht** dasselbe wie pflanzentötender
Frost. 3 von 5 Extrem-Kälte-Events waren harmlos — der Markt sah eine kalte, aber nicht
schädigende Nacht, der Erntedruck behielt die Oberhand, und Long-Positionen verloren zweistellig.
Man kann die *schädigenden* Frosts (2021) nicht von den *harmlosen* Kältenächten unterscheiden,
bevor die Schadensschätzungen da sind — und bis dahin hat der Markt den Unterschied längst
eingepreist (HFT-Diffusionswand, vgl. 0041).

Das bestätigt 0027 mit harten Daten und hebt es auf eine fundamentale Ebene: **Die Frostprämie
ist real, aber ein nicht-timebares Fat-Tail — egal ob über Kalenderfenster (0027) oder über
realisierte ERA5-Kälte-Events (0044).** Bezahltes Tail-Risiko, kein Edge.

**Übergreifender Befund (Fundamental-Programm 0042–0044):**
Drei Hypothesen, drei Ablehnungen — Zucker/Wetter (0042), Zucker/Ethanol (0043), Kaffee/Frost (0044).
Muster: Die meistbeobachteten Fundamentaldaten der Soft-Commodities (Wetter, Energie-Parität,
Frost) tragen keinen handelbaren 1–3-Monats-Edge. Sie sind entweder voll eingepreist oder
(beim Frost) ein nicht-timebares Fat-Tail. Framework-These bestätigt: Edge ≠ Datenexklusivität,
und eine starke Makro-Story ersetzt den Test nicht.

**Mögliche nächste Richtungen (jeweils neue Registrierung nötig):**
1. **USDA-Surprise-Hypothesen** (H-SB-03, H-CT-02, H-LE-02) — bislang ungetestet wegen
   API-Geoblock. Aus Heimnetz nachholen. Das ist die *einzige* Klasse, die im Katalog je
   funktioniert hat (Mais-WASDE 0032: 78 % der Edge auf 6 Report-Tagen).
2. **Crop-Condition-Δ** (H-CT-01, NASS wöchentlich, PIT) — höhere Frequenz, echtes
   Surprise-Feature statt breiter Wetter-/Frost-Anomalie.
3. **Frost-Idee aufgeben** — über 0027 + 0044 zweifach widerlegt, nicht weiter verfolgen.

---

## Plots

- `results/plots/frost_events_overview.png` — Kältenacht-Anomalie + KC-Preis mit Event-Haltefenstern
- `results/plots/event_study_returns.png` — Forward-Returns pro Frost-Event (Median negativ)
