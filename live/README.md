# Live-Trading-System

Signalerzeugung + Benachrichtigung + Protokollierung für alle live/live-nahen
Strategien (NEXT-STRATEGIES-AND-LIVE-SYSTEM.md, Teil 3). **Ausführung bleibt
human-in-the-loop** — das System platziert nie Orders.

## Komponenten

| Datei | Zweck |
|---|---|
| `calendar.yaml` | Eine Definition je Strategie: Trigger, Instrument, Backtest-Erwartung, Size-Hinweis. |
| `engine.py` | Trigger-Logik (ISO-Woche, Datumsfenster, Turn-of-Month, FOMC, Monats-Task, Daily-Gate) + US-Börsenkalender + verifizierte FOMC-Termine. Spiegelt exakt die Backtest-T+1-Konvention. |
| `run_daily.py` | Orchestrator: prüft fällige Trigger, läuft Gates, schreibt Order-Ticket-Report nach `outbox/`, loggt Signale, alertet via `notify.py`. |
| `notify.py` | Telegram-Alert (Credentials in gitignored `.telegram.key`: `{"token": ..., "chat_id": ...}`); ohne Key nur Konsole/Outbox. |
| `ledger.py` | Live-Forward-Log: `state/signals.csv` (was das System sagte) vs `state/fills.csv` (was gefüllt wurde) + Live-vs-Backtest-Report. |
| `signals/` | Standalone-Skripte je Strategie (Ticket auf Abruf) + `vix_signal.py` (täglicher Gate-Check 0056, Alert nur bei Flip). |

## Tägliche Nutzung

Läuft automatisch: Task-Scheduler-Task **„Backtests Trading Desk"** (täglich
08:00, Log: `logs/trading_desk.log`). Manuell:

```powershell
.\.venv\Scripts\python.exe live\run_daily.py            # Heute + 4-Tage-Vorschau
.\.venv\Scripts\python.exe live\run_daily.py --week     # "Was trade ich diese Woche?"
.\.venv\Scripts\python.exe live\run_daily.py --no-gates # ohne Netz (kein VIX-Check)
```

Nach jedem realen Fill (Ticket-ID steht im Report):

```powershell
.\.venv\Scripts\python.exe live\ledger.py fill pre_fomc-20260616 --side entry --price 6100
.\.venv\Scripts\python.exe live\ledger.py fill pre_fomc-20260616 --side exit  --price 6110
.\.venv\Scripts\python.exe live\ledger.py report        # Live vs Backtest
```

## Abgedeckte Strategien

- **Tier 1 (confirmed):** Benzin KW9 (0006), Mastrind KW21 (0009), Platin
  Jahreswechsel (0021)
- **Tier 3 (Overlay-Beine, testing):** Baumwolle Jahresend (0035), Mais
  Dezember (0030/0032)
- **Tier 2 (Leads, testing):** Turn-of-Month (0050, Forward ab Juli 2026),
  Pre-FOMC Overnight (0052), VIX-Carry-Sleeve (0056, Daily-Gate)
- **Crypto-ML (0059/0060):** monatlicher Task-Reminder für
  `scripts/crypto_live_signal.py --refresh`

## Wartung

- **FOMC-Termine** (`engine.py`): jedes Jahr erweitern, sobald die Fed den
  Folgejahres-Kalender publiziert (federalreserve.gov/monetarypolicy/
  fomccalendars.htm). Der Test `test_fomc_list_is_sane` erzwingt 8/Jahr.
- **calendar.yaml**: neue validierte Strategien als Eintrag ergänzen;
  `enabled: false` zum Pausieren.
- Tests: `pytest tests/test_live_calendar.py`
