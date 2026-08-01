"""Encrypt / mask credentials stored in BMC & system profiles."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

MASKED_PASSWORD = "********"
_ENC_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_masked_password(value: str | None) -> bool:
    if value is None or value == "":
        return True
    if value == MASKED_PASSWORD:
        return True
    return len(value) >= 6 and set(value) <= {"*"}


def encrypt_password(plain: str) -> str:
    token = _fernet().encrypt(plain.encode("utf-8")).decode("ascii")
    return f"{_ENC_PREFIX}{token}"


def decrypt_password(stored: str | None) -> str | None:
    if not stored:
        return None
    if not stored.startswith(_ENC_PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(_ENC_PREFIX) :].encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None


def is_encrypted_password(value: str | None) -> bool:
    return bool(value and value.startswith(_ENC_PREFIX))


def store_password(plain_or_masked: str | None, previous: str | None = None) -> str | None:
    """Persist password: encrypt new plaintext; keep previous when masked/empty."""
    if is_masked_password(plain_or_masked):
        return previous
    assert plain_or_masked is not None
    if is_encrypted_password(plain_or_masked):
        return plain_or_masked
    return encrypt_password(plain_or_masked)


def mask_password_field(stored: str | None) -> tuple[str | None, bool]:
    """Return (display_password, password_set)."""
    if not stored:
        return None, False
    return MASKED_PASSWORD, True
