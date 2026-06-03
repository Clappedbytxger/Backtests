# Strategie-Katalog

Master-Register jeder getesteten Strategie. Status: `idea` → `testing` →
`validated` / `rejected` (validiert / abgelehnt). Kennzahlen sind out-of-sample,
netto nach Kosten, sofern nicht anders vermerkt.

| ID   | Name                      | Kategorie | Hypothese                                                                        | Status    | Sharpe | CAGR |  MaxDD | #Trades | p-Wert |  DSR | Notiz                                                                                                      |
| ---- | ------------------------- | --------- | -------------------------------------------------------------------------------- | --------- | -----: | ---: | -----: | ------: | -----: | ---: | ---------------------------------------------------------------------------------------------------------- |
| 0001 | Saisonale Kalendereffekte | seasonal  | Turn-of-Month / Jahreswechsel / Sell-in-May schlagen Buy & Hold risikoadjustiert | abgelehnt |   0.45 | 7.6% | -38.8% |      16 |  0.114 | 0.00 | Kein signifikanter Einzel-Edge OOS; Sell-in-May marktübergreifend konsistent → als Overlay weiterverfolgen |
| 0002 | Gepooltes Sell-in-May     | seasonal  | Pooling über 5 Märkte gibt dem Sell-in-May-Effekt genug Power für Signifikanz    | abgelehnt |   0.59 | 7.9% | -32.4% |      80 |  0.297 | 0.00 | Pooling hebt Sharpe über Einzelmarkt + senkt Vola, aber kein Renditevorteil vs B&H → Risiko-Overlay        |

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
