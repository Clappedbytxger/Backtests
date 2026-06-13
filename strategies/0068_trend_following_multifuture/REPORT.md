# 0068 — Multi-Future Trend Following (fast + slow Sleeve)

**Verdikt: standalone abgelehnt (kein signifikanter Eigen-Edge auf 2010–2026),
ABER die registrierte Diversifikations-Eigenschaft ist echt — Beobachtungs-/
Overlay-Kandidat, kein Renditemotor.**

## Hypothese

Idee B aus `NEXT-STRATEGIES-AND-LIVE-SYSTEM.md`: Time-Series-Momentum
(Moskowitz/Ooi/Pedersen 2012; Hurst et al. 2017) als zweite, strukturell
unkorrelierte Edge-Familie. **Registrierte Frage: nicht „schlägt Trend das
Buch", sondern „verbessert ein Trend-Sleeve das bestehende 0036-Buch"**
(Korrelation, Krisen-Konvexität, Risiko-Reduktion).

## Spec (vorab fixiert, n_trials = 5, kein Parameter-Fitting)

- 20 liquide GLBX-Futures: Aktien (ES/NQ), Bonds (ZN/ZB/ZF), FX (6E/6J/6B/6A),
  Energie (CL/NG/HO/RB), Metalle (GC/SI/HG), Ags (ZC/ZW/ZS), Vieh (LE).
- Signale auf roll-bereinigten Closes (`instrument_id`-Back-Adjust, Lehre 0048):
  fast = sign(21d), slow = sign(252d), slow2 = sign(504d), zwei 50/50-Combos.
  **Die mittleren Horizonte (60–125d) FEHLEN bewusst** (2025er-Literatur:
  whipsawen post-2022 — vorregistrierter Ausschluss, keine gefittete Wahl).
- Sizing: per-Markt inverse-Vol-Risk-Parity (Position ∝ Ziel-Vol / vol60),
  Vol auf Info bis t-1. Wochen-Rebalance, T+1, IBKR 2,5 bps/Seite Turnover.

## Ergebnis — standalone

| Variante | Sharpe | CAGR | MaxDD | Vol | Turnover/J |
|----------|-------:|-----:|------:|----:|-----------:|
| fast21 | **−0,39** | −3,7% | −54,0% | 12,6% | 72 |
| slow252 | +0,17 | 3,3% | −28,8% | 11,8% | 23 |
| slow504 | −0,04 | 1,0% | −27,8% | 10,6% | 21 |
| combo21_252 (Headline) | −0,14 | 0,2% | −23,3% | 9,6% | 43 |
| combo21_504 | −0,23 | −0,4% | −24,3% | 8,6% | 39 |

**Headline-Batterie:** Permutation (per-Markt-Circular-Shift, Timing zerstört,
Kosten/Struktur erhalten) **p=0,794**; Bootstrap-Sharpe-KI [−0,65; +0,35];
**DSR 0,225**. → **Kein signifikanter Eigen-Edge.** Das ist exakt die
Doc-Prognose („post-2009 schwach"): TSMOM trägt auf diesem Sample standalone
nicht. Nebenbefund gegen die Doc: **der schnelle 21d-Sleeve ist hier der
schlechteste** (Whipsaw + 72× Turnover), nicht nur die mittleren Horizonte —
auf diesem Universum/Sample war nur der reine 252d-Slow knapp positiv.

## Ergebnis — die registrierte Frage (Diversifikation)

- **Korrelation Trend ↔ 0036-Buch: −0,103** über die volle Historie, und
  **−0,286 in den 5% schlechtesten Buch-Tagen**; Trend liefert dort im Mittel
  **+10,3 bps/Tag** — also genau dann positiv, wenn das Saison-Buch blutet.
- **Krisen-Konvexität real:** 2020Q1 Sharpe +2,45, Kalenderjahr 2022 (Bond-/
  Aktien-Crash) +20,5% (Sharpe 1,71) — der Long-Vol-Charakter aus der Literatur.
- **Risiko-Mix (70/30-Buch/Trend):**

| Mix | Sharpe | CAGR | MaxDD | Vol |
|-----|-------:|-----:|------:|----:|
| 0% Trend (nur Buch) | 1,43 | 38,5% | −33,4% | 23,2% |
| 20% Trend | 1,43 | 30,5% | −25,4% | 18,4% |
| **30% Trend** | **1,41** | 26,5% | **−21,2%** | 16,2% |
| 50% Trend | 1,31 | 18,7% | −13,4% | 12,1% |

Bei 30% Trend bleibt der Sharpe praktisch unverändert (1,43→1,41), während
**MaxDD von −33% auf −21% und Vol von 23% auf 16% fallen** — die erste
Strategie im Katalog, die das Markt-/DD-Risiko des Overlays SENKT (0036-Vorbehalt
war „senkt kein Marktrisiko, MaxDD −39%").

## Ehrliche Vorbehalte

1. **Der Standalone-Eigen-Edge ist ~0** — die Sharpe-Konstanz im Mix kommt
   teils schlicht aus Beimischen eines Niedrig-Vol-Streams (Verdünnung). Die
   echte Substanz ist die **negative Korrelation + Konvexität**, nicht Alpha.
2. **Das 0036-Buch (Sharpe 1,43) ist selbst full-history-gemined** (3/5 Beine,
   0036-Vorbehalt) → die absoluten Mix-Zahlen erben diesen Optimismus. Die
   Korrelations-/DD-Verbesserung ist davon aber unabhängig (Vorzeichen-Effekt).
3. **2023–2025 war Trend schwach** (−0,01/−0,05/−0,07) — die 2020/2022-Konvexität
   trägt das Mehrjahres-Ergebnis. Trend ist Versicherung mit laufender Prämie,
   kein stetiger Ertrag.

## Entscheid

- **Kein Standalone-Bein** (kein Eigen-Edge nachgewiesen — Disziplin wie 0047/0057).
- **Aber: Trend-Sleeve als Risiko-Overlay registriert** für Beobachtung. Die
  −0,10/−0,29-Korrelation und die Krisen-Konvexität sind strukturell (Long-Vol)
  und genau das im Bestand fehlende zweite Bein. Empfehlung an Robin: KEIN
  Kapital auf den Standalone-Trend, aber den combo21_252-Sleeve im Live-System
  mitlaufen lassen (Paper), um zu prüfen, ob die negative Korrelation OOS hält —
  wenn ja, ist ein 20–30%-Risiko-Overlay die sauberste DD-Senkung des Buchs.
- Infra-Gewinn: 9 Finanz-Futures (ES/NQ/ZN/ZB/ZF/6E/6J/6B/6A) jetzt gecacht
  (~$0,44), Trend-Engine (`build_positions`/`portfolio`) wiederverwendbar.

## Reproduktion

    .venv/Scripts/python.exe strategies/0068_trend_following_multifuture/run.py
