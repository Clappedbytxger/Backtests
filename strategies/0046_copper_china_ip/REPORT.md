# Strategie 0046 — Kupfer (HG) Fundamental: China-Industrieproduktions-Surprise (H-HG-01)

- **Kategorie:** fundamental / alt-data / makro
- **Status:** rejected
- **Datum:** 2026-06-07
- **Universum:** Kupfer-Future (HG=F, CME)
- **Stichprobe:** 2000–2023 (China-IP-Reihe endet 2023-11), IS 2000–2012 / OOS 2013–2023
- **Getestete Hypothese:** H-HG-01 (aus `fundamentals/HYPOTHESES.md`)

---

## 1. Hypothese

China-Industrieproduktion beschleunigt über ihren jüngsten Trend → Kupfernachfrage
steigt („Dr. Copper": China ist ~50 % der Weltnachfrage) → Preis steigt über 1–3 Monate.

---

## 2. Bedeutung dieses Tests

**Erstes Fundamental-Feature, das den IC-Screen passiert** (IC(66d)=+0.12, perm-p=0.046,
richtiges Vorzeichen). Es bekam deshalb die volle Validierungsbatterie — und ist der
Lehrfall dafür, **warum der IC-Screen allein nicht genügt**. Drei rote Flaggen waren vorab
bekannt und wurden geprüft:
1. Die China-IP-Reihe (FRED `CHNPRINTO01IXPYM`, OECD MEI) hat **keine ALFRED-Vintages**
   (1 Print/Monat) → PIT nur über konservativen **Publikations-Lag** (Referenzmonat M
   bekannt ab 1. von M+2), nicht über echte Vintages. Robustheit: 3M-Lag-Stress.
2. Reihe **discontinued** (endet 2023-11) → nicht live-handelbar, historische Studie.
3. **Überlappende 66-Tage-Returns** blähen die naive IC-t-Statistik auf → die
   Permutation (permutiert die gehaltene Position) ist die ehrliche Signifikanz.
4. Kupfer hatte einen massiven China-Superzyklus-Drift (2000–2011) → ein long-lastiges
   Signal sieht durch Beta gut aus. IS/OOS + Permutation + B&H-Vergleich kontrollieren das.

---

## 3. Regeln (vorab registriert)

- **Feature:** China-IP-Index − 6-Monats-Gleitmittel (shift(1)) = Trend-Surprise.
- **Signal:** Long HG=F wenn Surprise > 0 (IP über Trend = Beschleunigung), Halt 66 Tage.
- **PIT:** release_date = Referenzmonat + 2 Monate (konservativer NBS/OECD-Publikations-Lag).
- **Kosten:** `IBKR_METALS_LIQUID` (~4 bps RT).

---

## 4. Ergebnisse — die Batterie widerlegt den IC-Treffer

### 4a. IC-Screen (bestanden — aber irreführend)

| Horizont | IC | naive Perm-p |
|----------|-----:|------:|
| 22 Tage | +0.068 | 0.270 |
| 66 Tage | **+0.121** | **0.046** ✓ |

### 4b. Volle Validierung (Primär, Lag 2M)

| Kennzahl | Wert | Kommentar |
|----------|-----:|-----------|
| Sharpe (gesamt) | 0.39 | kaum über B&H 0.35 |
| **IS-Sharpe** | **0.64** | China-Superzyklus |
| **OOS-Sharpe** | **0.07** | **kollabiert** |
| Exposure | 65 % | long-lastig → Beta-Verdacht |
| Trefferquote | 37 % | fat-tail-getrieben |
| **Permutation p** | **0.099** | überlapp-korrekt → **verfehlt 5 %** |
| Bootstrap Sharpe-KI | [0.02, 0.77] | knapp über 0 |
| t-Test p | 0.013 | (überlapp-anfällig) |
| Deflated Sharpe (PSR) | 0.00 | Multiple-Testing-Strafe |

### 4c. Robustheit

| Test | Perm-p | OOS-Sharpe | Befund |
|------|-------:|-----------:|--------|
| **Lag-Stress 3M** | 0.172 | 0.15 | nicht robust gegen konservativeren Lag |
| **US-INDPRO (echte Vintages)** | 0.786 | 0.02 | komplett leer — properly-vintaged Makro-Surprise sagt Kupfer NICHT vorher |

---

## 5. Verdict

**ABGELEHNT (2/5 Kriterien).** Der IC-Gate-Treffer (p=0.046) war ein **Multiple-Testing-
Artefakt**, von der Batterie auf vier unabhängigen Wegen entlarvt:

1. **Naive IC vs. ehrliche Permutation:** Die naive IC-t-Statistik (p=0.046) ist durch
   überlappende 66-Tage-Forward-Returns aufgebläht. Die Permutation auf der tatsächlich
   gehaltenen Position — die die Überlappung respektiert — gibt **p=0.099**, nicht
   signifikant. *Das ist die zentrale methodische Lehre: bei überlappenden Returns ist
   die IC-t-Statistik nicht vertrauenswürdig; nur der Permutationstest zählt.*
2. **OOS-Kollaps:** IS-Sharpe 0.64 → OOS 0.07. Die ganze Performance liegt im China-
   Superzyklus vor 2013 — exakt die Drift-Falle aus Nasdaq 0017 / Zucker 0034.
3. **Beta, nicht Timing:** Sharpe 0.39 ≈ B&H 0.35 bei 65 % Exposure → das Signal ist
   großteils stures Kupfer-Long während des Booms, kein Timing.
4. **Cross-Check leer:** Die US-INDPRO-Variante mit *echten* ALFRED-Vintages (sauberste
   PIT-Daten im ganzen Programm) sagt Kupfer überhaupt nicht vorher (p=0.79). Hätte der
   China-Effekt einen realen Makro-Wachstums-Kern, sollte das US-Pendant zumindest andeuten.

**Wert dieses Tests:** Er zeigt die Verteidigung-in-der-Tiefe des Frameworks. Der
IC-Screen ließ einen Kandidaten durch; Permutation + IS/OOS + Lag-Robustheit + Vintage-
Cross-Check haben ihn übereinstimmend gekillt. **Genau dafür existiert die Batterie hinter
dem IC-Gate.** Bei 14 registrierten Hypothesen ist *ein* marginaler IC bei *einem* Horizont
(p=0.046) statistisch zu erwarten — der DSR (PSR=0) sagt das direkt.

**Befund über das Fundamental-Programm (0042–0046):** Fünf Hypothesen, fünf Ablehnungen.
Wetter (0042), Ethanol-Parität (0043), Frost (0044), Crop-Condition (0045), Makro-Wachstum
(0046). Die meistbeobachteten Soft-Commodity- und Makro-Fundamentaldaten tragen keinen
handelbaren 1–3-Monats-Edge. Die einzige je funktionierende Klasse (diskreter WASDE-Surprise,
0032) bleibt über die FAS-PSD-API nur flakey erreichbar (HTTP 500).

**Nächste sinnvolle Schritte:**
1. Diskreten WASDE-Surprise (H-SB-03/H-CT-02/H-KC-02) nachholen, sobald FAS-PSD wieder
   200 liefert oder via Cornell-Mann-WASDE-CSV-Archiv — das ist der einzige verbleibende
   Pfad mit echter diskreter Informations-Konzentration (wie Mais 0032).
2. Sonst Fundamental-Programm als „erschöpft auf den freien, breit-beobachteten Quellen"
   einordnen und zur Saison-Schiene (Platin 0021 confirmed) zurückkehren.

---

## Plots

- `results/plots/china_ip_overview.png` — Trend-Surprise + Kupferpreis mit Long-Perioden
- `results/plots/equity_vs_bh.png` — Equity vs. Buy & Hold (OOS-Kollaps sichtbar)
- `results/plots/ic_decay.png` — IC-Decay (66d positiv, aber Permutation entlarvt es)
