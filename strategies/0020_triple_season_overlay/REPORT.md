# Strategie 0020 — Triple-Saison-Overlay (Benzin + Mastrind + Platin) auf Aktien

- **Kategorie:** seasonal (Portfolio-Bündelung, kein neuer Edge)
- **Status:** Kandidat (erbt Forward-Status von 0006/0009; Platin-Bein nur teil-validiert)
- **Datum:** 2026-06-04
- **Universum:** Aktien-Kern S&P 500 (`^GSPC`) bzw. DAX (`^GDAXI`), plus drei
  Future-Beine: Benzin (`RB=F`), Mastrind (`GF=F`), Platin (`PL=F`).
- **Stichprobe:** 2001-04 – 2026-06 (gemeinsamer Datenbereich aller vier Serien).
  Forward-Fenster ab 2016 (siehe Vorbehalt unten).

## 1. Idee

Erweiterung von **0010**. Dort lag ein Aktien-Kern (S&P/DAX) ganzjährig im Index und
stieg nur für zwei kurze, vorab fixierte Saison-Fenster in einen Future um:
- **ISO-Woche 9** (~Anfang März): Benzin (`RB=F`) — 0006, forward-validiert.
- **ISO-Woche 21** (~Ende Mai): Mastrind (`GF=F`) — 0009, forward-validiert.

0018/0019 lieferten ein **drittes** makro-begründetes Saison-Bein: **Platin** über den
Jahreswechsel. 0019 schloss das Mitte-Januar-Roll-Artefakt aus und empfahl die
roll-sichere Verfeinerung **Einstieg 18.12., Ausstieg 10.1.** (knapp vor der Roll-Zone).
Dieses Fenster überlappt die beiden Frühjahrs-Fenster nicht → ein drittes Overlay auf
demselben Kern.

**Regel, ganzjährig:** Index halten; in jedem der drei Fenster in den jeweiligen Future
umsteigen, danach zurück in den Index.

## 2. Look-Ahead & Kosten

- Entscheidungszeit-Signale; gehaltene Position um **einen Bar verzögert** (`shift(1)`,
  T+1-Ausführung). Datums-/Wochen-basiert, keine Zukunftsdaten.
- **Futures-Guard** (CLAUDE-Lehre 0005): Abbruch bei nicht-positivem Schlusskurs.
- **Umschaltkosten** je Ein- und Ausstiegstag: eine Future-Seite (`IBKR_FUTURES`) +
  eine Index-Seite (`IBKR_LIQUID_ETF`) pro Index↔Future-Swap. Alle Zahlen **netto**.

## 3. Ergebnisse (netto nach Kosten)

### S&P 500

| Periode  | Variante  |   CAGR | Sharpe | Sortino |  MaxDD |
| -------- | --------- | -----: | -----: | ------: | -----: |
| Gesamt   | Overlay   | 29,31% |   1,11 |    1,59 | −39,3% |
| Gesamt   | Buy & Hold |  9,04% |   0,45 |    0,56 | −49,7% |
| **Forward ≥2016** | **Overlay** | **39,97%** | **1,38** | 1,98 | −34,1% |
| Forward ≥2016 | Buy & Hold | 13,47% | 0,68 | 0,83 | −33,9% |

### DAX

| Periode  | Variante  |   CAGR | Sharpe | Sortino |  MaxDD |
| -------- | --------- | -----: | -----: | ------: | -----: |
| Gesamt   | Overlay   | 27,53% |   0,97 |    1,43 | −60,3% |
| Gesamt   | Buy & Hold |  7,08% |   0,33 |    0,43 | −64,9% |
| **Forward ≥2016** | **Overlay** | **35,91%** | **1,26** | 2,00 | −35,7% |
| Forward ≥2016 | Buy & Hold |  8,56% |   0,43 |    0,54 | −38,8% |

### Bein-Statistik (gleiche Daten)

| Bein     | Trades | Win | Expectancy/Trade |
| -------- | -----: | --: | ---------------: |
| Benzin   |     22 | 95% |          +11,19% |
| Mastrind |     22 | 91% |   +4,12% (S&P) / +4,33% (DAX) |
| Platin   |     25 | 88% |           +4,54% |

## 4. Marginaler Beitrag des Platin-Beins (vs. 0010)

| Forward ≥2016 | 0010 (2 Beine) | 0020 (3 Beine) | Δ Platin |
| ------------- | -------------: | -------------: | -------: |
| S&P CAGR      |         36,2%  |         40,0%  |  +3,8 pp |
| S&P Sharpe    |          1,36  |          1,38  |  +0,02   |
| DAX CAGR      |         31,5%  |         35,9%  |  +4,4 pp |
| DAX Sharpe    |          1,18  |          1,26  |  +0,08   |

Das Platin-Bein hebt CAGR (~+4 pp) **und** Sharpe leicht und verbessert deutlich die
Sortino-Ratio (Aufwärts-lastige Verteilung). Es füllt zudem eine bisher leere
Jahreszeit (Jahreswechsel) — kein Kalender-Konflikt mit den Frühjahrs-Beinen.

## 5. Verdict

**Bündelung bestätigt — kein neuer Edge, aber kapitaleffiziente Hebelung dreier
Saison-Effekte.** Wie 0007/0010 erzeugt 0020 keine neue Alpha-Quelle; die Signifikanz
lebt in den Einzelstrategien (Benzin p≈0, Mastrind p≈0, Platin p=0,001/Verfeinerung
p=0,003). Der Mehrwert ist Portfolio-Konstruktion: drei nicht-überlappende Fenster
heben Index-B&H von Sharpe 0,68 auf 1,38 (S&P, Forward) bei 100% Index-Zeit den Rest
des Jahres.

**Ehrliche Vorbehalte (wichtig):**
1. **Platin-Bein ist KEIN vorab fixierter Forward-Test.** Anders als Benzin/Mastrind
   (in-sample entdeckt in 0005/0008, dann 2016+ forward getestet in 0006/0009) wurde
   Platin auf der **vollen Historie** geminte (Seasonax). Für Platin ist 2016+ **kein
   sauberes Out-of-Sample** — es liegt innerhalb der eigenen Stichprobe. Der echte
   Forward-Test des Platin-Beins steht noch aus.
2. **Mastrind-Fragilität geerbt** (Bootstrap-KI berührt Null, nur 11 Discovery-Trades).
3. **Notional-Annahme:** jeder Swap bewegt 100% des Kapitals zwischen Index und Future
   („entweder/oder"). Real sitzen Futures auf Margin → ein echtes Buch könnte Index +
   Margin parallel halten. Die Zahlen sind insofern **konservativ** modelliert.
4. **MaxDD bleibt hoch** (−34% Forward) — das Overlay reduziert das Marktrisiko nicht,
   es addiert Saison-Rendite obendrauf.

**Nächster Schritt:** Sauberer, vorab fixierter Forward-Test **nur des Platin-Beins**
(Einstieg 18.12., Exit 10.1.) — analog 0006/0009, eine Regel, keine weitere Suche —
um Platin von „Lead" zu echtem dritten Kandidaten zu heben. Erst danach ist 0020 ein
voll forward-bestätigtes Triple.
