# Strategie 0043 — Zucker #11 (SB) Fundamental: Ethanol-Parität (H-SB-02)

- **Kategorie:** fundamental / alt-data
- **Status:** rejected
- **Datum:** 2026-06-07
- **Universum:** Zucker #11 Futures (SB=F, ICE)
- **Stichprobe:** 2007–2026 (IC-Screen; kein Backtest ausgeführt)
- **Getestete Hypothese:** H-SB-02 (aus `fundamentals/HYPOTHESES.md`)

---

## 1. Hypothese

Hoher Ethanolpreis relativ zu Zucker → brasilianische Mühlen lenken Zuckerrohr in
Ethanol statt Zucker → Zucker-Angebot sinkt über die Crush-Season → Zucker-Preis
steigt über 1–3 Monate (Schwerpunkt 3M wegen langsamer Angebotsreaktion).

---

## 2. Makro-Begründung

Brasilien ist der weltgrößte Zuckerproduzent; die Mühlen sind technisch flexibel und
entscheiden saisonal, ob Zuckerrohr zu **Zucker oder Ethanol** verarbeitet wird. Diese
Entscheidung hängt am relativen Preis: Ist Ethanol (bzw. sein Substitut Benzin) teuer
gegenüber Zucker, wandert mehr Cane in Ethanol → das Zucker-Angebot sinkt → der
Zuckerpreis sollte mit einigen Wochen/Monaten Verzögerung steigen.

Ökonomisch fundiert (das ist die reale „Zucker-Ethanol-Parität", ein Standardkonzept
im Soft-Commodity-Handel). Makro-Begründung: ✓ vorhanden.

---

## 3. Datensubstitution (ehrlich dokumentiert)

Die **EIA Weekly Ethanol Price API** — die vorgesehene Quelle (H-SB-02) — ist in der
Arbeitsumgebung **geoblockt (HTTP 403 schon auf dem API-Root ohne Key)**, dieselbe
Netzwerk-/WAF-Wand wie USDA in Strategie 0042.

Substituiert wird der **ökonomische Treiber** der Ethanol-Attraktivität, der **Benzinpreis**:
In Brasilien konkurriert Hydro-Ethanol direkt mit Benzin an der Zapfsäule (Parität ~70 %
des Benzinpreises). Das **Benzin-zu-Zucker-Preisverhältnis** ist damit die ökonomische
Entscheidungsvariable der Mühlen. Das ist ein **Proxy** — nicht der EIA-Ethanolpreis —
und wird als solcher gekennzeichnet.

Alle Quellen frei + erreichbar (yfinance):
- **Primär:** RBOB-Benzin / Zucker, Paritäts-Ratio z-Score (RB=F, 252-Tage-Fenster)
- **Cross-Check:** Rohöl / Zucker (CL=F, längere Historie, Negativ-Print-Guard 0005:
  der WTI-Print von −37.63 am 2020-04-20 wird auf NaN gesetzt + vorwärts gefüllt)
- **Placebo:** RBOB / Gold → sagt Gold voraus. Gold hat **keinen** Ethanol-Mechanismus;
  leuchtet der Placebo gleich stark, ist ein Zucker-Signal nur generische Energie-Beta.

---

## 4. Regeln (vorab registriert)

- **Feature:** Paritäts-Ratio z-Score (Energie/Zucker), 252-Tage rollierend, shift(1)
  (rein vergangenheitsbasiert, PIT-korrekt). Marktpreise → `release_date = ref_date`.
- **Signal:** Long SB=F wenn z > +1.0 (Ethanol/Benzin teuer relativ zu Zucker).
- **Haltedauer:** 66 Handelstage (≈ 3 Monate, Crush-Season-Lag — vorab fixiert).
- **Gate:** IC-Permutationstest p < 0.10 bei 66-Tage-Horizont (Primär-Feature).
- **Look-Ahead-Schutz:** rollierender z-Score + Engine-Shift (1 Tag).

---

## 5. Kosten- & Ausführungsannahmen

- Kostenmodell: `IBKR_SOFTS` (4 bps/Seite = 8 bps Round-Trip)
- SB=F: ~112.000 lbs à ~20 ¢/lb → ~22.000 USD Nominalwert, EOD-Einstieg

---

## 6. IC-Screen-Ergebnisse (kein Backtest ausgeführt)

| Feature                  | IC(5d) | IC(22d) | IC(66d) | Perm-p(66d) | Verdict |
|--------------------------|-------:|--------:|--------:|------------:|---------|
| **RBOB/Zucker (primär)** | −0.039 | +0.015  | +0.040  | **0.530**   | FAIL ✗  |
| Crude/Zucker (Cross)     | −0.046 | +0.022  | +0.020  | 0.742       | FAIL ✗  |
| **RBOB/Gold (Placebo)**  | +0.004 | −0.168  | **−0.274** | **0.000** | (leuchtet) |

N = 232 monatliche Beobachtungen (2007–2026).

**Primär-Feature versagt:** RBOB/Zucker-Parität hat über alle Horizonte keine
Vorhersagekraft für Zucker-Returns. Perm-p bei Ziel-Horizont 66d = 0.530.
**Crude bestätigt** auf längerer Historie: ebenfalls ≈0.

---

## 7. Signifikanz

**IC-Screen failed.** Kein Backtest, keine Signifikanzbatterie auf einem Zucker-Edge —
es gibt keinen.

---

## 8. Robustheit & der Placebo-Befund

Der **Gold-Placebo ist stark signifikant** (IC(66d) = −0.27, perm-p = 0.0000), während
das eigentliche Zucker-Ziel flach bleibt. Das ist methodisch der zentrale Lernpunkt:

1. **Der Placebo funktioniert.** Die IC-Maschinerie erfasst einen echten, generischen
   Energie-Makro-Effekt (hohes Benzin-zu-Gold-Verhältnis → Gold fällt über 1–3 Monate,
   getrieben v.a. durch Gold-Mean-Reversion im Nenner + Energie-Inflations-Zyklus).
2. **Genau deshalb ist der Placebo wertvoll:** Hätte das RBOB/Zucker-Feature ein Signal
   gezeigt, wäre es angesichts des starken Placebo-Effekts hochverdächtig auf reine
   Energie-/Inflations-Beta gewesen — *nicht* den Cane-Diversions-Mechanismus.
3. **Das Zucker-Ziel zeigt aber NICHTS.** Zucker reagiert auf diesem Horizont nicht auf
   die Benzin-Parität — weder über den Ethanol-Mechanismus noch über generische Beta.

---

## 9. Verdict

**ABGELEHNT** auf IC-Ebene. Die Benzin/Ethanol-zu-Zucker-Parität (Proxy für H-SB-02)
hat keine nachweisbare Vorhersagekraft für SB-Futures-Returns (2007–2026, 232 Obs.).

**Warum kein Backtest:** IC ≈ 0 beim Ziel-Horizont. Ein Backtest hätte nur Rauschen
produziert und das DSR-Budget (N=14) belastet.

**Einschränkung:** Getestet wurde der **Energiepreis-Proxy**, nicht der echte
EIA-Ethanolpreis (geoblockt). Es ist denkbar — wenn auch nach diesem Befund
unwahrscheinlich — dass der *direkte* Ethanol-zu-Zucker-Spread (mit der brasilianischen
Realität: BRL-Wechselkurs, Petrobras-Benzinpreisregulierung, Anhydro/Hydro-Mix) ein
Signal trägt, das der globale Benzinpreis verwischt. Das wäre ein separater Test, sobald
EIA/CEPEA-Ethanoldaten zugänglich sind — kein neuer Test ohne neue Registrierung.

**Bisheriger Befund über beide Zucker-Hypothesen (0042 + 0043):**
Weder das São-Paulo-Wetter (H-SB-01) noch die Energie-/Ethanol-Parität (H-SB-02) tragen
einen 1–3-Monats-Edge auf Zucker #11. Beide sind die *meistbeobachteten* Inputs des
Marktes → vermutlich vollständig eingepreist (Framework-These: Edge ≠ Datenexklusivität;
diese breiten, langsamen Fundamentaldaten sind exakt die, die alle sehen).

**Nächste Schritte:**
1. Markt wechseln statt Zucker weiter durchzukauen. **H-KC-01 (Kaffee-Frost)** ist der
   nächste Kandidat: Frost-Events sind *seltener, schärfer und lokaler* als Niederschlag
   oder ein globaler Energiepreis — höhere Chance auf ein echtes, nicht voll eingepreistes
   Diffusionssignal (rein Open-Meteo, keyless, erreichbar).
2. H-SB-03 (WASDE) bleibt offen wegen API-Block — aus Heimnetz nachholen.

---

## Plots

- `results/plots/parity_feature_overview.png` — Benzin/Zucker-Paritäts-z-Score + SB-Preis
- `results/plots/ic_decay_summary.png` — IC-Decay aller 3 Features (Primär flach, Placebo leuchtet)
