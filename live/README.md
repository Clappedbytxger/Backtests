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
| `notify.py` | Alert via WhatsApp (CallMeBot, gratis) und/oder Telegram; ohne Key nur Konsole/Outbox. Credentials gitignored: `.callmebot.key` `{"phone": "+49...", "apikey": "..."}`, `.telegram.key` `{"token": ..., "chat_id": ...}`. |
| `ledger.py` | Live-Forward-Log: `state/signals.csv` (was das System sagte) vs `state/fills.csv` (was gefüllt wurde) + Live-vs-Backtest-Report. |
| `signals/` | Standalone-Skripte je Strategie (Ticket auf Abruf) + `vix_signal.py` (täglicher Gate-Check 0056, Alert nur bei Flip). |

## Tägliche Nutzung

Läuft automatisch auf ZWEI Wegen (redundant by design):

1. **Lokal:** Task-Scheduler-Task **„Backtests Trading Desk"** (täglich 08:00,
   Log: `logs/trading_desk.log`) — inkl. VIX-Gate (braucht Netz) und
   Telegram-Alert, sobald `.telegram.key` existiert. Braucht eingeschalteten PC.
2. **Cloud (PC kann aus sein):** Claude-Routine **„Trading Desk Daily"**
   (täglich 05:30 UTC ≈ 07:30 Berlin Sommer; claude.ai/code/routines) — checkt
   das GitHub-Repo aus, läuft `run_daily.py` und liefert den Report in der
   Claude-App; sendet zusätzlich Telegram, sobald Token+Chat-ID in der
   Routine-Konfiguration eingetragen sind.

Manuell:

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

## Benachrichtigung einrichten (beide gratis, optional)

**WhatsApp (CallMeBot):** +34 644 81 58 78 in die Kontakte speichern, der Nummer
per WhatsApp `I allow callmebot to send me messages` schicken, den geantworteten
`apikey` notieren. Dann `D:\Backtests\.callmebot.key` anlegen:
`{"phone": "+49DEINENUMMER", "apikey": "1234567"}`. (Nur Privatnutzung, rate-limitiert.)

**Telegram:** Bot via @BotFather (Token), Chat-ID via @userinfobot. Dann
`D:\Backtests\.telegram.key`: `{"token": "...", "chat_id": "..."}`.

Beide Dateien sind per `*.key`-Regel gitignored. `run_daily.py` sendet über
jeden konfigurierten Kanal (mind. einer reicht). Für die **Cloud-Routine**
dieselben Werte im Routine-Prompt eintragen (claude.ai/code/routines).

Test: `.\.venv\Scripts\python.exe live\notify.py "Test"`

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
