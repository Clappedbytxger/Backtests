# IBKR Prediction Markets / ForecastEx — Strategie-Einschätzung (Recherche 2026-06-18)

**Was es ist:** IBKR bündelt seit Mitte 2024 **ForecastEx** (eigene CFTC-regulierte Börse) + Zugang
zu **Kalshi** und **CME**-Event-Kontrakten in einem Konto. Yes/No-Kontrakte auf reale Ereignisse
(Politik/Makro/Zinsen/Klima), Settlement **$0 oder $1**, Preis $0,01–$0,99 = implizite
Wahrscheinlichkeit.

**Kosten/Struktur (strategie-relevant):**
- Gebühr **$0,01 pro Kontrakt/Paar** (sonst keine).
- **Incentive-Coupon ~3,12% APY** auf den Markt-Wert gehaltener Positionen, täglich akkumuliert,
  monatlich gezahlt — das ist der interessanteste strukturelle Hebel.

## Kann man daraus eine Strategie bauen? — Drei Winkel, ehrlich bewertet

1. **Coupon-Carry (delta-neutral) — der sauberste systematische Ansatz.** Kauft man Yes **und** No
   desselben Kontrakts für zusammen ~$1,00, ist das Event-Risiko gehedged (Settlement zahlt
   garantiert $1,00) und man kassiert den **~3,12%-Coupon** auf den Positionswert = synthetischer
   „T-Bill+" mit Cash-and-Carry-Charakter. **Bedingung:** Coupon-Ertrag > 2× $0,01-Gebühr + Spread.
   Bei $1-Nominal sind $0,02 Gebühr ~2% — der Coupon (3,12%) muss das + den Bid/Ask schlagen →
   funktioniert nur auf den **engsten Kontrakten** und bei längerer Haltedauer (Coupon ist p.a.).
   Kapazität klein, aber strukturell und marktneutral — das wäre der „quant-tauglichste" Trade.
2. **Arbitrage** — (a) **Yes+No < $1,00** (innerhalb einer Börse) → risikoloser Spread; (b)
   **Cross-Venue** (ForecastEx vs. Kalshi vs. CME) 1–3¢ auf demselben Flaggschiff-Kontrakt. Real
   (akademisch: ~$40M aus Polymarket 2024-25 extrahiert), aber **kapazitäts-/liquiditätslimitiert**
   (<$50k auf einer Seite → Slippage frisst den Edge), braucht schnelle Ausführung + Multi-Venue-
   Zugang. IBKRs Aggregation von 3 Börsen macht (b) hier ungewöhnlich gut zugänglich.
3. **Mispricing vs. Fundamentaldaten/Umfragen** (z. B. Zins-/Makro-Kontrakte vs. Konsens/Fed-Funds-
   Futures-implizit) — möglich, aber braucht einen **Informations-Edge** und ist schwer
   systematisierbar/backtestbar.

## Passt es zu unserer Pipeline? — Ehrliche Einschränkung
- **Nicht wie ein Preis-Backtest:** Event-Kontrakte sind binäre, einmalig auflösende Ereignisse —
  keine lange Zeitreihe, keine Permutations-/Sharpe-Logik wie bei `quantlab`. Der „Backtest" wäre
  eine Kalibrierungs-/Treffer-Analyse (Brier-Score) gegen aufgelöste Events.
- **Daten-Blocker:** saubere historische Kontrakt-Preisreihen sind **nicht frei** verfügbar wie OHLC
  (Kalshi hat eine API mit etwas Historie; ForecastEx weniger). Eine systematische Backtest-
  Validierung ist hier **deferred (Daten-Blocker)** — analog 0055/I0086-Disziplin.

## Fazit
**Ja, systematische Strategien existieren** — am ehesten **(1) Coupon-Carry delta-neutral** (der
strukturelle, marktneutrale Trade, lohnt Live-Quote-Check) und **(2) Cross-Venue-Arbitrage** (IBKR
macht's zugänglich). Beide sind aber **kapazitäts-klein, ausführungs-/liquiditätsgetrieben und nicht
mit unserer Preis-Backtest-Pipeline validierbar** (kein freier Daten-Feed, keine Zeitreihen-Logik).
Es ist eher ein **opportunistischer Live-/Manuell-Trade auf den liquidesten Makro-Kontrakten** als
ein quantlab-Edge. Empfehlung, falls vertieft: mit Live-Quotes den **Coupon-Carry** auf 2–3 engen
Makro-Kontrakten durchrechnen (Coupon p.a. vs. 2¢-Gebühr + Spread + Haltedauer) — das ist der
einzige Winkel, der ohne Informations-Edge und ohne HFT-Infrastruktur trägt.

**Quellen:** [ForecastEx About](https://forecastex.com/about) ·
[IBKR Prediction Markets](https://forecasttrader.interactivebrokers.com/en/home.php) ·
[IBKR Events-Pricing](https://www.interactivebrokers.com/en/pricing/commissions-events.php) ·
[ForecastEx Review (tech-insider)](https://tech-insider.org/prediction-markets/platforms/forecastex-review/) ·
[Prediction-Market-Arbitrage (PredScope)](https://predscope.com/guide/prediction-market-arbitrage)
