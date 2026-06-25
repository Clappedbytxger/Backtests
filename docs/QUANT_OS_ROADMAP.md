# Quant OS — Die ultimative Lern-Roadmap

### Vom absoluten Laien zum Schwarm-Commander eines Quant-Hedgefonds

> **Dokumentklasse:** Strukturierter Lernpfad · **Begleitdokument:** `QUANT_OS_HANDBUCH.md` · **Stand:** 2026-06-25
>
> Diese Roadmap führt eine Person ohne Vorkenntnisse in vier chronologischen Meilensteinen zum souveränen Power-User von Quant OS. Jede Phase hat **Lernziele**, **System-Übungen** (am echten System, mit echten Routen) und eine **Abschluss-Checkliste**, die erst abgehakt wird, wenn die Kompetenz nachweisbar sitzt. Der Ton ist der eines institutionellen Research-Hauses: präzise, nüchtern, fordernd — aber begehbar.

---

## Wie diese Roadmap funktioniert

- **Reihenfolge ist nicht verhandelbar.** Jede Phase setzt die vorige voraus. Wer im Risk-Management scheitert, scheitert, weil er die Regime-Lektion übersprungen hat.
- **Paper first.** Bis Phase 4 wird ausschließlich auf Papier/Simulation gearbeitet. Echtes Kapital ist eine Konsequenz nachgewiesener Disziplin, kein Startpunkt.
- **Jede Übung ist messbar.** Eine Checkbox darf nur abgehakt werden, wenn ein konkretes, überprüfbares Artefakt vorliegt (ein Screenshot, eine Notiz mit Zahlen, ein abgeschlossener Paper-Trade).
- **Mode-Disziplin.** Phasen 1–3 finden überwiegend im **Simple Mode** statt; der **Developer Mode** wird erst in Phase 4 zur Heimat.

### Reifegrad-Übersicht

| Phase | Woche | Rolle | Modus | Leitfrage |
|---|---|---|---|---|
| 1 | 1–2 | **Der Observer** | Simple | „Was für ein Markt ist das gerade?" |
| 2 | 3–4 | **Der Strategie-Architekt** | Simple → Dev | „Habe ich einen echten Edge oder nur ein Muster?" |
| 3 | 5–6 | **Der Risk Manager** | Dev | „Überlebt mein Buch den schlechten Monat?" |
| 4 | 7+ | **Der Schwarm-Commander** | Dev (voll) | „Läuft das System autonom — und kontrolliere ich es?" |

---

# Phase 1 — Der Observer (Woche 1–2)

> **Mission:** Lernen, den Markt zu *lesen*, bevor man ihn handelt. Ein Observer fasst nichts an; er beobachtet, klassifiziert und delegiert. Am Ende dieser Phase versteht der Nutzer das „Marktwetter" und hat seine ersten Paper-Trades laufen — ohne je eine Strategie selbst gebaut zu haben.

## Lernziele

1. **Die vier Regime sicher erkennen.** Den Unterschied zwischen 🟢 *Low Vol · Trending*, 🔴 *High Vol · Trending*, 🟠 *High Vol · Choppy* und ⚪ *Low Vol · Quiet* an Farbe **und** Begründung benennen können.
2. **Das Dashboard lesen.** Lebenszyklus-Buckets (`validated`, `candidate`, `testing`, `overlay`, `deferred`, `done`, `rejected`), Sharpe-Verteilung und Top-Strategien interpretieren.
3. **Den Unterschied Alpha vs. Beta verbal erklären.** Warum „immer long" kein Edge ist.
4. **Delegieren statt selbst handeln.** Im Swarm Command Center einen Strategie-Vorschlag verstehen und per Paper bestätigen.

## Theorie-Fundament (lesen, nicht überspringen)

- Handbuch **Kapitel 1** (Philosophie) — besonders 1.3 (Edge, Alpha, Beta) und 1.4 (Mensch konfiguriert, KI führt aus).
- Handbuch **Kapitel 3** (Wetter-Radar), Abschnitte 3.1–3.2.
- Konzept-Merksatz: *Volatilität = wie aufgeregt; Trend = ob es irgendwohin geht.* Das Kreuz dieser zwei Achsen ergibt die vier Regime.

## System-Übungen

| # | Übung | Route | Erwartetes Artefakt |
|---|---|---|---|
| 1.1 | Schalte in den **Simple Mode** (Toggle oben rechts) und mache dich mit den fünf Entscheidungs-Screens vertraut. | global | Notiz: die fünf sichtbaren Screens benennen. |
| 1.2 | Öffne das **Weather Radar** und notiere das aktuelle Regime eines Index (z. B. S&P 500) inkl. Farbe und Richtung (bull/bear/neutral). | `/radar` | Screenshot + ein Satz Klartext-Lesart. |
| 1.3 | Wechsle das Asset (z. B. Gold, Bitcoin) und vergleiche die Regime. Identisches Datum, unterschiedliches Wetter — warum? | `/radar` | Tabelle: 3 Assets × Regime. |
| 1.4 | Öffne das **Research Dashboard** und ordne 5 Strategien ihren Lebenszyklus-Buckets zu. | `/` (Dev kurz an) | Liste: 5 Strategien → Bucket. |
| 1.5 | Öffne das **Swarm Command Center**, löse eine Schwarm-Runde aus und lies das Commander-Urteil (welche Strategien ACTIVE, welches Gewicht, welche Begründung). | `/swarm` | Notiz: das Verdikt in eigenen Worten. |
| 1.6 | Starte **zwei Paper-Trades** entsprechend dem Swarm-Vorschlag. Nicht eingreifen. | `/live` | Zwei offene Paper-Positionen. |

## Häufige Anfängerfehler (und ihre Korrektur)

- **„Rot heißt verkaufen."** Falsch. 🔴 *High Vol · Trending* kann ein starker **Aufwärtstrend** sein (Richtung = bull). Farbe = Vola×Trend, nicht Kauf/Verkauf. Immer die Richtung mitlesen.
- **„Hoher Sharpe = gute Strategie."** Nicht ohne Kontext: Bucket `rejected` mit Sharpe 2 ist abgelehnt, weil der Wert ein Artefakt war. Bucket vor Zahl lesen.
- **Overtrading aus Langeweile.** Ein Observer, der nach drei Tagen „etwas tun will", hat die Phase nicht verstanden. Beobachten *ist* die Arbeit.

## Abschluss-Checkliste Phase 1

- [ ] Ich kann die vier Regime an Farbe und Beschreibung benennen.
- [ ] Ich verstehe, warum dasselbe Datum auf zwei Assets unterschiedliche Regime zeigt.
- [ ] Ich kann in einem Satz erklären, warum „immer long sein" (Beta) kein Edge (Alpha) ist.
- [ ] Ich habe ein Swarm-Verdikt gelesen und in eigenen Worten zusammengefasst.
- [ ] Ich habe zwei Paper-Trades laufen und greife nicht ein.
- [ ] Ich kenne die fünf Simple-Mode-Screens auswendig.

---

# Phase 2 — Der Strategie-Architekt (Woche 3–4)

> **Mission:** Vom Beobachter zum Hypothesen-Bauer. Der Architekt formuliert eine ökonomische These, kombiniert Signale (Saisonalität + COT) und — entscheidend — lernt, ein *hübsches Muster* von einem *echten Edge* zu unterscheiden. Hier beginnt der behutsame Übergang in den Developer Mode.

## Lernziele

1. **Eine ökonomische Hypothese formulieren.** Keine Strategie ohne Makro-Begründung (Hard Rule).
2. **COT-Daten lesen.** Commercials (Smart Money) vs. Managed Money; COT-Index 0–100 und den 3-Jahres-Z-Score interpretieren; Overcrowded-Extreme ($|z| > 2$) erkennen.
3. **Saisonalität auf Signifikanz prüfen.** Den p-Wert, das Bootstrap-Konfidenzintervall und den DSR als Trio verstehen — und die **richtige Nullhypothese** wählen.
4. **Signale kombinieren.** Eine einfache These bauen, die zwei unabhängige Spione verknüpft (z. B. „Saison-Long nur, wenn Commercials nicht overcrowded short").

## Theorie-Fundament

- Handbuch **Kapitel 4** vollständig (COT & Saisonalität).
- Handbuch **Kapitel 1.2** (die vier Hard Rules) — jetzt als Bauanleitung lesen.
- Merksatz zur Signifikanz: *Ein Durchschnitt ist eine Behauptung; p-Wert, Bootstrap und DSR sind der Beweis.*

## Die zentrale Lektion dieser Phase: Skill ≠ Ökonomie

Es gibt **zwei** verschiedene Tests, die oft verwechselt werden:

| Test | Frage | Werkzeug |
|---|---|---|
| **Schlägt es Zufall?** (Skill) | Trägt das *Timing*, oder ist es Glück? | Permutation gegen Zufalls-Timing |
| **Schlägt es Buy & Hold?** (Ökonomie) | Lohnt sich der Aufwand gegenüber „kaufen und halten"? | Vergleich gegen die richtige Benchmark |

Eine Strategie kann **echtes Skill** haben (schlägt Zufalls-Timing, p < 0,05) und trotzdem **B&H nicht schlagen** — dann ist sie bestenfalls ein Overlay-/Timing-Bein, kein Standalone. Diese Unterscheidung ist die teuerste Lektion des gesamten Forschungskatalogs. Wer sie verinnerlicht, ist kein Anfänger mehr.

## System-Übungen

| # | Übung | Route | Erwartetes Artefakt |
|---|---|---|---|
| 2.1 | Öffne **COT Positioning** und finde die drei Märkte mit dem extremsten Commercial-Z-Score. Sind sie net-long oder net-short overcrowded? | `/cot` | Tabelle: 3 Märkte, $z$, Bias. |
| 2.2 | Wähle einen Markt mit COT-Index ≥ 80 oder ≤ 20 und formuliere die contrarian-Lesart in einem Satz. | `/cot` | Ein-Satz-These. |
| 2.3 | Öffne **Seasonal**, wähle ein Kalendermuster und lies die drei Signifikanz-Stempel: p-Wert, Bootstrap-CI, DSR. | `/seasonal` | Notiz: alle drei Werte + Ampel (grün/rot). |
| 2.4 | Finde ein Muster, das einen **hohen Durchschnitt, aber ein CI mit 0** zeigt. Erkläre, warum es *kein* Lead ist. | `/seasonal` | Begründung in 2 Sätzen. |
| 2.5 | Formuliere eine **kombinierte Hypothese** (Saison + COT-Filter) als Klartext-Steckbrief: Universum, Entry, Exit, ökonomische Begründung. | Notiz / `/factory` | Steckbrief (4 Felder). |
| 2.6 | Lass die **Alpha Factory** deine Hypothese gegen die Regime-Matrix prüfen: In welchen Regimen ist sie `allowed`? | `/factory` | Liste `allowed_market_regimes`. |
| 2.7 | (Dev) Sieh dir einen bestehenden `strategies/NNNN_name/REPORT.md` an und identifiziere die vier Pflichtläufe (Kosten, Permutation, Bootstrap, DSR). | Repo | Notiz: die vier Läufe im Report finden. |

## Worauf der Architekt achten muss

- **Multiples Testen.** Wer 20 Saisonfenster scannt und das beste nimmt, hat fast garantiert ein Artefakt. Der DSR bestraft genau das — vertraue ihm.
- **Die richtige Nullhypothese.** Bei Saison-Long auf einem driftenden Index ist die Null *Zufalls-Long-Tage*, nicht 0. Sonst misst man Beta und nennt es Edge.
- **Roll-Tag-Falle bei Futures.** Ein Saison-Edge auf Erdgas/Öl muss das Entfernen einer Zone um jeden Verfallstag überleben (siehe Handbuch 4.2).

## Abschluss-Checkliste Phase 2

- [ ] Ich kann Commercials und Managed Money unterscheiden und ihre Rollen erklären.
- [ ] Ich kann COT-Index und Z-Score lesen und ein Overcrowded-Extrem ($|z|>2$) benennen.
- [ ] Ich verstehe p-Wert, Bootstrap-CI und DSR und weiß, wann ein Muster *trotz* schönem Durchschnitt verworfen wird.
- [ ] Ich kann den Unterschied „schlägt Zufall" vs. „schlägt Buy & Hold" erklären.
- [ ] Ich habe eine kombinierte Hypothese als 4-Feld-Steckbrief formuliert.
- [ ] Ich habe die vier Pflichtläufe in einem echten REPORT.md gefunden.

---

# Phase 3 — Der Risk Manager (Woche 5–6)

> **Mission:** Vom Edge zum **Buch**. Eine einzelne gute Strategie macht keinen Hedgefonds — ein robust diversifiziertes, risikolimitiertes Portfolio schon. Der Risk Manager lernt, Korrelationen zu lesen, Verlustgrenzen zu setzen und Kapital intelligent zu allokieren. Diese Phase findet vollständig im **Developer Mode** statt.

## Lernziele

1. **Die Korrelationsmatrix interpretieren.** Erkennen, wann „Diversifikation" nur eine Illusion ist (versteckte gemeinsame Faktoren).
2. **VaR und ES verstehen.** Den Unterschied zwischen „ab wann wird es schlimm" (VaR) und „wie schlimm im Tail" (ES) — und warum ES bei Short-Vol das letzte Wort hat.
3. **Verlustlimits setzen.** Das Buch gegen einen Tages-Drawdown und einen maximalen Drawdown verteidigen.
4. **Allokation optimieren.** Equal-Weight, MVO und HRP vergleichen — und verstehen, warum HRP out-of-sample gewinnt.

## Theorie-Fundament

- Handbuch **Kapitel 6** vollständig (VaR, ES, Korrelation, HRP).
- Merksatz: *Den Gewinn macht der Edge — überleben tut man durch das Risikomanagement.*

## Die drei Allokationsmodelle im direkten Vergleich

| Modell | Idee | Stärke | Schwäche |
|---|---|---|---|
| **Equal-Weight (1/N)** | Jedem Sleeve gleich viel Kapital. | Robust, keine Schätzung nötig; die ehrliche Benchmark. | Ignoriert Risiko & Korrelation; konzentriert Risiko in korrelierten Sleeves. |
| **Mean-Variance (MVO)** | Sharpe-optimales Tangentialportfolio. | Theoretisch optimal bei *bekannten* Momenten. | Braucht Kovarianz-Inversion → fragil, extreme Gewichte, OOS-Kollaps. |
| **Hierarchical Risk Parity (HRP)** | Korrelations-Hierarchie clustern, Kapital invers zur Cluster-Varianz verteilen. | Keine Inversion → robust; respektiert Faktorstruktur. | Etwas komplexer; nicht „Sharpe-maximal" auf dem Papier. |

**Die Schlüsselerkenntnis:** MVO sieht in-sample am besten aus und ist out-of-sample am schlechtesten — weil die Kovarianz-Inversion Schätzfehler maximiert. HRP gibt einen Bruchteil des theoretischen Optimums auf und gewinnt dafür Stabilität. Jeder Optimierer muss zudem **1/N schlagen**, sonst ist die Komplexität nicht gerechtfertigt.

## System-Übungen

| # | Übung | Route | Erwartetes Artefakt |
|---|---|---|---|
| 3.1 | Öffne das **Risk Desk** und lies die Portfolio-Kennzahlen: annualisierte Vola, Rendite, Sharpe. | `/risk` | Notiz: die drei Werte. |
| 3.2 | Lies die **VaR/ES-Matrix** (95 %/99 % × 1 Tag/10 Tage). Übersetze den 95 %-1-Tages-VaR in einen Euro-Betrag bei gegebenem Kapital. | `/risk` | Rechnung: VaR % → € . |
| 3.3 | Öffne die **Korrelationsmatrix**. Finde zwei Sleeves mit Korrelation > 0,6 — sie sind *keine* echten Diversifikatoren. | `/risk` | Paar + Korrelationswert. |
| 3.4 | Identifiziere über die **Risikobeitrags-Tabelle** (Euler-Zerlegung) ein Sleeve, das auf kleinem Gewicht überproportional Risiko frisst (`pct` ≫ `weight`). | `/risk` | Sleeve + Gewicht vs. Risikoanteil. |
| 3.5 | Vergleiche die Allokationen **Equal-Weight, MVO, HRP** für dasselbe Buch. Wo konzentriert MVO, wo verteilt HRP? | `/risk` | Tabelle: 3 Modelle × Gewichte. |
| 3.6 | Lies die **Diversifikationsratio** und den Nutzen. Was bedeutet ein DR nahe 1? | `/risk` | Ein-Satz-Interpretation. |
| 3.7 | Setze für dein Paper-Buch ein **Max-Drawdown-Limit** (z. B. 10 %) und prüfe im Switchboard, ob die aktiven Sleeves dazu passen. | `/switchboard` | Notiz: Limit + qualifizierte Sleeves. |

## Worauf der Risk Manager achten muss

- **Korrelation springt im Stress.** Die rollende Korrelation (90 Tage) zeigt, ob die Diversifikation *bleibt*. Sleeves, die normalerweise unkorreliert sind, aber im Crash gemeinsam fallen, sind die gefährlichsten.
- **Short-Vol ist ein Sonderfall.** Sharpe und DSR belohnen Vola-Verkauf, sehen aber den −34 %-Tag nicht. Bei solchen Strategien entscheidet **ES / MaxDD / Kurtosis**, nicht Sharpe.
- **Hebel ist nicht Diversifikation.** Ein hoher Drawdown durch Aufpyramidieren/Hebel ist ein Sizing-Problem, kein Strukturproblem — und durch lineares Down-Sizing exakt heilbar (der Edge bleibt invariant).

## Abschluss-Checkliste Phase 3

- [ ] Ich kann VaR und ES definieren und den 95 %-VaR in einen Euro-Betrag übersetzen.
- [ ] Ich erkenne in einer Korrelationsmatrix versteckte gemeinsame Faktoren.
- [ ] Ich kann mit der Risikobeitrags-Tabelle ein risikofressendes Sleeve identifizieren.
- [ ] Ich kann erklären, warum HRP out-of-sample MVO und 1/N schlägt.
- [ ] Ich habe ein Max-Drawdown-Limit für mein Paper-Buch gesetzt.
- [ ] Ich verstehe, warum ES bei Short-Vol das Sharpe-Urteil dominiert.

---

# Phase 4 — Der Schwarm-Commander (Woche 7+)

> **Mission:** Volle Kontrolle. Der Schwarm-Commander steigt vollständig in den Developer Mode ein, steuert die lokalen KI-Drohnen, betreibt factor-getriebenes Backtesting und überwacht die Live-Execution. Ab hier ist der Nutzer kein Lernender mehr, sondern der Operator eines halb-autonomen Desks.

## Lernziele

1. **Den Agentenschwarm steuern.** Lokale Ollama-Drohnen konfigurieren, den Gemini-Commander (mit Fallback-Kette) betreiben und das Zusammenspiel verstehen.
2. **Den Dynamic Strategy Router beherrschen.** Verstehen, wie der Router bei einem Regime-Wechsel automatisch Sleeves aktiviert/pausiert (`activated`/`deactivated`).
3. **Factor-driven Backtesting.** Eigene Hypothesen über die `quantlab`-Bibliothek bauen, validieren und in den Katalog überführen.
4. **Live-Execution überwachen.** Das Live Book, die Tickets und das Ledger lesen; verstehen, warum **kein LLM im Order-Pfad** sitzt.

## Theorie-Fundament

- Handbuch **Kapitel 5** vollständig (Schwarm & Router).
- Handbuch **Kapitel 2.2–2.3** (Developer Mode, Backtest-Ordner, BYOK).
- Anhang B (Modul-Landkarte) — ab jetzt das tägliche Nachschlagewerk.

## Die Schwarm-Architektur in der Praxis

```
   Drohnen (lokal, Ollama llama3) ── je 1 Signal ──┐
        Regime · Saison · COT                        │ aggregiert
                                                      ▼
   Commander (Gemini 2.5-flash → 2.0-flash)  ── ACTIVE/PAUSED + Gewicht
        │ 429/503 → Backoff → Modellwechsel
        │ alles aus → deterministischer Fallback (regelbasiert)
        ▼
   Dynamic Strategy Router (build_router)
        │ detect_switch:  Regime gewechselt?
        │ live_switch_delta: welche Sleeves flippen?
        ▼
   Live Book (human-in-the-loop Fills)
```

**Was der Commander wirklich tut:** Er routet **nicht** nach einer blanken Top-Sharpe-Liste, sondern nach **regime-konditionaler Evidenz**. Jede Strategie kommt mit ihrem `regime_status` (ACTIVE/PAUSED aus echtem Conditional-Backtesting), ihren `allowed_regimes` und ihrem Sharpe *im aktuellen* Regime. Eine im aktuellen Regime nicht qualifizierte (PAUSED) Strategie wird nur dann aktiviert, wenn die Drohnen es klar rechtfertigen — und das muss begründet werden.

## System-Übungen

| # | Übung | Route / Ort | Erwartetes Artefakt |
|---|---|---|---|
| 4.1 | Stelle sicher, dass der lokale **Ollama-Server** läuft (Modell `llama3`) und im Swarm-Screen als erreichbar gemeldet wird. | `/swarm` | Status: Drohnen „done", Modell genannt. |
| 4.2 | Hinterlege deinen **Gemini-Key** im verschlüsselten Tresor (Settings) und entsperre ihn mit dem Master-Passwort. | `/settings` | Vault entsperrt, `gemini` gelistet. |
| 4.3 | Löse eine **volle Schwarm-Runde** aus. Stammt das Verdikt von `gemini` oder vom `deterministic`-Fallback? Warum? | `/swarm` | Notiz: `source` + Grund. |
| 4.4 | Provoziere einen **Regime-Wechsel** (anderer Benchmark/Zeitraum) und beobachte im Router das `switch_delta`: welche Sleeves `activated`/`deactivated`. | `/switchboard` | Liste der geflippten Sleeves. |
| 4.5 | Baue im **Developer Mode** eine eigene Strategie (`strategies/NNNN_name/run.py`) mit `quantlab`. Führe die vier Pflichtläufe aus. | Repo + `/` | `REPORT.md` + `metrics.json`. |
| 4.6 | Lass die **Alpha Factory** die Regime-Behauptung deiner neuen Strategie gegen die realisierte, regime-geschnittene Performance prüfen. | `/factory` | `allowed_market_regimes` vs. Behauptung. |
| 4.7 | Überwache im **Live Book** ein Ticket über mehrere Tage und logge einen (Paper-)Fill über das Ledger. | `/live` | Ledger-Eintrag. |
| 4.8 | (Optional, fortgeschritten) Starte den **Evolution Monitor** und beobachte, wie der genetische Optimierer mit IS/OOS-Overfit-Schutz arbeitet. | `/optimize` | Notiz: Haircut-Flag erkannt. |

## Operator-Disziplin (die Verantwortung des Commanders)

- **Kein LLM im Order-Pfad.** Der Schwarm *entscheidet das Routing*, aber die Ausführung bleibt deterministisch und human-in-the-loop. Ein LLM darf nie direkt eine Order auslösen. Diese Grenze ist nicht verhandelbar.
- **Fallbacks sind Features, keine Fehler.** Wenn der deterministische Commander übernimmt (Gemini-Quota erschöpft), ist das System *by design* weiter handlungsfähig. Prüfe das Verdikt — es ist transparent regelbasiert.
- **Regime-Status ist ein starkes Prior.** Übersteuere die regime-konditionale Evidenz nur mit einer dokumentierten Begründung. Der häufigste Operator-Fehler ist, eine Lieblingsstrategie gegen ihren PAUSED-Status zu erzwingen.
- **BYOK-Hygiene.** Master-Passwort niemals im Repo; Keys nur im Tresor; bei Verdacht auf Kompromittierung Tresor neu anlegen und Keys rotieren.

## Abschluss-Checkliste Phase 4

- [ ] Mein lokaler Ollama-Schwarm läuft und meldet sich erreichbar.
- [ ] Mein Gemini-Key liegt im verschlüsselten Tresor und ist entsperrbar.
- [ ] Ich verstehe, wann das Verdikt von Gemini vs. vom deterministischen Fallback stammt.
- [ ] Ich kann einen Regime-Wechsel auslösen und das `switch_delta` lesen.
- [ ] Ich habe eine eigene Strategie gebaut, die alle vier Pflichtläufe besteht.
- [ ] Ich überwache ein Live-Ticket und logge Fills über das Ledger.
- [ ] Ich kann erklären, warum kein LLM im Order-Pfad sitzt — und halte mich daran.

---

## Nach Phase 4: Der kontinuierliche Kreislauf

Der Schwarm-Commander ist kein Endzustand, sondern der Beginn eines Kreislaufs, der das institutionelle Research-Haus ausmacht:

```
   Hypothese  →  Validierung (Permutation/Bootstrap/DSR)  →  Risiko-Integration (HRP/ES)
       ▲                                                              │
       │                                                              ▼
   Katalog-Lernen  ←  Live-Forward & Attribution  ←  Regime-konditionales Routing
```

Jede abgelehnte Strategie ist so wertvoll wie eine angenommene — sie verfeinert das Verständnis, *wo* Edges leben (niederfrequenter, institutionell erzwungener Flow) und *wo* nicht (intraday-Richtung eines liquiden Einzelmarktes nach Kosten). Der reife Operator misst seinen Fortschritt nicht an der Zahl der Strategien, sondern an der **Schärfe seiner Reject-Begründungen**.

---

## Schnellreferenz — Routen nach Phase

| Phase | Primäre Routen | Modus |
|---|---|---|
| 1 — Observer | `/radar`, `/swarm`, `/live`, `/cot`, `/seasonal`, `/` | Simple |
| 2 — Architekt | `/cot`, `/seasonal`, `/factory` | Simple → Dev |
| 3 — Risk Manager | `/risk`, `/switchboard` | Dev |
| 4 — Commander | `/swarm`, `/switchboard`, `/optimize`, `/live`, `/settings`, Repo | Dev (voll) |

---

*Ende der Roadmap. Das technische Begleitdokument ist `QUANT_OS_HANDBUCH.md`. Beide Dokumente liegen unter `D:\Backtests\docs\`.*
