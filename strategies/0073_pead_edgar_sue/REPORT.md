# Strategie 0073 — PEAD via EDGAR-SUE (IC-Gate-Pilot)

- **Kategorie:** event / equities / behavioral (cross-sectional)
- **Status:** testing — Signal vorhanden, handelbarer Edge unbewiesen (Kill-Screen bestanden)
- **Datum:** 2026-06-14
- **Universum:** 98 US-Large-Caps (S&P-100-nah; survivorship-VERZERRT auf der Mitgliedschaft, bewusst)
- **Stichprobe:** gepoolt 2009-10 … 2026-06 (Post-XBRL-Ära), 4.915 Earnings-Events
- **Vorläufer:** `strategies/0055_pead_blocked/ASSESSMENT.md` (war Daten-Blocker — jetzt teilweise gelöst)

## 1. Hypothese

Aktien mit positivem Earnings-**Surprise** driften über Wochen weiter in dessen
Richtung (Post-Earnings Announcement Drift, Ball/Brown 1968, Bernard/Thomas
1989/90). Cross-sectional: hohe **SUE** (Standardized Unexpected Earnings) →
positive markt-adjustierte Drift über 1–3 Monate.

## 2. Makro-Begründung

Strukturell/behavioral: systematische **Under-Reaction** auf Earnings-News
(begrenzte Aufmerksamkeit, langsame Informationsdiffusion, Limits-to-Arbitrage
besonders in kleinen/illiquiden Namen). Eine der am robustesten belegten
Anomalien der Literatur; in McLean/Pontiff (2016) **unterdurchschnittlich**
post-publikations-zerfallen. Erfüllt das Kausalketten-Kriterium des Katalogs.

## 3. Daten-Durchbruch — was 0055 löste (und was nicht)

0055 war zweifach blockiert: (a) historische Earnings-Surprises survivorship-frei
nur kostenpflichtig, (b) survivorship-freies Aktien-Universum nur teuer.

**Gelöst (a) — gratis + survivorship-frei auf der Earnings-Seite:**
SEC EDGAR XBRL (`companyconcept`) liefert die berichtete Quartals-EPS jedes je
registrierten Filers (delistete behalten ihre CIK). Statt Analysten-Konsens
nutze ich das **Seasonal-Random-Walk-SUE** — `(EPS_q − EPS_{q−4Q}) / std(frühere
Saison-Differenzen)` — das **keine** Analysten-Schätzung braucht, nur berichtete
EPS. Neuer Loader `quantlab.edgar_data` (Parquet-Cache, SEC-konforme UA,
Rate-Limit), Tests in `tests/test_edgar_sue.py` (5/5).

**NICHT gelöst (b):** survivorship-freie *Kurse* delisteter Namen bleiben offen.
Deshalb ist dieser Lauf bewusst ein **Kill-Screen auf dem heutigen Large-Cap-
Universum** — survivorship-VERZERRT auf der Mitgliedschaft (nur Überlebende). Das
ist die *entgegengesetzte* Verzerrung eines sauberen PEAD-Tests und beantwortet
die einzige entscheidende Vorfrage: **zeigt sich die Drift überhaupt in den
liquiden Namen, die wir handeln könnten?** Wenn hier IC ≈ 0 → tot für uns, kein
Geld für Sharadar-Kurse. Wenn positiv → Lead, der saubere Daten rechtfertigt.

## 4. Regeln (Pilot, kein Backtest)

- SUE je Aktie aus EDGAR; **release_date = 10-Q-Einreichungsdatum** (konservativer
  Proxy fürs Announcement — das 8-K-Press-Release liegt 2–4 Wochen FRÜHER, der
  Filing-Termin ist also strikt SPÄTER → kein Look-ahead, nur später Entry).
- Entry am ersten Handelstag ≥ release_date.
- Forward-Returns **markt-adjustiert** (Überschuss über den S&P-500-ETF) zur
  Isolation des Querschnitts-Signals vom Index-Beta. Horizonte 5 / 22 / 66 Tage.
- **Keine** Positionsgröße, **keine** Kosten — das ist der IC-Gate (wie 0042–0046),
  nicht der Handelstest.

## 5. Ergebnisse — gepoolter Rank-IC (markt-adjustiert)

| Horizont | N    | IC (Excess) | Perm-p (gepoolt)* | IC (roh) |
| -------- | ---: | ----------: | ----------------: | -------: |
| 5 T      | 4915 |     +0.0473 |            0.000   |  +0.0487 |
| 22 T     | 4905 |     +0.0421 |            0.0055  |  +0.0401 |
| 66 T     | 4820 |     +0.0473 |            0.0015  |  +0.0311 |

Vorzeichen korrekt, alle Horizonte positiv. Bei 66 T ist IC(Excess) > IC(roh) →
die Markt-Adjustierung **verbessert** das Signal (Beta-Rauschen raus) = Hinweis,
dass es echt cross-sectional ist.

\*Der gepoolte Permutations-p ist **zu optimistisch**: Earnings-Saison-Events
überlappen und sind quer-korreliert (viele Namen berichten im selben 2-Wochen-
Fenster, teilen Markt/Sektor-Moves) — die 0046-Überlapp-Lehre. Der ehrliche Test
folgt.

## 6. Signifikanz — ehrlich (monatliche IC-IR, Clustering-robust)

Spearman-IC je Eintrittsmonat, dann t-Test über die Monatsreihe (jeder Monat =
1 Beobachtung, Grinold/Kahn):

| Horizont | Monate | Ø monatl. IC | IC-IR t | p      | % positive Monate |
| -------- | -----: | -----------: | ------: | -----: | ----------------: |
| 5 T      | 138    |     +0.0434  |   2.10  | 0.0375 | 63.0 %            |
| 22 T     | 138    |     +0.0417  |   2.17  | 0.0317 | 62.3 %            |
| **66 T** | 136    |   **+0.0586**|**3.03** |**0.0030**| 60.3 %          |

**Das Signal überlebt den clustering-robusten Test** (66 T: t=3.03, p=0.003).
Residual-Überlapp bleibt (66-T-Holds spannen über Monate) → t indikativ, nicht
exakt — aber deutlich belastbarer als der gepoolte p.

**Aber der handelbare Dezil-Spread ist dünn:** Top-minus-Bottom-SUE-Dezil bei
66 T = **+1.22 %** (Top +0.70 %, Bottom −0.52 %), **t=1.56, p=0.119**,
Top-Dezil-Trefferquote nur **52.3 %**. Siehe `results/decile_drift.png` — hohe
Dezile driften klar positiv, tiefe schwach, aber **verrauscht** (nicht sauber
monoton).

## 7. Robustheit

- **Kein Decay:** IC(66d Excess) pre-2017 +0.0396 vs from-2017 +0.0514 — eher
  leicht stärker zuletzt (deckt sich mit McLean/Pontiff: PEAD zerfiel wenig).
  `results/cumulative_ic.png` zeigt eine stetig steigende kumulierte Monats-IC.
- **Markt-Adjustierung hilft** (s. o.) → cross-sectional, nicht Beta.

## 8. Verdict

**Testing-Lead, NICHT validiert — qualifizierter Kill-Screen-PASS.** Anders als
0042–0045 (leer) ist das Signal **da und clustering-robust signifikant** (monatl.
IC-IR t=3.0, kein Decay). Aber drei Gründe, warum das **noch kein handelbarer
Edge** ist:

1. **Handelbare Magnitude dünn:** +1.22 %/66 T Long-Short brutto, p=0.119,
   52 % Trefferquote — bevor **Kosten** überhaupt modelliert sind (Einzelaktien-
   Round-Trips, 60-T-Holds quartalsweise je Name; Bottom-Dezil braucht Leerverkauf
   + Borrow). Die Intraday-/Frequenz-Kosten-Lehre gilt hier weniger (60-T-Hold),
   aber Single-Stock-Spreads × Long-Short-Korb fressen plausibel viel von 1.22 %.
2. **Survivorship-Bias nach oben:** das Heute-Überlebenden-Universum **überschätzt**
   den Edge → der wahre (survivorship-freie) Wert ist schwächer.
3. **Kein sauberer Pfad ohne Geld:** der ehrliche nächste Schritt braucht
   survivorship-freie Kurse delisteter Namen (Sharadar SEP) + ein breiteres,
   PIT-rekonstruiertes Universum (inkl. Small-/Mid-Caps, wo PEAD laut Literatur
   am stärksten ist).

**Empfehlung:** PEAD ist als Phänomen **bestätigt vorhanden** in handelbaren
Large-Caps — der Kill-Screen rechtfertigt jetzt erstmals die **Investition in
saubere (bezahlte) Kursdaten**, *falls* Robin eine Einzelaktien-Cross-Sectional-
Schiene fahren will. Bis dahin: Lead, kein Live-Kandidat. Passt nicht zur
aktuellen CTI/Mean-Reversion-Richtung (0071/0072), sondern wäre ein eigenes
IBKR-Aktien-Programm.

**Offene Pfade (registriert, nicht verfolgt ohne Daten-Entscheidung):**
- Sharadar SF1+SEP (survivorship-frei, ~günstig) → echter Backtell mit Kosten +
  Small-/Mid-Cap-Tilt + Long-Short-Portfolio-Übersetzung (die IC→PnL-Lücke aus
  0058/0059 ist hier die Kernfrage).
- 8-K-Press-Release-Datum statt 10-Q-Filing (früherer Entry, fängt mehr Drift).
