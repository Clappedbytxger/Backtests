# Portfolio-Übersicht: Strategie-Bestand & Bewertung

> Stand: Juni 2026, 62 getestete Strategien (0001–0062). Alle Kennzahlen
> out-of-sample, netto nach Kosten, sofern nicht anders vermerkt. Geordnet nach
> Einsatzreife, nicht nach ID. Keine Anlageberatung.

---

## Das Gesamtbild in einem Absatz

Von 62 rigoros getesteten Strategien haben **~6 einen belastbaren Edge**, **~3
sind starke Leads in Validierung**, und **~50 wurden sauber abgelehnt** — mit
jeweils dokumentierter Lehre. Das ist eine **normale, gute Trefferquote** für
echte Quant-Forschung (professionelle Researcher liegen oft schlechter). Die
überlebenden Edges teilen drei Eigenschaften: **niederfrequent, strukturelle
Flow-Ursache, kostenunempfindlich.** Alles Intraday ist kostengebunden, alles
Fundamentale ist eingepreist, alle cross-sektionalen Rohstoff-Prämien sind
zerfallen — die eine Ausnahme ist die Crypto-Cross-Section.

---

## TIER 1 — Bestätigte Kern-Edges (einsatzreif)

| ID | Name | Sharpe | CAGR | MaxDD | #Trades | p | DSR | Bewertung |
|----|------|-------:|-----:|------:|--------:|--:|----:|-----------|
| **0006** | Benzin KW9 | 0.86 | 13.8% | −13.3% | 11 | 0.000 | 1.00 | **Stärkster Einzel-Edge.** Bootstrap-KI [0,44;1,23] ohne Null, Makro-Ursache (US-Driving-Season-Restocking). Schwäche: nur 11 Trades. |
| **0021** | Platin Jahreswechsel | 0.34 | 6.5% | −24.6% | 27 | 0.004 | 1.00 | **Bestbegründet.** Cross-Instrument (PPLT physisch, kein Roll) + Cross-Asset (Palladium 93% Win) bestätigt. Roll-Artefakt in 0019 ausgeschlossen. |
| **0009** | Mastrind KW21 | 0.52 | 5.5% | −6.0% | 11 | 0.000 | 1.00 | Confirmed, 10/11 Jahre positiv, Makro (Grillsaison). Schwäche: Bootstrap-KI [−0,01;0,90] berührt Null. Fragilster der drei. |

**Diese drei sind dein eigentliches Vermögen.** Niederfrequent, roll-sauber,
makro-begründet, forward- bzw. cross-instrument-bestätigt.

---

## TIER 1b — Die einsatzreife Bündelung

| ID | Name | Forward S&P | vs B&H | DAX | Bewertung |
|----|------|-------------|--------|-----|-----------|
| **0036** | Quint-Saison-Overlay | **40,7% / Sharpe 1,42** | 13,5% / 0,68 | 35,7% / 1,26 | **Dein Flaggschiff-System.** Aktien-Kern + 5 Saison-Beine (Benzin/Mastrind/Platin/Mais/Baumwolle), gleichgewichtet bei Dez-Überlappung. ~114 Trades. |

**Vorbehalt (wichtig):** 3 von 5 Beinen (Platin/Mais/Baumwolle) sind
full-history-gemined → für die 2016+-Forward-Zahlen **kein sauberes OOS**. Der
*belastbare* Kern bleiben die 3 Tier-1-Edges; das Overlay ist deren
kapitaleffiziente Hebelung, nicht ein eigener Edge. Senkt kein Marktrisiko
(MaxDD −39%).

---

## TIER 2 — Starke Leads in Validierung (testing)

| ID | Name | Sharpe | p | DSR | Bewertung |
|----|------|-------:|--:|----:|-----------|
| **0050** | Turn-of-the-Month | 0.50 | 0.035 | **0.916** | **Bestes IS/OOS-Profil im Katalog** (0,53/0,50/0,43, kein Kollaps), nicht kostengebunden, ^GSPC 1927+ p=0,0002. Overlay-Bein. Vorbehalt: Post-Publikations-Decay (Prämie ~halbiert). |
| **0052** | Pre-FOMC Drift | 4.0* | 0.003 | **0.995** | Nacht in die FOMC-Ankündigung +16 bps = 5× normale Nacht, **kein Decay** (2000–14 ≈ 2015–26). *ann. je aktiver Nacht; standalone ~1%/J → Overlay-Bein. |
| **0056** | VIX-Carry risk-managed | 0.55 | 0.012 | 0.972 | Echter VRP-Edge, klein gesized auf Defined-Risk-Sleeve. Tail bleibt das Thema (lineares Down-Sizing erhält Edge, Vol-Targeting zerstört ihn). Kleines Satellit-Sleeve. |

---

## TIER 2b — Crypto-ML (stärkster jüngster Lead, im Live-Forward)

| ID | Name | Sharpe | vs Markt | PBO | DSR | Bewertung |
|----|------|-------:|---------:|----:|----:|-----------|
| **0059** | ML Crypto Cross-Section | 0.98 | +0.81 | 0.007 | 0.36 | **Erste Strategie, die das Ridge-Gate besteht.** Echte (flache) Nichtlinearität. ABER Bootstrap-KI [−0,07;+1,20] berührt Null. |
| **0060** | Crypto Walk-Forward | 0.59 | +0.64 | — | 0.068 | LGBM-Vorsprung **überlebt out-of-time** (Ridge −0,15). Stablecoin-Bug gefunden+gefixt (ehrlich nach unten korrigiert). **Live-Forward registriert 2026-06-11.** |

**Status:** echter Lead, kein validierter Edge. Der einzige ehrliche
Rest-Beweis ist der laufende 24-Monats-Live-Forward. Nicht anfassen.

---

## TIER 3 — Weitere Saison-Leads (testing, im Kalender)

| ID | Name | Sharpe | p | Bewertung |
|----|------|-------:|--:|-----------|
| 0035 | Baumwolle Jahresend | 0.40 | 0.001 | Top-Stats, roll-sauber, Bootstrap-KI [0,03;0,77] ohne Null. Kein Faser-Schwester-Future für Cross-OOS → Live-Forward 2026. |
| 0032 | Mais WASDE-Kern | 0.44 | 0.000 | 92% Win, aber Stress-Test zeigt: 78% des Edges auf 6 WASDE-Tagen = **Event-Bet, kein Fenster**. Klein sizen (User-Wahl). |
| 0031 | Palladium Jahreswechsel | 0.42 | 0.005 | Roll-sauber, aber korrelierte Evidenz zu Platin (gleicher Treiber) → bestärkt PGM-Saison, kein unabhängiger Edge. Nicht separat handeln. |
| 0030 | Mais Dezember | 0.47 | 0.000 | ~60% des Edges in 5 Tagen → vermutlich nur im Kalenderspread voll real. |
| 0025 | Zink Sommer | 0.22 | 0.031 | In 0037 **rejected** (OOS-Sharpe −0,03, Bootstrap-KI berührt 0). |

---

## TIER 4 — Lehrreiche Ablehnungen (das Methoden-Fundament)

| Klasse | IDs | Kern-Lehre |
|--------|-----|-----------|
| **Drift-Fallen** | 0017 Nasdaq, 0022 Gold-Ostern, 0023 Akshaya, 0026 Kakao, 0027 Kaffee, 0034 Zucker | Permutationstest trennt echtes Timing (driftarm) von Drift-Illusion (driftstark). Starke Story ≠ Edge. |
| **Roll-Artefakte** | 0028 Erdgas (via 0029) | Bei monatlich rollenden Futures: Roll-Tag-Ausschluss ist Pflicht VOR Lead-Status. 105% des „Edges" saßen auf 6 Expiry-Tagen. |
| **Intraday kostengebunden** | 0012–0015 BTC, 0038–0041 ES/NQ, 0049, 0051 | Liquider Einzelmarkt = Intraday-Richtung netto ≈ 0. 0041: echtes RV-Signal, von 6 bps RT begraben. Retail-Prop kann Intraday-Index-Alpha nicht zugreifen. |
| **Fundamental eingepreist** | 0042–0046 | Meistbeobachtete Inputs (Wetter, USDA, China-IP) sind voll eingepreist. Nur diskrete Info-Konzentration (WASDE) trägt, laufende Daten (Crop-Condition) nicht. |
| **Cross-Section zerfallen** | 0047 Momentum, 0048 Carry, 0057 ML | Rohstoff-Prämien nach der Index-Welle 2004–14 tot. ML kombiniert tote Faktoren zu totem Faktor. |
| **Signal leer / Tail / Daten** | 0053 Monetary Mom., 0054 VIX outright (Tail), 0055 PEAD (Daten-Blocker), 0062 CNN (Null) | Diverse: Proxy-Rauschen, >10σ-Tail, fehlende Earnings-Daten, Deep-Learning überträgt nicht. |

---

## Was der Bestand sagt — die ehrliche Synthese

**Du hast einen handelbaren Kern:** drei bestätigte Saison-Edges + ihr Overlay
(Sharpe ~1,4 forward), plus drei Overlay-Beine in Validierung (Turn-of-Month,
Pre-FOMC, VIX-Sleeve), plus einen echten Crypto-ML-Lead im Live-Forward.

**Die Lücke:** Fast alles ist **dieselbe Familie** (Kalender-/Saison-/Flow-Effekte
auf Aktien & Rohstoffen) plus ein Crypto-Bein. Was fehlt, ist eine **zweite,
strukturell unkorrelierte Edge-Familie** als Diversifikator — genau das adressiert
das Ideen-Dokument (`NEXT-STRATEGIES-AND-LIVE-SYSTEM.md`): Calendar-Spreads
(saubere Saisonalität ohne Beta/Roll-Problem) und Trend-Following (jahrzehntelang
belegter Diversifikator).

**Methoden-Aktivposten:** Deine Validierungs-Pipeline (Permutation, CPCV/PBO,
Roll-Check, DSR korrekt nach Fix, Survivorship-Guards, Look-ahead-Tests) ist
besser als das, was viele bezahlte Junior-Quants bauen. Das ist der eigentliche,
übertragbare Wert dieses Repos.
