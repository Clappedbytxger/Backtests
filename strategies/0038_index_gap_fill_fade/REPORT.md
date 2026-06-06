# Strategie 0038 — Index Gap-Fill-Fade (Intraday, Tages-OHLC)

- **Kategorie:** mean-reversion / intraday
- **Status:** abgelehnt
- **Datum:** 2026-06-06
- **Universum:** S&P 500 (SPY, 1993+) und Nasdaq-100 (QQQ, 1999+) als Preis-Proxy;
  Zielinstrument Micro E-mini S&P 500 (MES) / Micro E-mini Nasdaq-100 (MNQ).
  Kontroll-Gegenprobe auf den Futures-Continuous-Reihen S&P-Future (ES=F) und
  Nasdaq-100-Future (NQ=F).
- **Stichprobe:** In-Sample = jeweils erste Zeithälfte, Out-of-Sample = zweite
  Zeithälfte (zeitlicher Mittel-Split pro Instrument).

Erste Strategie des Prop-Edge-Forschungsprogramms (`Prop-Edge-Framework.md`,
Hypothese #2: „Gap-Fill-Fade am Open ohne Übernacht-Halten"). Es ist die einzige
Priorität-1/2-Prop-Hypothese, die sich mit **voller Gratis-Historie** testen
lässt — sie braucht nur Tages-OHLC.

## 1. Hypothese

Übernacht-Gaps im Aktienindex mean-reverten intraday. Das Faden des Gaps am Open
(entgegengesetzt zur Gap-Richtung, Ausstieg zum Close, **flat über Nacht**) ist
ein hochfrequenter, glatter, prop-kompatibler Edge — viele kleine Gewinne, kein
Übernacht-Drawdown (genau das Profil, das die Prop-Drawdown-Regeln verlangen).

## 2. Makro-Begründung

Übernacht-Gaps entstehen aus Nachrichten/Orderungleichgewichten, die sich bei
geschlossenem Kassamarkt aufstauen. Am Open stellen Liquiditätsanbieter Liquidität
bereit; eine Überreaktion im Gap wird im Tagesverlauf teilweise korrigiert
(Liquiditätsbereitstellung + Überreaktion faden, Framework-Baustein #1). Ökonomisch
plausibel — aber, wie sich zeigt, im liquiden Index längst wegkonkurriert.

## 3. Regeln (Look-Ahead-Schutz)

- `gap_t = Open_t / Close_(t-1) − 1` — **zum Open bekannt** (Entscheidungszeit).
- Symmetrisch: Position = `−sign(gap_t)`, Eintritt zum Open, Ausstieg zum Close.
- Trade-PnL = `Position × (Close_t / Open_t − 1)` (reiner Open→Close-Move, strikt
  *nach* der Entscheidung; kein `shift` nötig, kein Look-Ahead).
- Trendfilter (für die konditionale Variante): `Close_(t-1) > MA50_(t-1)` —
  ausschließlich Information, die zum Open vorliegt.

**Datenquelle (gratis):** yfinance Tages-OHLC, `auto_adjust=True`. Der ETF-Open
(SPY/QQQ) ist der echte RTH-Eröffnungsauktions-Open, der den Übernacht-Gap voll
abbildet. Der Futures-Continuous-„Open" (ES=F/NQ=F) ist dagegen der Globex-Session-
Open (18:00 ET Vortag) — **für eine Gap-Studie ungeeignet**; ES/NQ laufen hier nur
als Gegenprobe und zeigen erwartungsgemäß kein Gap-Fill (siehe §7).

## 4. Kosten- & Ausführungsannahmen

Neuer Preset `MES_INTRADAY`/`MNQ_INTRADAY` in `quantlab.costs`: Micro-Index-Futures
sind die *günstigsten* liquiden Märkte pro Notional (großes Notional, winziger
Tick) — das Gegenteil der BTC-Perps (16 bps RT), an denen 0012–0015 starben. Real
~0,6 bps/Seite; **konservativ auf 1,5 bps/Seite = 3 bps Round-Trip gepolstert**
(Eröffnungsauktion kann mehr slippen). Der Brutto-Edge muss diese 3 bps mit
Sicherheitsmarge schlagen (Framework Schritt 2).

## 5. Ergebnisse (Out-of-Sample, netto nach Kosten)

Es existiert **kein handelbarer Edge**, daher Tabelle der entscheidenden
Diagnosen statt einer Headline-Kennzahl:

| Test | SPY | QQQ |
| --- | ---: | ---: |
| Symmetrischer Fade, Brutto/Trade (thr 0) | +1,20 bps | +2,01 bps |
| Symmetrischer Fade, **Netto/Trade** | **−1,80 bps** | **−0,99 bps** |
| Unkond. Open→Close-Drift (Beta) | 0,81 bps | 0,08 bps |

→ Der Brutto-Edge (~1–2 bps) schlägt die 3 bps Round-Trip **nirgends**. Kosten sind
die bindende Grenze — die BTC-0012–0015-Lehre, erneut.


## 6. Signifikanz (konditionale Survivor-Zelle: Down-Gap-Fade im Abwärtstrend)

Einzige look-ahead-freie Zelle mit positivem Netto — vollständige Batterie:

| Test | SPY (thr −0,40%) | QQQ (thr −0,40%) |
| --- | ---: | ---: |
| n Trades | 589 | 665 |
| Netto/Trade | +1,61 bps | +4,87 bps |
| Median/Trade | +1,55 bps | +3,84 bps |
| Trefferquote | 50 % | 50 % |
| Sharpe (Full-Time, netto) | **−0,23** | **−0,07** |
| **Top-5 Tage = % des Gesamtgewinns** | **148 %** | **117 %** |
| Permutationstest p (Mittel vs. Zufallstiming) | 0,160 | 0,073 |
| Bootstrap Sharpe 95%-KI | [−0,58; 0,10] | [−0,47; 0,30] |
| Deflated Sharpe (N=60 Varianten) | 0,00 | 0,00 |
| t-Test mittlere Rendite p | 0,823 | 0,597 |
| Schlechtester Tag / längste Verlustserie | −7,63 % / 10 | −7,91 % / 7 |

## 7. Robustheit & die zwei Fallen, die diesen Test definieren

**Falle 1 — Look-Ahead (Framework-Falle #1).** Eine konditionale Regel „Down-Gap
im *Aufwärts*trend long kaufen" (Dip kaufen im Bullenmarkt) lieferte zunächst
**Sharpe 2,82, +12,5 bps/Trade, 61 % Win** auf SPY. Die Quelle: der Trendfilter
nutzte den *heutigen* Close (`Close_t > MA_t`), der zum Open **nicht bekannt** ist.
`Close_t > MA` korreliert mechanisch mit einem positiven Open→Close (ein Tag, der
hoch zum Durchschnitt schließt, ist meist vom Open gestiegen) → der Long
pre-selektierte Auf-Tage. **Korrekt gelaggt** (`Close_(t-1) > MA_(t-1)`) bricht
derselbe Effekt auf **Sharpe −0,22, −3,4 bps/Trade** zusammen. Der gesamte
Traum-Edge war Bias. (Linker Plot: rote vs. blaue Equity-Kurve.)

**Falle 2 — Fat-Tail-Lotterie (Framework, im Prop-Kontext doppelt verboten).** Die
einzige nach der Look-Ahead-Korrektur positive Zelle (Down-Gap im *Abwärts*trend
long = fallendes Messer fangen) bezieht **> 100 % ihres Gewinns aus den 5 besten
Tagen** (Bärenmarkt-Rally-Spikes); ohne sie ist sie negativ. Permutation
insignifikant (p 0,07–0,16), IS/OOS instabil (SPY IS negativ, ganze Leistung nur
OOS post-2010 = die 0017-Drift-Falle), Full-Time-Sharpe ≈ 0, Win 50 % (Münzwurf).
Im Prop-Kontext ist genau dieses Profil das schlechtmöglichste: ein Fat-Tail-Tag
verletzt die Konsistenzregel, ein Fat-Tail-*Verlust* beim Messerfangen
(schlechtester Tag −7,9 %) reißt das 5-%-Tageslimit.

**Gegenprobe Futures:** ES=F/NQ=F zeigen brutto **negativen** Fade (Gaps
kontinuieren) — bestätigt, dass der Futures-Globex-„Open" kein Gap-Instrument ist
und die ETF-RTH-Open-Reihe die methodisch richtige Wahl war.

## 8. Verdict

**Abgelehnt.** Drei unabhängige Gründe, jeder allein ausreichend: (1) der
symmetrische Fade scheitert am Kosten-Gate (Brutto < 3 bps RT); (2) der
spektakuläre konditionale Edge war reiner Look-Ahead; (3) der einzige
look-ahead-freie Survivor ist eine permutations-insignifikante Fat-Tail-Lotterie
mit dem für Prop gefährlichsten Profil. Der Wert liegt im Prozess: die Pipeline hat
ihren eigenen Look-Ahead-Bug und eine Fat-Tail-Illusion entlarvt — die ersten zwei
Einträge der Anti-Selbstbetrugs-Checkliste in Aktion. Nächste Prop-Hypothesen
(#1 Opening-Range-Fade, #3 Time-of-Day) brauchen echte Intraday-Bars; gratis liegen
dafür nur ~2,4 Jahre ES=F-1h vor (dünn) → als exploratives Folgeprojekt vermerkt.
