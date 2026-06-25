"""Tests for the encrypted BYOK key vault (:mod:`quantlab.keystore`).

Verifies the security-critical behaviour: wrong-password rejection, encryption-at-rest
(plaintext keys never appear on disk), the lock/unlock lifecycle, and that
``read_api_key`` consults an unlocked vault ahead of env/keyfile.
"""

import json

import pytest

from quantlab.keystore import Vault, VaultLocked


def _vault(tmp_path):
    return Vault(tmp_path / ".vault.json")


def test_init_unlock_roundtrip(tmp_path):
    v = _vault(tmp_path)
    assert not v.exists()
    v.init("hunter2")
    assert v.exists() and v.unlocked
    v.set_key("gemini", "AIza-secret")
    v.lock()
    assert not v.unlocked
    assert v.get("gemini") is None  # locked → no access

    v2 = Vault(tmp_path / ".vault.json")
    v2.unlock("hunter2")
    assert v2.get("gemini") == "AIza-secret"
    assert v2.services() == ["gemini"]


def test_wrong_password_rejected(tmp_path):
    v = _vault(tmp_path)
    v.init("correct-horse")
    v.set_key("alpaca_key", "PK123")
    v.lock()
    with pytest.raises(ValueError, match="wrong master password"):
        v.unlock("battery-staple")


def test_encryption_at_rest(tmp_path):
    v = _vault(tmp_path)
    v.init("pw")
    v.set_key("databento", "db-PLAINTEXT-SECRET")
    raw = (tmp_path / ".vault.json").read_text()
    assert "db-PLAINTEXT-SECRET" not in raw          # never stored in the clear
    blob = json.loads(raw)
    assert set(blob) >= {"version", "salt", "token"}  # only salt + ciphertext on disk


def test_locked_vault_rejects_mutation(tmp_path):
    v = _vault(tmp_path)
    v.init("pw")
    v.lock()
    with pytest.raises(VaultLocked):
        v.set_key("fred", "x")


def test_change_password(tmp_path):
    v = _vault(tmp_path)
    v.init("old")
    v.set_key("gemini", "k")
    v.change_password("old", "new")
    v.lock()
    with pytest.raises(ValueError):
        v.unlock("old")
    v.unlock("new")
    assert v.get("gemini") == "k"


def test_read_api_key_prefers_vault(tmp_path, monkeypatch):
    """read_api_key must return the vault key ahead of env/keyfile when unlocked."""
    from quantlab import fundamental_data as fd
    from quantlab import keystore as ks

    v = Vault(tmp_path / ".vault.json")
    v.init("pw")
    v.set_key("gemini", "vault-key")
    monkeypatch.setattr(ks, "_VAULT", v)            # point the singleton at our test vault
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")  # vault must still win
    assert fd.read_api_key("gemini") == "vault-key"

    v.lock()
    assert fd.read_api_key("gemini") == "env-key"    # falls back to env when locked
