# Roadmap: Alternative-/Fundamentaldaten-Edge auf Nischen-Rohstoffen (für Claude Code)

> Handoff für Claude Code. Veredelt das Dokument `Dokument_Externe_Daten.txt`:
> der Rohansatz ist gut, ihm fehlen aber drei Guardrails, ohne die er an 20
> Märkten dutzendweise Falschpositive erzeugt. Diese Roadmap baut sie ein und
> hängt die bestehende `Backtests`-Validierungs-Batterie dran (Permutation, OOS,
> Bootstrap-KI, DSR, Kostenmodell-zuerst, Look-ahead-Schutz).
>
> Stand: Juni 2026. Keine Anlageberatung. Alle Effekte sind Hypothesen zum Validieren.

---

## Teil 0 — Was an diesem Ansatz gut ist (und was nicht)

**Gut:** Fundamentaldaten treiben Rohstoffpreise real (Wetter → Ertrag → Preis).
Das sind genau die ineffizienten, gering-institutionalisierten Märkte, die wir
suchen — aus Deutschland legal über einen Standard-Futures-Broker handelbar. Der
Ansatz ist mit unserer Rigorosität beweisbar und die freien Quellen sind echt.

**Drei Korrekturen am Rohdokument (zwingend):**

1. **Hypothese-zuerst statt IC-Scan.** Das Dokument will alle Features in einen
   IC-Scanner werfen. Bei 20 Märkten × N Quellen × M Features × 3 Horizonten sind
   das hunderte Tests → Drift-/Multiple-Testing-Falle (`0017`/`0026`). Stattdessen:
   pro Markt **eine spezifische, vorab aufgeschriebene Kausalkette** formulieren
   und *die* testen.
2. **Point-in-Time (PIT) ist hier der Look-ahead.** USDA-Zahlen werden revidiert;
   Wetter-Anomalien brauchen eine PIT-Klimatologie. Nur „as-known-at-the-time"-Daten
   verwenden. Feature = **Überraschung** (Ist − damalige Erwartung), nicht Absolutwert.
3. **„Niemand nutzt diese Daten" stimmt nur für Retail.** In Rohstoffen sind
   Wetter/USDA die meistbeobachteten Inputs. Edge ≠ Datenexklusivität, sondern
   (a) Märkte zu klein für große Desks + (b) **langsame Diffusion** nach dem Report
   (den Report selbst fangen HFT in Sekunden → `0041`-Wand). Darum Horizonte
   1 Woche / 1 Monat / 3 Monate — nicht der Release-Tick.

**Brücke zum bestehenden Katalog:** `0032` (Mais WASDE-Kern) fand, dass 78 % der
Edge auf 6 WASDE-Tagen saßen — ein echtes, konzentriertes Report-Surprise-Signal.
Dieser Ansatz ist die Verallgemeinerung davon über mehrere Märkte und Datenquellen.

---

## Teil 1 — Markt-Universum & Tradeability-Filter (zuerst!)

Wie immer: Marktwahl *vor* der Strategiesuche (Framework Teil 2). Die 20 Futures
zerfallen in Tradeability-Klassen. Spread/Liquidität entscheidet, ob ein gefundener
Edge überhaupt netto überlebt (BTC-Lehre).

| Klasse | Futures | Hinweis |
| --- | --- | --- |
| **Liquide, US-handelbar, edge wahrscheinlich crowded** | Zucker (SB), Kaffee (KC), Kakao (CC), Baumwolle (CT), Mais-Komplex, Kupfer (HG), Platin (PL), Palladium (PA), Live/Feeder Cattle (LE/GF), Lean Hogs (HE) | Beste Daten-/Liquiditäts-Balance. Hier zuerst testen. |
| **Dünn, US-handelbar — Edge-Chance hoch, Spread breit** | Orangensaft (OJ), Hafer (ZO), Rough Rice (ZR), Milch III / Butter / Käse, Raps/Canola (RS) | Größte Ineffizienz, aber **Spread-Kosten dominieren** → Netto-Filter ist hart. Genau hier den Kostentest streng fahren. |
| **Schwierig zugänglich / Kontrakt-Probleme** | Lumber, Gummi, Palmöl | Lumber: alter LBS-Kontrakt 2023 eingestellt (siehe `0011`), neuer LBR dünn. Gummi (TOCOM/SGX) + Palmöl (Bursa FCPO) = asiatische Börsen, von DE/IBKR oft nicht sauber handelbar → **erst Datenverfügbarkeit + Handelbarkeit klären, sonst skippen.** |

**Schritt 0 pro Markt:** Kontraktspezifikation + realer Spread + Kommission
modellieren. Continuous-Reihe mit Roll-Behandlung (deine `roll.py`/`0029`-Logik —
bei monatlich rollenden Kontrakten Pflicht).

---

## Teil 2 — Hypothesen-Register (pro Markt eine Kausalkette, vorab fixiert)

Schreib **vor** jedem Test die Kette auf. Beispiele (nicht erschöpfend):

- **Zucker (SB):** Niederschlags-Defizit im Cane-Gürtel São Paulo (CWB-Region)
  über die Wachstumsphase → Ertrags-Downgrade in folgendem PSD/WASDE → Preis ↑
  über 1–3 Mon. Plus: Ethanol-Parität (EIA) — hoher Ethanolpreis zieht Cane in
  Ethanol statt Zucker → Zucker-Angebot ↓.
- **Kakao (CC):** Harmattan-Trockenheit / Niederschlagsabweichung Côte d'Ivoire +
  Ghana → Ernte-Downgrade → Preis ↑. (Achtung Drift: Kakao war 2024 im
  Superzyklus — `0026`-Lehre, Permutation gegen Drift ist Pflicht.)
- **Kaffee (KC):** Frost-Ereignis / Temperatur-Tiefstwert Minas Gerais (Juni–Aug)
  → Schadens-Prämie. Aber `0027`-Lehre: *eine Überraschung kann man nicht timen* —
  also nicht „Frost vorhersagen", sondern „nach realisiertem Kältereignis
  positionieren, bevor der Markt es voll eingepreist hat" (Diffusions-Edge).
- **Baumwolle (CT):** Trockenheit/Hitze West-Texas (NASS-Crop-Condition fällt) →
  Ertrag ↓. Crop-Condition-Reports sind PIT und wöchentlich → gutes Surprise-Feature.
- **Live/Feeder/Hogs:** Futterkosten (Mais/Soja) als Lead; USDA Cattle-on-Feed /
  Hogs-&-Pigs-Surprise.
- **Kupfer (HG):** China-Industrieproduktion / Stromverbrauch-Surprise, LME+SHFE-
  Lagerbestandsänderung.
- **Platin/Palladium:** südafrikanische Stromrationierung (Loadshedding-Stufe) →
  Minen-Output-Risiko; Autoabsatz (Palladium-Nachfrage).

**Regel:** Keine Kette = kein Test. Das ist der Filter, der die IC-Scan-Falle killt.

---

## Teil 3 — Datenquellen-Layer (frei) + PIT-Status

| Quelle | Daten | API/Key | PIT-Fallstrick |
| --- | --- | --- | --- |
| **Open-Meteo** | Wetter-Historie bis 1940, Forecasts | keyless ✅ | Reanalyse — sauber, aber für *Forecast*-Features den damaligen Forecast nötig (nicht ex-post). |
| **NOAA CDO** | Station-Wetter, Niederschlag, Temp | Free-Token | Stationsdaten teils nachträglich korrigiert. |
| **USDA NASS QuickStats** | Crop Condition (wöchentl., PIT!), Flächen, Bestände, Produktion | Free-Key | Crop-Progress ist PIT; Production-Schätzungen werden revidiert. |
| **USDA PSD** | weltweite Produktion/Angebot/Verbrauch | Download/API | monatlich/jährlich revidiert → **Vintage beachten**. |
| **USDA WASDE** | monatliche S&D-Prognosen | CSV-Archiv (Cornell/Mann Library) | Headline-Zahl revidiert; **Surprise = WASDE-Ist − Pre-Report-Analystenkonsens** (Konsens frei schwer → ggf. Naïve-Forecast/Vormonat als Proxy, sauber dokumentieren). |
| **EIA** | Öl, Gas, Strom, **Ethanol** | Free-Key | Wöchentliche Reihen werden leicht revidiert. |
| **FRED** | Baubeginne, Makro, Industrieprod. | Free-Key | **ALFRED-Vintages nutzen** (FRED hat PIT-Vintage-Datenbank!) → Goldstandard für PIT. |
| **World Bank / USGS / FAOSTAT / ICO** | Minenproduktion, globale Ag-Statistik | keyless/Download | jährlich, stark gelaggt → eher Slow-Regime-Features. |

**Loader (neu in `quantlab`):** `fundamental_data.py` — pro Quelle ein Adapter,
Parquet-Cache unter `data/cache/fundamentals/`, **jede Zeile mit
`release_date`/`vintage`-Spalte** (nicht nur `ref_date`), damit der Backtest
PIT-korrekt nur das nutzen kann, was zum Entry bekannt war.

---

## Teil 4 — Feature-Engineering (PIT-korrekt)

Für jede Hypothese die Features so bauen, dass sie **zum Entry-Zeitpunkt bekannt
gewesen wären**:

- **Wetter-Anomalie:** `(Ist − Klimatologie)`, wobei die Klimatologie aus einem
  *rollierenden, nur vergangenheitsbasierten* Fenster stammt (z. B. 1991–vorJahr),
  nicht aus dem ganzen Sample.
- **Report-Surprise:** `Ist − Erwartung_vor_Release`. Erwartung = Analystenkonsens
  wenn frei verfügbar, sonst dokumentierter Naïve-Proxy (Vormonat / saisonale
  Naïve). Klar als Annahme markieren.
- **Wachstums-/Änderungsraten:** Export-YoY, Lagerbestands-Δ, Energiepreis-Δ — alle
  auf den jeweiligen `release_date` gelaggt, nie auf `ref_date`.
- **Crop-Condition-Δ:** Woche-über-Woche-Änderung des „good/excellent"-Anteils
  (NASS, sauber PIT).

**Look-ahead-Test (Pflicht, analog zu eurem bestehenden):** Ein Unit-Test, der
sicherstellt, dass für jeden Entry an Tag *t* ausschließlich Daten mit
`release_date ≤ t` einfließen.

---

## Teil 5 — Validierungs-Batterie (eure Pipeline, auf Features übertragen)

Pro vorab fixierter Hypothese, in dieser Reihenfolge:

1. **Kostenmodell zuerst.** Spread + Kommission + Slippage des Zielfutures. Bei den
   dünnen (OJ/Hafer/Reis/Dairy) ist das der bindende Filter.
2. **Information Coefficient (IC):** Rang-Korrelation Feature ↔ Forward-Return
   (1W/1M/3M). Aber **IC allein beweist nichts** — nur Eingangssichtung.
3. **Permutationstest:** Feature-Werte gegen die Returns shuffeln → schlägt der
   echte IC 95 % der Zufallsläufe? (Trennt echtes Signal von Drift, wie bei euren
   Saisonfenstern.)
4. **OOS-Split** zeitlich (z. B. vor/nach Stichjahr) — IS≈OOS oder Kollaps?
5. **Cross-Market-Generalisierung / Pooling:** Hält dieselbe Kette über verwandte
   Märkte (Mais↔Weizen wie `0032`; Cattle↔Hogs)? Pooling hebt die Power wie euer
   `0002` Sell-in-May-Pool.
6. **Bootstrap-KI** auf dem Trade-EV → muss Null ausschließen.
7. **Deflated Sharpe (DSR):** *Der* entscheidende Schritt hier. N = Zahl aller
   getesteten (Markt × Feature × Horizont)-Kombinationen. Bei diesem Ansatz ist N
   groß → DSR bestraft hart. Nur was DSR übersteht, wird „Kandidat".
8. **Regime-/Robustheits-Check:** Parameter-Plateau, Kosten-Stress (eure
   `0037`-Methode).

**Scoring (wie im Dokument gewünscht), aber diszipliniert:** pro Quelle/Feature
nicht nur IC, sondern (IC, Permutation-p, OOS-Stabilität, DSR-überlebt?, Netto-
Sharpe-Beitrag nach Kosten). Eine Quelle „zählt" erst, wenn sie DSR + Permutation
besteht.

---

## Teil 6 — Phasenplan (Deliverables im `strategies/NNNN`-Stil)

| Phase | Ziel | Deliverable | Gate |
| --- | --- | --- | --- |
| **0** | Universum + Kostenmodelle | Tradeability-Tabelle, Roll-sauber | Spread pro Markt fixiert |
| **1** | `quantlab/fundamental_data.py` + PIT-Cache | Loader mit `vintage`/`release_date`, FRED-ALFRED-Anbindung | Look-ahead-Unit-Test grün |
| **2** | Hypothesen-Register | `fundamentals/HYPOTHESES.md` (Kette pro Markt) | jede Kette ökonomisch begründet |
| **3** | Erste 3 liquide Märkte (SB/KC/CT) | je `strategies/00XX_*/REPORT.md` | Permutation p<0,05 **und** DSR überlebt |
| **4** | Cross-Market-Pooling + dünne Märkte | Pool-REPORT | Pooling hebt Sharpe, Netto-positiv nach Spread |
| **5** | Bündel-Overlay der überlebenden Ketten | Multi-Signal-Portfolio | glatte Kurve, OOS-stabil |

---

## Teil 7 — `quantlab`-Erweiterungen

- `quantlab/fundamental_data.py` — PIT-Loader (Vintage-aware), Parquet-Cache.
- `quantlab/features.py` — Anomalie/Surprise/Δ-Generatoren, alle release-gelaggt.
- `quantlab/ic.py` — IC, Rank-IC, IC-Decay über Horizonte, Reliability.
- Re-use: `significance.py` (Permutation/Bootstrap/DSR), `roll.py`, `costs.py`,
  `backtest.py`.
- Tests: **PIT-Look-ahead-Guard**, **Vintage-Korrektheit** (kein revidierter Wert
  vor seinem Release sichtbar).

---

## Teil 8 — Anti-Selbstbetrugs-Checkliste (Fundamental-Edition)

- **PIT-Look-ahead** ist hier euer Roll-Check: revidierte Zahlen / ex-post-
  Klimatologie = gefälschte Kurven. FRED-ALFRED-Vintages wo möglich.
- **Multiple Testing** ist die Hauptgefahr (20 Märkte!). DSR mit ehrlichem N. Ohne
  das ist der ganze Ansatz ein IC-Scan-Glückstreffer-Generator.
- **Hypothese-zuerst**, nie blinder Feature-Zoo (Kakao/Nasdaq-Drift-Falle).
- **Spread bindet** in den dünnen Märkten (BTC-Lehre). Netto-nach-Spread, immer.
- **Fat-Tail-Verbot** (`0027`): Median-Trade positiv, nicht nur Mittelwert. Wetter-
  Schocks sind per Definition Fat-Tails — „man kann eine Überraschung nicht timen",
  also Diffusion *nach* dem realisierten Ereignis handeln, nicht das Ereignis raten.
- **„Institutionen nutzen das nicht" ist falsch** für Rohstoffe. Edge = kleine
  Märkte + langsame Diffusion, nicht Datenexklusivität.
- **Report-Tag ≠ Edge-Tag:** Den Release fangen HFT (`0041`-Wand). Die Edge sitzt
  in der Diffusion über Tage/Wochen — darum 1W/1M/3M-Horizonte.

---

*Reihenfolge unverändert: erst der Beweis (DSR-überlebende, OOS-stabile Ketten),
dann Kapital — und zwar auf eigenem Futures-Konto, wo keine Prop-Konsistenzregel
eine fundamentale Swing-Edge bestraft.*
