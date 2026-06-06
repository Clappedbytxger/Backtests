# Strategie 0032 — Mais WASDE-Kern (8.–18.12.)

- **Kategorie:** seasonal
- **Status:** **testing / sauberere Verfeinerung von 0030** — Mais+Weizen-Getreide-Effekt bestätigt (nicht universal: Soja + Mais-ETF fallen aus).
- **Datum:** 2026-06-05
- **Universum:** Primär `ZC=F` (Mais-Front-Month). Cross: `CORN` (Teucrium-ETF), `ZW=F` (Weizen), `ZS=F` (Soja).

## 1. Hypothese (vorab fixiert, event-getrieben)

0030 fand den Mais-Dezember-Edge (p=0,000), aber ~60 % davon konzentriert in 11.–16. Dez.
(ohne diese Tage p=0,093). Frage: ist der Cluster ein *benennbares Event* oder Zufall? Hier
wird ein **enges Fenster um den Dezember-WASDE-Bericht** (USDA World Agricultural Supply &
Demand Estimates, ~9.–12. Dez. — die letzte große US-Ernteabrechnung des Jahres) + Verdauung
**vorab fixiert: 8.–18. Dezember**. Das Fenster stammt aus dem **Event-Kalender**, nicht aus
ZC=F-Tagesrenditen (der 15.-Dez.-Ausschlag motivierte nur das Hinschauen; das WASDE-Datum
definiert das Fenster).

## 2. Validierung: dieselbe eingefrorene Regel ohne Re-Fitting (0021-Methode)

| Instrument | Jahre | Perm p | Exp/Trade | Win | Sharpe | Bootstrap-KI | Urteil |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| **`ZC=F` Mais (primär)** | 2000–26 | **0,000** | +4,01 % | **92 %** | 0,44 | [0,05; 0,75] ✓ | stark |
| `ZW=F` Weizen | 2000–26 | **0,010** | +2,75 % | 73 % | 0,14 | [−0,25; 0,52] | ✓ bestätigt |
| `ZS=F` Soja | 2000–26 | 0,655 | +0,46 % | 50 % | −0,49 | [−0,89; −0,11] | ✗ kein Effekt |
| `CORN` ETF | 2010–26 | 0,852 | +0,16 % | 31 % | −0,80 | [−1,34; −0,31] | ✗ (strukturell) |

- **Mais primär:** das Verengen auf das WASDE-Fenster **hebt die Trefferquote von 77 % (0030, voller
  Dez.) auf 92 %** (24/26 Winter positiv) — ein *konsistenterer* Kern, weiter p=0,000, Bootstrap-KI
  ohne Null, IS +5,36 % / OOS +2,67 % beide positiv, 48/49 Robustheit. DSR/PSR=0 (Such-Strafe, n=49).
- **Weizen bestätigt** (p=0,010, 73 % Win) — selber WASDE-Getreide-Treiber, ohne Re-Fitting → der
  Effekt ist **kein Mais-Zufall**, sondern grain-complex. (Risiko-adjustiert dünn: Bootstrap-KI berührt Null.)
- **Soja fällt aus** (p=0,66) — ökonomisch plausibel: der Soja-Zyklus hängt am **südamerikanischen
  Wetter (Jan–Mär)**, nicht am Dez-WASDE; Soja teilt den Treiber nicht.
- **CORN-ETF fällt aus** (p=0,85) — **strukturell, kein Gegenbeweis:** Teucrium hält bewusst *hintere*
  Kontrakte (2./3.-Verfall + Dez-Folgejahr), um den Front-Month-Roll zu *vermeiden* → kann den
  Dezember-Front-Month-Effekt gar nicht abbilden (UNG-Contango-Problem, Lehre 0004). Bestätigt eher,
  dass der Edge im **Flat-Price-Front-Month** lebt.

## 3. Bewertung

**Der WASDE-Kern ist die sauberere, besser begründete Mais-Regel** als das volle 0030-Fenster:
benennbarer Treiber (Dez-WASDE + Jahresend-Getreide-Positionierung), 92 % Trefferquote, von Weizen
unabhängig bestätigt. Es ist ein **Mais-Weizen-Getreide-Effekt**, kein universaler Ag-Effekt (Soja
teilt ihn nicht), und er lebt im Front-Month (ETF kann ihn nicht heben).

**Grenzen:** kein echtes zeitliches OOS (Fenster aus Event-Kalender, aber Jahre dieselben); Bootstrap
bei Weizen risiko-adjustiert dünn; ~8-Tage-Fenster → wenige Handelstage, hohe Bedeutung jeder
Beobachtung. **Für das Overlay (0033) wird dieser verfeinerte WASDE-Kern (8.–18.12.) als Mais-Bein
verwendet** — analog zur verfeinerten Platin-Regel in 0020. Live-Forward Dez 2026 vorab registrieren.

## Artefakte

- `results/metrics.json`, `results/plots/equity_vs_bh.png`, `results/plots/cross_instrument.png`
