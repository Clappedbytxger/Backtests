# Ideen-Handoff — Arbeiten mit `D:\Backtest Ideas`

Anleitung für Claude Code (Quant Developer) in diesem Repo: **wie du die Forschungs-
Hypothesen aus dem Schwester-Workspace `D:\Backtest Ideas` aufgreifst und umsetzt.**
Bewusst nicht-technisch — es geht nur darum, **woher du was nimmst und wo was steht.**

---

## 1. Wo die Ideen liegen

Alle Hypothesen entstehen im separaten Workspace **`D:\Backtest Ideas`** (Research-
Agent). Dieses Repo (`D:\Backtests`) ist die **Umsetzung/Validierung**. Du holst dir
von dort eine Hypothese und baust sie hier als Strategie.

```
D:\Backtest Ideas\
  HYPOTHESES.md     ← LIES DAS ZUERST: Index-Tabelle aller Ideen (lesbar)
  HYPOTHESES.csv    ← gleiche Tabelle, maschinenlesbar/filterbar
  ideas\<kat>.md    ← der VOLLE Steckbrief je Hypothese (Entry/Exit/Varianten/…)
  SOURCES.md        ← Quellen-Beleg je Idee (#sNN: Paper-URL, Seasonax-Lauf, Zahlen)
  RESEARCH-PROCESS.md ← wie die Ideen entstanden + die De-Dup-/Reject-Regeln
  TEMPLATE.md       ← Feld-Definitionen des Steckbriefs
  README.md         ← Überblick
```

---

## 2. Dein Ablauf (woher nimmst du was)

1. **`D:\Backtest Ideas\HYPOTHESES.md` öffnen** → Index-Tabelle mit Spalten
   `ID | Titel | Markt | Kategorie | Prio | Quelle | Verwandt`.
2. **Eine Hypothese wählen** — nach Spalte **Prio** (mit `Hoch` anfangen). Am Ende
   der Datei steht eine **Batch-Summary** mit den 14 Hoch-Prio-Leads + offenen
   Daten-Blockern + nächsten Rechercherichtungen.
3. **Den vollen Steckbrief lesen:** Die Index-Zeile nennt die Datei (Spalte `Datei`
   in der CSV), z. B. `ideas\calendar-spreads.md`. Dort steht der Block mit der
   ID (z. B. `### I0001`) und allen Feldern.
4. **Den Quellen-Beleg lesen:** Feld `QUELLE` verweist auf `#sNN` → in
   `SOURCES.md` nachschlagen (Paper-URL, exakte Regel/Zahlen, oder Seasonax-Lauf).
   Bei den Hoch-Prio-Ideen sind die exakten Regeln dort schon extrahiert.
5. **Umsetzen wie gewohnt** in diesem Repo (`strategies\NNNN_name\`, siehe `CLAUDE.md`).

---

## 3. Was die Felder des Steckbriefs bedeuten (was steht wo)

- **KERNIDEE / MARKTLOGIK** — die These + warum sie ökonomisch funktionieren könnte.
- **TESTBARE HYPOTHESE** — die eine Regel, die du falsifizierst.
- **ENTRY / EXIT / STOP / TAKE PROFIT / HALTEDAUER / ZEITEBENE / MÄRKTE** — die
  konkreten Backtest-Regeln. Bei Hoch-Prio teils schon mit exakten Zahlen/Fenstern.
- **VARIANTEN** (≥10) — dein **Robustheits-Raster** (andere Haltedauer/Märkte/Filter).
  Nicht alle bauen — sie zeigen, in welche Richtungen du robustheits-testen sollst.
- **ERWEITERUNGEN** — optionale Zusatzdaten, die den Edge schärfen könnten (COT,
  Wetter, Term-Structure …). Kür, nicht Pflicht.
- **DATENQUELLEN** — woher die Daten kommen **und ob es einen Blocker gibt**
  (z. B. „survivorship-freie Liste nötig", „Konsens-Daten kostenpflichtig"). Vor dem
  Bau prüfen.
- **VERWANDT** — Bezug zum bestehenden `CATALOG.md` (siehe §4).
- **PRIORITÄT** — mit Begründung; oft mit Pflicht-Vorbehalt (z. B. „erst Permutation").

---

## 4. Das Feld `VERWANDT` — und die wichtigste Regel

- `neu` — kein Bezug im Bestand.
- `Variante von NNNN` — baut auf einer bestehenden Strategie auf (deren REPORT lesen).
- `umgeht-Reject NNNN` — adressiert gezielt einen früheren Ablehnungsgrund (z. B.
  Roll-Artefakt → als Spread). Den alten Reject-Grund kennen, damit du ihn wirklich umgehst.
- `re-test NNNN` — die Idee ist faktisch eine **frühere Ablehnung**, die aber an einer
  einzelnen Implementierungsstelle hängen könnte.

**WICHTIG (Robins ausdrückliche Anweisung): eine Ablehnung in `CATALOG.md`/Lessons ist
NICHT endgültig.** Strategien wurden teils falsch codiert und dann fälschlich abgelehnt
(Beispiel 0069 SMC: erst „Null", war ein Pivot-Bug, nach Fix ein Lead). Deshalb:
- Verwirf eine Idee nur, wenn der Reject-Grund **strukturell/ökonomisch UND mehrfach
  unabhängig bestätigt** ist.
- Hängt er an einer einzelnen heiklen Stelle (Roll/Pivot/Fenster, Look-ahead-Shift,
  Kostenmodell, Permutations-Null, dünne Daten, Survivorship) → **zuerst die Original-
  regel sauber reproduzieren**, dann erst urteilen. Details in
  `D:\Backtest Ideas\RESEARCH-PROCESS.md`.

---

## 5. Vorbehalte, die in den Ideen schon markiert sind (beachten!)

- **Seasonax-Leads (#s16, IDs I0044–I0052):** Das Fenster ist auto-optimiert + nur
  10–20 Vorkommen → **zuerst Permutation gegen Zufalls-Timing** (Drift-Falle, vgl.
  Lessons 0016/0017). Einzelaktien zusätzlich **survivorship-verzerrt** + Sommer-Drift
  → Permutation zwingend (vgl. 0074). Beispiel ehrlich dokumentiert: Palladium (I0045)
  zerfällt 10J→20J.
- **Rohstoff-Outright:** Roll-Check ist Pflicht (vgl. 0028/0029) — steht je Idee dabei.
- **Magnituden:** wo klein (z. B. Treasury-Auction I0009 ~2,4 bps) → Kostenwand beachten,
  ggf. als Spread/RV.
- **X/Twitter (#s17):** lieferte **keine** Hypothesen (nur Monitoring-Kanal). Nicht als
  Quelle für fertige Regeln behandeln.

---

## 6. Nach dem Test — zurückmelden

- In `D:\Backtest Ideas\HYPOTHESES.csv` die Spalte **`Status`** der Idee fortschreiben:
  `idea` → `testing` / `Kandidat` / `validated` / `rejected` / `overlay`.
- Hier im Repo wie immer `CATALOG.md` ergänzen; im Notiz-Feld die **Ideen-ID** (`I00NN`)
  vermerken, damit Idee ↔ Strategie verlinkt bleiben.

---

## 7. Schnellstart-Empfehlung

Die stärksten, sofort baubaren Leads (aus der Batch-Summary):
- **Calendar Spreads** (Roadmap-Top): I0001 Mais Old/New-Crop, I0002 Soja-Crush,
  I0003 NatGas-Winter (umgeht 0028-Reject), I0004 Benzin-Spread, I0007 Crack-Spread.
- **Niederfrequente Events:** I0008 FOMC-Even-Week, I0010 End-of-Month-Treasury
  (~20 bps/Monat, Sharpe ~1), I0009 Auction.
- **Diversifikator:** I0016 Multi-Asset-Trend (Fast/Slow).
- **Seasonax-Lead:** I0044 Getreide-Sommer-Short (über 20 J. bestätigt).
