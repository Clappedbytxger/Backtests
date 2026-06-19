# 0108 — Handoff / Resume-Notiz (Stand 2026-06-19)

Live-Deployment des 0106 CORE-Buchs (Sharpe 1,21) als Forward-Test auf **IBKR Paper**,
Vorstufe zum CTI-Funded-Account. Diese Notiz = Einstiegspunkt für die nächste Session.

## Was fertig + committed ist

| Commit | Inhalt |
|---|---|
| `adf5e8f` | **Freeze**: `FROZEN_SPEC.md` + `frozen_config.yaml` (Regeln unveränderlich, Ziel-Vol 6 %) |
| `184741f` | **`signal_engine.py`**: reproduziert alle 4 Sleeves bit-genau + Buch-Sharpe 1,210; Provenienz-Fix I0076 |
| `26d72a7` | **`ib_check.py` + `ib_instruments.py`**: IBKR-Paper-Verbindung + 15/15 Instrumente gemappt |
| `abccce0` | **`ib_adapter.py`**: Dry-Run-Reconciliation (Engine → Order-Liste), Sizing verifiziert |
| _(uncommitted)_ | **`ib_adapter.py` Order-PLACEMENT fertig**: marketable Limit, Margin-Preflight, Risiko-Caps, Fill-Ledger, `--arm`-Flag |

## Schlüssel-Fakten

- **IBKR Paper**: Konto `DUK911612` (~$1,2 Mio), TWS-Port **7497**, `ib_async`. Harter
  Paper-Safety-Check (verweigert Nicht-DU-Konten). Verbindung braucht TWS offen +
  API aktiviert (Configure → API → Enable Socket Clients, Port 7497, Trusted IP 127.0.0.1).
- **Engine-Konvention**: Signal nach Tagesschluss (yfinance), Ausführung T+1. Reine
  End-of-Day-Strategie, ~1 Entscheidung/Tag.
- **15 Instrumente**: 9 FX (IDEALPRO), 4 Index-CFDs (IBUS500/IBUS30/IBUST100/IBDE40 =
  matchen Backtest-Kosten), BTC/ETH (Paxos). Mapping in `results/ib_instruments.json`.
- **Provenienz-Fix I0076**: echter Stream = `0103/e4_vix_gate.py::rsi2_stream` (einfache
  Connors-Form: Entry `Close>SMA200 & RSI2<10`, Exit `Close>SMA5`; KEIN ATR-Stop/
  Zeitstop/RSI>65/Crash-Filter). Frühere Spec-Referenz auf `0102/e2_index_rsi2.py` war falsch.
- **Stand heute (2026-06-17 as-of)**: Buch **flat**, 0 Ziel-Positionen (kein Index-Dip,
  Carry-Gate aus, BTC unter SMA200, kein Monatsende).

## Befehle

```
# Engine validieren + heutige Ziele anzeigen
.venv/Scripts/python.exe strategies/0108_cti_core_book_live/signal_engine.py
# IBKR Paper-Check (TWS muss offen sein)
.venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_check.py
# Dry-Run-Reconciliation (Engine-Ziele → Order-Liste + synth. Sizing-Test, sendet NICHTS)
.venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_adapter.py
# SCHARF: platziert echte Paper-Orders (nur mit --arm; sonst immer dry-run)
.venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_adapter.py --arm
```
IBKR-Skripte brauchen `dangerouslyDisableSandbox` (localhost-Socket).

## Order-Placement — fertig (2026-06-19)

`ib_adapter.py` platziert jetzt Orders. Design-Entscheidungen:

- **Orderart = marketable LIMIT** (nicht Market). Grund: IBKRs Precaution **Error 354**
  ("blind trading without market data") cancelt Market- UND Limit-Orders, solange das
  Paper-Konto kein Marktdaten-Abo hat. Ein Limit hat einen definierten Preis → kein
  Blind-Trading, plus es deckelt Slippage (0070-Befund: Adaptive/Limit ≈ ½-Spread schlägt
  Taker). Preis = letzter yfinance-Close ± Puffer (FX 0,25 % · CFD 0,5 % · Krypto 1,5 %),
  auf `minTick` gerundet. Krypto = IOC, FX/CFD = DAY.
- **Scharfschalten = CLI-Flag `--arm`** (statt Datei editieren). `DRY_RUN=True` bleibt im
  Git committet → ein scharfer Bot kann nie versehentlich eingecheckt werden; das „Go" ist
  jeder Lauf bewusst.
- **Sicherheits-Layer:** Paper-Konto-Assert (DU*), `readonly`-Socket außer bei `--arm`,
  Risiko-Caps (`MAX_INSTRUMENT_WEIGHT` 60 % / `MAX_GROSS_WEIGHT` 600 %), Margin-Preflight
  via `whatIfOrder` (Abbruch wenn Init-Margin > 90 % AvailableFunds), Dust-Filter (200 $),
  Fill-Ledger `results/fills_ledger.csv`.
- **Markt­daten:** Adapter ruft `reqMarketDataType(1)` + abonniert je Order `reqMktData`,
  damit der Paper-Fill-Simulator einen Preis hat. **TWS-Precaution „Bypass Order Precautions
  for API Orders" ist aktiviert** (sonst Error 354).
- **Validiert (Paper, 2026-06-19) — END-TO-END FILL BESTÄTIGT:** Engine→Ziele, Sizing/
  Konvertierung, Verbindung, Risiko-Caps, Margin-Preflight, placeOrder, **echter Fill +
  Flatten auf EURUSD** (BUY 20k @ 1.14593 / SELL @ 1.14591, marketable Limit füllte am
  Markt nahe Ask, nicht am Worst-Case-Limit = Slippage minimal), Ledger-Schreiben, Konto
  wieder flat. `reqGlobalCancel` räumt hängende Orders.

## OFFEN — als Nächstes

1. **Marktdaten-Abo für CFDs + Krypto (WICHTIG):** Auf dem Paper-Konto liefern **FX**-Paare
   bid/ask (füllen sauber), aber die **Index-CFDs** (IBUS500/30/100, IBDE40) und vermutlich
   **Krypto** geben bid/ask = -1 → kein Abo → Orders bleiben `Submitted` ohne Fill. Damit
   der I0076-Index-Sleeve (4 CFDs) + I0099-Krypto-Sleeve im Forward-Test füllen: im IBKR
   Client-Portal die nötigen Marktdaten-Pakete abonnieren bzw. Live→Paper-Sharing aktivieren
   (z. B. „US Securities Snapshot and Futures Value Bundle" + CFD-/Krypto-Daten).
2. **Hands-off-Betrieb**: VPS + Tages-Scheduler (kein PC/keine Tokens), wie besprochen.
   Täglich nach US-Close `ib_adapter.py --arm` laufen lassen.
3. **Erste echte Signale** erwartbar: ~**30. Juni** (Monatsend-FX — füllt schon jetzt, da
   FX-Daten da sind), oder Index-RSI-2-Dip / Carry-Gate (brauchen die CFD-Daten aus Punkt 1).

## Kostenloser Forward-Tracker (`forward_track.py`) — fertig (2026-06-19)

Da das Buch reine End-of-Day-Strategie auf Tages-Closes ist, braucht der Forward-Test KEINE
Broker-Fills: `forward_track.py` baut das eingefrorene Buch täglich aus yfinance neu und
schneidet ab dem Freeze-Datum → echter Live-Kombi-Sharpe (Gate ≥ 0,9), ganz ohne Marktdaten-
Abo. Schreibt `results/forward_nav.csv` (NAV) + `results/forward_targets_log.csv` (Audit-Log
der täglich emittierten Ziele). **Täglich nach US-Close laufen lassen.** FX läuft parallel
echt über `ib_adapter.py --arm`.

## CTI-MT5-Adapter (`mt5_adapter.py`) — gebaut, Live-Test offen (2026-06-19)

CTI läuft auf **MetaTrader 5**, nicht IBKR — der IBKR-Bot ist nur der Paper-Test, dieser
Adapter ist die Echtgeld-/Challenge-Schiene. Gleiche Engine, gleiche Gewichte, andere Plumbing.
`pip install MetaTrader5` (im venv erledigt). Design:

- **Lot-Sizing statt Units:** `lots_for_target()` rechnet Gewicht→Lots broker-agnostisch aus
  `symbol_info` (contract_size, currency_base/profit, volume_min/step). **Offline validiert**
  via `--selftest` (6 Fälle FX/Index/Krypto + Rundung, alle PASS).
- **Symbol-Auflösung:** broker-spezifische Namen (US500/SPX500, DE40/GER40, …) — `resolve_symbol`
  probiert Kandidaten gegen die Terminal-Symbolliste. **VOR Live prüfen, ob die echten
  CTI-Broker-Symbole in `MAPPING` getroffen werden.**
- **Orderart = Market-Deal mit `deviation`-Slippage-Cap** (MT5-Äquivalent zum marketable Limit;
  Filling-Mode IOC/FOK/RETURN automatisch erkannt).
- **Trailing-DD-Notaus (CTI-Kernregel):** `dd_guard()` (trailing peak-to-equity ODER static),
  Soft-Flatten bei 80 % des harten Limits (Puffer), State in `results/mt5_dd_state.json`.
  `--monitor` = 60-Sek-Poll-Loop, flatten + halt bei Breach. **`MAX_DD_PCT`/`DD_MODE` auf den
  EXAKTEN CTI-Plan setzen, bevor scharf!** (Default 6 % trailing = Annahme 1-Step.)
- **Sicherheit:** `DRY_RUN=True` default (Git), `--arm` zum Scharfschalten, REAL-Konto wird
  verweigert (`ALLOW_REAL=False`), Risiko-Caps, Dust-Filter, Fill-Ledger `mt5_fills_ledger.csv`.
- **Befehle:** `--selftest` (offline) · ohne Flag = Dry-Run (Terminal offen) · `--arm` (scharf)
  · `--monitor` (DD-Notaus-Loop).
- **OFFEN für CTI-Live:** (a) CTI-MT5-Terminal öffnen + einloggen, (b) `MAPPING`-Symbole gegen
  die echten Broker-Namen verifizieren, (c) `MAX_DD_PCT`/`DD_MODE` = CTI-Plan setzen, (d) erst
  Dry-Run, dann `--arm`, (e) Monitor-Loop dauerhaft mitlaufen lassen.

## Erfolgs-Gate (unverändert)

Live-Kombi-Sharpe ≥ ~0,9 über das Forward-Fenster (Haircut-Toleranz vs. 1,21 in-sample,
SMC-Präzedenz 1,52→0,43) → **dann erst CTI-Echtgeld** (1-Step @4–6 % Vol oder 2-Step @8 %).
