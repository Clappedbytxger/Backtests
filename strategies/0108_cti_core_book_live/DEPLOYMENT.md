# 0108 — Hands-off VPS-Deployment

Ziel: Das CORE-Buch läuft täglich automatisch auf einem VPS (kein PC, keine Tokens,
kein LLM im Order-Pfad). Der Bot ist ein **deterministisches Python-Skript** — der VPS
braucht nur Python, das Repo, ein eingeloggtes Broker-Terminal und einen Tages-Task.

## 1. VPS wählen

- **Windows-VPS** (Server 2019/2022, ≥ 2 vCPU / 4 GB RAM). Grund: IB Gateway/TWS **und**
  MT5 sind GUI-Apps, die eine eingeloggte Desktop-Session brauchen. Linux ginge nur mit
  Wine-Gefrickel — nicht empfohlen.
- Anbieter z. B. Contabo / Hetzner (Windows-Lizenz) / AWS Lightsail Windows. Trading-VPS
  mit niedriger Latenz zur Broker-Region ist nett, aber für eine **End-of-Day**-Strategie
  irrelevant — Standard-VPS reicht.
- VPS so einstellen, dass die Session **dauerhaft eingeloggt** bleibt (RDP trennen ≠
  ausloggen; ggf. Autologon konfigurieren), sonst können die GUI-Terminals nicht laufen.

## 2. Repo + Python einrichten

```powershell
# Python 3.13 installieren (python.org), dann:
git clone <repo-url> C:\Backtests        # oder dein Pfad
cd C:\Backtests
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Smoke-Test (kein Broker nötig):
.\.venv\Scripts\python.exe strategies\0108_cti_core_book_live\run_cti_daily.py
```
Der Bot zieht Kursdaten live über yfinance (wird gecacht) — kein Daten-Transfer nötig.

## 3. Broker-Terminal (eingeloggt halten)

### IBKR Paper (Forward-Test, jetzt)
- **IB Gateway** installieren (schlanker als TWS) + **IBC** (IBController,
  github.com/IbcAlpha/IBC) für Auto-Login/Auto-Restart. IBC startet Gateway, loggt das
  Paper-Konto **DUK911612** ein und hält es 24/7 offen (täglicher IB-Auto-Restart wird
  abgefangen).
- API aktivieren: Configure → API → **Enable Socket Clients**, Port **7497**, Trusted IP
  127.0.0.1, **„Bypass Order Precautions for API Orders" anhaken** (sonst Error 354).
- Ohne IBC: Gateway manuell offen lassen — aber dann reißt der tägliche IB-Restart die
  Verbindung. IBC ist für hands-off Pflicht.

### CTI / MT5 (später, Echtgeld-Schiene)
- MT5-Terminal des CTI-Brokers installieren + Challenge-Login eingeloggt halten.
- „Algo Trading" im Terminal aktivieren. Vor dem ersten scharfen Lauf: `MAPPING`-Symbole
  und `MAX_DD_PCT`/`DD_MODE` in `mt5_adapter.py` auf den echten CTI-Plan prüfen (siehe
  HANDOFF).

## 4. Alerts (optional, empfohlen)

Lege im Repo-Root eine `.telegram.key` an (oder `.callmebot.key`):
```json
{ "token": "123456:ABC...", "chat_id": "987654321" }
```
Der Tages-Runner schickt dann jeden Tag eine Zusammenfassung (Forward-Sharpe, Ziele,
Fills) und alarmiert bei Fehlern. Ohne Key: alles steht nur im Log.

## 5. Tages-Task registrieren

```powershell
# elevated PowerShell:
powershell -ExecutionPolicy Bypass -File `
  C:\Backtests\strategies\0108_cti_core_book_live\deploy\install_scheduler.ps1 -At "22:35"
```
- `-At` = **VPS-Lokalzeit** ~30 Min nach US-Close. **Empfehlung:** VPS-Zeitzone auf
  *US Eastern* stellen, dann `-At "16:35"` — dann stimmt es ganzjährig (DST-sicher).
- Default-Args `--ibkr --arm` = Forward-Tracking **und** scharfe FX-Orders. Für reines
  Tracking ohne Orders: `-TaskArgs ""`. Für Dry-Run-Orders: `-TaskArgs "--ibkr"`.
- Testlauf: `Start-ScheduledTask -TaskName "CTI CORE Book Daily"`,
  Status: `Get-ScheduledTaskInfo -TaskName "CTI CORE Book Daily"`.

## 6. Was wann läuft

| Job | Wie | Wann |
|---|---|---|
| Forward-Tracking (immer) | `run_cti_daily.py` | täglich, im Tages-Task |
| FX-Orders IBKR Paper (`--arm`) | dito | täglich, nach US-Close |
| Index-CFD/Krypto-Fills | erst nach Marktdaten-Abo (HANDOFF) | — |
| **MT5 DD-Notaus** (CTI-Phase) | `mt5_adapter.py --monitor --arm` | **dauerhaft** (Autostart) |

Der DD-Monitor ist KEIN Tages-Task, sondern ein **Dauerprozess** (60-Sek-Poll). In der
CTI-Phase als Autostart-Eintrag oder eigene „bei Anmeldung"-Aufgabe einrichten, damit das
Trailing-DD-Notaus rund um die Uhr greift.

## 7. Monitoring / Betrieb

- **Logs:** `strategies/0108_cti_core_book_live/results/daily_logs/YYYY-MM-DD.log` (jeder
  Lauf vollständig).
- **Forward-Stand:** `results/forward_nav.csv` (NAV) + Telegram-Tagessummary.
- **Fills:** `results/fills_ledger.csv` (IBKR), `results/mt5_fills_ledger.csv` (CTI).
- **Ziel-Audit:** `results/forward_targets_log.csv` (was die Engine täglich emittierte).
- **Failure:** Task-Exit-Code ≠ 0 → die Tagessummary trägt „RUN HAD FAILURES"; im Log
  steht der Traceback. Häufigste Ursache: Broker-Terminal nicht eingeloggt.
- **Wartung:** FOMC-Termine in `live/engine.py` werden hier nicht gebraucht (eigene Engine);
  einzige laufende Pflege = Broker-Login wach halten (IBC erledigt das).

## 8. Sicherheits-Defaults (eingebaut)

- `DRY_RUN=True` ist im Code committet — scharf nur über `--arm` im Task-Argument.
- IBKR: harter Paper-Konto-Assert (nur DU*). MT5: REAL-Konto wird verweigert
  (`ALLOW_REAL=False`).
- Risiko-Caps (60 %/Instrument, 600 % Brutto), Margin-Preflight, Dust-Filter.
- Marketable-Limit (IBKR) / Deviation-Cap (MT5) deckeln Slippage.
