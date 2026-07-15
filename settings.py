"""Local settings and API-key storage.

Preferences and the API key are stored under Application Support. The API key
file is readable only by the current macOS user, which avoids Keychain prompts
for downloaded unsigned builds.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


APP_NAME = "OpenAI Chat Mac"
SETTINGS_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
SETTINGS_FILE = SETTINGS_DIR / "settings.json"
SECRETS_FILE = SETTINGS_DIR / "secrets.json"
CHAT_HISTORY_FILE = SETTINGS_DIR / "chat_history.json"
DEFAULT_MODEL = "gpt-4.1-mini"


def load_api_key() -> str:
    """Load the API key from local app storage if it exists."""

    try:
        data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
        return str(data.get("openai_api_key") or "")
    except (OSError, json.JSONDecodeError):
        return ""


def save_api_key(api_key: str) -> None:
    """Save or clear the API key in local app storage."""

    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        if api_key.strip():
            SECRETS_FILE.write_text(
                json.dumps({"openai_api_key": api_key.strip()}, indent=2),
                encoding="utf-8",
            )
            os.chmod(SECRETS_FILE, 0o600)
        else:
            SECRETS_FILE.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError("Could not save the API key to local app storage.") from exc


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


def load_chat_history() -> list[dict[str, Any]]:
    """Load locally saved conversations, ignoring malformed entries."""

    try:
        data = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [chat for chat in data if isinstance(chat, dict) and chat.get("id")]


def save_chat_history(chats: list[dict[str, Any]]) -> None:
    """Persist the conversation list to local Application Support."""

    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        CHAT_HISTORY_FILE.write_text(
            json.dumps(chats, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.chmod(CHAT_HISTORY_FILE, 0o600)
    except OSError as exc:
        raise RuntimeError("Could not save chat history to local app storage.") from exc
