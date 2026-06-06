# Strategie 0023 — Gold rund um asiatische Goldkauf-Feste (Dual-Studie)

- **Kategorie:** seasonal (event-getrieben, lunisolar bewegliche Feste)
- **Status:** gemischt — **Akshaya Tritiya abgelehnt**, **Chinesisches Neujahr = testing/Lead**, **Pooling abgelehnt**
- **Datum:** 2026-06-04
- **Universum:** Gold (Gold-Futures `GC=F`), Cross-Check: SPDR Gold Shares (`GLD`, physisch)
- **Stichprobe:** In-Sample 2000–2013 / Out-of-Sample 2013–2026 (Schnitt 01.07.2013, halbiert kein Winter-/Frühjahrsfenster)

## 1. Hypothese

Direkter Vergleich der zwei *realen* saisonalen Gold-Nachfrage-Events (im Gegensatz
zu 0022/Ostern, das keine Makro-Ursache hatte): Gold long im **Vorlauf** des Festes
— 15 Kalendertage vor bis 2 nach — getrieben durch physischen Schmuck-/Anlagekauf,
jeweils für **Akshaya Tritiya** (Indien) und **Chinesisches Neujahr** (China),
plus eine **gepoolte** „asiatische Gold-Saison" (Vereinigung beider Fenster).

## 2. Makro-Begründung

Beide Feste haben — anders als Ostern — eine echte, dokumentierte Ursache:

- **Akshaya Tritiya:** zweitwichtigster Goldkauftag des indischen Jahres (nach
  Dhanteras/Diwali), gilt als der glückverheißendste Tag für Goldkäufe. Juweliere
  bevorraten sich, Haushalte kaufen im Vorlauf. Indien ist **#2-Goldkonsument**.
- **Chinesisches Neujahr:** Schmucknachfrage und Gold-Gifting zum Frühlingsfest;
  chinesische Einzelhändler bevorraten, Verbraucher kaufen vor dem Feiertag. China
  ist **#1-Goldkonsument**. (Gleicher Treiber, den 0018/0021 für die Platin-
  Jahreswechsel-Saison zitieren — daher ist CNY-Gold *korrelierende* Evidenz zu
  jenen, kein voll unabhängiges Phänomen.)

Mechanismus in beiden Fällen: **Nachfragesog vor dem Fest** → long im Vorlauf.

## 3. Regeln

- **Entry:** long Gold ab `Fest − 15 Kalendertage`. **Exit:** flat ab `Fest + 2`.
- Fenster **vorab aus der Makro-Story** festgelegt (nicht aus dem Kurs gescannt).
- **Festdaten** beweglich (lunisolar) → exakt aus verifizierten Tabellen 2000–2026
  hartkodiert (Quellen drikpanchang/Wikipedia für Akshaya; Standard-CNY-Tabelle).
  Ein Formel-Ansatz wie der Oster-Computus (0022) ist hier nicht möglich.
- **Look-Ahead-Schutz:** Entscheidungszeit-Signal (nur Datum); Engine verzögert T+1.
- Ø Marktzeit ~5 % je Einzelfest, ~10 % gepoolt; Ø Haltedauer ~12,4 Handelstage.

## 4. Kosten- & Ausführungsannahmen

`IBKR_FUTURES` (Gold-Future): ~5 bps Round-Trip (2 bps Slippage/Seite + 0,5 bps
Gebühren). Cross-Check auf `GLD` mit `IBKR_LIQUID_ETF` (2 bps Slippage/Seite).
Ausführung Schlusskurs T+1. Futures-Guard (Lehre 0005): kein nicht-positiver Kurs.

## 5. Ergebnisse (Full Sample 2000–2026, netto nach Kosten)

| Kennzahl          | Akshaya Tritiya | **Chin. Neujahr** | Gepoolt | Gold B&H |
| ----------------- | --------------: | ----------------: | ------: | -------: |
| CAGR              |        −0,11 % |        **2,42 %** |  2,31 % |  11,50 % |
| Sharpe            |          −0,53 |        **0,12** |    0,08 |     0,59 |
| Max Drawdown      |        −14,7 % |        −6,8 % | −15,5 % |  −44,4 % |
| Trefferquote      |          58 % |          **65 %** |    62 % |        — |
| Profit-Faktor     |          0,96 |        **4,61** |    2,18 |        — |
| Expectancy/Trade  |        −0,05 % |        **+2,48 %** | +1,22 % |        — |
| Trades            |            26 |             26 |      52 |        — |

## 6. Signifikanz (Full Sample)

| Test                          | Akshaya | **Chin. Neujahr** | Gepoolt |
| ----------------------------- | ------: | ----------------: | ------: |
| Permutationstest p            |   0,832 |        **0,009** |   0,118 |
| Bootstrap Sharpe 95 %-KI      | [−0,92; −0,15] | **[−0,28; 0,47]** | [−0,29; 0,46] |
| t-Test mittlere Rendite p     |   0,961 |        **0,002** |   0,027 |
| Deflated Sharpe (N=49)        |    0,00 |          0,00 |    0,00 |
| **GLD-Cross-Check Perm p**    |   0,716 |        **0,019** |   0,115 |

**Kernbefund:** Der Permutationstest — derselbe Filter, der 0022/Ostern tötete —
trennt die beiden Feste scharf. **Akshaya Tritiya hat keinerlei Edge** (p=0,83,
expectancy negativ, GLD-Check p=0,72): die indische Nachfrage ist offenbar
eingepreist oder bewegt den Weltgoldpreis nicht. **Chinesisches Neujahr besteht**
(Perm p=0,009, t-Test p=0,002) **und generalisiert auf den physischen GLD-ETF**
(p=0,019) → kein Futures-/Roll-Artefakt. **Gepoolt scheitert (p=0,118)**, weil das
tote Akshaya-Bein das starke CNY-Bein verwässert — die „asiatische Gold-Saison" ist
in Wahrheit *nur* die China-Saison; Pooling ist hier kontraproduktiv.

## 7. Robustheit

CNY: **49/49** Fenster-Verschiebungen (±6 Tage) positiv — hier mehr wert als bei
0022/0017, weil der Permutationstest gleichzeitig grünes Licht gibt (das Plateau
ist also nicht nur Gold-Drift). IS/OOS beide positiv. Akshaya: 33/49 positiv, aber
das ist reine Gold-Drift ohne Timing-Signal (Perm p=0,83). Cross-Instrument auf GLD
bestätigt CNY (+2,40 %/Trade, p=0,019) und verwirft Akshaya (p=0,72).

## 8. Verdict

- **Akshaya Tritiya → abgelehnt.** Starke Story, aber null Timing-Edge (p=0,83); auf
  GC=F und GLD gleichermaßen tot. Lehre: eine plausible Makro-Geschichte ersetzt
  den Permutationstest nicht.
- **Chinesisches Neujahr → testing / Lead.** Erster Gold-Saison-Effekt mit echtem
  Timing-Beleg (Perm p=0,009, t-Test p=0,002) *und* Cross-Instrument-Bestätigung
  (GLD p=0,019). **Aber Demut:** (1) annualisierter Sharpe nur 0,12, **Bootstrap-KI
  [−0,28; 0,47] berührt die Null** — der risiko­adjustierte Vorteil ist schwach;
  (2) DSR=0 (Such-Strafe für 49 Fenster-Varianten); (3) nur 26 Trades; (4) **teilt
  den Treiber mit 0018/0021** (Schmucknachfrage vor CNY) → korrelierende, nicht
  unabhängige Evidenz. Damit ein **Lead**, kein validierter Edge.
- **Pooling → abgelehnt** (verwässert das CNY-Signal).

**Nächster Schritt:** CNY-Regel (−15/+2) einfrieren und wie bei 0006/0009/0021 einen
echten **Forward-Test auf ungesehenen Instrumenten/Zeiträumen** fahren (z. B. Silber
`SI=F` als Schwester-Edelmetall mit gleicher CNY-Schmucknachfrage, plus vorab
registrierter Live-Forward CNY 2027). Erst dann von „testing" nach „Kandidat".
