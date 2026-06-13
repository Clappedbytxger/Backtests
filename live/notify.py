"""Alert delivery for the live trading system.

Primary channel: Telegram bot (free). Credentials live in the gitignored
``.telegram.key`` at repo root (covered by the ``*.key`` rule), JSON:

    {"token": "123456:ABC...", "chat_id": "987654321"}

(Create a bot via @BotFather, get your chat_id via @userinfobot.)

Without credentials the system still works: ``run_daily.py`` always writes
the full ticket to ``live/outbox/`` and prints it; ``send()`` then just
reports that no channel is configured.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / ".telegram.key"


def _credentials() -> dict | None:
    if not KEY_FILE.exists():
        return None
    try:
        creds = json.loads(KEY_FILE.read_text(encoding="utf-8"))
        if creds.get("token") and creds.get("chat_id"):
            return creds
    except (json.JSONDecodeError, OSError):
        pass
    return None


def send(text: str, timeout: int = 15) -> bool:
    """Send a plain-text alert. Returns True on confirmed delivery."""
    creds = _credentials()
    if creds is None:
        print("[notify] kein .telegram.key — Alert nur in Konsole/Outbox.")
        return False
    # Telegram caps messages at 4096 chars; split conservatively.
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
    ok = True
    for chunk in chunks:
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


if __name__ == "__main__":
    import sys

    msg = " ".join(sys.argv[1:]) or "Test-Alert vom Backtests-Live-System."
    print("delivered" if send(msg) else "not delivered")
