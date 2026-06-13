"""Alert delivery for the live trading system.

Two free channels, tried in order; an alert counts as delivered if ANY
configured channel succeeds. Credentials live in gitignored ``*.key`` files
at repo root.

1. WhatsApp via CallMeBot (free, personal use only). ``.callmebot.key``:

       {"phone": "+4915123456789", "apikey": "1234567"}

   Setup: save +34 644 81 58 78 to contacts, WhatsApp it
   "I allow callmebot to send me messages", note the apikey it replies with.

2. Telegram bot. ``.telegram.key``:

       {"token": "123456:ABC...", "chat_id": "987654321"}

   Setup: create a bot via @BotFather, get your chat_id via @userinfobot.

Without any credentials the system still works: run_daily.py writes the full
ticket to ``live/outbox/`` and prints it; ``send()`` just reports no channel.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
TELEGRAM_KEY = ROOT / ".telegram.key"
CALLMEBOT_KEY = ROOT / ".callmebot.key"

# CallMeBot rate-limits hard; keep WhatsApp messages few and short.
WA_CHUNK = 900
TG_CHUNK = 3900


def _load(path: Path, *required: str) -> dict | None:
    if not path.exists():
        return None
    try:
        creds = json.loads(path.read_text(encoding="utf-8"))
        if all(creds.get(k) for k in required):
            return creds
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _chunks(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] or [text]


def send_whatsapp(text: str, timeout: int = 20) -> bool:
    """WhatsApp via CallMeBot. Returns True on confirmed delivery."""
    creds = _load(CALLMEBOT_KEY, "phone", "apikey")
    if creds is None:
        return False
    ok = True
    for i, chunk in enumerate(_chunks(text, WA_CHUNK)):
        if i:
            time.sleep(8)  # CallMeBot throttles consecutive sends
        try:
            r = requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": creds["phone"], "text": chunk,
                        "apikey": str(creds["apikey"])},
                timeout=timeout,
            )
            # CallMeBot returns 200 with an HTML body; treat non-200 as failure.
            ok = ok and r.status_code == 200
            if r.status_code != 200:
                print(f"[notify] CallMeBot-Fehler {r.status_code}: {r.text[:200]}")
        except requests.RequestException as exc:
            print(f"[notify] CallMeBot nicht erreichbar: {exc}")
            ok = False
    return ok


def send_telegram(text: str, timeout: int = 15) -> bool:
    """Telegram bot. Returns True on confirmed delivery."""
    creds = _load(TELEGRAM_KEY, "token", "chat_id")
    if creds is None:
        return False
    ok = True
    for chunk in _chunks(text, TG_CHUNK):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{creds['token']}/sendMessage",
                json={"chat_id": creds["chat_id"], "text": chunk},
                timeout=timeout,
            )
            ok = ok and r.status_code == 200
            if r.status_code != 200:
                print(f"[notify] Telegram-Fehler {r.status_code}: {r.text[:200]}")
        except requests.RequestException as exc:
            print(f"[notify] Telegram nicht erreichbar: {exc}")
            ok = False
    return ok


def send(text: str) -> bool:
    """Deliver via every configured channel. True if at least one succeeds."""
    results = [fn(text) for fn in (send_whatsapp, send_telegram)]
    if not any(_load(p, *r) for p, r in
               [(CALLMEBOT_KEY, ("phone", "apikey")), (TELEGRAM_KEY, ("token", "chat_id"))]):
        print("[notify] kein .callmebot.key / .telegram.key — Alert nur in Konsole/Outbox.")
        return False
    return any(results)


if __name__ == "__main__":
    import sys

    msg = " ".join(sys.argv[1:]) or "Test-Alert vom Backtests-Live-System."
    print("delivered" if send(msg) else "not delivered")
