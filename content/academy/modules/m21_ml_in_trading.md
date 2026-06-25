> **Repo-Anker:** `src/quantlab/crypto_features.py` + `ml_portfolio.py` und die ML-Roadmap
> 0057–0062. Das Abschlussmodul: ML im Trading — mit allen Fallstricken, die du nach Modul 7
> (ML-Mathe) und Modul 14 (CPCV/Leakage) jetzt benennen kannst.

## 1. Feature-Engineering — wo der Edge wirklich sitzt

ML-Modelle sind nur so gut wie ihre **Features**. Nicht das Modell, sondern die
theoriegetriebene Feature-Konstruktion trägt den Edge. Aus `crypto_features.py` (11
Basis-Features), jedes mit einer ökonomischen These:

- **Momentum** (7/14/28/56/84 Tage) — Persistenz (Modul 5).
- **Carry / Basis-Momentum** — die Terminstruktur-Prämie (Modul 10).
- **Illiquidität** (Amihud) — Kompensation für Handelskosten (Modul 13).
- **Lottery** (max. Tagesrendite) — überbezahlte Jackpot-Coins (negativ).

Die Features sind **rang-transformiert** und PIT-sauber (Modul 14) — kein Feature darf
Information vom Entscheidungszeitpunkt aus der Zukunft enthalten.

## 2. Meta-Labeling — die Wette sizen statt die Richtung raten

Das mächtigste ML-Muster im Trading (López de Prado) ist **nicht**, ein Modell die Richtung
vorhersagen zu lassen. Es ist **zweistufig**:

1. Ein **Primärsignal** (oft einfach/regelbasiert) entscheidet die **Richtung** — wann long/short.
2. Ein **Meta-Modell** entscheidet die **Größe** — *wie sehr* soll ich diesem Trade vertrauen?
   Es sagt nicht „long oder short", sondern „nehmen oder lassen / groß oder klein".

Warum das besser ist: Das Meta-Modell löst ein **leichteres** Problem (binär: vertrauen ja/nein)
und liefert **kalibrierte Wahrscheinlichkeiten** (Modul 7), die direkt ins Sizing fließen
(Modul 6, Kelly). Spiel mit dem Konfidenz-Filter:

::viz ICvsPnL

Nimm **alle** Signal-Trades (grau): der Edge ertrinkt in niedrig-konfidenten Trades plus
Kosten. Nimm nur die **meta-konfidenten** (grün): weniger, aber bessere Trades — der Netto-PnL
steigt, **obwohl der zugrunde liegende Signal-IC unverändert ist**. Das ist Sizing, nicht
Vorhersage.

## 3. Die teuerste Lehre: IC ≠ PnL

Du kennst sie aus Modul 9, hier ist sie ML-spezifisch (0058). Der OOS-IC eines Crypto-Modells
war stark und ohne Decay (h28 +0,137, t = 11,7) — und das naive Quintil-Portfolio
**monetarisierte ihn nicht** (Long-only 0,56 < Markt 0,61). Die Lücke war eine Konstruktions-/
Kostenfrage, kein Signalproblem. Die Hebel, die sie schlossen (0059) — und jeder zählt als
Trial (Modul 2):

- **Liquiditäts-Floor** ($5 M) **vor** dem Ranking, nicht als Strafe danach.
- **Dezil-Konzentration** + **Hold-Band-Buffer** (Hysterese) → Turnover 22× → 6×.
- **Monatliches** statt wöchentliches Rebalance.

Das war das **erste bestandene Ridge-Gate** des Katalogs: die kleinste LGBM-Konfig schlug
Ridge in 68–82 % der Splits — Crypto-Nichtlinearität ist real, aber **flach** (Kapazität klein
halten, Modul 7).

## 4. Die Fallstricke, jetzt benennbar

Was du nach den Vormodulen sofort erkennst:

- **Leakage** (Modul 14): ohne Purging/Embargo lernt das Modell die Zukunft — der häufigste,
  teuerste Bug.
- **CPCV ist kein Pfad** (Modul 15): 0061 bestand das CPCV-Gate und **kippte** im Walk-Forward.
- **Feature-Importance ≠ Edge** (0057): das LGBM lernte über alle Splits dieselbe stabile
  Struktur, die OOS **nichts** prognostizierte. Konsistenz ≠ Prognosekraft.
- **Deep Learning braucht Paper-Datenskala** (0062): JKX-CNN-on-Charts war auf ~25k
  Crypto-Bildern ein sauberes Null (0/28 Splits vs. LGBM) — „unkorreliert" ist kein
  Ensemble-Argument ohne eigenes Signal.
- **Faktor-Crash-Risiko** (0059): IC/Sharpe sehen es nicht — 2023 war ein −3,2-Jahr vs. Markt,
  ~2 Jahre Alpha unter Wasser.

## 5. Wann ML überhaupt hilft

Die nüchterne Bilanz (0057): Auf der toten Commodity-XSection kombinierte ML nur die
zerfallenen Faktoren zu einem zerfallenen Faktor (sauberes Null). ML **repariert kein fehlendes
Signal** — es kann ein vorhandenes, nichtlineares Signal besser extrahieren (Crypto 0059), aber
es erfindet keinen Edge. **Erst das Signal nachweisen, dann ML draufsetzen — nie umgekehrt.**

> **Payoff:** Du baust eine ehrliche ML-Trading-Pipeline — theoriegetriebene Features,
> Meta-Labeling zum Sizing, leakage-freie Validierung — und benennst die teuren Fallstricke
> (Leakage, IC≠PnL, CPCV≠Pfad, Importance≠Edge), bevor sie dich Geld kosten.

---

**Damit ist die Quant Academy komplett** — 22 Module vom Abitur-Return bis zur ehrlichen
ML-Pipeline. Du hast jede der vier Senior-Quant-Säulen durchlaufen: **Statistical Arbitrage**
(Cross-Sectional, Carry, Pairs), **Risikomanagement** (Drawdown, Sizing, Portfolio),
**Derivate-Pricing** (Black-Scholes, Greeks, VRP) und **Machine Learning** (Meta-Labeling,
Validierung) — jeder Baustein an deinem eigenen Repo und an einer real getesteten Strategie
verankert.
