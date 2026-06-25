# Strategie 0074 — Weinstein Stage-2-Breakout (Tagesadaption)

- **Kategorie:** momentum / breakout / equities (stage analysis, multi-position portfolio)
- **Status:** abgelehnt als Standalone — **echtes, signifikantes Timing-Skill + starker Drawdown-Schutz, schlägt aber Buy & Hold des gleichen Universums nicht**
- **Datum:** 2026-06-14
- **Universum:** 113 liquide US-Large/Mid-Caps quer über alle Sektoren (Apple, Microsoft, JPMorgan, ExxonMobil, Johnson & Johnson, Caterpillar, Coca-Cola, NVIDIA … volle Liste in `run.py`), Tagescharts; Benchmark-/RS-Referenz S&P 500 (SPY). **Survivorship-verzerrt auf Mitgliedschaft** (yfinance liefert nur heutige Überlebende) — siehe Abschnitt 7.
- **Stichprobe:** In-Sample bis 2014-12-31 / Out-of-Sample 2015-01-01 bis 2026-06

## 1. Hypothese

Stan Weinsteins Stage-Analysis (*Secrets for Profiting in Bull and Bear Markets*):
Eine Aktie, die aus einer Stage-1-Bodenbildung **über ihren 30er-MA und über eine
mehrfach getestete Widerstandszone ausbricht** — bestätigt durch Volumenexpansion
und eine von negativ auf positiv drehende relative Stärke — startet eine Stage-2-
Aufwärtsphase, die sich systematisch long handeln lässt. Getestet auf dem **Tages-
chart mit 30-Tage-MA** (Anforderung des Users; Weinsteins Original nutzt den
30-**Wochen**-MA — bewusste, dokumentierte Tagesadaption).

## 2. Makro-Begründung

Plausibel und verhaltensökonomisch fundiert: Eine lange Range bei flachem MA bündelt
Angebot an der Widerstandszone (Verkäufer aus früheren Verlustzonen, die „bei plus
minus null raus" wollen). Bricht der Kurs auf erhöhtem Volumen durch, ist dieses
Angebot absorbiert → der Pfad des geringsten Widerstands zeigt nach oben. Die
RS-Drehung filtert auf Titel, die den Gesamtmarkt **anführen** (institutionelle
Rotation in Stärke). Das ist ein anerkanntes Momentum-/Breakout-Muster — kein
data-gemintes Artefakt.

## 3. Regeln

Entry-Signal auf Bar `t` (Entscheidung am Close `t`, **Ausführung am Open `t+1`** —
look-ahead-frei, Engine-seitig erzwungen), gemessen über ein Basisfenster
`[t-40, t-1]` (die Konsolidierung vor dem Ausbruch, **ohne** den Ausbruchs-Bar):

1. **MA-Durchstoß von unten:** `Close[t]` über dem 30-Tage-MA, wobei der Close
   innerhalb der letzten 10 Bars mind. einmal **unter** dem MA lag (echter Aufwärts-
   durchstoß, kein bereits laufender Trend).
2. **Stage-1-Range:** 30er-MA über das Basisfenster ~flach (`|Drift| ≤ 15 %`) und
   Range-Höhe `(Widerstand−Support)/Support ≤ 45 %` (eine Basis, kein Trend).
3. **Widerstand ≥ 3× getestet, dann gebrochen:** Widerstand = Hoch des Basisfensters;
   die Zone (oberste 3 %) wurde in **≥ 3 distinkten Clustern** angelaufen, und `t`
   schließt erstmals darüber.
4. **Volumenexpansion:** `Volume[t] > 1,5 ×` dem Durchschnittsvolumen der vorherigen
   20 Bars.
5. **Relative Stärke dreht ins Plus:** Mansfield-RS (`Kurs/Benchmark`, nullzentriert)
   kreuzt von negativ nach positiv (war in den letzten 20 Bars `< 0`, ist jetzt `> 0`).

**Positionsmanagement (Headline = Weinsteins kanonische Regel):**
- **Initial-Stop** unter dem Basis-Support (2 % Puffer); Risiko `R = Entry − Stop`.
- **Exit (kanonisch):** Close fällt unter den 30er-MA → Verkauf am nächsten Open
  (Weinsteins Stage-4-Verkaufssignal).
- **Sizing:** risikobasiert, `Shares = risk_pct · Equity / R` (Headline 0,75 %/Trade),
  gekappt auf 20 % Notional/Position und auf das freie Kapital (kein Hebel).
- **Mehrere gleichzeitige Positionen** (geteiltes Konto), max. 12 distinkte Titel.

**Getestete Varianten** (Abschnitt 7): Exit ∈ {MA-Stop, 1R-Trailing, Chandelier-ATR,
Partial+Trail} × Pyramiding {aus, an (max. 2 Zukäufe je Titel auf Folge-Ausbrüche)} =
8 Konfigurationen.

## 4. Kosten- & Ausführungsannahmen

IBKR-Standardmodell (`quantlab.costs.IBKR_DEFAULT`): Kommission ~$0,0035/Aktie
(min $0,35, Cap 1 %), **3 bps Slippage** + 0,2 bps Gebühren je Seite. Voll auf jeden
Ein-/Ausstieg (inkl. Partial-Beine) gebucht. Ausführung am **nächsten Open**;
Stops/Trailing intrabar (Gap-Fills am Open, nie besser als der Stop). Adjustierte
Kurse (Splits/Dividenden). Alle Zahlen sind **netto**.

## 5. Ergebnisse (Out-of-Sample, netto nach Kosten) — Headline (MA-Exit, kein Pyramiding)

| Kennzahl                  | Wert |
| ------------------------- | ---: |
| CAGR                      | +4,3 % |
| Sharpe                    | 0,42 |
| Sortino                   | 0,52 |
| Calmar                    | 0,38 |
| Max Drawdown (+ Dauer)    | −11,4 % (740 Handelstage) |
| Trefferquote              | 44,4 % |
| Profit-Faktor             | 1,55 |
| Payoff-Ratio              | 1,94 |
| Expectancy                | +$105 / Trade (auf 100k-Konto) |
| Ø Haltedauer              | 27 Handelstage |
| Trades                    | 1.462 (OOS-Anteil; 1.901 Signale gesamt) |

## 6. Signifikanz

| Test                          | Wert |
| ----------------------------- | ---: |
| Permutationstest p-Wert (Random-Timing, full) | **0,0033** (real Sharpe 0,30 vs Null −0,14±0,15) |
| Permutationstest p-Wert (Random-Timing, OOS)  | **0,0199** (real 0,42 vs Null −0,04±0,21) |
| Bootstrap Sharpe 95%-KI (OOS, Block) | [−0,18, +1,05] |
| Deflated Sharpe (Varianten N=8) | 0,998 |
| t-Test mittlere Tagesrendite (OOS) | p = 0,0097 |

**Der entscheidende Test ist die Random-Timing-Permutation:** dasselbe Universum,
dieselbe Trade-Zahl je Titel, dieselbe Exit-Mechanik, aber **zufällige Eintritts-
zeitpunkte**. Die Null-Sharpe ist klar **negativ** (Zufalls-Entry wird zerhackt:
Stop-outs + Kosten + 2 %-RF-Hürde), die echte Strategie liegt signifikant darüber
→ das **Stage-2-Eintritts-Timing trägt echtes Skill** (nicht bloß Long-Exposure).
Dieser Test ist survivorship-robust (Null läuft im selben Survivor-Pool).

## 7. Robustheit

**Varianten (OOS-Sharpe / OOS-CAGR / Trades):** alle 8 positiv, eng beieinander —
MA 0,42 / 4,3 % / 1.462 · 1R-Trailing 0,41 / 5,0 % / 345 · Chandelier 0,26 / 3,1 % ·
Partial 0,41 / 4,3 % (Win 64 %!) · die Pyramiding-Varianten heben die Rendite kaum,
**erhöhen aber den Drawdown** (1R+Pyramid OOS-MaxDD −20 % vs −14 %) — Pyramiding hebt
Return nicht Sharpe (gleiche Lehre wie SMC 0069/0070). Plateau über die Exits =
Mechanismus, kein Zell-Glück.

**IS→OOS:** stabil, **kein Kollaps** (Sharpe 0,21 → 0,42, OOS sogar besser; Regeln
sind a priori fixiert, keine Parameter-Optimierung). DSR 0,998 bestätigt: der positive
In-Sample-Sharpe ist über die 8 Varianten kein Selektions-Glück.

**Der Knackpunkt — Survivorship/Beta-Kontrolle (gleiche Periode, OOS):**

| | CAGR | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| **Weinstein Stage-2 (Headline)** | +4,3 % | 0,42 | **−11,4 %** |
| Equal-Weight-B&H *gleiches Universum* | +17,1 % | **0,87** | −35,3 % |
| S&P 500 (SPY) | +13,8 % | 0,71 | −33,7 % |

→ **Die Strategie schlägt das Buy & Hold des gleichen Universums NICHT** — weder auf
Rendite noch risiko-adjustiert. Ihr einziger echter Vorteil ist der **Drawdown**:
sie sitzt in Stage-4-Phasen in Cash und umgeht 2008/2020 (Vollperiode MaxDD −12 % vs
EW-B&H −49 % / SPY −55 %) — genau Weinsteins eigentliche These (Bärenmärkte meiden),
aber als reine Rendite-Maschine unterlegen.

**Ist die niedrige Rendite nur klein gesized?** Teils. Ø **6 gleichzeitige
Positionen** (nur 9 % der Tage flat, 12 % am 12er-Cap) → kein Cash-Drag-Problem wie
RSI-2 (0071/0072), sondern kleine Notional je Slot (weite Support-Stops). Hochskaliert
steigt die Rendite — und sogar der Sharpe (mehr Diversifikation + die 2 %-RF-Hürde
wiegt bei höherer Rendite leichter):

| Risk/Trade · max. Positionen | CAGR (full) | Sharpe | MaxDD |
|---|---:|---:|---:|
| 0,75 % · 12 (Headline) | +3,6 % | 0,30 | −12 % |
| 1,5 % · 20 | +6,3 % | 0,50 | −23 % |
| 2,0 % · 25 | +7,8 % | 0,58 | −28 % |
| 3,0 % · 40 | +9,4 % | 0,65 | −35 % |

Selbst auf B&H-vergleichbaren Drawdown (−35 %) gesized bleibt der Sharpe (0,65)
**unter** EW-B&H (0,75 full) und SPY — die Größe verschiebt nur den Punkt entlang
derselben unterlegenen Effizienzlinie.

## 8. Verdict

**Abgelehnt als Standalone — aber ein ehrlich positiver Methoden-Befund, kein leeres
Signal.** Die Strategie ist mechanisch exakt nach Spec gebaut, look-ahead-sauber
(6/6 Tests) und ihr **Eintritts-Timing besitzt echtes, signifikantes Skill** (schlägt
Zufalls-Timing im selben Universum p=0,003, t-p=0,01, DSR 0,998). **Der eine Grund für
die Ablehnung:** als long-only-System schlägt sie das Buy & Hold des gleichen
(survivorship-verzerrten) Universums weder auf Rendite (+4 % vs +17 %) noch auf Sharpe
(0,42 vs 0,87) — das Timing-Skill reicht nicht, um den Verzicht auf die Aktien-
Risikoprämie in den Cash-Phasen auszugleichen. Ihr realer Mehrwert ist
**Drawdown-Reduktion** (¼ des B&H-DD durch Bärenmarkt-Vermeidung), nicht Mehrrendite —
also bestenfalls ein **defensives/risikoreduzierendes Bein**, kein Performance-Treiber.
Passt nicht zur CTI-Funded-Richtung (Trend/Momentum = klumpig, nicht das gesuchte
high-win/smooth-Profil). Wiederverwendbar: `quantlab/weinstein` (Stage-2-Detektor +
Multi-Position-Portfolio-Engine mit allen Exit-/Pyramiding-Varianten).

## 9. Anhang: 30-Wochen-Originalvariante (kanonischer Weinstein)

`run_weekly.py` baut **dieselbe Strategie auf Wochenbars mit dem 30-Wochen-MA** —
Weinsteins eigentlicher Original-Chart (Abschnitte 1-8 waren die vom User gewünschte
30-Tage-Tagesadaption). Alle Fenster in Wochen, Annualisierung mit 52 statt 252;
gleiche Engine, gleiches Universum, gleiche Batterie.

| | Trades | OOS Sharpe | OOS CAGR | OOS MaxDD | Random-Timing-Perm (OOS) |
|---|---:|---:|---:|---:|---:|
| **30-Tage (Headline, §5)** | 1.462 | **+0,42** | +4,3 % | −11,4 % | **p = 0,020 (signifikant)** |
| 30-Wochen (kanonisch) | 133 | **−1,00** | +0,3 % | −5,7 % | p = 0,073 (n.s.) |

**Befund: die kanonische 30-Wochen-Form ist auf diesem Universum DEUTLICH schwächer
als die Tagesadaption** — und zwar aus zwei Gründen:

1. **Zu selten → fast kein Kapital im Markt.** Nur **134 Signale** (vs 1.901 daily);
   die strikte ≥3-Touch-Basis auf 30-Wochen-Bars feuert kaum. Ø **2,3 gleichzeitige
   Positionen**, 26 % der Wochen komplett flat. → Konto bleibt ~98 % in Cash → CAGR
   ~0,3 % **unter** der 2 %-Risk-free-Hürde → **negative Sharpe (−1,0)**. Wichtig:
   das sind **keine Verlust-Trades** — Expectancy **+$98/Trade**, Gewinner $37,7k vs
   Verlierer −$24,6k, Profit-Faktor 1,53. Die negative Sharpe ist **reiner Cash-Drag**,
   nicht ein verlierendes Signal (die long-Holds sind ~23 Wochen, Payoff 2,71).
2. **Kein nachweisbares Timing-Skill mehr.** Die Random-Timing-Permutation **scheitert**
   (full p=0,13, OOS p=0,073) — anders als die Tagesvariante (p=0,003/0,020). Mit nur
   133 Trades fehlt die statistische Power, und der Eintritts-Zeitpunkt ist nicht mehr
   von Zufall zu unterscheiden. DSR 0,554, t-Test p=0,44.

→ **Die vom User ursprünglich gewählte 30-Tage-Adaption ist die bessere der beiden**:
schnellerer MA = genug Signale für deploybare Exposure UND statistische Power. Die
kanonische 30-Wochen-Form ist auf dem survivorship-verzerrten yfinance-Aktienkorb
unterpowert. (Eine Lockerung der Basis-/Touch-Regeln würde mehr Wochen-Trades
erzeugen — das wäre aber Parameter-Exploration, nicht der kanonische Test.)
Artefakte: `results/metrics_weekly.json`, `trades_weekly.csv`, `equity_weekly.png`.
