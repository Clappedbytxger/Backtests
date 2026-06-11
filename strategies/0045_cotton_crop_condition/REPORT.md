# Strategie 0045 — Baumwolle (CT) Fundamental: NASS Crop-Condition Δ (H-CT-01)

- **Kategorie:** fundamental / alt-data / report-surprise
- **Status:** rejected
- **Datum:** 2026-06-07
- **Universum:** Baumwolle-Future (CT=F, ICE)
- **Stichprobe:** 2000–2026 (CT-Futures), NASS-Condition Texas 2000–2025
- **Getestete Hypothese:** H-CT-01 (aus `fundamentals/HYPOTHESES.md`)

---

## 1. Hypothese

Trockenheit/Hitze in West-Texas → USDA NASS wöchentliche Crop-Condition (Anteil
Good+Excellent) fällt → Ertragsschätzung sinkt → Baumwoll-Preis steigt über 1W–1M.
Positionieren, wenn die Woche-über-Woche-Verschlechterung scharf ist (Δ < −5 Prozent-
punkte, vorab registriert).

---

## 2. Makro-Begründung & Bedeutung dieses Tests

**Erster Test der Report-Surprise-/PIT-Klasse mit echten USDA-Daten.** Das ist die
*einzige* Klasse, die im Katalog je funktioniert hat (Mais-WASDE 0032: 78 % der Edge
auf 6 Report-Tagen). Crop-Condition ist der höherfrequente Cousin — eine wöchentliche,
point-in-time Beobachtung. Texas ist der größte US-Baumwollstaat (~40 % der Produktion,
der West-Texas-Dürregürtel). Die Kernfrage: trägt die *inkrementelle* wöchentliche
Condition-Änderung einen handelbaren Surprise, oder ist dieser meistbeobachtete
US-Ag-Report laufend (effizient) eingepreist?

---

## 3. Regeln (vorab registriert)

- **Feature:** WoW-Δ des Good+Excellent-Anteils (NASS, Texas). Nur konsekutive
  Saison-Wochen (Lücke zur Vorbeobachtung ≤ 14 Tage → Kreuz-Saison-Sprünge entfernt).
- **Event/Signal:** Long CT=F wenn Δ < −5pp (Verschlechterung). Haltedauer 22 Tage.
- **PIT:** NASS-Release Montag 16:00 ET; week_ending = Vorsonntag; release_date =
  Sonntag + 1 (Montag). Engine-Shift +1 Tag → effektiver Entry am Folgetag, kein Look-Ahead.

---

## 4. Kosten- & Ausführungsannahmen

`IBKR_SOFTS` (4 bps/Seite = 8 bps RT). CT=F ~50.000 lbs à ~70 ¢/lb. EOD-Einstieg.

---

## 5. Ergebnisse

### 5a. Kontinuierlicher IC-Screen (585 in-season Wochen)

| Horizont | IC | Perm-p |
|----------|-----:|-------:|
| 5 Tage  | −0.001 | 0.978 |
| 10 Tage | −0.051 | 0.240 |
| 22 Tage | −0.037 | 0.419 |

IC nahe Null, bei längeren Horizonten leicht **negativ** (Verschlechterung → eher
*fallender* Preis, gegen die Hypothese — aber insignifikant). **Kein Signal.**

### 5b. Event-Study (Δ < −5pp, 41 Events)

| Horizont | mean | median | win |
|----------|-----:|-------:|----:|
| 5 Tage  | −0.69% | −0.47% | 44% |
| 22 Tage | −0.43% | **+0.10%** | 51% |

Reiner Münzwurf. 41 Events sind ein ordentlicher Stichprobenumfang (vs. Frost 0044: nur 5),
und das Ergebnis ist eindeutig leer — kein Diffusions-Edge nach scharfer Verschlechterung.

### 5c. Netto-Backtest (long 22d nach jedem Event)

| Kennzahl | Wert |
|----------|-----:|
| Sharpe | −0.23 |
| CAGR | −1.5 % |
| Max Drawdown | −51.4 % |
| Trefferquote | 50 % (28 Trades) |
| Expectancy/Trade | −0.92 % |
| Median/Trade | +0.18 % |

## 6. Signifikanz

| Test | Wert |
|------|-----:|
| Permutationstest p | 0.717 ✗ |
| Bootstrap Sharpe 95%-KI | [−0.58, 0.17] ✗ |
| t-Test mittlere Rendite p | 0.743 ✗ |
| Deflated Sharpe (PSR) | 0.00 |

Alle Tests klar insignifikant.

---

## 7. Verdict

**ABGELEHNT** auf beiden Wegen: kein kontinuierliches IC-Signal (sogar leicht negativ)
und leere Event-Study (22d-Median +0.10 %, Win 51 % bei n=41).

**Die Pointe — warum gerade die Report-Surprise-Klasse hier leer ist:** Die wöchentliche
Crop-Condition ist einer der **meistbeobachteten** US-Ag-Reports. Die inkrementelle
WoW-Änderung wird laufend und effizient eingepreist — es gibt keinen konzentrierten
Informations-Release mit Surprise-Lücke. Das ist der entscheidende Unterschied zum
diskreten **monatlichen WASDE-Bericht** (0032), der eine einzelne, scharf datierte
Schätzungs-Revision liefert. **Nicht jede „Surprise"-Klasse trägt einen Edge — nur die
mit echter diskreter Informations-Konzentration.** Eine wöchentliche, kontinuierlich
beobachtete Reihe ist eher wie ein Preis als wie ein Report.

**Befund über das Fundamental-Programm (0042–0045):** Vier Hypothesen, vier Ablehnungen
(Zucker/Wetter, Zucker/Ethanol, Kaffee/Frost, Baumwolle/Crop-Condition). Die einzige je
funktionierende Klasse (diskreter WASDE-Surprise, 0032) ist über die FAS-PSD-API nur
flakey erreichbar. **Die Daten-Erreichbarkeit ist jetzt aber gelöst** (FRED/EIA/NASS live,
gecacht) — der nächste Test ist die FRED-Makro-Klasse (H-HG-01), die strukturell anders
ist (ALFRED-Vintages = echte point-in-time Makro-Revisionen, nicht eine
hochbeobachtete Preisreihe).

**Nächste Schritte:**
1. **H-HG-01** (Kupfer / China-Industrieproduktion, FRED-ALFRED-Vintages) — als Nächstes.
2. Diskreten WASDE-Surprise (H-SB-03/H-CT-02) nachholen, sobald FAS-PSD-API wieder 200 liefert
   (aktuell HTTP 500) oder via Cornell-Mann-WASDE-CSV-Archiv.

---

## Plots

- `results/plots/crop_condition_overview.png` — wöchentliche Condition-Δ + CT-Preis mit Events
- `results/plots/ic_decay.png` — IC-Decay (alle Horizonte ≈ 0)
