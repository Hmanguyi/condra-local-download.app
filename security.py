"""Small encryption helpers for the email save worker."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


ENV_KEY = "SAVE_APP_ENCRYPTION_KEY"
LEGACY_ENV_KEY = "CONDRA_ENCRYPTION_KEY"
APP_NAME = "OpenAI Chat Mac"
KEY_FILE = Path.home() / "Library" / "Application Support" / APP_NAME / "saveApp.key"
PREFIX = "enc:v1:"


def _get_key() -> bytes:
    env_value = os.getenv(LEGACY_ENV_KEY, "").strip() or os.getenv(ENV_KEY, "").strip()
    if env_value:
        return _normalize_key(env_value)

    if KEY_FILE.exists():
        return _normalize_key(KEY_FILE.read_text(encoding="utf-8").strip())

    generated = Fernet.generate_key().decode("ascii")
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(generated, encoding="utf-8")
    os.chmod(KEY_FILE, 0o600)
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
