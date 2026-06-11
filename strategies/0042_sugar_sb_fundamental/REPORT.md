# Strategie 0042 — Zucker #11 (SB) Fundamental: São Paulo Dürre + WASDE Surprise

- **Kategorie:** fundamental / alt-data
- **Status:** rejected
- **Datum:** 2026-06-07
- **Universum:** Zucker #11 Futures (SB=F, ICE)
- **Stichprobe:** 2000–2026 (IC-Screen; kein Backtest ausgeführt)
- **Getestete Hypothesen:** H-SB-01, H-SB-03 (aus `fundamentals/HYPOTHESES.md`)

---

## 1. Hypothese

São Paulo Niederschlagsdefizit in der Wachstumsphase (Okt–Mär) signalisiert
Produktionsrückgang → Zucker-Preis steigt über 1–3 Monate (H-SB-01).
Monatliche USDA-WASDE-Revisions-Surprises (Produktionsdowngrade) diffundieren
langsam in den Preis über 1 Monat (H-SB-03).

---

## 2. Makro-Begründung

**H-SB-01 (Wetter):** Brasilien produziert ~40 % des weltweiten Zucker-Exports.
Der CWB-Gürtel (Bundesstaat São Paulo) ist die zentrale Anbauregion. Ein Niederschlagsdefizit
während der Wachstumsphase (Oktober bis März, Regenzeit) sollte Ertragsverluste triggern,
die sich über 1–3 Monate in USDA-Produktionsschätzungen und dann im Preis niederschlagen
(langsame Diffusion durch Analysten-Konsens-Anpassung).

**H-SB-03 (WASDE):** USDA WASDE-Revisionssurprises sind für Mais (0032) ein echter,
konzentrierter Signal-Treiber. Übertragen auf Zucker: negativer Surprise (Downgrade)
→ Diffusion über 1–4 Wochen → bullischer Preisdruck.

Ökonomisch plausibel. Makro-Begründung: ✓ vorhanden.

---

## 3. Regeln (vorab registriert)

- **Feature H-SB-01:** Monatlicher Niederschlag-z-Score für São Paulo (lat=-22°, lon=-47°,
  Open-Meteo ERA5), rollierend-vergangenheitsbasierte 20-Jahres-Klimatologie (PIT-korrekt).
  Nur Wachstumsmonate (Okt–Mär). `release_date = 1. des Folgemonats`.
- **Feature H-SB-03:** WASDE Produktions-Surprise = aktueller − Vormonats-Wert.
  `release_date ≈ 10. des Monats` (naïver Proxy). *(Nicht testbar — FAS PSD API
  nicht erreichbar in dieser Umgebung, siehe Abschnitt 8.)*
- **Signal:** Long SB=F wenn z < −1.5σ (H-SB-01) bzw. Surprise < 0 (H-SB-03).
- **Haltedauer:** 22 Handelstage (≈ 1 Monat).
- **Look-Ahead-Schutz:** `pit_join()` + Engine-Shift (1 Tag). Klimatologie rein vergangenheitsbasiert.
- **Gate:** IC-Permutationstest p < 0.10 bei 22-Tage-Horizont → Backtest wird nur
  ausgeführt, wenn mindestens ein Feature diesen Gate passiert.

---

## 4. Kosten- & Ausführungsannahmen

- Kostenmodell: `IBKR_SOFTS` (4 bps/Seite = 8 bps Round-Trip)
- SB=F: ca. 112.000 lbs à ~22 ¢/lb → ~24.600 USD Nominalwert
- Spread: typisch 1–2 Ticks (~5–10 bps RT), konservativ auf 8 bps RT gesetzt
- Einstieg täglich Close (EOD), kein Intraday-Timing

---

## 5. IC-Screen-Ergebnisse (kein Backtest ausgeführt)

### H-SB-01: Niederschlag-Anomalie (neg_precip_anomaly = −z)

| Horizont | N Beob. | IC     | t-Stat | p-Wert | Perm-p |
|----------|---------|--------|--------|--------|--------|
| 5 Tage   | 158     | +0.014 | +0.18  | 0.860  | 0.858  |
| 22 Tage  | 158     | +0.002 | +0.03  | 0.979  | 0.978  |
| 66 Tage  | 156     | −0.073 | −0.91  | 0.364  | 0.346  |

**Hit-Rate (22d):** 51.9 % gesamt — kaum über Münzwurf.
**Hit-Rate Dürre-Monate (Anomalie-Signal positiv, 22d):** 46.9 % — schlechter als Münzwurf.

### H-SB-03: WASDE-Surprise

Nicht testbar (USDA FAS PSD API im Testumgebungs-Netzwerk nicht erreichbar, HTTP 403/404).
Muss manuell mit lokalem API-Key oder aus einer anderen Netzwerkumgebung ausgeführt werden.

---

## 6. Signifikanz

**IC-Screen failed.** Kein Backtest ausgeführt.

Alle p-Werte (Permutationstest, 500 Läufe) weit über 0.10. IC bei Ziel-Horizont 22 Tage = 0.002,
nicht von null unterscheidbar. Das ist statistisch eindeutig: kein Signal vorhanden.

---

## 7. Robustheit

Wegen mangelnder IC-Signifikanz nicht untersucht.

Beobachtungen aus dem IC-Profil:
- **Kein monotoner IC-Decay:** IC(5d) > IC(22d) < IC(66d) — kein typisches Diffusionsprofil.
- **IC(66d) = −0.073 (negativ):** Schwache Anzeichen, dass Dürre-Monate eher mit *rückläufigem*
  Preis über 3 Monate korrelieren — das Gegenteil der Hypothese. Nicht signifikant, aber noteworthy.
  Mögliche Erklärung: El-Niño-Muster, bei dem Trockenheit in São Paulo mit gleichzeitig hohem
  globalen Zuckerpreis zusammenfällt (Mean-Reversion danach).
- **Hit-Rate für Dürre → Long:** 46.9 % (22d) — *schlechter* als Münzwurf. Das Feature predicted
  die Richtung nicht besser als Zufall.

---

## 8. Verdict

**ABGELEHNT** auf IC-Ebene. Kein Edge zwischen São Paulo Niederschlagsanomalie und
SB Futures-Returns nachweisbar (2000–2026, 158 monatliche Beobachtungen).

**Warum kein Backtest:** Der IC-Gate ist der korrekte wissenschaftliche Schritt.
Ein Backtest hätte angesichts IC ≈ 0 nur zufällige Ergebnisse produziert, die bei
N=14 im Multiple-Testing-Budget das DSR-Rauschen erhöhen würden.

**H-SB-03 Ausstand:** WASDE-Surprise (H-SB-03) ist noch nicht getestet — technische
Einschränkung (FAS PSD API), kein inhaltlicher Befund. Kann nachgeholt werden, sobald
API-Zugang besteht (ggf. over Home-Network oder mit direktem USDA-Account-Token).

**Was das Muster bedeutet:**
- Das São-Paulo-Wetter ist *zu breite*, zu verzögerte und zu verrauschte Information für
  1-3-Monats-Preis-Edges. Wahrscheinlich schon längst in den USDA-Ernte-Prognosen
  eingepreist (HFT-Diffusions-Problem, wie in 0041 für ES/NQ-Lead-Lag gefunden).
- Sugar #11 hat zusätzlich Brasilien-Ethanol-Parität als Demand-Side-Variable, die mit
  dem Wetter interagiert — ein einfaches Wetter-z-Score-Signal unterschätzt diese Komplexität.
- Interessanter: IC(66d) negativ → mögliches **Mean-Reversion**-Muster nach Dürre-Preisspiike.
  Das wäre H-SB-01-alt: *short* nach realisiertem Dürre-Spike im Preis. Aber das wäre
  ein neuer, unregistrierter Test → muss erst in HYPOTHESES.md eingetragen werden.

**Nächste Schritte:**
1. H-SB-03 (WASDE) aus Home-Network testen (FAS PSD API-Zugang klären)
2. H-SB-02 (Ethanol-Parität) als nächste SB-Hypothese registrieren + testen
3. Cross-Market: H-KC-01 (Kaffee-Frost) als nächste Hypothese — Frost-Events
   sind seltener und spezifischer als Niederschlag; potenziell höheres IC-Niveau

---

## Plots

- `results/plots/weather_feature_overview.png` — São Paulo Niederschlag-Anomalie über Zeit
  + SB=F Preis mit Dürre-Perioden-Overlay
- `results/plots/ic_decay_rejected.png` — IC-Decay über alle Horizonte (alle nahe null)
