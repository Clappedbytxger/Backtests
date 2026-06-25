"""Quant-OS Settings API — the BYOK encrypted-key vault (Phase 3.1).

Mounted under ``/api/settings`` by :mod:`apps.api.main`. A thin HTTP shell over the
master-password Fernet vault (:mod:`quantlab.keystore`): initialise / unlock / lock the
vault and set / delete individual service keys. **Key values are never returned** — the
status endpoint reports only which services have a key set.

The master password travels over localhost only; it is used to derive the Fernet key and
is never persisted. Once unlocked, keys flow to the rest of the app via
``read_api_key`` (vault > env > keyfile), so e.g. the Swarm commander picks up the
Gemini key the moment it is entered here.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from quantlab.keystore import VaultLocked, get_vault

router = APIRouter(prefix="/api/settings", tags=["settings"])

# The external services the app can BYOK. ``group`` drives the UI sectioning.
KNOWN_SERVICES: list[dict] = [
    {"service": "gemini", "label": "Google Gemini (Commander)", "group": "AI"},
    {"service": "alpaca_key", "label": "Alpaca API Key-ID", "group": "Daten/Broker"},
    {"service": "alpaca_secret", "label": "Alpaca API Secret", "group": "Daten/Broker"},
    {"service": "databento", "label": "Databento (Intraday-Futures)", "group": "Daten/Broker"},
    {"service": "fred", "label": "FRED (Makro)", "group": "Daten/Broker"},
    {"service": "eia", "label": "EIA (Energie)", "group": "Daten/Broker"},
    {"service": "nass", "label": "USDA NASS (Agrar)", "group": "Daten/Broker"},
    {"service": "fas", "label": "USDA FAS (WASDE/PSD)", "group": "Daten/Broker"},
]


def _status() -> dict:
    v = get_vault()
    have = set(v.services())
    return {
        "ok": True,
        "vault_exists": v.exists(),
        "unlocked": v.unlocked,
        "services_set": sorted(have),
        "known": [{**k, "set": k["service"] in have} for k in KNOWN_SERVICES],
    }


@router.get("/status")
def status() -> dict:
    """Vault state + which known services have a key set (never the values)."""
    return _status()


class PasswordBody(BaseModel):
    password: str


@router.post("/init")
def init(body: PasswordBody) -> dict:
    """Create a fresh encrypted vault under the given master password."""
    try:
        get_vault().init(body.password)
        return _status()
    except (FileExistsError, ValueError) as e:
        return {"ok": False, "error": str(e)}


@router.post("/unlock")
def unlock(body: PasswordBody) -> dict:
    """Decrypt the vault into memory for this session."""
    try:
        get_vault().unlock(body.password)
        return _status()
    except (FileNotFoundError, ValueError) as e:
        return {"ok": False, "error": str(e)}


@router.post("/lock")
def lock() -> dict:
    """Drop the decrypted keys from memory."""
    get_vault().lock()
    return _status()


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.post("/password")
def change_password(body: ChangePasswordBody) -> dict:
    """Re-encrypt the vault under a new master password."""
    try:
        get_vault().change_password(body.old_password, body.new_password)
        return _status()
    except (FileNotFoundError, ValueError) as e:
        return {"ok": False, "error": str(e)}


class KeyBody(BaseModel):
    service: str
    value: str


@router.post("/key")
def set_key(body: KeyBody) -> dict:
    """Store/update one service key (vault must be unlocked)."""
    try:
        get_vault().set_key(body.service, body.value)
        return _status()
    except (VaultLocked, ValueError) as e:
        return {"ok": False, "error": str(e)}


@router.delete("/key/{service}")
def delete_key(service: str) -> dict:
    """Remove one service key (vault must be unlocked)."""
    try:
        get_vault().delete_key(service)
        return _status()
    except VaultLocked as e:
        return {"ok": False, "error": str(e)}
