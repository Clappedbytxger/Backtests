# Strategie 0033 — Quad-Saison-Overlay (Benzin + Mastrind + Mais + Platin)

- **Kategorie:** seasonal (Portfolio-Konstruktion / Bündelung)
- **Status:** **Kandidat-Bündelung** — kein neuer Edge; kapitaleffiziente Stapelung von vier Saison-Beinen auf einem Aktien-Kern. Erbt die „kein sauberes OOS für Platin & Mais"-Vorbehalte.
- **Datum:** 2026-06-05
- **Universum:** Kern S&P 500 / DAX, ganzjährig; Umstieg in Futures für vier kurze, disjunkte Fenster.

## 1. Idee

Erweitert 0020 (Benzin KW9 + Mastrind KW21 + Platin 18.12.–10.1.) um ein **viertes Bein**:
den **Mais-WASDE-Kern** (`ZC=F`, 8.–18. Dez., aus 0032). Ganzjährig den Index halten; nur in
den vier Saisonfenstern in den jeweiligen Future umsteigen, sonst Index.

Mais (8.–18.12.) und Platin (18.12.–10.1.) **berühren sich am 18.12.** Da das Overlay nur ein
Instrument gleichzeitig hält, sind die Beine **disjunkt nach Listen-Priorität**: Mais besitzt sein
8.–18.-Dez.-Fenster, Platin startet effektiv ~19. Dez. (der verlorene ~1 Platin-Tag ist
vernachlässigbar). `held_total ≤ 1` wird per Assertion garantiert — keine Doppelallokation.

## 2. Ergebnisse (netto nach Kosten)

| Bein | Trades | Win | Expectancy/Trade |
| --- | ---: | ---: | ---: |
| Benzin (RB=F, KW9) | 22 | 95 % | +11,19 % |
| Mastrind (GF=F, KW21) | 22 | 91 % | +4,12 % |
| **Mais (ZC=F, 8.–18.12.)** | 21 | 86 % | **+2,69 %** |
| Platin (PL=F, 18.12.–10.1.) | 25 | 88 % | +4,53 % |

| | S&P Quad (gesamt) | S&P B&H | S&P Quad (ab 2016) | S&P B&H (ab 2016) |
| --- | ---: | ---: | ---: | ---: |
| CAGR | 33,0 % | 9,1 % | **44,2 %** | 13,5 % |
| Sharpe | 1,22 | 0,45 | **1,49** | 0,68 |
| Max Drawdown | −39,3 % | −49,7 % | −34,1 % | −33,9 % |

DAX analog: gesamt 30,9 %/Sharpe 1,06 vs B&H 7,1 %/0,32; ab 2016 38,8 %/1,34 vs 8,6 %/0,43.

**Beitrag des Mais-Beins ggü. 0020 (Triple):** S&P ab 2016 CAGR 40,0 %→**44,2 %**, Sharpe
1,38→**1,49**; DAX 35,9 %→38,8 %, 1,26→1,34. Mais stapelt sauber (disjunkt, +2,69 %/Trade,
86 % Win), füllt zusammen mit Platin die Jahreswechsel-Saison.

## 3. Ehrliche Vorbehalte (vor den Zahlen lesen)

- **Kein neuer Edge** — reine kapitaleffiziente Bündelung (wie 0007/0010/0020).
- **Nur 2 von 4 Beinen sind echte Forward-Tests** (Benzin/Mastrind, vorab fixiert 0006/0009 → 2016+
  sauberes OOS). **Platin (Seasonax) UND Mais (WASDE, 0030/0032) wurden auf voller Historie geminte
  → für sie ist 2016+ KEIN sauberes OOS.** Die spektakulären „Forward"-Zahlen sind daher für die
  Hälfte der Beine in-sample-kontaminiert.
- **Senkt kein Marktrisiko:** Vol 24–27 %, MaxDD −39…−57 % — das Overlay addiert Saison-Rendite,
  hebt nicht die Drawdowns. „Either/or"-100%-Notional = während der Fenster voll in einem volatilen
  Einzel-Future (hebelartig).
- **Benzin dominiert** (95 % Win, +11,19 %/Trade); Mais ist das schwächste der vier Beine.
- Mais- und Platin-Bein liegen zeitlich benachbart (Dez/Jahreswechsel) → leichte Treiber-Nähe, aber
  unterschiedliche Assets/Sektoren (Getreide vs PGM), daher ok.

## 4. Nächste Schritte

- **Live-Forward 2026/27** für die nicht-vorregistrierten Beine (Platin + Mais) sauber registrieren;
  erst danach zählen ihre Zukunftsjahre als echtes OOS.
- Positionsgrößen-/Vol-Targeting, bevor das real handelbar ist (MaxDD/Vol hoch).
- Mastrind-Fragilität (Bootstrap-KI berührt Null, 0009) bleibt geerbt.

## Artefakte

- `results/metrics.json`, `results/equity.csv`
- `results/plots/overlay_gspc.png`, `overlay_gspc_forward.png`, `overlay_gdaxi.png`, `overlay_gdaxi_forward.png`
