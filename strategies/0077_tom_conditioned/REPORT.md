# Strategie 0077 — Turn-of-Month conditioned (Rebalancing-Stärke)

> Idee **I0028** aus dem Handoff `D:\Backtest Ideas` (Quelle #s10 + bestätigter Lead 0050).

- **Kategorie:** behavioral-calendar / flow (Conditioning eines bestätigten Leads)
- **Status:** abgelehnt als eigener Edge — bestätigt 0050-Flow, schlägt 0050 aber nicht
- **Datum:** 2026-06-15
- **Universum:** S&P 500 (SPY 1993+ handelbar, ^GSPC 1927+ für Power)

## 1. Hypothese

0050 (Turn-of-the-Month) ist bestätigt. #s10 (Goldman/NBER-Pension-Rebalancing):
der TOM-Effekt ist am **Quartals-/Halbjahresende stärker** (12,2 / 22,2 vs 5,2 bps)
und skaliert mit dem Rebalancing-Flow. Test: bringt Quartals-Conditioning/-Gewichtung
einen höheren Sharpe als das gleichgewichtete 0050?

## 2. Regeln & Look-Ahead

Vorab fixiertes 0050-Fenster (letzter 1 + erste 3 Handelstage, NICHT re-optimiert).
Conditioning oben drauf: `quarter_only`, `quarter_double` (2× an Quartalsenden),
`prior_up` (nur nach positivem Vormonat — Vormonatsreturn ist am Monatsstart bekannt).
Engine shiftet T+1.

## 3. Ergebnisse

**Per-Turn ^GSPC (1927+, 1.182 Turns):**

| Gruppe | n | Ø-Return | Median |
| --- | ---: | ---: | ---: |
| Quartalsende-Turns | 394 | **+0,626 %** | +0,740 % |
| gewöhnliche Turns | 788 | +0,388 % | |
| Halbjahresende-Turns | 197 | **+0,765 %** | |

Gap Quartal − gewöhnlich = **+0,238 %**, Permutation (Zufalls-Relabeling der
Quartalsmonate) **p=0,054**, Bootstrap-KI **[−0,044 %, +0,519 %] (berührt 0)**.
→ Richtung bestätigt #s10 (Quartals-/Halbjahresende stärker), aber **nur grenzwertig
signifikant** — nicht statistisch konklusiv.

**Conditioning auf Vormonats-Aktienreturn:** TOM nach UP-Monat +0,526 % vs nach
DOWN-Monat +0,381 % — leicht stärker nach starken Monaten, also das **Gegenteil** der
naiven Pension-Sell-Vorhersage (#s10: Fonds verkaufen Aktien nach Stärke). Der
TOM-Kaufflow dominiert; Effekt klein.

**Strategie-Vergleich SPY (aktive-Tage-Sharpe, netto MES) — die Entscheidungsmetrik:**

| Variante | aktive-Tage-Sharpe | CAGR | Investitionszeit |
| --- | ---: | ---: | ---: |
| `all` (= 0050) | +1,23 | +4,0 % | 19 % |
| `quarter_only` | +1,68 | +1,8 % | 6 % |
| `quarter_double` | +1,25 | +5,6 % | 19 % |
| `prior_up` | +1,53 | +2,5 % | 12 % |

## 4. Verdict

**Abgelehnt als eigenständiger Edge — kein risikoadjustierter Mehrwert über 0050.**
Die höhere aktive-Tage-Sharpe von `quarter_only` (1,68) und `prior_up` (1,53) entsteht
**mechanisch durch Konzentration**: man handelt nur die besten Turns und lässt 2/3 der
TOM-Gelegenheiten brachliegen → CAGR halbiert/drittelt sich. `quarter_double` (gleiche
Sharpe 1,25, aber CAGR 5,6 % statt 4,0 %) ist die einzige sinnvolle Verfeinerung: an
Quartalsenden übergewichten bringt mehr Rendite bei gleichem Risiko-Profil.

**Praktisches Fazit:** 0050 bleibt unverändert das Bein; #s10's Flow-Richtung ist
bestätigt (Quartals-/Halbjahresende sind stärker), und ein optionales 2×-Sizing an
Quartalsenden (`quarter_double`) ist eine legitime kleine Renditeverbesserung ohne
Sharpe-Kosten. Die Hypothese „conditioned TOM hat höheren Sharpe als 0050" ist
falsifiziert (gleicher Sharpe, nur Konzentration). Kein neues Lead.
