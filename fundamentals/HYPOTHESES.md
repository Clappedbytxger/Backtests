# Phase 2 — Hypothesen-Register (Alt-Data Fundamentals)

> **Regel: Keine Kette = kein Test.**  
> Jede Hypothese muss VOR dem Feature-Build hier eingetragen und ökonomisch
> begründet sein. Das ist der Filter gegen den IC-Scan-Glückstreffer-Generator
> (Multiple-Testing-Falle, 20 Märkte × N Features × 3 Horizonte).
>
> Format pro Eintrag:
> 1. **Kausalkette** (Ereignis → Markt-Impact → Preis-Richtung)
> 2. **Feature** (PIT-korrekt, Release-gelaggt)
> 3. **Horizonte** (1W / 1M / 3M)
> 4. **Datequelle** + PIT-Caveat
> 5. **Vorab-Prediction** (long/short, Stärke erwartet)
> 6. **Status** (PENDING / TESTING / PASS / REJECT)

---

## SB — Zucker #11

### H-SB-01: São-Paulo-Niederschlagsdefizit → Preis ↑

**Kausalkette:**  
Niederschlagsdefizit in der CWB-Region (Hauptanbaugebiet, SP-Bundesstaat) während
der Wachstumsphase (Okt–März) → Ertragsprognose ↓ → USDA PSD "Brazil Production"
Downgrade im nächsten WASDE → Preis-Anstieg über 1–3 Monate.

**Feature:**  
`precipitation_sum_anomaly` (monatlich, São Paulo lat=-22.0, lon=-47.0, ERA5),
berechnet als z-Score vs. rollierende 20-Jahres-Klimatologie (nur Vergangenheit).

**Vorab-Prediction:** Anomalie < -1.5 σ → long SB. Erwarteter Horizont: 1M–3M.

**Horizonte:** 22 Tage, 66 Tage  
**Datenquelle:** Open-Meteo (keyless), `get_weather_daily()` → `weather_anomaly()`  
**PIT-Caveat:** ERA5 reanalysis ist historisch fertig; release_date = ref_date + 1 Tag.
Klimatologie-Fenster muss rein vergangenheitsbasiert sein (rollierende 20J).  
**Multiple-Testing-N:** Zählt als Test-Nr. 1 im Gesamt-N für DSR.  
**Status:** REJECT — IC(22d)=+0.002, Perm-p=0.978 (158 Obs., 2000–2026). Kein Signal. Strategie 0042.

---

### H-SB-02: Ethanol-Parität → Zucker-Angebot ↓ → Preis ↑

**Kausalkette:**  
Hoher Ethanolpreis (relativ zu Zucker) → brasilianische Mühlen lenken Zuckerrohr
in Ethanol-Produktion statt Zucker → effektives Zucker-Angebot sinkt → Preis ↑.

**Feature:**  
Ethanol-zu-Zucker Preis-Ratio (Änderungsrate, nicht Absolutwert).
EIA Weekly Ethanol Price / SB Front-Month-Close (lag: release_date EIA = Donnerstag).

**Vorab-Prediction:** Ratio hoch (Ethanol teuer relativ zu Zucker) → Mühlen
diversifizieren in Ethanol → Zucker-Angebot sinkt über die Crush-Season →
long SB über 1–3 Monate (langsame Angebots-Reaktion → Schwerpunkt 66 Tage).

**Horizonte:** 5 / 22 / 66 Tage (Ziel-Horizont 66d — Crush-Season-Lag)  
**Datenquelle (geplant):** EIA Weekly Ethanol Price (`get_eia_series()`).  
**Datenquelle (TATSÄCHLICH verwendet, Strategie 0043):** EIA ist in der
Arbeitsumgebung **geoblockt (HTTP 403, wie USDA)**. Stattdessen **Energie-Proxy**
für die Ethanol-Attraktivität: **RBOB-Benzin/Zucker-Paritäts-Ratio z-Score**
(RB=F, primär) + **Crude/Zucker** (CL=F, Cross-Check, Negativ-Print-Guard 0005)
+ **Gold-Placebo** (GC=F, kein Ethanol-Mechanismus). Ökonomische Rechtfertigung
des Proxys: Hydro-Ethanol konkurriert in Brasilien direkt mit Benzin an der
Zapfsäule (Parität ~70 % des Benzinpreises) → Benzinpreis treibt die
Mühlen-Entscheidung Zucker-vs-Ethanol. Alle Quellen yfinance, frei + erreichbar.  
**PIT-Caveat:** Energie-Preise sind Marktdaten (real-time, `release_date = ref_date`),
kein Revisions-Lag. Ratio-z-Score nutzt rollierendes 252-Tage-Fenster (shift(1),
rein vergangenheitsbasiert). **Proxy-Annahme klar als solche markieren** —
das ist NICHT der EIA-Ethanolpreis, sondern sein ökonomischer Treiber.  
**Multiple-Testing-N:** Test-Nr. 2  
**Status:** REJECT (Proxy) — RBOB/Zucker-Parität IC(66d)=+0.04, perm-p=0.530;
Crude/Zucker bestätigt ≈0 (232 Obs., 2007–2026). Gold-Placebo leuchtete dagegen
stark (IC(66d)=−0.27, p=0.000) → Methodik validiert, Zucker-Ziel leer. Strategie 0043.
Echte EIA-Ethanoldaten bleiben ungetestet (geoblockt) — direkter Ethanol-Spread könnte
separat geprüft werden, aber nach diesem Befund unwahrscheinlich.

---

### H-SB-03: WASDE-Produktions-Surprise → Preis-Reaktion, Diffusion über Wochen

**Kausalkette:**  
USDA WASDE revisioniert monatlich die globale Zucker-Produktionsschätzung.
Negativer Surprise (Ist < Vormonat-Schätzung) → Markt verdaut Information
langsam über 1–4 Wochen → Preis steigt nach negativem Surprise.

**Feature:**  
`wasde_surprise` = WASDE-Aktualwert − Vormonats-Schätzung (gleiche Attribut-Reihe,
naïver Proxy für Analyst-Konsens). Negativ = Downgrade = bullish für Preis.

**Vorab-Prediction:** surprise < 0 → long SB über 1M. Diffusion-Edge, nicht Release-Tick.

**Horizonte:** 5 Tage, 22 Tage, 66 Tage  
**Datenquelle:** USDA FAS PSD API (`get_wasde_psd()`), commodity code 0240000  
**PIT-Caveat:**  
- release_date ≈ 10. des Monats (WASDE-Kalender, gerundet; dokumentieren).
- Naïver Proxy für Konsens → als Annahme in REPORT.md markieren.
- Keine echter Analyst-Konsens frei verfügbar.  
**Multiple-Testing-N:** Test-Nr. 3  
**Status:** PENDING

---

## KC — Kaffee

### H-KC-01: Realisiertes Frost-Ereignis Minas Gerais → Schadens-Prämie, Diffusion

**Kausalkette:**  
Temperatur-Tiefstwert < 0 °C in Minas Gerais (Juni–August) beschädigt
Kaffeepflanzen physisch → Ertragsverlust für die nächste Ernte → Preis steigt.
**Nicht**: Frost vorhersagen, sondern nach realisiertem Kälte-Event positionieren
(Diffusions-Edge: Markt preist langsam ein, weil Schadensschätzung Zeit braucht).
Lektion 0027: „Eine Überraschung kann man nicht timen" → nach dem Event einsteigen.

**Feature:**  
`temperature_2m_min_anomaly` < -2.0 σ (monatliche Kältenacht, `agg=min`),
Monat Juni/Juli/August. **Koordinaten-Korrektur (Strategie 0044):** registriert war
(-19.5, -43.5) — dort ERA5-Warm-Bias (nie < 2.3 °C, sieht 2021er Frost nicht).
Verwendet wurde **Sul de Minas (-21.5, -45.5)** = realer Frostgürtel, wo die
kältesten Anomalien 1994/2021/2000 = die bekannten Frostjahre ranken.

**Vorab-Prediction:** Frost-Flag = 1 → long KC über 1M–3M. Größerer Effekt in 3M.

**Horizonte:** 22 Tage, 66 Tage  
**Datenquelle:** Open-Meteo ERA5  
**PIT-Caveat:** Tages-Minimum erst am Folgetag bekannt; release_date = ref_date + 1d.
Frost ist ein seltenes Ereignis (~5–15 starke Jahre in 30J) → kleine Stichprobe,
Bootstrap-KI breit, DSR bestraft → erst ab p<0.01 Permutation als Lead werten.  
**Multiple-Testing-N:** Test-Nr. 4  
**Status:** REJECT — kontinuierlicher IC(66d)=+0.08 (p=0.47, kurzfr. sogar negativ:
Erntedruck dominiert); Event-Study (5 Events z<-2σ, 2000-2026) **Median 22d=-14%,
66d=-12%**, nur 2/5 positiv → Fat-Tail-Lotterie (Verbot 0027). Selbst nach
realisiertem Kälte-Event verliert man auf dem Median: z<-2σ ≠ pflanzentötender Frost.
Frostprämie ist real aber nicht-timebar. Strategie 0044 (verstärkt 0027).

---

### H-KC-02: WASDE Kaffee-Produktions-Surprise → Diffusion

**Kausalkette:** Analog H-SB-03 für Kaffee.

**Feature:** `wasde_surprise` für Kaffee, FAS-Code 0813100  
**Datenquelle:** USDA FAS PSD API  
**Horizonte:** 5 Tage, 22 Tage, 66 Tage  
**Multiple-Testing-N:** Test-Nr. 5  
**Status:** PENDING

---

## CT — Baumwolle

### H-CT-01: West-Texas-Trockenheit / NASS Crop Condition Drop → Preis ↑

**Kausalkette:**  
Trockenheit/Hitze in West-Texas (Hauptanbaugebiet USA) → USDA NASS Crop Condition
Anteil „Good/Excellent" fällt wöchentlich → Ertragsschätzung ↓ → Preis ↑.

**Feature:**  
`crop_condition_delta` = Woche-über-Woche-Änderung des Good/Excellent-Anteils
(NASS QuickStats, state_fips="48" für Texas, Juli–September).
Negatives Delta (Verschlechterung) = bearish für Ernte = bullish für Preis.

**Vorab-Prediction:** Δ < -5 Prozentpunkte → long CT über 1W–1M.

**Horizonte:** 5 Tage, 22 Tage  
**Datenquelle:** USDA NASS QuickStats API (`get_nass_crop_condition()`), free key  
**PIT-Caveat:** NASS Crop Progress erscheint montags 16:00 ET.
week_ending = Sonntag; release_date = Sonntag + 1 Tag (Montag).
Für Intraday-Entries: Montag EOD einsteigen (nach 16 Uhr ET).
Für Daily-Backtest: Entry am Dienstag (sicherste PIT-Variante).  
**Multiple-Testing-N:** Test-Nr. 6  
**Status:** REJECT — kont. IC(22d)=-0.037 (p=0.42, sogar leicht negativ); Event-Study
41 Events Δ<-5pp: 22d-Median +0.10%, Win 51% = Münzwurf (585 in-season Wochen, 2000-2025).
Strategie 0045. **Erste echte-Daten-Lehre der Klasse:** die wöchentliche Crop-Condition
ist laufend eingepreist (meistbeobachtet, kontinuierlich) → kein Surprise wie der diskrete
monatliche WASDE (0032). Nicht jede „Surprise"-Klasse trägt Edge — nur diskrete
Info-Konzentration.

---

### H-CT-02: WASDE Cotton Surprise

**Feature:** `wasde_surprise` Baumwolle, FAS-Code 2631000  
**Horizonte:** 5 Tage, 22 Tage, 66 Tage  
**Multiple-Testing-N:** Test-Nr. 7  
**Status:** PENDING

---

## CC — Kakao

### H-CC-01: Harmattan-Trockenheit Côte d'Ivoire / Ghana → Ernte-Downgrade

**Kausalkette:**  
Harmattan-Trockenwind (Dez–Feb) senkt Niederschlag in CdI + Ghana →
Kakaobohnen-Qualität ↓, Mittelernteausfall → Preis ↑ über 1–3 Monate.

**Feature:**  
`precipitation_sum_anomaly` Dez–Feb in CdI (lat=6.8, lon=-5.3) + Ghana (lat=7.0, lon=-1.5),
kombiniert als Durchschnitt beider Standorte.

**Drift-Warnung (Lektion 0026):** Kakao war 2023–2024 im Superzyklus. Permutationstest
MUSS gegen Drift testen (shuffle-Variante mit Trend-Erhalt). Ohne das ist CC unbrauchbar.

**Horizonte:** 22 Tage, 66 Tage  
**Multiple-Testing-N:** Test-Nr. 8  
**Status:** PENDING

---

## LE / GF — Live/Feeder Cattle

### H-LE-01: Mais-Futterkosten als Lead für Cattle-Margins

**Kausalkette:**  
Mais-Preis (ZC) steigt → Feed-Kosten für Cattle-Betriebe steigen → Marginaldruck →
Betriebe reduzieren Bestände (mehr Schlachtungen kurzfristig) → LE kurzfristig ↓,
dann langfristig ↑ (weniger Nachschub). Horizont entscheidend: 1M-Effekt unklar,
3M-Effekt plausibel bullish (Herdenmuster).

**Feature:**  
`corn_price_change` = ZC Close-Änderung über 4 Wochen (lagged 1 Tag).
(Direkt aus yfinance, kein fundamentaler Loader nötig — Preis ist PIT-korrekt.)

**Vorab-Prediction:** ZC-Anstieg > +10% → short LE 1M, dann long 3M.

**Horizonte:** 22 Tage, 66 Tage  
**Datenquelle:** yfinance ZC=F, LE=F  
**Multiple-Testing-N:** Test-Nr. 9  
**Status:** PENDING

---

### H-LE-02: USDA Cattle-on-Feed Surprise → Preis-Reaktion

**Kausalkette:**  
USDA Cattle-on-Feed-Report (monatlich, NASS) zeigt mehr Rinder on feed als erwartet
→ Angebot in 3–6 Monaten höher → Preis-Druck.

**Feature:**  
`wasde_surprise` für Cattle, oder NASS-Daten-Pull.  
**Multiple-Testing-N:** Test-Nr. 10  
**Status:** PENDING

---

## HG — Kupfer

### H-HG-01: China-Industrieproduktion Surprise → Kupfer-Nachfrage

**Kausalkette:**  
China-Industrieproduktion (NBS, via FRED Proxy) überraschend stark →
Kupfer-Nachfrage steigt → Preis ↑.

**Feature:**  
`fred_vintage` für China-IP (FRED `CHNPRINTO01IXPYM`, OECD MEI), Trend-Surprise =
Index − 6M-Gleitmittel. **Daten-Caveat (0046):** diese Reihe hat KEINE ALFRED-Vintages
(1 Print/Monat) → PIT nur über konservativen Publikations-Lag (Ref+2M); Reihe endet
2023-11 (discontinued).

**Horizonte:** 22 Tage, 66 Tage  
**Datenquelle:** FRED/ALFRED API (`get_fred_vintage()`)  
**Multiple-Testing-N:** Test-Nr. 11  
**Status:** REJECT — **bestand als EINZIGES den IC-Screen** (IC(66d)=+0.12, naive p=0.046),
aber volle Batterie widerlegt: überlapp-korrekte Permutation **p=0.099** (naive IC-t durch
überlappende Returns aufgebläht), **IS 0.64→OOS 0.07** (Superzyklus-Drift-Falle), Sharpe
0.39≈B&H 0.35 (Beta), nicht lag-robust (3M p=0.172), US-INDPRO-Cross-Check mit ECHTEN
Vintages leer (p=0.79). Multiple-Testing-Artefakt unter 14 Hypothesen. Strategie 0046.
**Methodik-Lehre: bei überlappenden Forward-Returns ist die IC-t-Statistik wertlos — nur
der Permutationstest auf der Position zählt.**

---

### H-HG-02: LME + SHFE Lagerbestands-Änderung → Preis-Signal

**Kausalkette:**  
Rückgang der LME-Kupfervorräte → physische Knappheit → Backwardation → Preis ↑.
Wöchentliche LME-Bestandszahlen sind frei verfügbar.

**Feature:**  
`inventory_change` LME-Kupferbestände (Δ WoW). Quellen: LME.com weekly data /
westmetall.com (bereits in `lme_data.py` für andere Metalle).  
**Multiple-Testing-N:** Test-Nr. 12  
**Status:** PENDING

---

## PL / PA — Platin / Palladium

### H-PL-01: Südafrika-Loadshedding → Minen-Output-Risiko → Preis ↑

**Kausalkette:**  
Eskom Loadshedding erhöht (Stufe 4+) → Platinminen im Bushveld-Komplex müssen
Produktion drosseln (kein Strom für Lift/Ventilation) → Supply-Risiko → PL-Preis ↑.

**Feature:**  
Loadshedding-Stufe als numerisches Feature (freie Daten von loadshedding.co.za oder
Eskom-API). Wöchentlicher Durchschnitt der Stufe; Anomalie vs. Jahresmittel.

**Vorab-Prediction:** Durchschnittsstufe > 4.0 → long PL über 1M–3M.

**Horizonte:** 22 Tage, 66 Tage  
**Datenquelle:** Eskom/loadshedding public data (TBD — Verfügbarkeit prüfen)  
**Multiple-Testing-N:** Test-Nr. 13  
**Status:** PENDING (Datenverfügbarkeit zuerst verifizieren)

---

### H-PA-01: Autoabsatz-Surprise → Palladium-Nachfrage (Katalysatoren)

**Kausalkette:**  
Palladium wird primär in Benzin-Katalysatoren verwendet.
US + China Autoabsatz-Surprise → Palladium-Nachfrage-Signal.

**Feature:**  
US Autoabsatz (FRED: TOTALSA, monatlich), ALFRED-Vintage für PIT.
YoY-Änderung als Feature.  
**Multiple-Testing-N:** Test-Nr. 14  
**Status:** PENDING

---

## Multiple-Testing-Budget

Aktuell vorab registrierte Tests: **14**  
Für den DSR gilt: `N = 14` (und steigt mit jedem nachträglich hinzugefügten Test).
Jeder Test, der NACH der Registrierung hier hinzugefügt wird, erhöht N rückwirkend
für alle bereits getesteten Hypothesen.

**Regel:** Erst eintragen, dann testen. Niemals nachträglich aus dem Register löschen.

---

## Scoring-Schwellen (pro Hypothese)

Ein Feature gilt als **Kandidat** (→ Phase 4 / Portfolio-Overlay) wenn:
1. Permutationstest: p < 0.05 (zweiseitig)
2. DSR überlebt bei N = aktuellem Register-Stand
3. OOS ≥ IS × 0.5 (kein vollständiger Kollaps)
4. Netto-Sharpe nach Kosten > 0 (auf dem richtigen Cost-Preset)
5. Bootstrap-KI 95% auf Trade-EV schließt Null aus
6. Median-Trade > 0 (kein Fat-Tail-Spiel)

Alle 6 müssen erfüllt sein. Einer reicht nicht.
