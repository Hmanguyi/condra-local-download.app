import base64
import hashlib
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


ENCRYPTED_PREFIX = "enc:v1:"
DEFAULT_ENCRYPTION_SECRET = "condra-local-development-encryption-key-change-me"


def encryption_secret() -> str:
    return (
        os.getenv("CONDRA_ENCRYPTION_KEY")
        or os.getenv("FLASK_SECRET_KEY")
        or DEFAULT_ENCRYPTION_SECRET
    )


def encryption_is_using_default() -> bool:
    return encryption_secret() == DEFAULT_ENCRYPTION_SECRET


def _fernet() -> Fernet:
    secret = encryption_secret().strip()
    try:
        base64.urlsafe_b64decode(secret.encode("utf-8"))
        if len(secret) == 44:
            return Fernet(secret.encode("utf-8"))
    except Exception:
        pass
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_text(value: str) -> str:
    text = str(value or "")
    if not text or text.startswith(ENCRYPTED_PREFIX):
        return text
    token = _fernet().encrypt(text.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_text(value: str) -> str:
    text = str(value or "")
    if not text.startswith(ENCRYPTED_PREFIX):
        return text
    token = text[len(ENCRYPTED_PREFIX):].encode("utf-8")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Could not decrypt stored data. Check CONDRA_ENCRYPTION_KEY.") from exc


def encrypt_json_text(value: Any) -> str:
    import json

    return encrypt_text(json.dumps(value, ensure_ascii=False))


def decrypt_json_text(value: Any, fallback: Any = None) -> Any:
    import json

    if value in (None, ""):
        return fallback
    if not isinstance(value, str):
        return value
    raw = decrypt_text(value)
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def encrypt_file_payload(raw: str) -> str:
    return encrypt_text(raw)


def decrypt_file_payload(raw: str) -> str:
    return decrypt_text(raw)
