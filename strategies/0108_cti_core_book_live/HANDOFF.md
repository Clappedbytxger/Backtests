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
# Dry-Run-Reconciliation (Engine-Ziele → Order-Liste, sendet NICHTS)
.venv/Scripts/python.exe strategies/0108_cti_core_book_live/ib_adapter.py
```
IBKR-Skripte brauchen `dangerouslyDisableSandbox` (localhost-Socket).

## OFFEN — das machen wir als Nächstes (morgen)

1. **Order-PLACEMENT-Code** in `ib_adapter.py` (existiert noch NICHT; `DRY_RUN=True` hart an,
   keine `placeOrder`-Calls). **Offene Entscheidung: Markt- vs. Limit-Order.** Empfehlung:
   **Market-on-next-session** (sichere Fills, backtest-treu für die täglichen Close-Signale).
   Dazu: Fill-Logging (Ledger), Per-Instrument-Risiko-Caps, Margin-Check (v. a. Monatsend-FX
   erzeugt hohes Brutto).
2. **Scharfschalten**: `DRY_RUN=False` + `connect(readonly=False)` — erst nach (1) + dein Go.
3. **Hands-off-Betrieb**: VPS + Tages-Scheduler (kein PC/keine Tokens), wie besprochen.
4. **Erste echte Signale** erwartbar: ~**30. Juni** (Monatsend-FX), oder Index-RSI-2-Dip,
   oder wenn das Carry-Gate anspringt (VIX < SMA50 & < 25).

## Erfolgs-Gate (unverändert)

Live-Kombi-Sharpe ≥ ~0,9 über das Forward-Fenster (Haircut-Toleranz vs. 1,21 in-sample,
SMC-Präzedenz 1,52→0,43) → **dann erst CTI-Echtgeld** (1-Step @4–6 % Vol oder 2-Step @8 %).
