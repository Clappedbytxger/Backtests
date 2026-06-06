# Strategie 0041 — ES↔NQ Lead-Lag / Relative-Value-Reversion (1-Minute)

- **Kategorie:** relational / market-neutral / intraday
- **Status:** abgelehnt (unwirtschaftlich)
- **Datum:** 2026-06-07
- **Universum:** S&P 500 e-mini (ES) + Nasdaq-100 e-mini (NQ), 1-Minute;
  Zielinstrumente MES/MNQ.
- **Stichprobe:** 2010-06-07 .. 2026-06-05, **1.548.962 ausgerichtete RTH-Minuten**.

Letzte Hypothese der Framework-Liste (#5): Verwandte Instrumente bewegen sich
nicht perfekt synchron; temporäre Dislokationen mean-reverten. Marktneutral →
geringeres Tail-Risiko, die vom Framework favorisierte verbleibende Klasse.

## 1. Hypothese

(A) **Lead-Lag-Momentum:** Führt ES den NQ (oder umgekehrt) von Minute zu Minute?
(B) **Relative-Value-Reversion:** Der beta-gehedgte Spread (long ein Bein, short
das andere) weicht ab und konvergiert → Extreme faden.

## 2. Makro-Begründung

ES und NQ teilen denselben Makro-Treiber (US-Aktien-Beta), bewegen sich aber durch
Sektor-/Flow-Unterschiede nicht im Gleichschritt. Temporäre Dislokationen sollten
durch Index-Arbitrageure zurückgezogen werden. Plausibel — und der Effekt
existiert auch, nur nicht in handelbarer Größe.

## 3. Regeln (Look-Ahead-Schutz)

- 1-Minuten-Returns ES/NQ, RTH 09:30–16:00 ET, Tagesgrenzen genullt.
- Hedge-Beta β aus Regression NQ-Return auf ES-Return (durch Ursprung) = **1,078**.
- Spread-Return `s_t = NQr − β·ESr` (marktneutral). Kumulativer Spread/Tag,
  rollender 30-min-z-Score. Signal bei Minute t aus z_t; Forward-Spread über H
  Minuten ist strikt danach → look-ahead-sicher.
- Daten: Databento GLBX.MDP3 (`ES.c.0`, `NQ.c.0` 1m), `quantlab.futures_intraday`.

## 4. Kosten

Zwei Beine: jedes ~1,5 bps/Seite → Pairs-Round-Trip ≈ **6 bps** (2 Beine × 2 Seiten).
Das ist der Knackpunkt.

## 5. Ergebnisse

**(A) Lead-Lag — leer.** Contemporane corr(ES, NQ) = **0,90**. Aber:

| Lag k | corr(ES[t], NQ[t+k]) | corr(NQ[t], ES[t+k]) |
| ---: | ---: | ---: |
| 1 | +0,0014 | −0,0014 |
| 2 | −0,0044 | −0,0070 |
| 3 | −0,0038 | −0,0060 |

→ keiner führt den anderen. Auf den zwei liquidesten Index-Futures ist der
Lead-Lag vollständig HFT-wegarbitriert. Keine handelbare Momentum-Kante.

**(B) RV-Reversion — ein ECHTES Signal, aber winzig.** Spread-1-min-Autokorr =
**−0,107** (Reversion). z-Score-Fade (short Spread bei z>k, long bei z<−k):

| k | H | n | Brutto/Trade | Win% | Netto (6 bps) |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,5 | 5m | 401.745 | +0,29 bps | 54,8 | −5,71 bps |
| 2,0 | 5m | 151.616 | +0,40 bps | 56,3 | −5,60 bps |
| 2,5 | 5m | 40.002 | +0,52 bps | **57,8** | −5,48 bps |

Die Win-Rate steigt **monoton** mit der z-Schwelle (je extremer die Abweichung,
desto verlässlicher die Konvergenz) — das ist die Signatur eines *echten* Edges,
nicht von Rauschen. **Es ist das einzige genuine Signal im ganzen Intraday-Programm
(0012–0015 / 0038–0041).** Aber die Magnitude ist 0,3–0,5 bps/Trade.

## 6. Der entscheidende Punkt: echtes Signal, von Kosten begraben

Break-even bräuchte einen Round-Trip von **≤ 0,52 bps** = 0,13 bps/Seite/Bein —
also praktisch Maker-Rebate-/Co-Location-HFT-Niveau. Ein Retail-Prop-Konto zahlt
~6 bps. Die Reversion lebt im Sub-Basispunkt-Mikrostruktur-Bereich, den nur
Market-Maker mit Rebates ernten können (rechter Plot: grüne Brutto-Linie weit
unter der roten 6-bps-Kostenlinie, während die Win-Rate auf 58% klettert).

## 7. Verdict

**Abgelehnt — unwirtschaftlich, nicht insignifikant.** Das ist die reinste Form
der Framework-Lektion #1 (Teil 7): ein reales, robustes, hoch-trefferquotiges
Intraday-Signal, das die Kosten untragbar machen. Lead-Lag ist leer, RV-Reversion
ist echt aber 10× zu klein für die Retail-Kostenstruktur.

**Damit ist die Intraday-Liste des Frameworks vollständig abgearbeitet** (#1
Opening-Range 0039, #3 Time-of-Day 0040, #5 Lead-Lag/RV 0041; #2 Gap 0038; #4
Continuation in 0039 mitgetestet). **Übergreifendes Fazit:** Auf liquiden
Index-Futures ist *jede* getestete Intraday-Kante entweder leer (Richtung) oder
real-aber-sub-Kosten (RV) — die Retail-/Prop-Kostenstruktur kann Intraday-Index-
Alpha nicht zugreifen. Der bestätigte Pfad für dieses Konto bleibt die
**niederfrequente Saison-Schiene** (Platin 0021 confirmed etc.), wo wenige Trades/
Jahr die Kosten zu einer vernachlässigbaren Größe machen — das exakte Gegenteil
des Intraday-Regimes.

## 8. Ausblick — die einzige ehrliche Rettung: Maker-Limit-Fills

Der ganze Intraday-Reject hängt an **einer** Annahme: wir überqueren den Spread
als **Taker** (Market-Order) und zahlen ihn auf beiden Beinen, beide Seiten ≈ 6 bps
Round-Trip. Das ist der Killer — nicht das Signal. Die RV-Reversion (§5B) ist real;
sie braucht nur eine Kostenstruktur unter ~0,5 bps RT. Genau das liefert **Maker-
Execution** (Limit-Order statt Market-Order):

**Mechanismus.** Ein Taker *zahlt* den Half-Spread pro Seite; ein Maker (Limit am
besten Bid/Ask) *verdient* ihn — er stellt Liquidität bereit und wird am besseren
Kurs gefüllt. MES/MNQ-Tick = 0,25 Punkt ≈ 0,5 bps Spread; der Vorzeichenwechsel
(zahlen → verdienen) ist die ganze 6-bps-Lücke. **Besonders günstig hier:** Die
RV-Reversion *will* genau dann kaufen, wenn der Spread zu ihr fällt (der z-Score
ist extrem, weil der Preis sich gegen die Position bewegt hat) — das passive
Limit wird also **im Moment der Dislokation gefüllt, die die Strategie ohnehin
faden will**. Maker-Logik und Reversions-Logik sind hier ausnahmsweise *aligned*.

**Die drei Risiken, die das vor einem „Edge-Stempel" beweisen muss** (sonst
Selbstbetrug — der Maker-Vorteil ist nicht gratis):
1. **Non-Execution / Fill-Wahrscheinlichkeit.** Ein Limit füllt nur, wenn der
   Markt zu ihm kommt. Die profitabelsten Reversionen (Preis dreht sofort) füllen
   evtl. *nicht* → der realisierte Edge ist kleiner als der papierne.
2. **Adverse Selection.** Limits werden bevorzugt gefüllt, wenn der Preis
   *durchläuft* (man wird „aufgesammelt", bevor es weiter gegen einen geht). Das
   beißt die linke Tail der Reversion an.
3. **Legging-Risiko.** Ein marktneutraler Pairs-Trade mit Maker auf *beiden*
   Beinen füllt selten gleichzeitig → ein Bein offen = nacktes Richtungsrisiko.
   Realistisch: ein Bein passiv (make), das andere aktiv (take), oder Entry make /
   Exit take — was den Kostenvorteil halbiert.

**Testbarer Plan (vorab registriert).** Databento `GLBX.MDP3` liefert genau die
nötigen Daten: `tbbo` (Trades + Top-of-Book Bid/Ask zum Trade-Zeitpunkt) bzw.
`mbp-1`/`mbp-10` (Orderbuch-Tiefe). Damit lässt sich ein **konservativer Maker-
Fill-Simulator** bauen: Limit am Bid/Ask platzieren, als gefüllt zählen **nur**,
wenn ein Trade die Limit-Seite *durchhandelt* (pessimistische Queue-Annahme:
hinten in der Queue), Entry passiv / Exit aktiv. Dann die RV-Reversion (z>2, β-
gehedgt) erneut netto bewerten. **Erfolgskriterium:** Übersteht der Edge die
*konservative* Fill-Regel mit Netto > 0 und sauberem IS/OOS, ist es die erste
intraday-prop-taugliche Kante; verfehlt er sie, ist Intraday-Index endgültig
geschlossen. Kosten: `tbbo` für ein paar Symbol-Monate liegt im niedrigen
einstelligen Dollar-Bereich des verbleibenden Databento-Freikredits.

**Demut vorab:** Dieser Pfad ist anspruchsvoll (Mikrostruktur, Fill-Modellierung)
und der wahrscheinlichste Ausgang ist, dass Adverse Selection + Non-Execution den
0,3–0,5-bps-Brutto-Edge genau auffressen — Market-Maker verdienen ihn, weil sie
Queue-Priorität und Rebates haben, die ein Prop-Retail-Konto nicht hat. Aber es
ist die *einzige* wissenschaftlich ehrliche Möglichkeit, das eine echte Intraday-
Signal des Programms zu retten, statt es nur an der Taker-Kostenannahme zu beerdigen.
