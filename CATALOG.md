# Strategie-Katalog

Master-Register jeder getesteten Strategie. Status: `idea` → `testing` →
`Kandidat` (forward-bestätigt, aber noch nicht live-fertig) / `validated` /
`rejected` (validiert / abgelehnt) / `overlay` (taugt als Risiko-Overlay, nicht
als eigenständige Alpha-Quelle). Kennzahlen sind
out-of-sample, netto nach Kosten, sofern nicht anders vermerkt.

| ID   | Name                         | Kategorie | Hypothese                                                                                  | Status    | Sharpe |  CAGR |  MaxDD | #Trades | p-Wert |  DSR | Notiz                                                                                                       |
| ---- | ---------------------------- | --------- | ------------------------------------------------------------------------------------------ | --------- | -----: | ----: | -----: | ------: | -----: | ---: | ----------------------------------------------------------------------------------------------------------- |
| 0001 | Saisonale Kalendereffekte    | seasonal  | Turn-of-Month / Jahreswechsel / Sell-in-May schlagen Buy & Hold risikoadjustiert           | abgelehnt |   0.45 |  7.6% | -38.8% |      16 |  0.114 | 0.00 | Kein signifikanter Einzel-Edge OOS; Sell-in-May marktübergreifend konsistent → als Overlay weiterverfolgen  |
| 0002 | Gepooltes Sell-in-May        | seasonal  | Pooling über 5 Märkte gibt dem Sell-in-May-Effekt genug Power für Signifikanz              | abgelehnt |   0.59 |  7.9% | -32.4% |      80 |  0.297 | 0.00 | Pooling hebt Sharpe über Einzelmarkt + senkt Vola, aber kein Renditevorteil vs B&H → Risiko-Overlay         |
| 0003 | Sell-in-May Risiko-Overlay   | seasonal  | T-Bill-Carry bzw. 50%-Sommer-Position schließt die Renditelücke zu Buy & Hold              | overlay   |   0.77 | 10.8% | -32.4% |      80 |  0.328 | 0.00 | De-Risking-Overlay (Sommer 50%) ist bester Kompromiss: Sharpe nahe B&H bei ~18% weniger Vola; kein Alpha    |
| 0004 | Saisonale Rohstoff-Fenster   | seasonal  | Rohstoffe mit realem Angebots-/Nachfrage-Saisontreiber schlagen Buy & Hold (Seasonax-Idee) | abgelehnt |   0.01 |  1.6% | -38.0% |     107 |  0.432 | 0.00 | Kein Fenster schlägt B&H; Erdgas trotz stärkster Story am schlechtesten (ETF-Contango/Roll-Decay)           |
| 0005 | Kurzfristige Futures-Fenster | seasonal  | Kurzes Fenster auf Futures (statt ETF) umgeht Roll-Decay; IS-Scan wählt, OOS validiert     | abgelehnt |  -0.04 |  1.9% |  -4.3% |      83 |    n/a | 0.00 | 7/8 Fenster kollabieren OOS (IS-Sharpe 4-8 = Overfit); nur Benzin KW9 hält OOS (Perm p≈0) → Lead, kein Edge |
| 0006 | Benzin-Saisonfenster KW9     | seasonal  | Vorab fixierte Benzin-KW9-Regel (aus 0005) übersteht einen echten Forward-Test 2016–2026   | Kandidat  |   0.86 | 13.8% | -13.3% |      11 |  0.000 | 1.00 | Erster nicht abgelehnter Edge: Bootstrap-Sharpe-KI [0,44;1,23] schließt Null aus, robustes Plateau (47/54), Makro-Ursache; aber nur 11 Trades → Demut |

## Kategorien

- **seasonal** — Kalender-/wiederkehrende Datumseffekte
- **mean-reversion** — kurzfristige Bewegungen ausreizen (fade)
- **momentum / trend** — Persistenz mitreiten
- **cross-sectional** — relatives Ranking über Assets
- **macro / regime** — vom Makro-Zustand getrieben

## Legende

- **DSR** = Deflated Sharpe Ratio (Wahrscheinlichkeit, dass der wahre Sharpe > 0
  ist, nach Korrektur für Multiple Testing)
- **p-Wert** = Permutationstest gegen zufälliges Timing
