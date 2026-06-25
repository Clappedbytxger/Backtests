# Strategie 0082 — Crypto Low-Vol / BAB Cross-Section

> Idee **I0025** aus dem Handoff `D:\Backtest Ideas` (#s08 BAB + 0058-0061-Crypto-Infra).

- **Kategorie:** cross-sectional-factor (crypto)
- **Status:** abgelehnt (keine Low-Vol-Prämie in Crypto)
- **Datum:** 2026-06-15
- **Universum:** survivorship-freies CMC-Top-150 PIT (0058-Infra), Binance daily 2017-2026

## 1. Hypothese & Regeln

Im retail-getriebenen Crypto-Markt soll High-Vol-„Lottery"-Overcrowding eine
Low-Vol-Prämie erzeugen: long niedrigste-Vol-Quintil / short höchste, monatlich.
60d-realisierte Vol, **Liquiditäts-Floor $5M (0059) + Pegged-Guard Vol≥10% p.a. (0060,
sonst schlucken Stablecoins das Low-Vol-Long-Bein)**, 20 bps/Seite.

## 2. Ergebnisse

| Konstruktion | Sharpe | Signifikanz |
| --- | ---: | --- |
| Low-Vol L/S Quintil | −0,12 (CAGR −12 %, MaxDD −90 %) | perm p=0,27, Monats-KI [−3,6 %, +2,7 %] mit 0 |
| Long-only Low-Vol | +0,45 | vs Eligible-Universum **+0,46** |

Median 53 eligible Namen/Tag (Pegged-Guard wirkt — keine Stablecoin-Verseuchung wie
im 0060-Live-Buch). IS/OOS L/S: −0,48 / +0,35 (flippt, full negativ/insignifikant).

## 3. Verdict

**Abgelehnt — keine handelbare Low-Vol/BAB-Prämie in Crypto.** Das L/S ist insignifikant
(perm p=0,27, Monats-KI mit 0) und verliert netto; entscheidend: **Long-only-Low-Vol
(0,45) schlägt das Eligible-Universum (0,46) NICHT** — es gibt schlicht keine Low-Vol-
Prämie im Querschnitt. Spiegelt 0079 (Country-BAB ebenfalls insignifikant) und die
0058-Kern-Lehre (hoher Querschnitts-IC monetarisiert nicht in ein Portfolio). Die
Behavioral-Story (High-Vol-Overcrowding) klingt plausibel, hält aber empirisch nicht
netto der Kosten. Pegged-Guard + Liquiditäts-Floor (0059/0060) korrekt angewandt — das
Ergebnis ist kein Konstruktionsartefakt, sondern ein echtes Null.
