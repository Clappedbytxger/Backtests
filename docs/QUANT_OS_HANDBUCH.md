# Quant OS — Das Nutzerhandbuch

> **Dokumentklasse:** Produktions-Handbuch · **Adressat:** Nutzer aller Erfahrungsstufen (Investor bis Quant-Entwickler) · **Stand:** 2026-06-25
>
> Dieses Handbuch beschreibt das **Quant OS** — ein KI-gesteuertes, halb-autonomes Trading- und Research-System — so, wie es im Repository `D:\Backtests` tatsächlich implementiert ist. Jede beschriebene Zahl, Schwelle und Formel ist gegen den Quellcode (`src/quantlab/`, `apps/api/`, `apps/web/`) verifiziert. Es gibt keine Platzhalter und keine Funktionen, die nur „geplant" sind, ohne dass dies ausdrücklich gekennzeichnet wird.

---

## Inhaltsverzeichnis

1. [Die Philosophie des systematischen Handels](#kapitel-1--die-philosophie-des-systematischen-handels)
2. [Die Benutzeroberfläche & die zwei Welten (Simple vs. Pro Mode)](#kapitel-2--die-benutzeroberfläche--die-zwei-welten)
3. [Das Wetter-Radar — Market Regime Detection](#kapitel-3--das-wetter-radar--market-regime-detection)
4. [Die Spione im Markt — COT-Daten & Saisonalität](#kapitel-4--die-spione-im-markt--cot-daten--saisonalität)
5. [Der Agentenschwarm & der Dynamic Strategy Router](#kapitel-5--der-agentenschwarm--der-dynamic-strategy-router)
6. [Risikomanagement auf Hedgefonds-Niveau](#kapitel-6--risikomanagement-auf-hedgefonds-niveau)
7. [Anhang A — Glossar](#anhang-a--glossar)
8. [Anhang B — Modul-Landkarte](#anhang-b--modul-landkarte-quantlab)

---

# Kapitel 1 — Die Philosophie des systematischen Handels

## 1.1 Warum die meisten manuellen Trader scheitern

Die oft zitierte Zahl, dass rund 90–95 % der aktiven Privathändler über einen mehrjährigen Horizont Geld verlieren, ist kein Mythos, sondern in Brokerage-Studien und Regulierungsberichten breit dokumentiert. Entscheidend ist die **Ursache**: Das Scheitern ist selten ein Mangel an Information, sondern fast immer ein Versagen der **Verhaltensdisziplin** unter Unsicherheit. Vier kognitive Verzerrungen dominieren:

| Verzerrung | Mechanik | Folge im Handel |
|---|---|---|
| **Verlustaversion** (Kahneman/Tversky) | Ein Verlust schmerzt psychologisch etwa doppelt so stark wie ein gleich großer Gewinn erfreut. | Gewinner werden zu früh realisiert, Verlierer „ausgesessen" — das genaue Gegenteil eines positiven Erwartungswerts. |
| **Dispositionseffekt** | Die Tendenz, gewinnende Positionen zu verkaufen und verlierende zu halten. | Systematisch abgeschnittene rechte Verteilungs-Flanke, verlängerte linke Flanke. |
| **Recency-Bias / Overtrading** | Der jüngste Trade dominiert die Wahrnehmung; nach Verlusten wird „revanchiert". | Positionsfrequenz und -größe entkoppeln sich von der statistischen Grundlage. |
| **Bestätigungsfehler** | Information wird selektiv so interpretiert, dass sie die offene Position stützt. | Stop-Loss-Regeln werden im Moment der Wahrheit aufgeweicht. |

Der gemeinsame Nenner: Jede dieser Verzerrungen wirkt **genau dann am stärksten, wenn am meisten Kapital auf dem Spiel steht** — also exakt im Entscheidungsmoment, in dem ein Mensch sie am wenigsten kompensieren kann.

## 1.2 Wie Quant OS Disziplin *erzwingt*

Quant OS löst dieses Problem nicht durch Appelle an Selbstdisziplin, sondern durch **strukturelle Entkopplung der Entscheidung von der Emotion**. Die Disziplin ist in den Code eingebaut, nicht in den Willen des Nutzers. Konkret durch vier nicht verhandelbare Prinzipien, die im Projekt als „Hard Rules" gelten und in der gesamten Bibliothek durchgesetzt werden:

1. **Kein Look-ahead (Zukunftsblick).** Ein Signal wird zum *Entscheidungszeitpunkt* berechnet; die Backtest-Engine verschiebt es konsequent um einen Bar (T+1-Konvention), sodass niemals Information desselben oder eines künftigen Bars in eine Entscheidung einfließt. Die Regime-Erkennung (`quantlab/regime.py`) ist ausschließlich aus *kausalen*, nachlaufenden Fenstern aufgebaut (rolling/EWM/expanding, keine zentrierten Fenster, kein `shift(-k)`) — ein Eigenschaftstest pinnt diese Kausalität fest.

2. **Kosten werden immer modelliert.** Es wird grundsätzlich **netto** berichtet, nie brutto. Das System kennt explizite IBKR- und CFD-Kostenmodelle (`quantlab/costs.py`). Eine Strategie, deren Bruttoertrag an der Kostenwand verdampft, gilt als abgelehnt — unabhängig davon, wie attraktiv die Bruttozahl aussieht.

3. **Makro-Begründung ist Pflicht.** Jede Strategie braucht eine ökonomische Ursache (Risikoprämie, struktureller Flow, Verhaltensanomalie). Fehlt sie, wird die Strategie als *data-mined* / verdächtig markiert. Ein hoher Sharpe ohne Mechanismus ist ein Warnsignal, kein Kaufsignal.

4. **Statistische Signifikanz statt Anekdote.** Jede Kandidaten-Strategie durchläuft eine Batterie: **Permutationstest** (gegen die passende Nullhypothese), **Bootstrap-Konfidenzintervall**, **Deflated Sharpe Ratio** (DSR, die den Sharpe um die Anzahl getesteter Varianten bestraft) sowie eine getrennte In-Sample/Out-of-Sample-Auswertung. Nur Out-of-Sample-Zahlen werden als belastbar betrachtet.

> **Kernidee.** Disziplin ist hier ein *Eigenschaftsbeweis des Systems*, kein guter Vorsatz des Nutzers. Der Mensch kann eine Regel nicht „im Affekt" aufweichen, weil der Affekt vom Ausführungspfad getrennt ist.

## 1.3 Drei Begriffe, exakt definiert

### Statistischer Edge

Ein **Edge** ist ein positiver Erwartungswert pro Einheit Risiko, der sich **nach Kosten** statistisch vom Zufall unterscheiden lässt. Für eine Strategie mit Gewinnwahrscheinlichkeit $p$, durchschnittlichem Gewinn $W$ und durchschnittlichem Verlust $L$ gilt:

$$\mathbb{E}[R] = p \cdot W - (1-p) \cdot L$$

Ein Edge liegt vor, wenn $\mathbb{E}[R] > 0$ **und** dieser Wert nicht durch eine zufällige Anordnung der Signale reproduzierbar ist. Genau das prüft der Permutationstest: Er würfelt die Eintrittszeitpunkte (oder Labels) tausendfach neu und misst, in welchem Anteil der Zufallsläufe der beobachtete Sharpe erreicht wird — dieser Anteil ist der **p-Wert**. Ein Edge gilt erst als belegt, wenn er die Schwelle (üblich $p < 0{,}05$) übersteht *und* den DSR-Abschlag für die Suchbreite überlebt.

### Alpha (Überrendite)

Zerlegt man die Rendite eines Portfolios $r_p$ in einer Einfaktor-Regression gegen die Marktrendite $r_m$:

$$r_p = \alpha + \beta \, r_m + \varepsilon$$

dann ist **Alpha ($\alpha$)** der Achsenabschnitt — die durchschnittliche Rendite, die *nicht* durch Marktexposure erklärt wird. Alpha ist teuer, knapp und das eigentliche Ziel: Es ist die Bezahlung für *Skill* (richtiges Timing, richtige Selektion). Im Quant-OS-Forschungsprozess ist das entscheidende Werkzeug zum Nachweis von echtem Alpha die **Permutation gegen Zufalls-Timing**: Schlägt eine long-only-Aktienstrategie nur deshalb, weil sie meistens long ist (= Beta), liegt der Zufalls-Long-Sharpe *über* dem der Strategie und der p-Wert geht gegen 1 — das entlarvt verstecktes Beta zuverlässiger als jeder Renditevergleich.

### Beta (Marktrendite)

**Beta ($\beta$)** ist die Sensitivität des Portfolios gegenüber dem Gesamtmarkt — das Maß für reines Markt-Exposure. Beta ist *billig* (über einen ETF nahezu kostenlos zu haben) und keine Leistung. Der häufigste Selbstbetrug im systematischen Handel besteht darin, **Beta als Alpha zu verkaufen**: Eine Strategie, die schlicht den langfristigen Aufwärtsdrift von Aktien einsammelt, sieht im Backtest großartig aus, liefert aber keinen handelbaren Vorteil gegenüber „kaufen und halten". Quant OS trennt beide sauber, indem jede Strategie regime-konditional (siehe Kap. 3 & 5) und gegen die richtige Nullhypothese bewertet wird.

## 1.4 Das Zusammenspiel: Intuition konfiguriert, KI führt aus

Quant OS ist **kein** vollautonomer Black-Box-Handelsroboter und gibt auch nicht vor, einer zu sein. Es ist ein **Mensch-Maschine-System** mit einer klaren Arbeitsteilung:

| Ebene | Akteur | Verantwortung |
|---|---|---|
| **Hypothese & Konfiguration** | Mensch (Intuition) | Welche ökonomische These? Welche Schwellen, welche Risiko-Limits? Welche API-Keys (BYOK)? Welche Märkte im Universum? |
| **Validierung** | System (Statistik) | Permutation, Bootstrap, DSR, IS/OOS, Kosten — gnadenlos und emotionsfrei. |
| **Routing & Nowcast** | KI-Schwarm (Autonomie) | Welche Strategie ist im *aktuellen* Marktregime aktiv? Wann pausieren? (Kap. 5) |
| **Ausführung / Fills** | Mensch + Broker (Human-in-the-Loop) | Die tatsächliche Orderausführung bleibt bewusst beim Menschen bzw. einem deterministischen Bot — **keine LLM im Order-Pfad**. |

Die menschliche Intuition liefert die **Richtung und die Grenzen**; die KI-Autonomie liefert die **Geschwindigkeit und die Konsistenz** innerhalb dieser Grenzen. Der Mensch entscheidet, *welches Spiel* gespielt wird; das System sorgt dafür, dass es *nach den Regeln* gespielt wird — jeden Tag, ohne Müdigkeit, ohne Rache, ohne Euphorie.

---

# Kapitel 2 — Die Benutzeroberfläche & die zwei Welten

Quant OS präsentiert dieselbe Engine durch zwei radikal unterschiedliche Linsen. Die Umschaltung ist ein globaler UI-Zustand (`apps/web/lib/mode.tsx`), der im Browser unter dem Schlüssel `qos_mode` persistiert wird und zwei Werte annimmt: `"simple"` oder `"developer"`. Die erste Server-Render-Stufe ist immer `simple`, damit es keinen Hydration-Mismatch gibt; danach wird die gespeicherte Wahl angewandt.

```
┌──────────────────────────────────────────────────────────────┐
│  Quant-OS        Research ▾   Markets ▾   Trading Desk ▾   [Simple|Dev] ⚙ │
└──────────────────────────────────────────────────────────────┘
        Der Segmented-Toggle oben rechts schaltet die zwei Welten.
```

## 2.1 Simple Mode — das „Marktwetter" für Investoren und Laien

Im Simple Mode wird die Navigation bewusst auf **fünf Entscheidungs-Screens** reduziert. Alles, was Forschungs- oder Code-Charakter hat, ist ausgeblendet (im Code über das Flag `dev: true` je Navigationspunkt). Die sichtbaren fünf sind:

| Screen | Route | Was der Laie hier tut |
|---|---|---|
| **Swarm Command Center** | `/swarm` | Liest das aggregierte KI-Urteil: Welche Strategien sollen jetzt aktiv sein, mit welchem Gewicht, mit welcher Begründung. |
| **COT Positioning** | `/cot` | Sieht, wo das „Smart Money" extrem positioniert ist (Überhitzungs-Warnung). |
| **Seasonal** | `/seasonal` | Sieht statistisch signifikante Kalendermuster. |
| **Live Book** | `/live` | Sieht die laufenden, freigegebenen Strategien und ihre Tickets. |
| **Charts / Footprint** | `/charts` | Visuelle Marktbeobachtung. |

**Wie liest ein Laie das Marktwetter?** Das Herzstück ist die Vier-Quadranten-Klassifikation (Kap. 3), die als Farb-Ampel dargestellt wird. Die Palette ist im Code fest definiert und überall im System konsistent:

| Regime | Farbe | Klartext-Lesart |
|---|---|---|
| **High Vol · Trending** | 🔴 Alarmrot (`#ef4444`) | Starker Richtungsschub, aber ruppig — Breakouts/Crashes. |
| **Low Vol · Trending** | 🟢 Neongrün (`#22c55e`) | Stabiler, geordneter Trend — „das ruhige Trendregime". |
| **High Vol · Choppy** | 🟠 Bernstein (`#f59e0b`) | Unruhiger Seitwärtsmarkt, Whipsaws, schwer handelbar. |
| **Low Vol · Quiet** | ⚪ Schiefergrau (`#64748b`) | Ruhige Range / Akkumulation. |

Der Laie muss die Mathematik dahinter nicht verstehen. Er sieht eine Farbe, eine deutschsprachige Beschreibung und — auf dem Swarm-Screen — eine **Delegation per Klick**: Das System schlägt vor, welche Strategien zum aktuellen Wetter passen, und der Nutzer bestätigt oder lehnt ab. Die eigentliche Routing-Logik (Aktiv/Pausiert) übernimmt der Dynamic Strategy Router (Kap. 5) automatisch.

## 2.2 Quant Developer Mode — die Code-Ebene

Im Developer Mode erscheint die **volle Oberfläche**, gruppiert in drei Menüs:

- **Research:** Strategies-Registry, Research Hub, Alpha Factory, Evolution Monitor (genetischer Optimierer), Feature Store, Agent, Academy.
- **Markets:** Weather Radar, COT Positioning, Seasonal, Pairs/Cointegration, Alternative Data, News Terminal.
- **Trading Desk:** Swarm Command Center, Live Book, Switchboard, Risk Desk, Attribution Desk, Execution Desk, Charts/Footprint.

### Integration des Backtest-Ordners

Der Developer Mode ist das Fenster auf die eigentliche Forschungssubstanz: den Ordner `strategies/NNNN_name/`. Jede Strategie folgt einem festen Workflow (siehe `CLAUDE.md` und `strategies/REPORT_TEMPLATE.md`):

1. Template nach `strategies/NNNN_name/` kopieren.
2. `run.py` schreiben — **immer** unter Verwendung der `quantlab`-Bibliothek (Metriken/Engine werden nie reimplementiert).
3. In-Sample / Out-of-Sample splitten; nur OOS-Zahlen vertrauen.
4. Pflichtläufe: Kosten an, Permutationstest, Bootstrap-CI, Deflated Sharpe.
5. `REPORT.md` schreiben, Plots + `metrics.json` + `trades.csv` nach `results/` speichern.
6. Eine Zeile in `CATALOG.md` ergänzen.

Die Web-Oberfläche liest die so erzeugte Registry (über die API `apps/api/main.py`) und stellt das Research-Dashboard dar: Lebenszyklus-Buckets (`validated`, `candidate`, `testing`, `overlay`, `deferred`, `done`, `rejected`), die Sharpe-Verteilung des Katalogs (OOS netto) und die Top-Strategien.

### Anpassung von Python-/JS-Skripten und Steuerung des Schwarms

Im Developer Mode hat der Nutzer Zugriff auf:

- die **Python-Forschungsbibliothek** `src/quantlab/` (Datenlader, Backtest-Engine, Signifikanztests, Risiko-Engine — siehe Anhang B);
- die **FastAPI-Schicht** `apps/api/` (ein Modul je Desk: `swarm.py`, `switchboard.py`, `cot.py`, `risk.py`, `regime.py`, `conditional.py`, …);
- das **Next.js-Frontend** `apps/web/` (TypeScript/React, ein Verzeichnis je Screen).

Das **Swarm Command Center** (`/swarm`) ist die Steuerzentrale: Hier konfiguriert der Entwickler die lokalen Analyse-Drohnen und den Cloud-Commander und löst eine Schwarm-Runde aus (Details in Kap. 5).

## 2.3 BYOK — Bring Your Own Key

Quant OS speichert **keine** zentralen Zugangsdaten. Jeder Nutzer bringt seine eigenen API-Keys mit (BYOK) — sowohl für LLM-Anbieter (Gemini, Claude/Anthropic, OpenAI) als auch für Broker- und Daten-Schnittstellen (Alpaca, Binance, Databento, FRED). Diese Keys werden in einem **verschlüsselten Tresor** abgelegt.

### Der verschlüsselte Tresor (`quantlab/keystore.py`)

- Eine einzige Datei `.vault.json` im Repo-Wurzelverzeichnis (git-ignoriert) hält alle Schlüssel.
- Verschlüsselung: **Fernet** (AES-128 in CBC mit HMAC-Authentifizierung). Der Verschlüsselungsschlüssel wird aus einem **Master-Passwort** abgeleitet — via **PBKDF2-HMAC-SHA256 mit 480 000 Iterationen** (OWASP-konformer Arbeitsfaktor). Das Master-Passwort selbst wird **nie** gespeichert.
- On-Disk-Format: `{"version": 1, "salt": <b64 16B>, "token": <b64 Fernet(JSON{service: key})>}`. Ohne das Master-Passwort ist die Datei vollständig opak — echte Verschlüsselung at-rest.
- Nach dem `unlock` liegen die entschlüsselten Keys nur im Prozessspeicher der laufenden Sitzung; das ist die pragmatische Vertrauensgrenze einer lokalen Single-Process-Desktop-App.

### Schlüssel-Auflösungsreihenfolge

Wenn das System einen Key braucht, fragt `read_api_key(service)` die Quellen in fester Präzedenz ab:

$$\text{explizit übergeben} \;\succ\; \text{Vault (entsperrt)} \;\succ\; \text{Umgebungsvariable} \;\succ\; \text{Klartext-}\texttt{.key}\text{-Datei}$$

Das erlaubt einen sanften Migrationspfad: Wer noch gitignored `.gemini.key`-Dateien nutzt, funktioniert weiter; der Tresor hat aber Vorrang, sobald er entsperrt ist.

### LLM- und Broker-Schnittstellen

| Dienst | Service-Name im Vault | Zweck |
|---|---|---|
| Google Gemini | `gemini` | Cloud-Commander des Schwarms (Free Tier möglich) |
| Alpaca | `alpaca_key`, `alpaca_secret` | Marktdaten v2 (IEX-Feed, gratis auf Paper-Konten) + Broker |
| Databento | `databento` | Intraday-/Futures-Terminstruktur (kostenpflichtig) |
| FRED / EIA / NASS | `fred`, `eia`, `nass` | Makro-/Fundamentaldaten |

Die einheitliche Datenschicht (`quantlab/datasource.py`) abstrahiert die Anbieter: `get_bars(symbol, …, provider="yfinance"|"alpaca")` liefert immer dieselbe OHLCV-Form (`Open/High/Low/Close/Volume` auf einem `Date`-Index). `provider_status()` meldet dem Settings-Screen, welche Anbieter mit gültigen Keys verdrahtet sind — yfinance ist immer verfügbar (frei, tiefe Historie), Alpaca erst nach Hinterlegung von `alpaca_key`/`alpaca_secret`.

> **Sicherheitshinweis.** Lege das Master-Passwort niemals im Repo ab. Verlierst du es, ist der Tresor unwiederbringlich — das ist by design (es gibt keine Hintertür). Die Keys lassen sich dann nur durch Neuanlage des Tresors und erneutes Eintragen wiederherstellen.

---

# Kapitel 3 — Das Wetter-Radar — Market Regime Detection

Das Wetter-Radar (`quantlab/regime.py`, Frontend `/radar`) ist die zentrale Kontextmaschine des gesamten Systems. Es beantwortet eine einzige, aber alles entscheidende Frage: **In welcher Art von Markt befinden wir uns gerade?** Erst diese Antwort macht das regime-konditionale Routing (Kap. 5) möglich.

## 3.1 Die zwei orthogonalen Achsen

Das Radar klassifiziert jeden Bar durch das Kreuzen **zweier unabhängiger Achsen**:

### Volatilitäts-Achse (hoch / niedrig)

Die Frage: *Ist der Markt — gemessen an sich selbst — ungewöhnlich aufgeregt?* Zwei Bausteine:

1. **Annualisierte realisierte Volatilität.** Die rollende Standardabweichung der logarithmierten Tagesrenditen über `vol_window = 21` Bars, annualisiert:

$$\sigma_{\text{ann}}(t) = \sqrt{252} \cdot \operatorname{std}\!\big(\ln(P_t / P_{t-1})\big)_{\text{21 Bars}}$$

2. **ATR als Prozent des Preises.** Die Wilder-ATR über `atr_period = 14`, geteilt durch den Schlusskurs: $\text{ATR}\%(t) = \text{ATR}_{14}(t)\,/\,P_t$.

Der entscheidende Trick ist die **adaptive Rangbildung**: Die realisierte Vola wird nicht gegen einen absoluten Schwellenwert verglichen (was über Assets hinweg nicht funktioniert), sondern **innerhalb ihres eigenen nachlaufenden Fensters** von `vol_rank_window = 252` Bars perzentiliert (`rolling(...).rank(pct=True)`, look-ahead-sicher). Liegt der Perzentilrang $\geq$ `vol_high_pct = 0,55` (knapp über dem Median), gilt das Regime als **high vol**, sonst **low vol**.

Optional kann ein externer Volatilitätsindex (z. B. `^VIX` für US-Aktien) beigemischt werden. Dann wird der Vola-Rang des Assets mit dem Rang des Index gemischt:

$$\text{vol\_rank} = (1 - w_{\text{vix}}) \cdot \text{rank}_{\text{asset}} + w_{\text{vix}} \cdot \text{rank}_{\text{vix}}, \qquad w_{\text{vix}} = 0{,}5$$

Das fängt den Fall ab, dass ein ruhiges Asset in einem gestressten Gesamtmarkt liegt (oder umgekehrt).

### Trend-Achse (trendig / seitwärts)

Die Frage: *Geht der Preis irgendwohin, oder hackt er nur?* Auch hier zwei Bausteine, die **beide** erfüllt sein müssen:

1. **Trendstärke via Wilder-ADX** (`adx_period = 14`). Der ADX misst die *Stärke* einer Bewegung, unabhängig von ihrer Richtung. Konstruktion: gerichtete Bewegung (+DM/−DM) wird Wilder-geglättet und durch die geglättete True Range normiert zu +DI/−DI; daraus

$$\text{DX} = 100 \cdot \frac{|{+}\text{DI} - {-}\text{DI}|}{+\text{DI} + {-}\text{DI}}, \qquad \text{ADX} = \text{Wilder-RMA}(\text{DX})$$

Ein Markt gilt als momentumstark, wenn `ADX ≥ adx_trend_min = 22` (Wilders klassischer Bereich liegt bei 20–25).

2. **Richtungs-Kohärenz via MA-Stack.** Der ADX allein kann auch in einer *gewaltsamen Range* hoch lesen. Deshalb verlangt das Radar zusätzlich, dass der gleitende Durchschnitts-Stapel **ausgerichtet** ist: EMA20, SMA50, SMA200. Bullish heißt: Preis über SMA50 **und** über SMA200 **und** EMA20 über SMA50; Bearish ist die Spiegelung; sonst neutral.

$$\text{trending} \iff (\text{ADX} \geq 22) \ \wedge\ (\text{MA-Stack ist bull ODER bear})$$

Die Forderung nach Stack-Ausrichtung filtert das „hoher ADX im Whipsaw"-Artefakt heraus — der häufigste Fehler naiver Regime-Filter.

## 3.2 Das 2×2-Kreuz: die vier kanonischen Regime

| | **Trending** | **Seitwärts (Choppy/Quiet)** |
|---|---|---|
| **High Vol** | `high_vol_trend` — Breakout/Crash, ruppiger Trend | `high_vol_range` — Whipsaw, news-getrieben |
| **Low Vol** | `low_vol_trend` — geordneter Trend („easy money") | `low_vol_range` — ruhige Akkumulation |

Zusätzlich wird **orthogonal** eine Richtung (`bull`/`bear`/`neutral`) aus dem MA-Stack berichtet, sodass ein Trend-Regime als bullisch oder bärisch ausgewiesen werden kann, ohne die Regime-Zahl zu vervierfachen.

**Aufwärm-Schutz:** Bevor `min_history = 60` Bars vorliegen — und solange SMA200, ADX oder Vola-Rang noch undefiniert sind — wird `regime = None` ausgegeben. Das Regime ist ein **Nowcast**, der am Schluss von Bar $t$ bekannt ist; genau das macht die spätere Per-Regime-Performance-Auswertung ehrlich (keine Zukunftsinformation).

## 3.3 Praxis-Matrix: welche Strategie in welchem Regime

Die folgende Matrix ist die operative Übersetzung des Radars in Handlungsanweisungen. Sie ist die *qualitative* Leitlinie; die *quantitative* Durchsetzung übernimmt der Switchboard-Gate (Kap. 5), der eine Strategie in einem Regime nur dann freischaltet, wenn ihre dort isolierte Performance die Schwelle besteht.

| Regime | Farbe | Bevorzugte Strategieklasse | Verboten / gefährlich |
|---|---|---|---|
| **Low Vol · Trending** 🟢 | grün | **Trendfolge** (Momentum, Breakout-Continuation, gleitende Durchschnitte). Das ertragreichste Regime für Trendsysteme. | Mean-Reversion gegen den Trend (wird systematisch überrollt). |
| **High Vol · Trending** 🔴 | rot | **Trendfolge mit reduzierter Größe** + Tail-Hedge. Echte Richtung, aber Gap-Risiko. | Naives Short-Vol / Carry ohne Hedge; enge Stops (werden ausgeschüttelt). |
| **High Vol · Choppy** 🟠 | bernstein | **Selektive Mean-Reversion** an statistischen Extremen, kleine Größe; oft besser: gar nicht direktional handeln. | Breakout-/Trendsysteme (maximale Whipsaw-Verluste). |
| **Low Vol · Quiet** ⚪ | grau | **Mean-Reversion / Range-Handel**, Vola-Verkauf (mit definiertem Risiko), Carry. | Breakout-Systeme (Fehlausbrüche); große direktionale Wetten ohne Katalysator. |

**Die ökonomische Logik dahinter:** Trendfolge und Mean-Reversion sind *spiegelbildliche* Wetten auf die Autokorrelation der Renditen. In trendigen Regimen ist die Autokorrelation positiv (Momentum), in Ranges negativ oder null (Reversion). Eine Strategie in das falsche Regime zu schalten heißt, gegen das Vorzeichen der Autokorrelation zu handeln — der sicherste Weg, einen echten Brutto-Edge in einen Netto-Verlust zu verwandeln.

> **Wichtige Einschränkung (aus dem Forschungskatalog).** Niederfrequente, struktur-/flowgetriebene Strategien (Saison, Monatsend-Rebalancing, Auktions-Konzession) sind weitgehend **regime-agnostisch** — ihr Edge hängt am Kalender/Flow, nicht an Trend vs. Range. Der Schwarm-Commander behandelt solche Kategorien (siehe `_REGIME_AGNOSTIC`) bewusst als regimeunabhängig und pausiert sie nicht bei einem Wetterwechsel.

---

# Kapitel 4 — Die Spione im Markt — COT-Daten & Saisonalität

## 4.1 Institutional Positioning: das Smart Money lesen

Der wöchentliche **Commitments-of-Traders-(COT-)Report** der US-Aufsicht CFTC ist das nächste, was Privathändler an einem Röntgenbild der institutionellen Positionierung bekommen. Quant OS verarbeitet ihn in `quantlab/cot.py` (auf Basis des PIT-sicheren Loaders `quantlab/cot_data.py`) und stellt ihn auf `/cot` als Institutional-Positioning-Desk dar.

### Die zwei Lager

| Gruppe | Wer | Verhalten | Rolle |
|---|---|---|---|
| **Commercials** | Produzenten, Verarbeiter, Swap-Dealer | Hedger; kaufen, wenn der Preis tief ist (sichern Vorräte), verkaufen in Stärke | **Smart Money** — typischerweise *contrarian* und früh richtig |
| **Non-Commercials** (Managed Money) | Hedgefonds, CTAs, Trendfolger | Momentum; jagen Trends, am extremsten am Wendepunkt | **Trendfolger** — oft *spät* und am Extrem falsch |

Die Net-Position je Gruppe ist schlicht `long − short`. Daraus baut das System zwei normierte Faktoren:

### Der COT-Index (3-Jahres-Normierung)

Der **COT-Index** (Williams/Briese-Definition) normiert die Net-Position per rollendem Min-Max über ein Fenster von **156 Wochen ≈ 3 Jahre** auf eine Skala von 0 bis 100:

$$\text{COT-Index}(t) = \frac{\text{net}(t) - \min_{156w}(\text{net})}{\max_{156w}(\text{net}) - \min_{156w}(\text{net})} \cdot 100$$

- **0** = die net-shortste Positionierung der letzten 3 Jahre.
- **100** = die net-longste Positionierung der letzten 3 Jahre.
- Ein flaches Fenster (max = min) ergibt 50 (neutral).

### Der rollende Z-Score und „Overcrowded Trades"

Parallel wird ein **rollender Z-Score** der Net-Position über dasselbe 156-Wochen-Fenster berechnet:

$$z(t) = \frac{\text{net}(t) - \mu_{156w}}{\sigma_{156w}}$$

Die Faustregel: **$|z| > 2$ markiert ein Extrem** (Erschöpfung / Overcrowding). Wenn die Hedgefonds extrem net-long sind (hoher positiver $z$ bei den Non-Commercials), ist die Wette „überfüllt" — es gibt kaum noch marginale Käufer, und das Rückschlagrisiko ist hoch. Genau solche überfüllten Trades will man **vermeiden** oder **gegen** sie positionieren.

Die Signal-Logik (`classify_signal`) liest die *Commercial*-Seite contrarian:

| Bedingung | Signal | Bias |
|---|---|---|
| $z \geq +2$ **oder** COT-Index $\geq 80$ | „Commercial Buying Extreme" | **bullish** |
| $z \leq -2$ | „Hedgefonds Overcrowded Short" | **bearish** |
| COT-Index $\leq 20$ | „Commercial Selling" | bearish |
| COT-Index $\geq 60$ | „Commercials akkumulieren" | mild bullish |
| COT-Index $\leq 40$ | „Commercials verteilen" | mild bearish |
| sonst | „Neutral" | neutral |

Die Extreme-Positioning-Tabelle scannt das gesamte Universum (27 Roots: Energie, Metalle, Getreide, Vieh, FX, Indizes) und sortiert nach $|z|$ der Commercials — die extremste Positionierung steht oben.

### Point-in-Time-Korrektheit (kein Zukunftsblick)

Der COT-Report bezieht sich auf den **Dienstag** (`ref_date`), wird aber erst am **Freitag** 15:30 ET veröffentlicht (`release_date`) — *nach* dem Futures-Settlement. Quant OS bildet jeden Wochenwert daher auf seinen Freitags-Release ab und verschiebt ihn um **einen Handelstag** (`cot_daily_panel`), sodass der Faktor erst ab dem ersten Schluss *nach* seiner Veröffentlichung handelbar ist. Das ist strenger als die übliche „+3-Tage"-Konvention und schließt aus, dass der Backtest die Information desselben Erscheinungstages nutzt.

## 4.2 Die Zeitmaschine: Saisonalität mit statistischer Signifikanz

Das Saisonalitäts-Modul (`quantlab/seasonal.py`, Frontend `/seasonal`) sucht nach wiederkehrenden Kalendermustern — Monatsend-Effekte, Wochentags-Muster, Feiertags-Drifts, Ernte-/Roll-Zyklen bei Rohstoffen. Der entscheidende Unterschied zu populären „Seasonax"-artigen Darstellungen ist die **Signifikanzprüfung**: Ein hübsches Durchschnittsmuster ist wertlos, solange es nicht vom Zufall unterschieden werden kann.

### Warum der Durchschnitt allein lügt

Bei rund 252 Handelstagen pro Jahr und einer Suche über viele Fenster findet man *immer* irgendein Fenster, das historisch gut aussah — rein durch Zufall (multiples Testen). Drei Schutzmechanismen wirken zusammen:

1. **Permutationstest (p-Wert).** Die beobachtete Saison-Performance wird gegen eine Verteilung aus tausenden **Zufalls-Timings gleicher Trade-Zahl** verglichen. Der p-Wert ist der Anteil der Zufallsläufe, die mindestens so gut waren. Entscheidend ist die **richtige Nullhypothese**: Bei einem Saison-Long auf einem driftenden Aktienindex muss gegen *Zufalls-Long-Tage* getestet werden (nicht gegen 0), sonst misst man nur den Aufwärtsdrift (= Beta) statt das Timing (= Skill).

2. **Bootstrap-Konfidenzintervall.** Durch Resampling der einzelnen Trade-Renditen wird ein Konfidenzintervall für den mittleren Ertrag (oder Median-CLV) gebildet. Berührt das Intervall die Null, ist der Effekt nicht belastbar — egal wie schön der Punktschätzer ist.

3. **Deflated Sharpe Ratio (DSR).** Der DSR bestraft den beobachteten Sharpe um die **Anzahl der getesteten Varianten** ($n_{\text{trials}}$) und die Nicht-Normalität der Renditen (Schiefe, Kurtosis). Ein Sharpe von 4, der als bester von 156 gescannten Fenstern entstand, kollabiert im DSR auf nahe 0 — die ehrliche Antwort auf „nur in-sample herausoptimiert".

### Die Roll-Tag-Falle (Pflichtprüfung bei Futures)

Eine im Katalog teuer gelernte Lektion: Auf monatlich rollenden Futures (Erdgas, Rohöl, Benzin) enthält **jedes** mehrwöchige Fenster einer Continuous-Serie zwangsläufig Verfallstage, und ein naiver Front-Month-Stitch kann dort Renditen *fabrizieren*. Ein Saison-Effekt zählt erst dann als Lead, wenn er das **Entfernen einer engen Zone um jeden Verfallstag** übersteht. Permutation, Bootstrap und IS/OOS bestehen den Artefakt-Test *alle*, wenn er Jahr für Jahr konsistent auftritt — deshalb ist die Roll-Tag-Ausschlussprüfung ein eigener, nicht verhandelbarer Schritt.

> **Lesart für den Nutzer.** Im Seasonal-Screen ist nicht die Höhe des Durchschnittsbalkens entscheidend, sondern die **drei Signifikanz-Stempel** daneben: p-Wert (< 0,05?), Bootstrap-CI (schließt es die 0 aus?) und DSR (> 0,5?). Erst wenn alle drei grün sind, ist ein Muster mehr als Folklore.

---

# Kapitel 5 — Der Agentenschwarm & der Dynamic Strategy Router

Dieses Kapitel beschreibt das „Gehirn" des Live-Betriebs: wie verteilte KI-Agenten den Markt parallel analysieren und wie ihr Urteil mechanisch in Aktiv/Pausiert-Entscheidungen übersetzt wird.

## 5.1 Die Hierarchie: Drohnen, Commander, Fallbacks

Die Architektur (`quantlab/swarm.py`, API `apps/api/swarm.py`, Frontend `/swarm`) ist bewusst **hybrid lokal/Cloud** und auf Robustheit ausgelegt.

```
        ┌─────────────── lokale Worker-Drohnen (Ollama) ───────────────┐
        │  Regime-Drohne     Saison-Drohne     COT-Drohne   …          │
        │  (je 1 Signal →   (je 1 Signal →   (je 1 Signal → JSON-Zeile) │
        └───────────────┬──────────────────────────────────────────────┘
                        │  Aggregation zu EINEM kompakten Prompt
                        ▼
        ┌──────────── Cloud-Commander (Gemini) ────────────┐
        │  Eingang: Regime-Kontext + Drohnen-JSON +          │
        │           handelbare Strategien (mit regime_status)│
        │  Ausgang: finales Urteil — ACTIVE/PAUSED + Gewicht │
        │           + ehrliche Begründung (striktes JSON)    │
        └────────────────────────┬───────────────────────────┘
                                 ▼
              normalisiertes Verdikt → Dynamic Strategy Router
```

### Worker-Drohnen (lokal, Ollama)

Kleine, spezialisierte Modelle laufen lokal über einen **Ollama**-Server (`OllamaClient`, Standard `http://localhost:11434`, z. B. Modell `llama3`). Jede Drohne bekommt **genau ein** bereits berechnetes Markt-Signal (Regime, Saison, COT) und „erzählt" es in eine schlanke JSON-Zeile: eine knappe deutsche Schlagzeile plus eine Haltung (`risk_on` / `risk_off` / `neutral`). Die Drohnen sind billig und laufen parallel. Der Aufruf erzwingt `format=json`; schlägt er fehl, fällt die Drohne auf eine **deterministische Vorlage** aus denselben Daten zurück und wirft nie eine Ausnahme.

> Das ursprüngliche Designziel waren lokale Drohnen auf einem Mac (Apple-Silicon) über das LAN — der `base_url` lässt sich dafür ohne Codeänderung umstellen. In der aktuellen Umgebung laufen die Drohnen lokal mit `llama3` auf GPU; die Modelle liegen unter `D:\ollama\models`.

### Commander (Cloud, Gemini)

Der Commander (`GeminiClient`) erhält das **aggregierte** Drohnen-JSON in *einem* kompakten Prompt (ein Prompt für alle Drohnen = weniger API-Requests, ein erklärtes Designziel) plus den aktuellen Regime-Kontext und die Liste handelbarer Strategien — jede mit ihrem **regime-konditionalen Status** (`regime_status` ACTIVE/PAUSED aus echtem Conditional-Backtesting, `allowed_regimes`, Sharpe im aktuellen Regime). Er fällt ein finales, ungeschöntes Urteil: welche Strategien aktiv/pausiert sein sollen und mit welchem Allokationsgewicht (ACTIVE-Gewichte summieren sich auf ~1,0).

Robustheit ist der ganze Punkt:

- **Modell-Fallback-Kette:** Bei `429` (Quota/Rate) oder `503` wiederholt der Client dasselbe Modell mit **exponentiellem Backoff**; ist es erschöpft, wechselt er zum nächsten Modell (`gemini-2.5-flash` → `gemini-2.0-flash`). `400/401/403` (falscher Key / falsche Anfrage) scheitern sofort — Wiederholen hilft dort nicht.
- **Deterministischer Fallback:** Ist Gemini gänzlich unerreichbar oder die Quota verbraucht, übernimmt eine **transparente Regel-Engine** (`deterministic_commander`). Im Regime-Modus routet sie strikt nach dem Conditional-Backtest (ACTIVE = qualifiziert im aktuellen Regime) und gewichtet proportional zum Regime-Sharpe. Der Desk läuft also weiter, auch ohne Cloud.

Jedes LLM-Urteil wird durch `normalize_verdict` in die kanonische Form gezwungen: Jede handelbare Strategie kommt genau einmal vor (vergessene Strategien werden als PAUSED ergänzt), Gewichte werden auf $[0,1]$ geklemmt und die ACTIVE-Gewichte auf Summe 1 renormiert — die Oberfläche und der Allokator können den Zahlen also vertrauen.

## 5.2 Das Switchboard: regime-konditionale Performance-Matrix

Bevor der Commander überhaupt routen kann, braucht er die Evidenz, *in welchem Regime eine Strategie nachweislich verdient*. Diese liefert das **Switchboard** (`quantlab/switchboard.py`, Frontend `/switchboard`).

Für jede Strategie (jedes „Sleeve") schneidet das Switchboard deren Tagesrenditen nach dem **globalen Marktregime** (der Regime-Zeitreihe eines Benchmarks, z. B. `SPY`) und baut eine **Performance-Matrix**: Sharpe, Profit Factor, Win Rate und Max Drawdown — isoliert für jedes der vier kanonischen Regime.

### Der Routing-Gate

Eine Strategie ist in einem Regime **qualifiziert** genau dann, wenn:

$$\text{Sharpe} > 0{,}8 \quad\wedge\quad \text{Profit Factor} > 1{,}2 \quad\wedge\quad n \geq 10 \text{ Bars Evidenz}$$

Die Evidenzschwelle (`min_trades = 10`) verhindert, dass ein 2-Bar-„Edge" als Route durchgeht. Jede Zelle bekommt zusätzlich eine Farbstufe:

| Stufe | Farbe | Bedingung |
|---|---|---|
| **excellent** | tiefgrün (`#15803d`) | qualifiziert **und** Sharpe ≥ 1,5 **und** PF ≥ 2,0 |
| **good** | hellgrün (`#4ade80`) | qualifiziert (würde ACTIVE geroutet) |
| **neutral** | grau (`#3f3f46`) | zu wenig Evidenz oder unter Schwelle |
| **loss** | rot (`#dc2626`) | Geldverlierer in diesem Regime (negativ) |

Der Live-Router aktiviert exakt die Sleeves, die für das **aktuelle** Regime qualifizieren; alles andere wird pausiert. Sortiert wird die Matrix so, dass ACTIVE-Sleeves oben stehen, danach nach Sharpe im aktuellen Regime (die beste Route zuerst).

## 5.3 Der Dynamic Strategy Router: automatischer Regime-Switch

Der eigentliche Live-Mechanismus sitzt in `quantlab/conditional.py` (Phase-2-Brücke) und kombiniert das Switchboard mit der **Umschalt-Erkennung**:

1. **Regime-getaggte Trades** (`tag_trades`): Jeder historische Trade wird mit dem Regime gestempelt, das bei seinem Eintritt *nowcast-aktiv* war (look-ahead-sicher per rückwärtsgerichtetem `asof`). So entsteht die ereignisbasierte Per-Regime-Statistik.

2. **Switch-Detektion** (`detect_switch`): Erkennt den jüngsten Regime-Übergang. Das Flag `just_switched` ist gesetzt, wenn das aktuelle Regime-Segment nur wenige Bars alt ist ($\leq$ `SWITCH_FRESH_BARS = 3`) — der Router behandelt die Aktiv/Pausiert-Menge dann als *frische Neuverteilung*, nicht als eingeschwungenen Zustand.

3. **Flip-Delta** (`live_switch_delta`): Berechnet beim Übergang *vorheriges → aktuelles* Regime exakt, welche Sleeves **online** gehen (`activated`) und welche **flachgestellt** werden (`deactivated`). Das ist die mechanische Antwort des Desks auf das neue Wetter — und genau das Ereignis, das der Schwarm-Commander konsumiert.

4. **Voller Router** (`build_router`): Setzt alles zu einer Payload zusammen — die Switchboard-Matrix + das Switch-Ereignis + der Flip-Plan + die `allowed_market_regimes` je Strategie (die auch die Alpha-Factory für ihre Regime-Behauptung prüft).

> **Praktische Konsequenz.** Wechselt der Benchmark beim Schluss des jüngsten Bars z. B. von `low_vol_trend` (🟢) nach `high_vol_range` (🟠), pausiert der Router automatisch die Trendfolge-Sleeves, die nur im Trendregime qualifizieren, und aktiviert — falls qualifiziert — die Mean-Reversion-Sleeves. Der Mensch sieht im Swarm-Screen die Begründung; die Mechanik läuft, ohne dass jemand „den Hebel umlegen" muss. Die tatsächliche Orderausführung bleibt dennoch human-in-the-loop bzw. einem deterministischen Bot vorbehalten — **kein LLM im Order-Pfad**.

---

# Kapitel 6 — Risikomanagement auf Hedgefonds-Niveau

Das Risk Desk (`quantlab/risk.py`, Frontend `/risk`) arbeitet auf einem **Panel täglicher Strategie-Renditen** (ein `DataFrame`, Datumsindex, eine Spalte je Strategie). So lässt sich ein Buch heterogener Sleeves auf einer gemeinsamen Grundlage aggregieren, stressmessen und kapitalgewichten.

## 6.1 Value-at-Risk (VaR)

**VaR** beantwortet die Frage: *Welchen Verlust überschreiten wir mit Wahrscheinlichkeit $1-c$ über einen Horizont von $h$ Tagen nicht?* Ein 1-Tages-95-%-VaR von 2,1 % bedeutet: An ungefähr einem von 20 Handelstagen erwarten wir, mehr als 2,1 % zu verlieren. **Konvention im System:** VaR/ES werden als **positive Verlustbeträge** berichtet, und Horizonte werden per Wurzel-der-Zeit ($\sqrt{h}$) skaliert.

Zwei Methoden stehen nebeneinander:

**Historischer VaR** — das empirische $(1-c)$-Quantil der realisierten Renditeverteilung, negiert zum Verlust:

$$\text{VaR}_{\text{hist}} = \max\!\big(-Q_{1-c}(r),\, 0\big) \cdot \sqrt{h}$$

**Parametrischer (Varianz-Kovarianz-)VaR** — unter Normalverteilungsannahme:

$$\text{VaR}_{\text{param}} = z_c \cdot \sigma \cdot \sqrt{h} \;-\; \mu \cdot h, \qquad z_c = \Phi^{-1}(c)$$

Der Driftterm $\mu \cdot h$ ist auf kurzen Horizonten winzig, wird aber der Korrektheit halber mitgeführt (abschaltbar).

## 6.2 Expected Shortfall (ES / Conditional VaR)

Der VaR sagt, *ab wann* es schlimm wird, aber nichts darüber, *wie schlimm* es im Tail wird. Genau diese Lücke schließt der **Expected Shortfall** — der erwartete Verlust *unter der Bedingung*, dass der VaR überschritten wurde:

**Historischer ES** — Mittelwert aller Renditen jenseits der VaR-Schwelle:

$$\text{ES}_{\text{hist}} = \max\!\Big(-\,\mathbb{E}[\,r \mid r \leq Q_{1-c}(r)\,],\, 0\Big)\cdot \sqrt{h}$$

**Parametrischer ES** — die geschlossene Gauß-Form:

$$\text{ES}_{\text{param}} = \sigma \cdot \frac{\varphi(z_c)}{1-c}\cdot\sqrt{h} \;-\; \mu \cdot h$$

wobei $\varphi$ die Standardnormal-Dichte ist. Der ES ist das robustere Tail-Maß und für Short-Vol-/Short-Gamma-Strategien das **entscheidende** Urteilskriterium — denn Sharpe und sogar DSR *belohnen* Vola-Verkauf, sind aber blind für den Links-Tail. Eine Strategie mit attraktivem Sharpe, aber einem Worst-Day von −34 % (real im Katalog vorgekommen) wird auf Basis von ES/MaxDD/Kurtosis abgelehnt, nicht auf Basis von Sharpe.

Das Risk Desk berechnet alle Kombinationen aus Konfidenz $c \in \{0{,}95;\,0{,}99\}$ und Horizont $h \in \{1;\,10\}$ Tagen und — bei gegebenem Buchkapital — die zugehörigen **Währungsbeträge**.

## 6.3 Korrelation: ist die Diversifikation noch da?

Das Desk bildet die paarweise Pearson-Korrelation der Tagesrenditen (`correlation_matrix`), wobei NaNs paarweise entfernt werden und Paare mit weniger als `min_overlap = 20` gemeinsamen Beobachtungen auf NaN gesetzt werden — eine Korrelation aus drei gemeinsamen Tagen ist Rauschen und darf keine Allokation treiben. Die **rollende Korrelation** (`rolling_correlation`, Standardfenster 90 Tage) ist die „Lebt die Diversifikation noch?"-Zeitreihe: Wenn zuvor unkorrelierte Sleeves im Stress gemeinsam fallen (Korrelationen springen gegen 1), verschwindet der Diversifikationsnutzen genau dann, wenn man ihn am dringendsten braucht.

## 6.4 Der heilige Gral der Allokation: warum 1/N und Markowitz versagen — und HRP gewinnt

### Das Problem mit Gleichgewichtung (1/N)

Die **Gleichgewichtung** (`equal_weight`) ist die ehrliche Benchmark, die jeder Optimierer schlagen muss. Ihr Defekt: Sie ignoriert Risiko und Korrelation vollständig. Liegen drei der fünf Sleeves im selben Risikofaktor (etwa drei Aktien-Beta-Strategien), konzentriert 1/N 60 % des Kapitals — und einen noch höheren Anteil des *Risikos* — in einer einzigen Wette, die nur wie Diversifikation aussieht.

### Das Problem mit Mean-Variance (Markowitz/MVO)

Die klassische **Markowitz-Optimierung** (`mean_variance_optimization`, long-only SLSQP) maximiert den Sharpe der Tangentialportfolios. Ihr fundamentaler Schwachpunkt: Sie erfordert die **Inversion der Kovarianzmatrix**. Bei ähnlichen, korrelierten Sleeves ist diese Matrix nahezu singulär; ihre Inversion verstärkt Schätzfehler dramatisch und erzeugt extreme, instabile Gewichte, die out-of-sample kollabieren („error-maximization"). MVO ist mathematisch elegant, aber praktisch fragil.

### Die Lösung: Hierarchical Risk Parity (HRP, López de Prado 2016)

**HRP** (`hierarchical_risk_parity`) verzichtet vollständig auf Matrixinversion und ist deshalb robust gegen genau die near-singulären Kovarianzen, die MVO ruinieren. Drei Stufen:

1. **Tree-Clustering.** Aus der Korrelationsmatrix wird eine Distanzmatrix $d_{ij} = \sqrt{(1 - \rho_{ij})/2}$ gebildet und hierarchisch geclustert (Single-Linkage). Ähnliche Sleeves landen im selben Ast.

2. **Quasi-Diagonalisierung.** Die Sleeves werden so umgeordnet, dass ähnliche (hoch korrelierte) nebeneinander liegen — die Kovarianzmatrix wird „quasi-diagonal".

3. **Rekursive Bisektion.** Das Kapital wird top-down zwischen Clustern aufgeteilt, jeweils **invers zur Cluster-Varianz**: Der Faktor $\alpha = 1 - \frac{V_{\text{links}}}{V_{\text{links}} + V_{\text{rechts}}}$ steuert, wie viel Kapital in den linken vs. rechten Teilbaum fließt. Risikoreiche Cluster bekommen automatisch weniger.

Das Ergebnis ist eine Allokation, die die **Hierarchie der Korrelationsstruktur respektiert**: Drei ähnliche Aktien-Sleeves teilen sich gemeinsam ein Risikobudget, statt jeder einzeln so viel zu bekommen wie ein echtes Diversifikator-Sleeve. HRP schlägt 1/N und MVO out-of-sample typischerweise bei der risikoadjustierten Stabilität.

### Risikobeitrag und Diversifikationsnutzen

Zwei Diagnosen runden das Desk ab:

- **Euler-Risikozerlegung** (`risk_contributions`): Zerlegt die Portfolio-Volatilität in den Beitrag jedes Sleeves. Die Spalten `mcr` (marginaler Beitrag $\partial\sigma/\partial w_i$), `contribution` ($w_i \cdot \text{mcr}_i$, summiert sich auf $\sigma_p$) und `pct` (Risikoanteil) entlarven ein Sleeve, das auf kleiner Allokation den Großteil des Risikos frisst.

- **Choueifaty-Diversifikationsratio** (`diversification_ratio`):

$$\text{DR} = \frac{\sum_i w_i \sigma_i}{\sigma_p} \geq 1, \qquad \text{Nutzen} = 1 - \frac{\sigma_p}{\sum_i w_i \sigma_i}$$

Das gewichtete Mittel der Einzel-Volatilitäten über der realisierten Portfolio-Vola. Ein Wert nahe 1 bedeutet ein quasi-undiversifiziertes Buch; je höher, desto mehr Risiko wurde durch Diversifikation weggenettet.

> **Die Kernbotschaft des Risk Desks.** Gewinne werden durch den Edge erzeugt, aber *überleben* tut man durch das Risikomanagement. Ein robustes, korrelationsbewusstes Allokationsverfahren (HRP) plus tail-sensitive Maße (ES) plus die ehrliche 1/N-Benchmark sind der Unterschied zwischen einem Buch, das einen schlechten Monat übersteht, und einem, das an ihm zerbricht.

---

# Anhang A — Glossar

| Begriff | Definition |
|---|---|
| **Alpha** | Renditeanteil, der nicht durch Marktexposure erklärt wird (Achsenabschnitt der Faktor-Regression); Bezahlung für Skill. |
| **Beta** | Sensitivität gegenüber dem Gesamtmarkt; billiges, leistungsloses Markt-Exposure. |
| **ADX** | Average Directional Index (Wilder); misst Trendstärke unabhängig von der Richtung. Schwelle „trendig" = 22. |
| **ATR** | Average True Range; Volatilitätsmaß. Hier als ATR% (relativ zum Preis) genutzt. |
| **COT** | Commitments of Traders; wöchentlicher CFTC-Positionierungsreport. |
| **COT-Index** | Net-Position min-max-normiert über 156 Wochen (0–100). |
| **DSR** | Deflated Sharpe Ratio; Sharpe abzüglich Strafe für Suchbreite und Nicht-Normalität. |
| **ES / CVaR** | Expected Shortfall; mittlerer Verlust *jenseits* des VaR. |
| **HRP** | Hierarchical Risk Parity; inversionsfreie, korrelations-hierarchische Allokation. |
| **Look-ahead** | Unzulässige Nutzung von Information, die zum Entscheidungszeitpunkt nicht vorlag. |
| **MVO** | Mean-Variance-Optimization (Markowitz); fragil wegen Kovarianz-Inversion. |
| **Nowcast** | Schätzung des *aktuellen* Zustands, bekannt am Schluss des Bars (keine Zukunft). |
| **PIT** | Point-in-Time; Daten so, wie sie zum jeweiligen Zeitpunkt vorlagen. |
| **Permutationstest** | Signifikanzprüfung durch Vergleich mit zufällig permutierten Signalen. |
| **Regime** | Marktzustand aus dem 2×2-Kreuz Vola × Trend. |
| **Sharpe** | Risikoadjustierte Rendite: mittlere Überrendite / Volatilität. |
| **VaR** | Value-at-Risk; Verlustschwelle zu Konfidenz $c$ und Horizont $h$. |

# Anhang B — Modul-Landkarte (`src/quantlab`)

| Modul | Rolle |
|---|---|
| `data.py` / `datasource.py` | Gecachter Datenlader (yfinance, Parquet) bzw. einheitliche Multi-Provider-Schicht (yfinance + Alpaca, BYOK). |
| `regime.py` | Wetter-Radar: 2×2-Regime-Klassifikation (ADX/ATR/Vola-Rang + MA-Stack). |
| `switchboard.py` | Regime-konditionale Performance-Matrix + Routing-Gate (Sharpe > 0,8 ∧ PF > 1,2). |
| `conditional.py` | Trade-Tagging, Switch-Detektion, Live-Router (ACTIVE/PAUSED-Flip). |
| `swarm.py` | Hybrid-Multi-Agent-Kern: Ollama-Drohnen + Gemini-Commander + deterministische Fallbacks. |
| `cot.py` / `cot_data.py` | COT-Positionierung: Net-Positionen, COT-Index, Z-Score, PIT-Release-Logik. |
| `seasonal.py` | Kalenderfeatures, Bucket-Analyse, Signifikanz-Harness. |
| `significance.py` | Permutation, Bootstrap, Deflated Sharpe, t-Test. |
| `risk.py` | VaR/ES, Korrelation, Risikobeitrag, MVO/HRP/Equal-Weight, Diversifikationsratio. |
| `costs.py` | IBKR-/CFD-Kostenmodelle (Netto-Pflicht). |
| `backtest.py` | Vektorisierte, look-ahead-sichere Backtest-Engine mit Trade-Log. |
| `keystore.py` | Master-Passwort-Fernet-Tresor (BYOK, PBKDF2 480k). |
| `optimize.py` | Genetischer Optimierer mit IS/OOS-Overfit-Schutz. |

---

*Ende des Handbuchs. Die zugehörige Lern-Roadmap (Vom Laien zum Schwarm-Commander) findet sich in `QUANT_OS_ROADMAP.md`.*
