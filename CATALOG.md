# Strategie-Katalog

Master-Register jeder getesteten Strategie. Status: `idea` → `testing` →
`validated` / `rejected` (validiert / abgelehnt) / `overlay` (taugt als
Risiko-Overlay, nicht als eigenständige Alpha-Quelle). Kennzahlen sind
out-of-sample, netto nach Kosten, sofern nicht anders vermerkt.

| ID   | Name                       | Kategorie | Hypothese                                                                                  | Status    | Sharpe |  CAGR |  MaxDD | #Trades | p-Wert |  DSR | Notiz                                                                                                      |
| ---- | -------------------------- | --------- | ------------------------------------------------------------------------------------------ | --------- | -----: | ----: | -----: | ------: | -----: | ---: | ---------------------------------------------------------------------------------------------------------- |
| 0001 | Saisonale Kalendereffekte  | seasonal  | Turn-of-Month / Jahreswechsel / Sell-in-May schlagen Buy & Hold risikoadjustiert           | abgelehnt |   0.45 |  7.6% | -38.8% |      16 |  0.114 | 0.00 | Kein signifikanter Einzel-Edge OOS; Sell-in-May marktübergreifend konsistent → als Overlay weiterverfolgen |
| 0002 | Gepooltes Sell-in-May      | seasonal  | Pooling über 5 Märkte gibt dem Sell-in-May-Effekt genug Power für Signifikanz              | abgelehnt |   0.59 |  7.9% | -32.4% |      80 |  0.297 | 0.00 | Pooling hebt Sharpe über Einzelmarkt + senkt Vola, aber kein Renditevorteil vs B&H → Risiko-Overlay        |
| 0003 | Sell-in-May Risiko-Overlay | seasonal  | T-Bill-Carry bzw. 50%-Sommer-Position schließt die Renditelücke zu Buy & Hold              | overlay   |   0.77 | 10.8% | -32.4% |      80 |  0.328 | 0.00 | De-Risking-Overlay (Sommer 50%) ist bester Kompromiss: Sharpe nahe B&H bei ~18% weniger Vola; kein Alpha   |
| 0004 | Saisonale Rohstoff-Fenster | seasonal  | Rohstoffe mit realem Angebots-/Nachfrage-Saisontreiber schlagen Buy & Hold (Seasonax-Idee) | abgelehnt |   0.01 |  1.6% | -38.0% |     107 |  0.432 | 0.00 | Kein Fenster schlägt B&H; Erdgas trotz stärkster Story am schlechtesten (ETF-Contango/Roll-Decay)          |

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
