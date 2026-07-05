"""Small encryption helpers for the email save worker."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import keyring
from cryptography.fernet import Fernet, InvalidToken
from keyring.errors import KeyringError


KEYRING_SERVICE = "CondraLocalDownload"
KEYRING_USERNAME = "save_app_encryption_key"
ENV_KEY = "SAVE_APP_ENCRYPTION_KEY"
LEGACY_ENV_KEY = "CONDRA_ENCRYPTION_KEY"
PREFIX = "enc:v1:"


def _get_key() -> bytes:
    env_value = os.getenv(LEGACY_ENV_KEY, "").strip() or os.getenv(ENV_KEY, "").strip()
    if env_value:
        return _normalize_key(env_value)

    try:
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if stored:
            return _normalize_key(stored)

        generated = Fernet.generate_key().decode("ascii")
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, generated)
        return generated.encode("ascii")
    except KeyringError:
        fallback_path = os.path.join(os.getcwd(), ".saveApp.key")
        if os.path.exists(fallback_path):
            with open(fallback_path, "r", encoding="utf-8") as key_file:
                return _normalize_key(key_file.read().strip())

        generated = Fernet.generate_key().decode("ascii")
        with open(fallback_path, "w", encoding="utf-8") as key_file:
            key_file.write(generated)
        os.chmod(fallback_path, 0o600)
        return generated.encode("ascii")


def _normalize_key(value: str) -> bytes:
    raw = value.encode("utf-8")
    try:
        Fernet(raw)
        return raw
    except ValueError:
        digest = base64.urlsafe_b64encode(raw.ljust(32, b"0")[:32])
        Fernet(digest)
        return digest


def _cipher() -> Fernet:
    return Fernet(_get_key())


def encrypt_text(value: Any) -> str:
    text = str(value)
    if text.startswith(PREFIX):
        return text
    token = _cipher().encrypt(text.encode("utf-8")).decode("ascii")
    return f"{PREFIX}{token}"


def decrypt_text(value: Any) -> str:
    text = str(value)
    if not text.startswith(PREFIX):
        return text
    token = text[len(PREFIX) :].encode("ascii")
    try:
        return _cipher().decrypt(token).decode("utf-8")
    except InvalidToken:
        return text


def encrypt_json_text(value: Any) -> str:
    return encrypt_text(json.dumps(value, ensure_ascii=False))


def decrypt_json_text(value: Any, fallback: Any = None) -> Any:
    try:
        return json.loads(decrypt_text(value))
    except (TypeError, json.JSONDecodeError):
        return fallback


def encrypt_file_payload(value: Any) -> str:
    return encrypt_text(value)


def decrypt_file_payload(value: Any) -> str:
    return decrypt_text(value)


def encryption_is_using_default() -> bool:
    return not bool(os.getenv(LEGACY_ENV_KEY, "").strip() or os.getenv(ENV_KEY, "").strip())
