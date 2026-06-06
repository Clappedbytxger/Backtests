# Framework: Eine prop-kompatible Edge finden

> Ziel dieses Dokuments: ein vollständiger Such- und Validierungsprozess für eine Strategie, die unter Prop-Regeln (5 % Tages-, 10 % Gesamt-Drawdown, Mindesthandelstage, ggf. Konsistenzregel) *überleben* kann. Es ist kein fertiger Edge — es ist die Methode, einen zu finden, ohne dich selbst zu betrügen. Es baut direkt auf deiner bestehenden Pipeline (Permutation, OOS, Bootstrap-KI, DSR, Roll-Check) auf und ergänzt sie um die prop-spezifischen Schritte, die dir bisher fehlen.
>
> Keine Anlageberatung. Alles unten sind *Hypothesen zum Testen*, keine Empfehlungen.

---

## Teil 0 — Das Designziel rückwärts ableiten

Der entscheidende Denkfehler wäre, „eine profitable Strategie" zu suchen und dann zu hoffen, dass sie die Regeln einhält. Richtig herum: **Die Prop-Regeln definieren die *Form* der Equity-Kurve, die du brauchst. Daraus leitest du den Steckbrief der Edge ab — und suchst nur danach.**

Aus den Regeln folgen vier harte Designvorgaben:

**1. Winziges Risiko pro Trade.** Bei 10 % Gesamt-Drawdown willst du, dass selbst eine normale Verlustserie weit innerhalb der Grenze bleibt. Eine 7er-Verlustserie tritt bei ~50 % Trefferquote mit ~0,8 % Wahrscheinlichkeit auf — sie *wird* passieren. Bei 0,5 % Risiko/Trade sind das 3,5 % Drawdown, bei 0,25 % nur 1,75 %. → **Zielkorridor: 0,25–0,5 % Konto-Risiko pro Trade.** Das ist nicht vorsichtig, das ist Überlebensbedingung.

**2. Kurze Haltedauer.** Übernacht-Gaps sind unkontrollierbar und reißen bei *trailing intraday*-Drawdown sofort. → **Intraday oder kurzes Swing (Stunden bis 1–2 Tage), bevorzugt flat über Nacht und übers Wochenende.** Das eliminiert die gefährlichste Drawdown-Quelle komplett.

**3. Genug Frequenz.** Drei Gründe gleichzeitig: (a) Mindesthandelstage erfüllen, (b) zum Gewinnziel (~8–10 %) compounden bei 0,5 %-Risiko-Schritten, (c) genug Trades für statistische Aussagekraft. Deine Saisonstrategie mit ~4 Trades/Jahr scheitert an allen dreien. → **Ziel: mehrere Trades pro Woche, idealerweise täglich.**

**4. Glatte Equity-Kurve.** Konsistenzregeln und trailing-Drawdown bestrafen Lumpigkeit. Eine Edge, deren Gewinn von wenigen Fat-Tail-Tagen abhängt (wie dein Kaffee-Frost 0027), ist hier *doppelt* gefährlich: ein Riesentag verletzt die Konsistenzregel, ein Fat-Tail-*Verlust* reißt das Limit. → **Du brauchst hohen Sharpe durch *viele kleine* Gewinne, nicht durch seltene große.** Das ist das Gegenteil deines bisherigen Profils.

**Der Edge-Steckbrief, nach dem du suchst:** hoher Sharpe (>1,5 angestrebt, glatt), kurze Haltedauer, hohe Frequenz, kleines Risiko/Trade, in einem **liquiden, günstigen Markt**.

---

## Teil 1 — Worauf eine Edge basieren kann (die vier Bausteine)

Jede systematische Edge nutzt eines von wenigen *persistenten* Marktphänomenen aus. Für den Intraday-/Kurzhalte-Kontext sind das vier — jeweils mit der ökonomischen Ursache (deine Stärke: nie ohne „Warum"), dem Ort und der Prop-Eignung.

### 1. Mean-Reversion (Liquiditätsbereitstellung / Überreaktion faden)
- **Warum es existiert:** Kurzfristige Preisbewegungen überschießen, weil Liquidität abgezogen wird oder Stops/Margin-Calls kaskadieren. Wer in dem Moment Liquidität *bereitstellt*, wird für das Risiko bezahlt.
- **Wo intraday:** Aktienindex-Futures zeigen intraday in vielen Regimes Reversion (anders als Krypto — dort *kontinuieren* Extreme, das hast du in 0013 selbst gemessen). Opening-Range-Fade, VWAP-Reversion, Gap-Fill am Open.
- **Prop-Eignung: sehr gut.** Viele kleine Gewinne, hoher Sharpe, glatte Kurve → passt zu Konsistenzregeln.
- **Vorsicht:** Reversion hat fette linke Tails (man fadet einen Move, der *weiterläuft*). Harte Stops sind Pflicht — sonst wird aus „viele kleine Gewinne" ein Konto-Killer.

### 2. Momentum / Continuation (Unterreaktion / Trendpersistenz)
- **Warum es existiert:** Information wird langsam eingepreist; Trend-Tage haben Folgebewegung.
- **Wo intraday:** Opening-Range-Breakout, Trend-Day-Capture.
- **Prop-Eignung: mittel.** Niedrigere Trefferquote, größere Gewinner → lumpiger, kann mit Konsistenzregeln kollidieren, wenn ein Tag dominiert. Mit Mini-Risiko aber machbar.
- **Vorsicht:** Unterscheide echtes Momentum von reiner Long-Beta. In deinem BTC-0015-Test war der „Nachmittags-Effekt" nur das immer-long-Beta, kein Signal — derselbe Fehler lauert intraday überall.

### 3. Strukturell / Kalendarisch (Time-of-Day, Session, Event)
- **Warum es existiert:** Wiederkehrende Fluss-Muster (Eröffnungsauktion, Lunch-Flaute, Schluss-Auktion/Index-Rebalancing-Flows, geplante Releases).
- **Wo intraday:** Letzte-Stunde-Drift, Lunch-Reversion, Verhalten um geplante Wirtschaftsdaten.
- **Prop-Eignung: gut**, weil zeitlich exakt definierbar und damit testbar wie deine Saisonfenster — nur viel häufiger.
- **Vorsicht:** Event-Volatilität (NFP, CPI, FOMC) hat hohe Varianz → gefährlich für Tages-Drawdown. Eher das *Abklingen* nach dem Release handeln als den Release selbst.

### 4. Relational (Lead-Lag / Pairs / Basis)
- **Warum es existiert:** Verwandte Instrumente bewegen sich nicht perfekt synchron; temporäre Dislokationen mean-reverten.
- **Wo intraday:** ES↔NQ relative Stärke, Future↔ETF-Basis, sektor-interne Paare.
- **Prop-Eignung: gut** (marktneutral → geringeres Tail-Risiko), aber datenintensiv und kostensensitiv (zwei Beine = doppelte Kosten).
- **Vorsicht:** Kointegration kann brechen (Regimewechsel). Braucht Stabilitäts-Monitoring.

---

## Teil 2 — Markt- und Instrumentenwahl (zuerst!)

Deine wichtigste eigene Lektion: **Kosten sind bei höherer Frequenz die bindende Grenze, nicht die Richtung** (BTC 0012–0015, dreimal in Folge an den Kosten gescheitert). Also wird die Marktwahl *vor* der Strategiesuche entschieden.

Kriterien: hohe Liquidität, enge Spreads, niedrige Kommission, durchgehende Handelszeiten, prop-handelbar.

Geeignete Kandidaten (Micro-Futures halten das Risiko pro Trade klein genug):
- **Micro E-mini S&P 500 (MES)** — $5 × Index, extrem liquide, Tick = $1,25.
- **Micro E-mini Nasdaq-100 (MNQ)** — $2 × Index, sehr liquide, höhere Vola (mehr Bewegung pro Trade).
- **Micro Gold (MGC)** — 10 oz, liquide.
- **Micro FX (z. B. M6E EUR/USD)** — sehr enge Spreads, günstig.

Meide für den Anfang: illiquide Commodities, exotische Kontrakte, alles mit weiten Spreads — genau die Falle, in der deine BTC-Tests starben.

**Schritt 0 jeder Suche: das Kostenmodell.** Bevor du *irgendeinen* Backtest startest, modelliere Kommission + Spread + realistischen Slippage pro Round-Trip in den Ticks deines Zielmarkts. Der **Brutto-Edge muss die Kosten mit Sicherheitsmarge schlagen** — sonst sofort verwerfen, egal wie schön die Stats aussehen.

---

## Teil 3 — Der Discovery-Workflow (Schritt für Schritt)

Deine bestehende Pipeline bleibt das Rückgrat; **fett = neu** für den Prop-Kontext.

1. **Hypothese mit ökonomischer Ursache.** Kein Blind-Mining. Schreib auf, *warum* der Effekt existieren *sollte* (Liquidität, Fluss, Verhalten). Ohne Ursache = Drift-/Tail-Falle (Lehre aus Kakao/Kaffee).
2. **Kostenmodell zuerst** (Teil 2). Brutto-Edge ≥ Kosten × Sicherheitsfaktor, sonst Stopp.
3. **Look-ahead-Check.** Intraday die größte Falle: handle *niemals* auf dem Schlusskurs derselben Bar, auf der dein Signal entsteht. Entry frühestens nächste Bar/Tick. Ein einziger Look-ahead-Bug erzeugt traumhaft falsche Kurven.
4. **In-Sample-Exploration** auf einem Datenausschnitt; Rest unberührt lassen.
5. **Deine Validierungs-Batterie:** Permutationstest gegen zufälliges Timing → OOS-Split → Walk-Forward → Bootstrap-KI (muss Null ausschließen) → Deflated Sharpe gegen Multiple-Testing.
6. **NEU — Prop-Regel-Simulation.** Spiele die Equity-Kurve *Trade für Trade unter den exakten Firmenregeln* durch: Wird je das Tages- oder Gesamt-Drawdown-Limit (auch *trailing*, inkl. unrealisierter Verluste) verletzt? Konsistenzregel? Mindesthandelstage? Das ist ein eigener Filter — eine Strategie kann profitabel *und* trotzdem prop-untauglich sein.
7. **NEU — Monte-Carlo der Pfade.** Resample/permutiere die Trade-Reihenfolge in tausenden Pfaden und miss: (a) Wahrscheinlichkeit, das Gewinnziel zu erreichen, *bevor* ein DD-Limit reißt (= Pass-Wahrscheinlichkeit), (b) Überlebenswahrscheinlichkeit des Funded-Kontos über 12 Monate. Eine Edge mit positivem Erwartungswert, aber 40 % Ruin-Wahrscheinlichkeit pro Pfad ist nutzlos.
8. **Robustheit:** Parameter-Plateau (nicht Spitze), Regime-Splits, Transaktionskosten-Stress (deine 0037-Methode).

---

## Teil 4 — Prop-spezifische Metriken (zusätzlich zu deinem Katalog)

Sharpe/CAGR/MaxDD/p-Wert/DSR reichen nicht. Ergänze pro Kandidat:

| Metrik | Warum |
| --- | --- |
| Worst peak-to-trough auf *trailing*-Basis | Das ist, was die Firma misst — nicht statischer MaxDD |
| Verteilung des schlechtesten Einzeltags | Gegen das Tageslimit (5 %) prüfen |
| Verteilung der längsten Verlustserie | Bestimmt das maximale Risiko/Trade |
| Größter Tag als % des Gesamtgewinns | Konsistenzregel (z. B. < 30–40 %) |
| Time-to-Target-Verteilung + Pass-% | Aus Monte-Carlo (Teil 3.7) |
| Recovery Factor / Ulcer Index | Glätte der Kurve |

**Die Schlüssel-Kennzahl ist nicht die Rendite, sondern die Pass-/Überlebenswahrscheinlichkeit unter den Regeln.**

---

## Teil 5 — Konkrete Edge-Hypothesen zum Testen (priorisiert)

Antwort auf „worauf kann sie basieren" — konkret und prop-tauglich sortiert. Alles **Startpunkte zum Validieren**, größtenteils teilweise wegkonkurriert; der Wert liegt in deinem sauberen Test.

1. **Aktienindex-Intraday-Mean-Reversion / Opening-Range-Fade (MES/MNQ).** Ökonomie: Liquiditätsbereitstellung + intraday Überreaktion. Profil: viele kleine Gewinne, glatt → bestes Konsistenz-/Drawdown-Fit. *Höchste Priorität.*
2. **Gap-Fill-Fade am Open ohne Übernacht-Halten.** Ökonomie: Übernacht-Gaps tendieren intraday zur Schließung. Umgeht Übernacht-Drawdown komplett.
3. **Time-of-Day-Effekte (Lunch-Reversion, Schluss-Stunde-Drift).** Strukturell, zeitlich exakt testbar — wie deine Saisonfenster, nur täglich.
4. **Opening-Range-Breakout-Continuation an Trend-Tagen (MES/MNQ).** Momentum; lumpiger → striktes Risiko, evtl. mit Vola-Regimefilter.
5. **ES↔NQ relative-value / Lead-Lag intraday.** Marktneutral → geringeres Tail-Risiko; datenintensiv.
6. **Post-Release-Stabilisierung um geplante Daten.** Das *Abklingen* der Vola handeln, nicht den Release. Vorsicht: hohe Varianz.
7. **FX-Session-Edges (London-/NY-Open auf M6E).** Liquide, günstig.

Sortierkriterium: Prop-Kompatibilität × Zugänglichkeit. Punkt 1–3 sind am ehesten regelkonform; 6 ist am gefährlichsten für den Tages-Drawdown.

---

## Teil 6 — Anti-Selbstbetrugs-Checkliste (deine Lektionen, festgehalten)

- **Kosten = bindende Grenze** (BTC). Brutto-Edge muss Kosten klar schlagen, sonst tot.
- **Look-ahead-Bias** ist intraday die häufigste Quelle gefälschter Kurven. Nie auf der Signal-Bar handeln.
- **Beta-Maskerade** (BTC 0015): Prüfe, ob dein „Edge" nur die immer-long-Drift des Markts ist. Long-only-Bias entlarven.
- **Fat-Tail-Abhängigkeit** (Kaffee 0027): Im Prop-Kontext doppelt verboten — verletzt Konsistenz *und* riskiert DD-Bruch. Median-Trade muss positiv sein, nicht nur der Mittelwert.
- **Session-Boundary-Artefakte:** Das Intraday-Äquivalent deines Roll-Checks — prüfe, ob der Edge nur an Auktions-/Session-Übergängen sitzt (oft nicht handelbar).
- **Multiple Testing → Deflated Sharpe.** Je mehr Hypothesen, desto mehr Glückstreffer.
- **Drift-Falle:** Bei trendendem Markt sieht fast jedes Long-Fenster grün aus → Permutationstest gegen zufälliges Timing ist Pflicht (genau wie bei deinen Saisoneffekten).

---

## Teil 7 — Realistischer Pfad & Erwartung

Sei ehrlich zu dir: Intraday-liquide Edges sind die *härteste* Disziplin, weil dort die meisten und schnellsten Gegner sitzen. Rechne mit **Monaten verworfener Hypothesen** — das ist kein Scheitern, das ist der Prozess (dein Katalog zeigt 30+ Tests für 3 Edges; hier wird das Verhältnis nicht besser). Der Gewinn ist die Methode, nicht der erste Treffer.

Reihenfolge bis zum Funded Account:
1. Markt + Kostenmodell fixieren (Teil 2).
2. Hypothesen aus Teil 5 durch den Workflow (Teil 3) jagen, bis eine *alle* Gates inkl. Prop-Simulation + Monte-Carlo besteht.
3. **6–12 Monate Paper-Trading** der Kandidatin unter exakten Prop-Regeln (viele Firmen/Plattformen bieten Simulatoren).
4. **Micro-Live** in winziger Größe — der echte Test gegen reale Slippage und deine eigene Psyche.
5. **Erst dann** die Challenge — als Monetarisierung einer *bewiesenen* Edge, nicht als Lernumgebung. Erste Challenge-Gebühr als erwartete Lehrkosten budgetieren.

Die Reihenfolge ist nicht verhandelbar: **erst der Beweis, dann das Kapital.** Der Funded Account belohnt nur, was du vorher selbst nachgewiesen hast.

---

*Kein Anlageberatungs-Ersatz. Alle genannten Effekte sind Hypothesen, die du selbst validieren musst; viele sind teilweise wegkonkurriert. Prüfe Kontraktspezifikationen und Firmenregeln stets an der Originalquelle.*
