# Strategie 0024 — CNY-Gold-Fenster: Forward-/Cross-Asset-Test auf Silber

- **Kategorie:** seasonal (event-getrieben, Forward-/OOS-Test einer eingefrorenen Regel)
- **Status:** testing — **Lead bestärkt** (Silber-Future bestätigt), aber nicht validiert
- **Datum:** 2026-06-04
- **Universum:** Gold-Future `GC=F` (Referenz), Silber-Future `SI=F` (ungesehenes Asset), SPDR Silber `SLV` (physisch)
- **Stichprobe:** GC=F/SI=F 2000–2026, SLV 2006–2026 (keine IS/OOS-Teilung — Cross-Asset IST der OOS-Test)

## 1. Hypothese

Die in 0023 auf **Gold** gefundene Vor-CNY-Saison (long 15 Tage vor bis 2 nach dem
chinesischen Neujahr, Perm p=0,009) ist ein Lead, der auf Gold *gesehen* wurde. Wenn
es eine echte Edelmetall-CNY-Saison ist, muss die **eingefrorene** Regel ohne jedes
Re-Fitting auch auf **Silber** funktionieren — dem Schwestermetall mit gleicher
CNY-Schmuck-/Geschenknachfrage, auf dem das Fenster nie kalibriert wurde.

## 2. Makro-Begründung

China ist nicht nur der #1-Gold-, sondern auch ein Top-Markt für Silberschmuck und
Tafelsilber; das Frühlingsfest treibt dieselbe Geschenk-/Schmucknachfrage. Silber und
Gold teilen zudem den Edelmetall-Risk-on/-off-Faktor. **Ehrliche Einschränkung:**
Silber ist deutlich **industrieller und volatiler** als Gold — die Nachfragegeschichte
ist *verwandt*, nicht identisch. Es ist ein partieller, ehrlicher OOS-Test, kein Klon.
Wie in 0021 (Palladium für Platin) ist das **korrelierende** Evidenz (gleiche Jahre,
gleicher Treiber), kein unabhängiger zeitlicher Forward-Test.

## 3. Regeln (eingefroren aus 0023 — kein Re-Fitting)

- **Entry:** long ab `CNY − 15 Kalendertage`. **Exit:** flat ab `CNY + 2`. Ein Trade/Jahr.
- CNY-Daten 2000–2026 hartkodiert; **identisch für jedes Instrument** (keine Pro-Asset-Justierung).
- **Look-Ahead-Schutz:** Entscheidungszeit-Signal (nur Datum); Engine verzögert T+1.

## 4. Kosten- & Ausführungsannahmen

Futures (`GC=F`, `SI=F`): `IBKR_FUTURES` (~5 bps RT). ETF (`SLV`): `IBKR_LIQUID_ETF`
(2 bps Slippage/Seite). Ausführung Schlusskurs T+1. Futures-Guard (Lehre 0005): kein
nicht-positiver Kurs. (Silber kann nicht negativ werden, Guard bleibt zur Sicherheit.)

## 5. Ergebnisse (netto nach Kosten, eingefrorene Regel)

| Instrument | Rolle | Trades | Win | Expectancy/Trade | Sharpe (B&H) | **Perm p** | Bootstrap-Sharpe-KI | t-Test p |
| ---------- | ----- | -----: | --: | ---------------: | -----------: | ---------: | ------------------: | -------: |
| **GC=F** Gold | Referenz (in-sample) | 26 | 65 % | +2,48 % | 0,12 (0,59) | 0,009 | [−0,28; 0,47] | 0,013 |
| **SI=F** Silber | OOS-Asset (ungesehen) | 26 | **73 %** | **+3,55 %** | 0,22 (0,43) | **0,025** | [−0,15; 0,58] | 0,062 |
| **SLV** Silber phys. | OOS-Instrument (kein Roll) | 20 | 60 % | +2,53 % | 0,08 (0,34) | 0,116 | [−0,35; 0,55] | 0,350 |

## 6. Signifikanz & Forward-Registrierung

**Silber-Future bestätigt den Lead:** Die eingefrorene Gold-Regel besteht auf dem nie
gemineten Silber-Future den Permutationstest (**p=0,025**) und ist pro Trade sogar
**stärker** als auf Gold (+3,55 %, 73 % Win). Das ist echte Cross-Asset-OOS-Evidenz: die
Vor-CNY-Edelmetall-Saison ist kein reines Gold-Kuriosum.

**Aber die Belege bleiben hinter Platin (0021) zurück:**
1. Der **physische Silber-ETF `SLV` verfehlt** die 5 %-Schwelle (p=0,116) — zwar positiv
   und mit nur 20 Trades (ab 2006) schwächer befüllt, aber kein Beweis. Bei Platin
   bestand der physische ETF (PPLT p=0,003).
2. **Kein einziges Bootstrap-Sharpe-KI schließt die Null aus** (alle berühren 0) — der
   *risikoadjustierte* Vorteil ist durchweg schwach, anders als Palladium ([0,01;0,63]).
3. **Kein zeitlicher Forward-Test:** Silber teilt dieselben Jahre und denselben Treiber
   wie Gold = korrelierende, nicht unabhängige Evidenz.

**Vorab registrierter Live-Forward (eingefroren 2026-06-04):** Erste *ungesehene*
Beobachtung = CNY **2027** (und folgende Winter). Regel: long Gold-Future ab CNY−15,
Exit CNY+2; parallel Silber-Future mitführen. Erfolgskriterium: über ~5 Live-Winter
mehrheitlich positiv und gepoolter Perm-p < 0,05. Erst dann „validated".

## 7. Robustheit

Cross-Asset: Future-Ebene konsistent (Gold p=0,009, Silber p=0,025, beide ~+2,5–3,5 %/
Trade). Cross-Instrument: physisches Silber positiv, aber insignifikant (kürzere Historie,
höhere Vola). Die Edge-Signatur ist über Metalle robust auf der Timing-/Expectancy-Ebene,
fragil auf der Sharpe-/Risiko-Ebene.

## 8. Verdict

**Lead bestärkt, nicht validiert — Status testing.** Der Silber-Future-OOS (p=0,025,
73 % Win) ist genau die unabhängige Bestätigung, die man sehen will, und hebt die
CNY-Edelmetall-Saison über ein reines Ein-Asset-Ergebnis. Doch der schwache physische
SLV-Check (p=0,116) und die durchweg null-berührenden Bootstrap-KIs verhindern eine
Höherstufung: die CNY-Saison ist auf der **Timing-Ebene real**, auf der **Risiko-Ebene
schwach**, und schwächer belegt als die Platin-Jahreswechsel-Saison (0021). Entscheidung
fällt der **pre-registrierte Live-Forward ab CNY 2027**. Bis dahin kein Live-Kapital;
kein Re-Fitting des Fensters (jede weitere Optimierung würde den OOS-Charakter zerstören).
