"""Encrypted BYOK key vault — master-password Fernet store (Phase 3.1).

A single encrypted file (``.vault.json`` at the repo root, git-ignored) holds all of
the user's external API keys (Gemini, Alpaca, Databento, FRED …). The encryption key is
derived from a **master password** via PBKDF2-HMAC-SHA256; the password is never stored.
On ``unlock`` the vault is decrypted into the running process's memory for the session;
the rest of the app reads keys via :func:`vault_key`, which :func:`quantlab.fundamental_
data.read_api_key` consults ahead of env vars / plaintext ``.key`` files.

On-disk format (the only thing persisted):
    {"version": 1, "salt": <b64 16B>, "token": <b64 Fernet(JSON{service: key})>}

This is real encryption-at-rest: without the master password the file is opaque. The
decrypted keys live only in process memory while unlocked (a local single-process app),
which is the pragmatic trust boundary for a desktop BYOK setup.
"""

from __future__ import annotations

import base64
import json
import os
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_PBKDF2_ITERS = 480_000  # OWASP-tier work factor for PBKDF2-SHA256
_VERSION = 1


def _derive(password: str, salt: bytes) -> bytes:
    """Derive a urlsafe-b64 Fernet key from the master password + salt (PBKDF2)."""
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=_PBKDF2_ITERS)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


class VaultLocked(RuntimeError):
    """Raised when a mutating op is attempted on a locked vault."""


class Vault:
    """A master-password-encrypted store of ``{service: api_key}``.

    Thread-safe (a single process-wide instance is shared by the FastAPI workers).
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._fernet: Fernet | None = None
        self._salt: bytes | None = None
        self._keys: dict[str, str] = {}

    # ── state ────────────────────────────────────────────────────────────────
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def unlocked(self) -> bool:
        return self._fernet is not None

    def services(self) -> list[str]:
        """Names (never values) of the stored keys; empty while locked."""
        with self._lock:
            return sorted(self._keys) if self.unlocked else []

    # ── lifecycle ────────────────────────────────────────────────────────────
    def init(self, password: str) -> None:
        """Create a fresh empty vault encrypted under ``password``. Errors if one exists."""
        with self._lock:
            if self.exists():
                raise FileExistsError("vault already initialised")
            if not password:
                raise ValueError("master password must not be empty")
            self._salt = os.urandom(16)
            self._fernet = Fernet(_derive(password, self._salt))
            self._keys = {}
            self._save()

    def unlock(self, password: str) -> None:
        """Decrypt the on-disk vault into memory. Raises on a wrong password."""
        with self._lock:
            if not self.exists():
                raise FileNotFoundError("no vault — initialise it first")
            data = json.loads(self.path.read_text(encoding="utf-8"))
            salt = base64.b64decode(data["salt"])
            fernet = Fernet(_derive(password, salt))
            try:
                raw = fernet.decrypt(base64.b64decode(data["token"]))
            except InvalidToken as e:
                raise ValueError("wrong master password") from e
            self._fernet = fernet
            self._salt = salt
            self._keys = json.loads(raw.decode("utf-8"))

    def lock(self) -> None:
        """Drop the decrypted keys + Fernet from memory."""
        with self._lock:
            self._fernet = None
            self._keys = {}

    def change_password(self, old: str, new: str) -> None:
        """Re-encrypt the vault under a new master password."""
        with self._lock:
            self.unlock(old)
            if not new:
                raise ValueError("new master password must not be empty")
            self._salt = os.urandom(16)
            self._fernet = Fernet(_derive(new, self._salt))
            self._save()

    # ── keys ─────────────────────────────────────────────────────────────────
    def set_key(self, service: str, value: str) -> None:
        with self._lock:
            if not self.unlocked:
                raise VaultLocked("vault is locked")
            if not service:
                raise ValueError("service name required")
            self._keys[service] = value
            self._save()

    def delete_key(self, service: str) -> None:
        with self._lock:
            if not self.unlocked:
                raise VaultLocked("vault is locked")
            self._keys.pop(service, None)
            self._save()

    def get(self, service: str) -> str | None:
        with self._lock:
            return self._keys.get(service) if self.unlocked else None

    def _save(self) -> None:
        assert self._fernet is not None and self._salt is not None
        token = self._fernet.encrypt(json.dumps(self._keys).encode("utf-8"))
        payload = {"version": _VERSION,
                   "salt": base64.b64encode(self._salt).decode(),
                   "token": base64.b64encode(token).decode()}
        self.path.write_text(json.dumps(payload), encoding="utf-8")


# ── process-wide singleton ──────────────────────────────────────────────────
_VAULT: Vault | None = None
_VAULT_LOCK = threading.Lock()


def get_vault() -> Vault:
    """The process-wide vault (path from settings: ``<repo>/.vault.json``)."""
    global _VAULT
    if _VAULT is None:
        with _VAULT_LOCK:
            if _VAULT is None:
                from quantlab.config import get_settings

                _VAULT = Vault(get_settings().keys_dir / ".vault.json")
    return _VAULT


def vault_key(service: str) -> str | None:
    """The in-memory key for ``service`` if the vault is unlocked, else ``None``.

    Safe to call always (returns ``None`` when locked / missing) — this is the hook
    :func:`quantlab.fundamental_data.read_api_key` uses before env/keyfile fallback.
    """
    try:
        return get_vault().get(service)
    except Exception:  # noqa: BLE001 - key resolution must never raise
        return None
