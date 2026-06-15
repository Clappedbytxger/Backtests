# Strategie 0100 — Cross-Sovereign Auction-Concession (I0053) — DEFERRED (Daten-Blocker)

> Batch-2-Idee **I0053** aus `D:\Backtest Ideas` (#s21 Lou/Yan/Zhang 2013 JFE; Beetsma et al.;
> Sigaux). Höchste konzeptionelle Priorität: **Out-of-Universe-Robustheitsbeweis des
> p=0,000-Gewinners 0078** — repliziere die eingefrorene 0078-Regel (Short laufzeitgleiches
> Future T−5..T−1 vor der Auktion) auf Bund/Gilt/JGB.

- **Kategorie:** event-driven / rates / Primärmarkt-Mikrostruktur (Cross-Market-Replikation)
- **Status:** **deferred — Daten-Blocker** (kein Pseudo-Test, Disziplin wie 0055-PEAD)
- **Datum:** 2026-06-15

## 1. Warum deferred (und nicht abgelehnt)

Der Test braucht zwei Inputs:
1. **Tradeable Sovereign-Bond-Serie** (roll-frei oder roll-sauber) — **VERFÜGBAR gratis:**
   `IGLT.L` (iShares Core UK Gilts, 2010+), `IBGL.L` / `SEGA.L` (iShares/SPDR EUR-Govt,
   lang-datiert — passt zur 0078-Kernerkenntnis, dass der Effekt am LANGEN Ende sitzt). Diese
   ETFs sind wie TLT roll-frei → die 0028/0029-Roll-Falle entfällt.
2. **Historischer Sovereign-Auktionskalender** (exakte Auktionstage Bund/Gilt/JGB seit ~2010)
   — **NICHT frei zugänglich.** Anders als die US-`TreasuryDirect`-API (gratis, kein Key,
   JSON — die 0078 nutzt) liefern die deutsche Finanzagentur, das UK DMO und das japanische
   MoF keinen offenen, maschinenlesbaren Auktions-Ergebnis-Feed (mehrere Endpunkt-Proben
   gaben HTTP 404; die Kalender liegen in PDF/HTML-Terminübersichten).

**Ein heuristischer Auktions-Zeitplan** (z. B. „Bund ~2.-4. Mittwoch") wäre **untaugliche
Eingabe** — die Concession ist ein **tagesgenauer** Effekt (0078: T−5..T−1, sauberes
Inverted-V), und ungenaue Auktionstage würden ein falsches Null/Positiv erzeugen. Das ist
exakt die **0055-PEAD-Disziplin** (kein Pseudo-Test auf unzureichenden Daten) und die
0025-Lehre (Daten-Qualität vor Backtest).

## 2. Was zum Abschluss fehlt (konkrete To-dos)

- **Auktionskalender beschaffen** — Optionen: (a) UK DMO „Gilt auction results"-Excel-Export
  (historisch, scrapebar); (b) deutsche Finanzagentur Tender-Ergebnis-Archiv; (c) Japan MoF
  JGB-Auktionskalender; (d) Databento/Bloomberg-Kalender (kostenpflichtig). Alle erfordern
  HTML/PDF-Parsing oder Kauf — geschätzt mehrere Stunden Daten-Engineering je Land.
- Dann: eingefrorene 0078-Regel (Short T−5..T−1, langes Ende) auf IGLT.L (Gilt) + IBGL.L/SEGA.L
  (Bund/EUR-Govt), gepoolte Permutation gegen Nicht-Auktionstage je Markt.

## 3. Einordnung

I0053 bleibt der **stärkste offene konzeptionelle Lead** des Batches (würde 0078 von einem
einzelnen Markt auf einen generischen Primärmarkt-Mechanismus heben). Es ist **nicht
widerlegt**, nur **datenblockiert** — die handelbaren Proxies liegen vor, allein der
historische Auktionskalender ist die Beschaffungshürde. Empfehlung: in Batch 3 als gezieltes
Daten-Engineering-Ticket (ein Land genügt für den Robustheitsbeweis — Gilt via DMO ist der
wahrscheinlich zugänglichste Pfad). Bewusst kein Pseudo-Test.
