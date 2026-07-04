"""Local settings and API-key storage.

The API key is stored with the Python keyring package, which uses macOS
Keychain on a normal macOS install. Non-secret preferences, such as the model
name, are stored in a JSON file under Application Support.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import keyring
from keyring.errors import KeyringError


APP_NAME = "OpenAI Chat Mac"
KEYRING_SERVICE = "OpenAIChatMac"
KEYRING_USERNAME = "openai_api_key"
SETTINGS_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
DEFAULT_MODEL = "gpt-4.1-mini"


def load_api_key() -> str:
    """Load the API key from macOS Keychain if it exists."""

    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or ""
    except KeyringError:
        return ""


def save_api_key(api_key: str) -> None:
    """Save or clear the API key in the system keyring."""

    try:
        if api_key.strip():
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key.strip())
        else:
            try:
                keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
            except KeyringError:
                pass
    except KeyringError as exc:
        raise RuntimeError(
            "Could not save the API key to macOS Keychain. "
            "Install keyring support or paste the key again when you launch the app."
        ) from exc


def load_preferences() -> dict[str, Any]:
    """Load non-secret app preferences."""

    if not SETTINGS_FILE.exists():
        return {"model": DEFAULT_MODEL}

    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"model": DEFAULT_MODEL}

    return {"model": str(data.get("model") or DEFAULT_MODEL)}


def save_preferences(model: str) -> None:
    """Persist non-secret app preferences to Application Support."""

    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps({"model": model.strip() or DEFAULT_MODEL}, indent=2),
        encoding="utf-8",
    )
