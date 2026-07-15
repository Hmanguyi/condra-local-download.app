from __future__ import annotations

import os
import time
import threading
import traceback
import hashlib
import copy
import numpy as np
import faiss
import re
import html as html_lib
import json
import datetime
import msal
import requests

from flask import Flask, jsonify, redirect, request, session, abort, render_template, g

from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import base64
import urllib.parse
import urllib.request
import urllib.error

from security import (
    decrypt_file_payload,
    decrypt_json_text,
    decrypt_text,
    encrypt_file_payload,
    encrypt_json_text,
    encrypt_text,
    encryption_is_using_default,
)
from local_storage import request as local_storage_request, vector_match as local_vector_match




# I am here I am here
# =========================
# CONFIG
# =========================
# I am here I am here
# I am here
# I am here 

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

CLIENT_SECRET_FILE = "client_secret.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.labels"
]

MICROSOFT_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")
MICROSOFT_AUTHORITY_TENANT = os.environ.get("AZURE_AUTHORITY_TENANT", "common")
MICROSOFT_AUTHORITY = os.environ.get(
    "AZURE_AUTHORITY",
    f"https://login.microsoftonline.com/{MICROSOFT_AUTHORITY_TENANT}"
)
MICROSOFT_SCOPES = [
    "User.Read",
    "Mail.Read",
    "Mail.ReadWrite",
    "MailboxSettings.ReadWrite",
]
MICROSOFT_TOKEN_CACHE_FILE = os.environ.get("MICROSOFT_TOKEN_CACHE_FILE", "")

OLLAMA_CHAT_URL = os.environ.get("OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
OLLAMA_ASK_MODEL = os.environ.get("OLLAMA_ASK_MODEL", os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:latest"))

CHECK_INTERVAL = 10  # seconds
NOTE_LABEL_SYNC_INTERVAL = 30  # seconds
RUN_SAVE_WORKER_IN_APP = str(os.getenv("RUN_SAVE_WORKER_IN_APP", "0")).strip().lower() in ("1", "true", "yes")

MAX_NOTES = 5
MAX_NOTE_LENGTH = 5000

SUPABASE_URL_DEFAULT = ""
SUPABASE_SERVICE_ROLE_KEY_DEFAULT = ""
SUPABASE_VECTOR_RPC_DEFAULT = "match_email_embeddings"

CACHE_TTL_EMAIL_ROWS_SECONDS = int(os.getenv("CACHE_TTL_EMAIL_ROWS_SECONDS", "4"))
CACHE_TTL_NOTES_SECONDS = int(os.getenv("CACHE_TTL_NOTES_SECONDS", "4"))
CACHE_TTL_ASK_CHUNKS_SECONDS = int(os.getenv("CACHE_TTL_ASK_CHUNKS_SECONDS", "12"))
CACHE_TTL_SUMMARY_MATCH_SECONDS = int(os.getenv("CACHE_TTL_SUMMARY_MATCH_SECONDS", "20"))
CACHE_TTL_EMBEDDING_SECONDS = int(os.getenv("CACHE_TTL_EMBEDDING_SECONDS", "3600"))
EMBED_CACHE_MAX_ITEMS = int(os.getenv("EMBED_CACHE_MAX_ITEMS", "512"))
EXTENSION_MATCH_ROW_LIMIT = int(os.getenv("EXTENSION_MATCH_ROW_LIMIT", "250"))

# =========================
# INIT
# =========================

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "IamAM")
_default_cookie_secure = bool(os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL"))
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv(
    "SESSION_COOKIE_SAMESITE",
    "None" if _default_cookie_secure else "Lax",
)
app.config["SESSION_COOKIE_SECURE"] = str(
    os.getenv("SESSION_COOKIE_SECURE", "1" if _default_cookie_secure else "0")
).strip().lower() in ("1", "true", "yes")
if not MICROSOFT_TOKEN_CACHE_FILE:
    MICROSOFT_TOKEN_CACHE_FILE = os.path.join(app.instance_path, "msal_token_cache.json")
EXTENSION_API_KEY = str(os.getenv("EXTENSION_API_KEY", "")).strip()


@app.after_request
def add_extension_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if (
        origin == "https://mail.google.com"
        or origin == "https://outlook.live.com"
        or origin == "https://outlook.office.com"
        or origin.startswith("chrome-extension://")
        or origin.startswith("moz-extension://")
    ):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Condra-Key"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        if request.headers.get("Access-Control-Request-Private-Network") == "true":
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        response.headers["Vary"] = "Origin"
    return response


def is_local_extension_request() -> bool:
    return (request.remote_addr or "") in {"127.0.0.1", "::1"}


def _clean_user_email(value: str) -> str:
    return str(value or "").strip()


def _is_placeholder_user(value: str) -> bool:
    return _clean_user_email(value).lower() in {"outlook-local", "gmail-local", "local"}


def _same_email(left: str, right: str) -> bool:
    return _clean_user_email(left).lower() == _clean_user_email(right).lower()


def require_extension_access():
    g.extension_auth_method = ""
    g.extension_user_email = ""
    if is_local_extension_request():
        g.extension_auth_method = "local"
        return
    signed_in_user = str(session.get("user_email") or "").strip()
    if signed_in_user:
        g.extension_auth_method = "session"
        g.extension_user_email = signed_in_user
        return
    if not EXTENSION_API_KEY:
        return jsonify({
            "error": "extension_auth_required",
            "message": "Sign in with Gmail or Microsoft to connect Condra. Admins can also set EXTENSION_API_KEY on the Render service.",
            "signin_url": urllib.parse.urljoin(request.url_root, "sign"),
        }), 403
    provided = str(request.headers.get("X-Condra-Key") or "").strip()
    if provided != EXTENSION_API_KEY:
        return jsonify({
            "error": "extension_auth_invalid",
            "message": "Sign in with Gmail or Microsoft, or enter the Condra server key for this Render deployment.",
            "signin_url": urllib.parse.urljoin(request.url_root, "sign"),
        }), 403
    g.extension_auth_method = "api_key"
    return None


def require_extension_user(requested_user: str):
    requested = _clean_user_email(requested_user)

    if is_local_extension_request():
        if requested and not _is_placeholder_user(requested):
            return resolve_strict_extension_user(requested) or requested
        return jsonify({
            "error": "missing_user",
            "message": "Missing mailbox account.",
        }), 400

    signed_in_user = _clean_user_email(getattr(g, "extension_user_email", "") or session.get("user_email") or "")
    if not signed_in_user:
        return jsonify({
            "error": "session_required",
            "message": "Sign in with Gmail or Microsoft before accessing mailbox data. A server key alone cannot select a user's emails.",
            "signin_url": urllib.parse.urljoin(request.url_root, "sign"),
        }), 403

    if requested and not _is_placeholder_user(requested) and not _same_email(requested, signed_in_user):
        return jsonify({
            "error": "user_mismatch",
            "message": "The requested mailbox does not match the signed-in account.",
            "requested_user": requested,
            "signed_in_user": signed_in_user,
        }), 403

    resolved = resolve_strict_extension_user(signed_in_user)
    if not resolved:
        return jsonify({
            "error": "missing_user",
            "message": "The signed-in account does not have saved mailbox data yet.",
            "requested_user": signed_in_user,
        }), 400
    return resolved


@app.errorhandler(Exception)
def extension_json_error_handler(exc):
    if request.path.startswith("/extension/"):
        traceback.print_exc()
        status = getattr(exc, "code", 500)
        return jsonify({
            "error": "extension_server_error",
            "message": str(exc),
            "path": request.path,
        }), status
    raise exc



# Per-user in-memory set of processed IDs
# Key: user_email (str) → Value: set of processed msg IDs
user_stored_ids: dict[str, set] = {}

# Track which users already have a background thread running
active_threads: set[str] = set()
active_threads_lock = threading.Lock()

_cache_lock = threading.Lock()
_email_rows_cache = {}
_notes_cache = {}
_ask_chunks_cache = {}
_summary_match_cache = {}
_prepared_match_rows_cache = {}
_embedding_cache = {}
_embedding_cache_order = []
_backfill_last_run = {}
_notes_label_metadata_supported = str(os.getenv("NOTES_LABEL_METADATA_ENABLED", "0")).strip().lower() in ("1", "true", "yes")


def _cache_get(bucket: dict, key):
    now = time.time()
    with _cache_lock:
        item = bucket.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at <= now:
            bucket.pop(key, None)
            return None
        return copy.deepcopy(value)


def _cache_set(bucket: dict, key, value, ttl_seconds: int):
    if ttl_seconds <= 0:
        return
    with _cache_lock:
        bucket[key] = (time.time() + ttl_seconds, copy.deepcopy(value))


def _invalidate_email_caches(user_email: str):
    with _cache_lock:
        for key in list(_email_rows_cache.keys()):
            if isinstance(key, tuple) and user_email in key[:2]:
                _email_rows_cache.pop(key, None)
        for key in list(_ask_chunks_cache.keys()):
            if isinstance(key, tuple) and key and key[0] == user_email:
                _ask_chunks_cache.pop(key, None)
        for key in list(_summary_match_cache.keys()):
            if isinstance(key, tuple) and key and key[0] == user_email:
                _summary_match_cache.pop(key, None)
        for key in list(_prepared_match_rows_cache.keys()):
            if isinstance(key, tuple) and key and key[0] == user_email:
                _prepared_match_rows_cache.pop(key, None)
        _backfill_last_run.pop(user_email, None)


def _invalidate_notes_cache(user_email: str):
    with _cache_lock:
        _notes_cache.pop(user_email, None)


def _safe_iso_now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def google_error_response(exc: Exception, generic_error: str, generic_message: str):
    msg = str(exc)
    low = msg.lower()
    status = getattr(getattr(exc, "resp", None), "status", None)
    detail = ""
    if isinstance(exc, HttpError):
        try:
            detail = (exc.content or b"").decode("utf-8", errors="ignore")
        except Exception:
            detail = msg
    low_all = f"{low} {detail.lower()}"

    if (
        "insufficient authentication scopes" in low_all
        or "insufficientpermissions" in low_all
        or "invalid_grant" in low_all
        or "invalid_scope" in low_all
        or "token has been expired or revoked" in low_all
    ):
        return jsonify({
            "error": "reauth_required",
            "message": "Please re-connect at /sign to grant required Google permissions. If this persists, remove the saved token and sign in again."
        }), 403

    if (
        "accessnotconfigured" in low_all
        or "api has not been used" in low_all
        or "google docs api has not been used" in low_all
        or "google calendar api has not been used" in low_all
    ):
        return jsonify({
            "error": "docs_api_not_enabled",
            "message": "Enable required Google APIs (Docs/Drive/Calendar) in your Google Cloud project, then retry."
        }), 403

    if status == 429 or "rate limit" in low_all:
        return jsonify({
            "error": "rate_limited_upstream",
            "message": "Google API rate limit hit. Please retry shortly."
        }), 429

    return jsonify({"error": generic_error, "message": generic_message or msg}), 500


# =========================
# LOCAL JS/API DATA HELPERS (INDEPENDENT FROM saveApp.py)
# =========================

def ollama_chat(prompt: str, system: str = "") -> str:
    messages = []
    if str(system or "").strip():
        messages.append({"role": "system", "content": str(system).strip()})
    messages.append({"role": "user", "content": str(prompt or "")})

    response = requests.post(
        OLLAMA_CHAT_URL,
        headers={"X-API-Key": OLLAMA_API_KEY},
        json={
            "model": OLLAMA_ASK_MODEL,
            "messages": messages,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    body = response.json()
    return str(((body or {}).get("message") or {}).get("content") or "").strip()

def _normalize_supabase_url(value: str) -> str:
    v = (value or "").strip().rstrip("/")
    if not v:
        return v
    if v.startswith("http://") or v.startswith("https://"):
        return v
    if "." not in v:
        return f"https://{v}.supabase.co"
    if v.endswith(".supabase.co"):
        return f"https://{v}"
    return f"https://{v}"

def get_supabase_url() -> str:
    return _normalize_supabase_url(os.getenv("SUPABASE_URL", SUPABASE_URL_DEFAULT))

def get_supabase_key() -> str:
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or SUPABASE_SERVICE_ROLE_KEY_DEFAULT
        or ""
    ).strip()

def supabase_enabled() -> bool:
    # Kept as a compatibility name for the existing feature checks. Persistence
    # is always available through the local SQLite database.
    return True


SUPABASE_ENCRYPTED_FIELDS = {
    "emails": {
        "sender",
        "subject",
        "snippet",
        "full_email",
        "objective_info",
        "objective_completion",
        "raw_chunk",
    },
    "email_embeddings": {
        "content_chunk",
    },
    "notes": {
        "text",
        "topic",
        "expected_from",
        "ai_action",
    },
}

SUPABASE_ENCRYPTED_JSON_FIELDS = {
    "emails": {
        "bullet_points_json",
        "excerpts_json",
    },
}


def _encrypt_supabase_row(table: str, row: dict) -> dict:
    if not isinstance(row, dict):
        return row
    encrypted = dict(row)
    for field in SUPABASE_ENCRYPTED_FIELDS.get(table, set()):
        if encrypted.get(field) not in (None, ""):
            encrypted[field] = encrypt_text(encrypted[field])
    for field in SUPABASE_ENCRYPTED_JSON_FIELDS.get(table, set()):
        if encrypted.get(field) not in (None, ""):
            encrypted[field] = encrypt_json_text(encrypted[field])
    return encrypted


def _decrypt_supabase_row(table: str, row: dict) -> dict:
    if not isinstance(row, dict):
        return row
    decrypted = dict(row)
    for field in SUPABASE_ENCRYPTED_FIELDS.get(table, set()):
        if decrypted.get(field) not in (None, ""):
            decrypted[field] = decrypt_text(decrypted[field])
    for field in SUPABASE_ENCRYPTED_JSON_FIELDS.get(table, set()):
        if decrypted.get(field) not in (None, ""):
            decrypted[field] = decrypt_json_text(decrypted[field], fallback=decrypted[field])
    return decrypted


def _encrypt_supabase_body(table: str, body):
    if isinstance(body, list):
        return [_encrypt_supabase_row(table, item) for item in body]
    if isinstance(body, dict):
        return _encrypt_supabase_row(table, body)
    return body


def _decrypt_supabase_result(table: str, result):
    if isinstance(result, list):
        return [_decrypt_supabase_row(table, item) for item in result]
    if isinstance(result, dict):
        return _decrypt_supabase_row(table, result)
    return result

def supabase_request(method: str, table: str, query_params=None, body=None, prefer: str = ""):
    result = local_storage_request(
        method,
        table,
        query_params=query_params,
        body=_encrypt_supabase_body(table, body) if body is not None else None,
        prefer=prefer,
    )
    return _decrypt_supabase_result(table, result)

def supabase_rpc(function_name: str, payload: dict):
    del function_name
    return _decrypt_supabase_result("email_embeddings", local_vector_match(payload))

def supabase_vectors_enabled() -> bool:
    flag = str(os.getenv("SUPABASE_VECTOR_ENABLED", "1")).strip().lower()
    return supabase_enabled() and flag not in ("0", "false", "no")

def _to_pgvector_literal(values) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in values) + "]"

def upsert_supabase_email_embedding(user_email: str, source_index: int, email_id: str, chunk_text: str):
    if not supabase_vectors_enabled():
        return
    if not chunk_text or not chunk_text.strip():
        return

    emb = embed_text(chunk_text)
    row = {
        "user_email": user_email,
        "source_index": int(source_index),
        "email_id": (email_id or "").strip() or None,
        "content_chunk": chunk_text,
        "embedding": _to_pgvector_literal(emb),
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    supabase_request(
        "POST",
        "email_embeddings",
        query_params={"on_conflict": "user_email,source_index"},
        body=[row],
        prefer="resolution=merge-duplicates,return=minimal",
    )

def get_supabase_relevant_chunks(user_email: str, question: str, k: int = 40):
    if not supabase_vectors_enabled():
        return []
    cache_key = (user_email, (question or "").strip(), int(k))
    cached = _cache_get(_ask_chunks_cache, cache_key)
    if cached is not None:
        return cached

    fn_name = (os.getenv("SUPABASE_VECTOR_RPC", SUPABASE_VECTOR_RPC_DEFAULT) or "").strip() or SUPABASE_VECTOR_RPC_DEFAULT
    q_emb = embed_text(question)
    payloads = [
        {"p_user_email": user_email, "query_embedding": _to_pgvector_literal(q_emb), "match_count": int(k)},
        {"user_email": user_email, "query_embedding": _to_pgvector_literal(q_emb), "match_count": int(k)},
    ]
    last_err = None
    for payload in payloads:
        try:
            rows = supabase_rpc(fn_name, payload)
            chunks = []
            seen = set()
            for r in rows:
                chunk = str(r.get("content_chunk") or r.get("raw_chunk") or "").strip()
                if chunk and chunk not in seen:
                    chunks.append(chunk)
                    seen.add(chunk)
            _cache_set(_ask_chunks_cache, cache_key, chunks, CACHE_TTL_ASK_CHUNKS_SECONDS)
            return chunks
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    return []

def backfill_supabase_embeddings_for_user(user_email: str, max_items: int = 40):
    if not supabase_vectors_enabled():
        return 0
    now = time.time()
    with _cache_lock:
        last = float(_backfill_last_run.get(user_email, 0.0))
        if now - last < 20:
            return 0
        _backfill_last_run[user_email] = now

    rows = get_email_rows(user_email, descending=True)
    if not rows:
        return 0

    existing = supabase_request(
        "GET",
        "email_embeddings",
        query_params={"select": "source_index", "user_email": f"eq.{user_email}"},
    ) or []
    existing_index = set()
    if isinstance(existing, list):
        for r in existing:
            try:
                existing_index.add(int(r.get("source_index")))
            except Exception:
                continue

    created = 0
    for r in rows:
        try:
            source_index = int(r["source_index"])
        except Exception:
            continue
        if source_index in existing_index:
            continue
        raw_chunk = str(r["raw_chunk"] or "").strip()
        if not raw_chunk:
            continue
        upsert_supabase_email_embedding(
            user_email=user_email,
            source_index=source_index,
            email_id=str(r["email_id"] or ""),
            chunk_text=raw_chunk,
        )
        created += 1
        if created >= max_items:
            break
    return created

def _extract_first_json_object(raw: str):
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if ch == '"' and not escape:
            in_string = not in_string
        if not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return raw[start:i + 1]
        escape = (ch == "\\") and not escape
        if ch != "\\":
            escape = False
    if depth > 0:
        return raw[start:] + ("}" * depth)
    return None

def _load_summary_json(json_raw: str):
    raw_text = str(json_raw or "").strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.I)
        raw_text = re.sub(r"\s*```$", "", raw_text).strip()

    def backtick_value_to_json_string(match):
        key = match.group(1)
        value = match.group(2)
        return f'{key}{json.dumps(value, ensure_ascii=False)}'

    repaired = re.sub(
        r'("(?:(?:excerpt)|(?:point)|(?:title)|(?:is Objective)|(?:info about Objective)|(?:completion of objective)|(?:type))"\s*:\s*)`([^`]*)`',
        backtick_value_to_json_string,
        raw_text,
        flags=re.S,
    )
    repaired = re.sub(r'(:\s*)None(\s*[,}])', r'\1null\2', repaired)
    attempts = [raw_text, repaired]
    stripped = str(repaired or "").rstrip()
    for extra_closers in range(1, 4):
        attempts.append(stripped + ("}" * extra_closers))

    last_error = None
    for attempt in attempts:
        try:
            parsed = json.loads(attempt)
            if isinstance(parsed, str):
                return _load_summary_json(parsed)
            if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], str):
                return _load_summary_json(parsed[0])
            return parsed
        except Exception as e:
            last_error = e
    raise last_error

def _parse_summary_fields(summary_text: str):
    bullet_points = []
    excerpts = []
    objective_id = ""
    objective_info = ""
    objective_completion = ""
    email_type = ""
    parsed = None
    try:
        parsed = _load_summary_json(summary_text or "")
    except Exception:
        json_raw = _extract_first_json_object(summary_text or "")
        if json_raw:
            try:
                parsed = _load_summary_json(json_raw)
            except Exception as e:
                print(f"Summary parse ERROR: {e}; raw={_summary_preview(summary_text)}")
    if parsed is not None:
        try:
            bullets = []
            if isinstance(parsed, dict):
                for key in ("bullets", "bullet_points", "bulletPoints", "summary_bullets", "points", "summaries"):
                    if isinstance(parsed.get(key), list):
                        bullets = parsed.get(key)
                        break
            for b in bullets:
                if isinstance(b, dict):
                    point = (
                        b.get("point")
                        or b.get("bullet")
                        or b.get("summary")
                        or b.get("text")
                        or b.get("content")
                        or ""
                    )
                    excerpt = (
                        b.get("excerpt")
                        or b.get("exact excerpt")
                        or b.get("exactExcerpt")
                        or b.get("evidence")
                        or b.get("evidence_quote")
                        or b.get("body_quote")
                        or b.get("source_quote")
                        or b.get("quote")
                        or b.get("exact")
                        or b.get("exact_quote")
                        or b.get("source")
                        or ""
                    )
                    point = str(point or "").strip()
                    excerpt = str(excerpt or "").strip()
                    if point or excerpt:
                        bullet_points.append(point)
                        excerpts.append(excerpt)
                elif str(b or "").strip():
                    bullet_points.append(str(b or "").strip())
                    excerpts.append("")
            if isinstance(parsed, dict):
                objective_id = str(parsed.get("is Objective", "") or parsed.get("objective_id", "") or "")
                objective_info = str(parsed.get("info about Objective", "") or parsed.get("objective_info", "") or "")
                completion_value = parsed.get("completion of objective", None)
                if completion_value is None:
                    completion_value = parsed.get("objective_completion", "")
                if isinstance(completion_value, (dict, list)):
                    objective_completion = json.dumps(completion_value, ensure_ascii=False)
                else:
                    objective_completion = str(completion_value or "")
                email_type = str(parsed.get("type", "") or parsed.get("email_type", "") or "")
        except Exception as e:
            print(f"Summary parse ERROR: {e}; raw={_summary_preview(summary_text)}")
    return {
        "bullet_points_json": json.dumps(bullet_points, ensure_ascii=False),
        "excerpts_json": json.dumps(excerpts, ensure_ascii=False),
        "bullet_count": len(bullet_points),
        "objective_id": objective_id,
        "objective_info": objective_info,
        "objective_completion": objective_completion,
        "type": email_type,
    }

def _summary_column_values(summary_text: str, email_text: str = "") -> tuple[list, list, dict]:
    fields = _parse_summary_fields(summary_text or "")
    try:
        bullet_points = json.loads(fields.get("bullet_points_json") or "[]")
    except Exception:
        bullet_points = []
    try:
        excerpts = json.loads(fields.get("excerpts_json") or "[]")
    except Exception:
        excerpts = []

    bullet_points = [str(item or "").strip() for item in bullet_points if str(item or "").strip()]
    excerpts = [str(item or "").strip() for item in excerpts]
    email_excerpt = _chunk_body_preview(email_text or "", max_chars=500)

    if not bullet_points:
        fallback = _summary_preview(summary_text, max_len=1200)
        if fallback:
            bullet_points = [fallback]
            excerpts = [email_excerpt]
            fields["bullet_points_json"] = json.dumps(bullet_points, ensure_ascii=False)
            fields["excerpts_json"] = json.dumps(excerpts, ensure_ascii=False)
            fields["bullet_count"] = len(bullet_points)

    if len(excerpts) < len(bullet_points):
        excerpts.extend([""] * (len(bullet_points) - len(excerpts)))
    elif len(excerpts) > len(bullet_points):
        excerpts = excerpts[:len(bullet_points)]
    excerpts = [
        email_excerpt if str(excerpt or "").strip().lower() in {"", "no exact excerpt", "none", "null"} and email_excerpt else str(excerpt or "").strip()
        for excerpt in excerpts
    ]

    return bullet_points, excerpts, fields

def _summary_preview(summary_text: str, max_len: int = 500) -> str:
    preview = " ".join(str(summary_text or "").split())
    if len(preview) > max_len:
        return preview[:max_len] + "..."
    return preview

def print_summary_bullets_or_error(user_email: str, subject: str, summary_text: str):
    label = f"[{user_email}] Summary for: {subject or '(No Subject)'}"
    json_raw = _extract_first_json_object(summary_text or "")
    if not json_raw:
        print(f"{label} ERROR: model did not return a JSON object")
        print(f"{label} raw output: {_summary_preview(summary_text)}")
        return

    try:
        parsed = _load_summary_json(json_raw)
    except Exception as e:
        print(f"{label} ERROR: could not parse JSON: {e}")
        print(f"{label} raw output: {_summary_preview(summary_text)}")
        return

    fields = _parse_summary_fields(summary_text or "")
    try:
        points = json.loads(fields.get("bullet_points_json") or "[]")
        excerpts = json.loads(fields.get("excerpts_json") or "[]")
    except Exception:
        points = []
        excerpts = []

    if not points:
        print(f"{label} ERROR: JSON did not include any summary bullets")
        print(f"{label} parsed output: {_summary_preview(json.dumps(parsed, ensure_ascii=False))}")
        return

    print(f"{label} bullet points:")
    for i, point in enumerate(points, 1):
        excerpt = excerpts[i - 1] if i - 1 < len(excerpts) else ""
        print(f"  {i}. {point or '(blank bullet)'}")
        if excerpt and excerpt.lower() != "no exact excerpt":
            print(f"     excerpt: {excerpt}")

def summary_payload_from_raw_chunk(raw_chunk: str) -> dict:
    fields = _parse_summary_fields(raw_chunk or "")
    try:
        points = json.loads(fields.get("bullet_points_json") or "[]")
    except Exception:
        points = []
    try:
        excerpts = json.loads(fields.get("excerpts_json") or "[]")
    except Exception:
        excerpts = []
    if not points:
        try:
            points = json.loads(_chunk_field(raw_chunk, "SummaryBulletPointsJSON") or "[]")
        except Exception:
            points = []
    if not excerpts:
        try:
            excerpts = json.loads(_chunk_field(raw_chunk, "SummaryExcerptsJSON") or "[]")
        except Exception:
            excerpts = []

    bullets = []
    for idx, point in enumerate(points):
        excerpt = excerpts[idx] if idx < len(excerpts) else ""
        bullets.append({
            "point": str(point or "").strip(),
            "excerpt": str(excerpt or "").strip(),
        })

    return {
        "id": _chunk_field(raw_chunk, "ID"),
        "subject": _chunk_field(raw_chunk, "Subject") or "(No Subject)",
        "sender": _chunk_field(raw_chunk, "From"),
        "time": _chunk_field(raw_chunk, "Time"),
        "objectiveId": fields.get("objective_id", ""),
        "objectiveInfo": fields.get("objective_info", ""),
        "objectiveCompletion": fields.get("objective_completion", ""),
        "bullets": bullets,
        "excerpts": [b["excerpt"] for b in bullets if b["excerpt"]],
    }

def _read_flag_from_chunk(chunk: str):
    lines = [l for l in chunk.strip().splitlines() if l.strip()]
    if not lines:
        return 0
    tail = lines[-1].strip()
    if tail == "1":
        return 1
    return 0

def _chunk_field(chunk: str, key: str):
    prefix = f"{key}:"
    for line in chunk.splitlines():
        if line.startswith(prefix):
            return line.replace(prefix, "", 1).strip()
    return ""

def _chunk_body_preview(chunk: str, max_chars: int = 260) -> str:
    body_lines = []
    capture = False
    for line in chunk.splitlines():
        clean = line.strip()
        if clean.startswith("Body:"):
            capture = True
            body_lines.append(clean.replace("Body:", "", 1).strip())
            continue
        if capture:
            if clean in {"0", "1"}:
                break
            body_lines.append(clean)

    preview = re.sub(r"\s+", " ", " ".join(body_lines)).strip()
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip() + "..."
    return preview

def _chunk_snippet_and_full_email(chunk: str):
    snippet = ""
    full_lines = []
    capture = False
    for line in chunk.splitlines():
        clean = line.strip()
        if clean.startswith("Snippet:"):
            snippet = clean.replace("Snippet:", "", 1).strip()
            capture = True
            full_lines.append(snippet)
            continue
        if capture:
            if clean in ("0", "1"):
                break
            full_lines.append(line)
    return snippet, "\n".join(full_lines).strip()

def saved_email_snippet(email_text: str, max_chars: int = 500) -> str:
    snippet = _chunk_field(email_text or "", "Snippet").strip()
    if not snippet:
        snippet = _chunk_body_preview(email_text or "", max_chars=max_chars)
    snippet = re.sub(r"\s+", " ", str(snippet or "")).strip()
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip()
    return snippet

def get_email_rows(user_email: str, descending: bool = False, limit: int | None = None):
    cache_key = (user_email, bool(descending), int(limit or 0))
    cached = _cache_get(_email_rows_cache, cache_key)
    if cached is not None:
        return cached

    order = "source_index.desc" if descending else "source_index.asc"
    query_params = {
        "select": "source_index,email_id,subject,sender,snippet,raw_chunk,is_read",
        "user_email": f"eq.{user_email}",
        "order": order,
    }
    if limit:
        query_params["limit"] = int(limit)
    rows = supabase_request(
        "GET",
        "emails",
        query_params=query_params,
    ) or []
    rows = rows if isinstance(rows, list) else []
    _cache_set(_email_rows_cache, cache_key, rows, CACHE_TTL_EMAIL_ROWS_SECONDS)
    return rows

def get_email_rows_by_message_id(user_email: str, message_id: str):
    clean_id = str(message_id or "").strip()
    if not user_email or not clean_id:
        return []
    cache_key = ("message_id", user_email, clean_id)
    cached = _cache_get(_email_rows_cache, cache_key)
    if cached is not None:
        return cached
    rows = supabase_request(
        "GET",
        "emails",
        query_params={
            "select": "source_index,email_id,subject,sender,snippet,raw_chunk,is_read",
            "user_email": f"eq.{user_email}",
            "email_id": f"eq.{clean_id}",
            "limit": 3,
        },
    ) or []
    rows = rows if isinstance(rows, list) else []
    _cache_set(_email_rows_cache, cache_key, rows, CACHE_TTL_EMAIL_ROWS_SECONDS)
    return rows

def supertest_norm(value: str) -> str:
    return " ".join(str(value or "").lower().split())

def supertest_row_fields(row: dict) -> dict:
    raw = str((row or {}).get("raw_chunk") or "")
    return {
        "raw": raw,
        "user_email": str((row or {}).get("user_email") or ""),
        "email_id": str((row or {}).get("email_id") or _chunk_field(raw, "ID") or "").strip(),
        "time": _chunk_field(raw, "Time"),
        "subject": _chunk_field(raw, "Subject") or "(No Subject)",
        "sender": _chunk_field(raw, "From") or "(Unknown sender)",
        "direction": _chunk_field(raw, "sent or received email") or "(Unknown direction)",
        "snippet": str((row or {}).get("snippet") or "").strip(),
        "body_preview": _chunk_body_preview(raw, max_chars=300) or "(No body preview)",
    }

def supertest_row_light_fields(row: dict) -> dict:
    raw = str((row or {}).get("raw_chunk") or "")
    return {
        "raw": raw,
        "user_email": str((row or {}).get("user_email") or ""),
        "email_id": str((row or {}).get("email_id") or _chunk_field(raw, "ID") or "").strip(),
        "time": _chunk_field(raw, "Time"),
        "subject": str((row or {}).get("subject") or "").strip() or _chunk_field(raw, "Subject") or "(No Subject)",
        "sender": str((row or {}).get("sender") or "").strip() or _chunk_field(raw, "From") or "(Unknown sender)",
        "direction": _chunk_field(raw, "sent or received email") or "(Unknown direction)",
        "snippet": str((row or {}).get("snippet") or "").strip(),
    }

def supertest_matches(row: dict, time_query: str, subject_query: str, snippet_query: str) -> bool:
    return supertest_matches_fields(supertest_row_fields(row), time_query, subject_query, snippet_query)

def supertest_matches_fields(fields: dict, time_query: str, subject_query: str, snippet_query: str) -> bool:
    if time_query and supertest_norm(time_query) not in supertest_norm(fields["time"]):
        return False

    if subject_query and supertest_norm(subject_query) not in supertest_norm(fields["subject"]):
        return False

    if snippet_query:
        query_norm = supertest_norm(snippet_query)
        saved_snippet_norm = supertest_norm(fields["snippet"])
        body_preview = fields.get("body_preview")
        if body_preview is None:
            body_preview = _chunk_body_preview(fields.get("raw", ""), max_chars=300) or "(No body preview)"
            fields["body_preview"] = body_preview
        haystack = supertest_norm(f"{fields['snippet']} {body_preview} {fields['raw']}")
        snippet_ok = bool(query_norm and query_norm in haystack)
        if not snippet_ok and saved_snippet_norm and query_norm:
            query_tokens = _email_match_tokens(query_norm)
            saved_tokens = _email_match_tokens(saved_snippet_norm)
            overlap = len(query_tokens & saved_tokens)
            snippet_ok = overlap >= max(3, min(8, len(query_tokens) // 3 if query_tokens else 3))
        if not snippet_ok:
            return False

    return True

def get_prepared_match_rows(user_email: str, descending: bool = True, limit: int | None = None):
    cache_key = (user_email, bool(descending), int(limit or 0))
    cached = _cache_get(_prepared_match_rows_cache, cache_key)
    if cached is not None:
        return cached
    rows = get_email_rows(user_email, descending=descending, limit=limit)
    prepared_rows = [
        (row, supertest_row_light_fields(row))
        for row in rows
        if str((row or {}).get("raw_chunk") or "").strip()
    ]
    _cache_set(_prepared_match_rows_cache, cache_key, prepared_rows, CACHE_TTL_SUMMARY_MATCH_SECONDS)
    return prepared_rows

def summary_match_cache_key(user_email: str, provider: str, message_id: str, subject: str, snippet: str, time_text: str):
    snippet_hash = hashlib.sha1(supertest_norm(snippet[:1200]).encode("utf-8", errors="ignore")).hexdigest()
    return (
        user_email,
        str(provider or "").strip().lower(),
        str(message_id or "").strip(),
        supertest_norm(subject),
        supertest_norm(time_text),
        snippet_hash,
    )

def repair_summary_columns_for_user(user_email: str) -> int:
    rows = supabase_request(
        "GET",
        "emails",
        query_params={
            "select": "source_index,email_id,raw_chunk",
            "user_email": f"eq.{user_email}",
            "order": "source_index.asc",
        },
    ) or []
    repaired = 0
    for row in rows if isinstance(rows, list) else []:
        raw_chunk = str((row or {}).get("raw_chunk") or "").strip()
        msg_id = str((row or {}).get("email_id") or _chunk_field(raw_chunk, "ID") or "").strip()
        if not raw_chunk or not msg_id:
            continue

        fields = _parse_summary_fields(raw_chunk)
        try:
            bullet_points = json.loads(fields.get("bullet_points_json") or "[]")
        except Exception:
            bullet_points = []
        try:
            excerpts = json.loads(fields.get("excerpts_json") or "[]")
        except Exception:
            excerpts = []
        if not bullet_points:
            continue
        if len(excerpts) < len(bullet_points):
            excerpts.extend([""] * (len(bullet_points) - len(excerpts)))
        email_excerpt = _chunk_body_preview(raw_chunk, max_chars=500)
        excerpts = [
            email_excerpt if str(excerpt or "").strip().lower() in {"", "no exact excerpt", "none", "null"} and email_excerpt else str(excerpt or "").strip()
            for excerpt in excerpts
        ]
        snippet = saved_email_snippet(raw_chunk)

        supabase_request(
            "PATCH",
            "emails",
            query_params={
                "user_email": f"eq.{user_email}",
                "email_id": f"eq.{msg_id}",
            },
            body={
                "bullet_points_json": bullet_points,
                "excerpts_json": excerpts[:len(bullet_points)],
                "bullet_count": len(bullet_points),
                "snippet": snippet,
            },
            prefer="return=minimal",
        )
        repaired += 1
    _invalidate_email_caches(user_email)
    return repaired

def embed_text(text: str):
    cache_key = hashlib.sha1((text or "").encode("utf-8", errors="ignore")).hexdigest()
    cached = _cache_get(_embedding_cache, cache_key)
    if cached is not None:
        return cached

    vector = [0.0] * 3072
    tokens = re.findall(r"[a-zA-Z0-9_@.\-]+", str(text or "").lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
        index = int.from_bytes(digest[:4], "big") % len(vector)
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = float(np.linalg.norm(np.array(vector, dtype="float32")))
    if norm > 0:
        vector = [value / norm for value in vector]
    _cache_set(_embedding_cache, cache_key, vector, CACHE_TTL_EMBEDDING_SECONDS)

    with _cache_lock:
        _embedding_cache_order.append(cache_key)
        while len(_embedding_cache_order) > EMBED_CACHE_MAX_ITEMS:
            oldest = _embedding_cache_order.pop(0)
            _embedding_cache.pop(oldest, None)

    return vector

def get_email_chunks_for_retrieval(user_email: str):
    rows = get_email_rows(user_email, descending=False)
    return [str(r["raw_chunk"] or "") for r in rows if str(r["raw_chunk"] or "").strip()]

def get_synced_index(user_email: str, chunks):
    index = faiss.IndexFlatL2(3072)
    for chunk in chunks:
        vector = np.array([embed_text(chunk)]).astype("float32")
        index.add(vector)
    return index

# =========================
# SUPABASE-ONLY STORAGE HELPERS
# =========================


def ensure_user_registered(user_email: str):
    email = str(user_email or "").strip()
    if not email:
        return
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    supabase_request(
        "POST",
        "users",
        query_params={"on_conflict": "email"},
        body=[{
            "email": email,
            "folder_path": "local",
            "migrated_at": now_iso,
        }],
        prefer="resolution=merge-duplicates,return=minimal",
    )


def save_user_credentials(user_email: str, creds: Credentials):
    email = str(user_email or "").strip()
    if not email or not creds:
        return

    token_json = creds.to_json()
    ensure_user_registered(email)
    now_iso = _safe_iso_now()
    supabase_request(
        "POST",
        "users",
        query_params={"on_conflict": "email"},
        body=[{
            "email": email,
            "folder_path": "local",
            "migrated_at": now_iso,
            "google_token_json": token_json,
            "google_token_updated_at": now_iso,
        }],
        prefer="resolution=merge-duplicates,return=minimal",
    )


def _credentials_from_json_text(token_json: str):
    text = str(token_json or "").strip()
    if not text:
        return None
    try:
        return Credentials.from_authorized_user_info(json.loads(text))
    except Exception:
        return None


def missing_google_scopes(creds: Credentials, required_scopes: list[str]) -> list[str]:
    if not creds:
        return list(required_scopes)
    try:
        if creds.has_scopes(required_scopes):
            return []
    except Exception:
        pass
    granted = set(getattr(creds, "scopes", None) or [])
    return [scope for scope in required_scopes if scope not in granted]












































def _normalize_email_match_text(value: str) -> str:
    text = html_lib.unescape(str(value or "")).lower()
    text = re.sub(r"^((re|fw|fwd):\s*)+", "", text)
    text = re.sub(r"[^a-z0-9@._+-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _email_match_tokens(value: str) -> set:
    stop_words = {
        "the", "and", "for", "you", "your", "that", "this", "with", "from", "have",
        "are", "was", "were", "will", "can", "all", "not", "but", "our", "has",
        "had", "they", "their", "there", "what", "when", "where", "about", "into",
        "please", "thanks", "thank", "hello", "hi", "gmail", "email",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", _normalize_email_match_text(value))
        if token not in stop_words
    }


def _extract_email_address(value: str) -> str:
    match = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", str(value or ""))
    return match.group(0).lower() if match else ""


def score_open_email_against_chunk(subject: str, sender: str, body_text: str, chunk: str) -> int:
    open_subject = _normalize_email_match_text(subject)
    chunk_subject = _normalize_email_match_text(_chunk_field(chunk, "Subject"))
    open_sender = _normalize_email_match_text(sender)
    chunk_sender = _normalize_email_match_text(_chunk_field(chunk, "From"))
    open_body = _normalize_email_match_text(body_text)
    chunk_text = _normalize_email_match_text(chunk)

    score = 0
    if open_subject and chunk_subject:
        if open_subject == chunk_subject:
            score += 30
        elif open_subject in chunk_subject or chunk_subject in open_subject:
            score += 12

    if open_sender and chunk_sender:
        open_email = _extract_email_address(open_sender) or open_sender
        chunk_email = _extract_email_address(chunk_sender) or chunk_sender
        if open_email and chunk_email and open_email == chunk_email:
            score += 20

    if open_body and chunk_text:
        body_sample = open_body[:700].strip()
        if len(body_sample) >= 80 and body_sample in chunk_text:
            score += 100
        else:
            open_tokens = _email_match_tokens(open_body)
            chunk_tokens = _email_match_tokens(chunk_text)
            if open_tokens and chunk_tokens:
                overlap = len(open_tokens & chunk_tokens)
                score += min(80, overlap * 4)

    return score






















# =========================
# GMAIL AUTH
# =========================

def get_google_client_redirect_uris() -> list[str]:
    try:
        with open(CLIENT_SECRET_FILE, "r", encoding="utf-8") as secret_file:
            client_config = json.load(secret_file)
        oauth_config = client_config.get("web") or client_config.get("installed") or {}
        return [str(uri or "").strip() for uri in oauth_config.get("redirect_uris", []) if str(uri or "").strip()]
    except Exception:
        return []


def get_oauth_redirect_uri() -> str:
    configured = str(os.getenv("GOOGLE_REDIRECT_URI", "")).strip()
    if configured:
        return configured

    google_url_root = request.url_root
    parsed_root = urllib.parse.urlparse(google_url_root)
    if parsed_root.hostname == "127.0.0.1":
        netloc = "localhost"
        if parsed_root.port:
            netloc = f"{netloc}:{parsed_root.port}"
        google_url_root = urllib.parse.urlunparse(parsed_root._replace(netloc=netloc))

    default_gmail = urllib.parse.urljoin(google_url_root, "gmail/callback")
    default_legacy = urllib.parse.urljoin(google_url_root, "callback")
    redirect_uris = get_google_client_redirect_uris()
    if default_gmail in redirect_uris:
        return default_gmail
    if default_legacy in redirect_uris:
        return default_legacy

    return default_gmail


# =========================
# MICROSOFT AUTH
# =========================

def get_microsoft_redirect_uri() -> str:
    configured = str(os.getenv("MICROSOFT_REDIRECT_URI", "")).strip()
    if configured:
        return configured
    return urllib.parse.urljoin(request.url_root, "callback")


def microsoft_secret_config_error():
    if not MICROSOFT_CLIENT_SECRET:
        return "Missing AZURE_CLIENT_SECRET environment variable."
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", MICROSOFT_CLIENT_SECRET):
        return "AZURE_CLIENT_SECRET looks like a Secret ID. Paste the secret Value from Azure instead."
    return None


def load_microsoft_token_cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(MICROSOFT_TOKEN_CACHE_FILE):
        with open(MICROSOFT_TOKEN_CACHE_FILE, "r", encoding="utf-8") as cache_file:
            cache.deserialize(decrypt_file_payload(cache_file.read()))
    return cache


def save_microsoft_token_cache(cache):
    if cache.has_state_changed:
        os.makedirs(os.path.dirname(MICROSOFT_TOKEN_CACHE_FILE), exist_ok=True)
        with open(MICROSOFT_TOKEN_CACHE_FILE, "w", encoding="utf-8") as cache_file:
            cache_file.write(encrypt_file_payload(cache.serialize()))


def build_microsoft_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        MICROSOFT_CLIENT_ID,
        authority=MICROSOFT_AUTHORITY,
        client_credential=MICROSOFT_CLIENT_SECRET,
        token_cache=cache,
    )


def microsoft_graph_get(token: str, url: str, params=None):
    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        params=params,
        timeout=30,
    )
    try:
        body = response.json()
    except ValueError:
        body = None
    return response, body


def microsoft_graph_send(method: str, token: str, url: str, body=None, params=None):
    response = requests.request(
        method,
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        params=params,
        json=body,
        timeout=30,
    )
    try:
        parsed = response.json() if response.text else None
    except ValueError:
        parsed = None
    return response, parsed


def get_microsoft_access_token(user_email: str):
    cache = load_microsoft_token_cache()
    msal_app = build_microsoft_msal_app(cache)
    requested = str(user_email or "").strip().lower()
    accounts = msal_app.get_accounts()
    account = None
    for candidate in accounts:
        username = str(candidate.get("username") or "").strip().lower()
        if username and (not requested or username == requested):
            account = candidate
            break

    if not account:
        raise Exception(f"No saved Microsoft account found for {user_email or 'current user'}. Sign in at /sign.")

    result = msal_app.acquire_token_silent(MICROSOFT_SCOPES, account=account)
    save_microsoft_token_cache(cache)
    if "access_token" not in (result or {}):
        raise Exception(f"Could not get Microsoft access token: {json.dumps(result or {}, indent=2)}")

    return result["access_token"]


def get_microsoft_cached_user_emails() -> list[str]:
    try:
        cache = load_microsoft_token_cache()
        msal_app = build_microsoft_msal_app(cache)
        out = []
        seen = set()
        for account in msal_app.get_accounts():
            email = str(account.get("username") or "").strip()
            if email and email.lower() not in seen:
                seen.add(email.lower())
                out.append(email)
        return out
    except Exception as e:
        print(f"[Microsoft] Could not read cached accounts: {e}")
        return []
















@app.route("/sing")
@app.route("/sign")
def sign_in():
    provider = str(request.args.get("provider") or request.args.get("mail") or "gmail").strip().lower()
    if provider in {"gmail", "google"}:
        return gmail_login()
    return microsoft_login()


@app.route("/microsoft/sign")
def microsoft_login():
    config_error = microsoft_secret_config_error()
    if config_error:
        return f"<pre>{html_lib.escape(config_error)}</pre>", 500

    redirect_uri = get_microsoft_redirect_uri()
    msal_app = build_microsoft_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        MICROSOFT_SCOPES,
        redirect_uri=redirect_uri,
        prompt="consent",
    )
    session["microsoft_redirect_uri"] = redirect_uri
    return redirect(auth_url)


@app.route("/callback")
@app.route("/microsoft/callback")
def microsoft_callback():
    try:
        callback_scope = str(request.args.get("scope") or "")
        looks_like_google_callback = bool(
            request.path == "/callback"
            and (
                "googleapis.com/auth" in callback_scope
                or (session.get("oauth_redirect_uri") and not session.get("microsoft_redirect_uri"))
            )
        )
        if looks_like_google_callback:
            return gmail_callback()

        if request.args.get("error"):
            error = {
                "error": request.args.get("error"),
                "error_description": request.args.get("error_description"),
                "error_uri": request.args.get("error_uri"),
                "trace_id": request.args.get("trace_id"),
                "correlation_id": request.args.get("correlation_id"),
                "all_callback_params": request.args.to_dict(flat=True),
                "expected_redirect_uri": get_microsoft_redirect_uri(),
                "authority": MICROSOFT_AUTHORITY,
                "client_id": MICROSOFT_CLIENT_ID,
            }
            return f"<pre>{html_lib.escape(json.dumps(error, indent=2))}</pre>", 400

        code = request.args.get("code")
        if not code:
            return "<pre>Missing Microsoft authorization code.</pre>", 400

        config_error = microsoft_secret_config_error()
        if config_error:
            return f"<pre>{html_lib.escape(config_error)}</pre>", 500

        redirect_uri = session.get("microsoft_redirect_uri") or get_microsoft_redirect_uri()
        cache = load_microsoft_token_cache()
        msal_app = build_microsoft_msal_app(cache)
        result = msal_app.acquire_token_by_authorization_code(
            code,
            scopes=MICROSOFT_SCOPES,
            redirect_uri=redirect_uri,
        )
        if "access_token" not in result:
            diagnostic = {
                "token_result": result,
                "redirect_uri_used": redirect_uri,
                "authority": MICROSOFT_AUTHORITY,
                "client_id": MICROSOFT_CLIENT_ID,
                "scopes": MICROSOFT_SCOPES,
            }
            return f"<pre>{html_lib.escape(json.dumps(diagnostic, indent=2))}</pre>", 400

        response, me = microsoft_graph_get(
            result["access_token"],
            "https://graph.microsoft.com/v1.0/me",
            params={"$select": "displayName,userPrincipalName,mail"},
        )
        if not response.ok:
            body_text = json.dumps(me, indent=2) if me is not None else response.text[:1000]
            return f"<pre>Microsoft Graph /me failed ({response.status_code})\n{html_lib.escape(body_text)}</pre>", 400

        email = str((me or {}).get("mail") or (me or {}).get("userPrincipalName") or "").strip()
        if not email:
            claims = result.get("id_token_claims") or {}
            email = str(claims.get("preferred_username") or claims.get("email") or "").strip()
        if not email:
            return "<pre>Microsoft account did not return an email address.</pre>", 400

        save_microsoft_token_cache(cache)
        session["user_email"] = email
        ensure_user_registered(email)
        return "Signed in with Microsoft. You can return to Outlook and use the Condra extension."
    except Exception as e:
        print("[microsoft_callback] error:", traceback.format_exc())
        return jsonify({
            "error": "microsoft_oauth_callback_failed",
            "message": str(e),
        }), 500


@app.route("/gmail/sign")
@app.route("/google/sign")
def gmail_login():
    redirect_uri = get_oauth_redirect_uri()
    configured_redirects = get_google_client_redirect_uris()
    if configured_redirects and redirect_uri not in configured_redirects:
        parsed_redirect = urllib.parse.urlparse(redirect_uri)
        legacy_redirect = urllib.parse.urlunparse(parsed_redirect._replace(path="/callback"))
        suggested = [
            redirect_uri,
            legacy_redirect,
        ]
        return f"""<pre>Google OAuth redirect URI mismatch.

The app is trying to use:
{html_lib.escape(redirect_uri)}

But client_secret.json only lists:
{html_lib.escape(json.dumps(configured_redirects, indent=2))}

Add one of these redirect URIs to your Google OAuth client, then re-download/update client_secret.json:
{html_lib.escape(json.dumps(suggested, indent=2))}

Or set GOOGLE_REDIRECT_URI to one of the already-allowed redirect URIs and run Flask on that same host/port.</pre>""", 500

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES + ["openid", "https://www.googleapis.com/auth/userinfo.email"],
        redirect_uri=redirect_uri
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true"
    )
    session["oauth_redirect_uri"] = redirect_uri
    session["oauth_code_verifier"] = getattr(flow, "code_verifier", None)
    return redirect(auth_url)


@app.route("/gmail/callback")
@app.route("/google/callback")
def gmail_callback():
    try:
        redirect_uri = session.get("oauth_redirect_uri") or get_oauth_redirect_uri()
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES + ["openid", "https://www.googleapis.com/auth/userinfo.email"],
            redirect_uri=redirect_uri
        )
        code_verifier = session.get("oauth_code_verifier")
        if code_verifier:
            flow.code_verifier = code_verifier
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials

        oauth2_service = build("oauth2", "v2", credentials=creds)
        user_info = oauth2_service.userinfo().get().execute()
        email = str(user_info.get("email") or "").strip()
        if not email:
            return "<pre>Google account did not return an email address.</pre>", 400

        session["user_email"] = email
        ensure_user_registered(email)
        save_user_credentials(email, creds)
        return "Signed in with Gmail. You can return to Gmail and use the Condra extension."
    except Exception as e:
        print("[gmail_callback] error:", traceback.format_exc())
        return jsonify({
            "error": "gmail_oauth_callback_failed",
            "message": str(e),
        }), 500


# =========================
# GMAIL SERVICE HELPERS
# =========================

def get_user_credentials(user_email: str):
    rows = supabase_request(
        "GET",
        "users",
        query_params={
            "select": "google_token_json",
            "email": f"eq.{user_email}",
            "limit": "1",
        },
    ) or []
    if isinstance(rows, list) and rows:
        creds = _credentials_from_json_text(rows[0].get("google_token_json", ""))
        if creds:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                save_user_credentials(user_email, creds)
            return creds

    raise Exception("No locally saved token found for user. Sign in again at /sign.")


def get_gmail_service_for_user(user_email: str):
    creds = get_user_credentials(user_email)
    return build("gmail", "v1", credentials=creds)


def get_docs_service_for_user(user_email: str):
    creds = get_user_credentials(user_email)
    return build("docs", "v1", credentials=creds)


def get_drive_service_for_user(user_email: str):
    creds = get_user_credentials(user_email)
    return build("drive", "v3", credentials=creds)


def get_supabase_user_emails() -> list[str]:
    if not supabase_enabled():
        return []
    rows = supabase_request(
        "GET",
        "users",
        query_params={
            "select": "email",
            "order": "email.asc",
        },
    ) or []
    if not isinstance(rows, list):
        return []
    return [
        str(row.get("email", "")).strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("email", "")).strip()
    ]


def candidate_user_emails(requested_user: str = "") -> list[str]:
    out = []
    requested = str(requested_user or "").strip()
    if requested:
        out.append(requested)
    try:
        out.extend(get_supabase_user_emails())
    except Exception as e:
        print(f"[users] Could not read local users: {e}")
    seen = set()
    unique = []
    for email in out:
        if email and email not in seen:
            seen.add(email)
            unique.append(email)
    return unique


def extension_candidate_user_emails(requested_user: str = "") -> list[str]:
    requested = str(requested_user or "").strip()
    if requested:
        return [requested]
    return []


def known_user_emails() -> list[str]:
    out = []
    out.extend(get_microsoft_cached_user_emails())
    try:
        out.extend(get_supabase_user_emails())
    except Exception as e:
        print(f"[users] Could not read local users: {e}")
    seen = set()
    unique = []
    for email in out:
        clean = str(email or "").strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            unique.append(clean)
    return unique


def resolve_strict_extension_user(requested_user: str):
    requested = str(requested_user or "").strip()
    if not requested or requested.lower() in {"outlook-local", "gmail-local", "local"}:
        return None
    try:
        for email in known_user_emails():
            if email.lower() == requested.lower():
                return email
    except Exception as e:
        print(f"[users] Could not resolve {requested}: {e}")
    return None


# =========================
# EMAIL PARSING HELPERS
# =========================

def _decode_part_data(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def _html_to_text(html_body: str) -> str:
    if not html_body:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_body)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|td|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_email_content(service, msg):
    payload = msg.get("payload", {})
    message_id = msg.get("id", "")

    plain_parts = []
    html_parts = []
    def walk(part):
        mime = (part.get("mimeType") or "").lower()
        body = part.get("body", {}) or {}

        data = body.get("data")
        attachment_id = body.get("attachmentId")
        part_bytes = b""
        if data:
            part_bytes = _decode_part_data(data)
        elif attachment_id:
            try:
                attachment = service.users().messages().attachments().get(
                    userId="me", messageId=message_id, id=attachment_id
                ).execute()
                raw = attachment.get("data")
                if raw:
                    part_bytes = _decode_part_data(raw)
            except Exception:
                part_bytes = b""

        if mime == "text/plain" and part_bytes:
            plain_parts.append(part_bytes.decode("utf-8", errors="ignore"))
        elif mime == "text/html" and part_bytes:
            html_parts.append(part_bytes.decode("utf-8", errors="ignore"))

        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)

    html_body = "\n\n".join([p for p in html_parts if p.strip()]).strip()
    plain_body = "\n\n".join([p for p in plain_parts if p.strip()]).strip()

    body_text = _html_to_text(html_body) if html_body else plain_body
    if not body_text:
        body_text = msg.get("snippet", "")

    return {
        "body_text": body_text,
        "html_body": html_body,
    }


def get_attachments(service, msg):
    attachments = []

    def walk_parts(parts):
        for part in parts:
            filename = part.get("filename")
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")
            headers = {h.get("name", "").lower(): h.get("value", "") for h in part.get("headers", [])}
            content_disposition = headers.get("content-disposition", "").lower()
            is_inline = "inline" in content_disposition
            if filename and attachment_id and not is_inline:
                attachment = service.users().messages().attachments().get(
                    userId="me", messageId=msg["id"], id=attachment_id
                ).execute()
                data = attachment.get("data")
                if data:
                    attachments.append({
                        "filename": filename,
                        "data": base64.urlsafe_b64decode(data)
                    })
            if "parts" in part:
                walk_parts(part["parts"])

    payload = msg.get("payload", {})
    if "parts" in payload:
        walk_parts(payload["parts"])
    return attachments


def process_attachments(attachments):
    results = []
    for att in attachments:
        filename = att.get("filename", "")
        file_data = att.get("data", b"")
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]:
                continue

            if ext in [".txt", ".csv", ".md", ".log"]:
                text = file_data.decode("utf-8", errors="ignore")
                results.append(f"[Text: {filename}]\n{text[:5000]}")

            elif ext == ".pdf":
                import io, PyPDF2
                text = ""
                reader = PyPDF2.PdfReader(io.BytesIO(file_data))
                for page in reader.pages:
                    text += page.extract_text() or ""
                results.append(f"[PDF: {filename}]\n{text[:5000]}")

            else:
                results.append(f"[Unsupported: {filename}]")

        except Exception as e:
            results.append(f"[Error processing {filename}: {e}]")

    return "\n\n".join(results)








def _build_objective_key(note: dict) -> str:
    topic = str(note.get("topic", "")).strip()
    expected_from = str(note.get("expected_from", "")).strip()
    ai_action = str(note.get("ai_action", "")).strip()
    text = str(note.get("text", "")).strip()
    created_at = str(note.get("created_at", "")).strip()
    seed = "\n".join([topic, expected_from, ai_action, text, created_at])
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


NOTE_LABEL_COLORS = [
    {"backgroundColor": "#16a766", "textColor": "#ffffff"},
    {"backgroundColor": "#4a86e8", "textColor": "#ffffff"},
    {"backgroundColor": "#ffad47", "textColor": "#000000"},
    {"backgroundColor": "#a479e2", "textColor": "#ffffff"},
    {"backgroundColor": "#f691b3", "textColor": "#000000"},
    {"backgroundColor": "#43d692", "textColor": "#000000"},
    {"backgroundColor": "#fad165", "textColor": "#000000"},
    {"backgroundColor": "#fb4c2f", "textColor": "#ffffff"},
]

OUTLOOK_CATEGORY_COLORS = [
    "preset0",
    "preset1",
    "preset2",
    "preset3",
    "preset4",
    "preset5",
    "preset6",
    "preset7",
    "preset8",
    "preset9",
    "preset10",
    "preset11",
    "preset12",
    "preset13",
    "preset14",
    "preset15",
    "preset16",
    "preset17",
    "preset18",
    "preset19",
    "preset20",
    "preset21",
    "preset22",
    "preset23",
    "preset24",
]


def note_gmail_label_number(note: dict, note_number: int = None) -> int:
    if note_number is not None:
        try:
            return max(1, int(note_number))
        except (TypeError, ValueError):
            return 1
    try:
        return max(1, int((note or {}).get("source_index", 0)) + 1)
    except (TypeError, ValueError):
        return 1


def note_gmail_label_name(note: dict, note_number: int = None) -> str:
    return f"Note {note_gmail_label_number(note, note_number)}"


def note_gmail_label_color(note: dict, note_number: int = None) -> dict:
    number = note_gmail_label_number(note, note_number)
    return NOTE_LABEL_COLORS[(number - 1) % len(NOTE_LABEL_COLORS)]


def note_outlook_category_name(note: dict, note_number: int = None) -> str:
    return note_gmail_label_name(note, note_number)


def note_outlook_category_color(note: dict, note_number: int = None) -> str:
    number = note_gmail_label_number(note, note_number)
    return OUTLOOK_CATEGORY_COLORS[(number - 1) % len(OUTLOOK_CATEGORY_COLORS)]


def is_microsoft_cached_user(user_email: str) -> bool:
    requested = str(user_email or "").strip().lower()
    if not requested:
        return False
    return requested in {email.lower() for email in get_microsoft_cached_user_emails()}


def legacy_note_gmail_label_name(note: dict) -> str:
    base = _note_label_base(note)
    objective_key = str((note or {}).get("objective_key", "")).strip() or _build_objective_key(note or {})
    return f"Condra Notes/{base or 'Untitled Note'} [{objective_key}]"


def get_label_id(service, label_name: str):
    result = service.users().labels().list(userId="me").execute()
    labels = result.get("labels", [])

    for label in labels:
        if label.get("name") == label_name:
            return label.get("id")

    return None


def get_gmail_labels(service) -> list:
    result = service.users().labels().list(userId="me").execute()
    return result.get("labels", [])


def get_gmail_label_by_name(service, label_name: str):
    clean_name = str(label_name or "").strip()
    if not clean_name:
        return None
    for label in get_gmail_labels(service):
        if str(label.get("name") or "").strip() == clean_name:
            return label
    return None


def get_label_from_list_by_id(labels: list, label_id: str):
    clean_id = str(label_id or "").strip()
    if not clean_id:
        return None
    for label in labels or []:
        if str(label.get("id") or "").strip() == clean_id:
            return label
    return None


def get_existing_note_gmail_label(service, note: dict):
    note = note or {}
    recorded_label_id = str(note.get("gmail_label_id") or "").strip()
    labels = get_gmail_labels(service)
    by_id = get_label_from_list_by_id(labels, recorded_label_id)
    if by_id:
        return by_id

    candidates = [
        str(note.get("gmail_label_name") or "").strip(),
        note_gmail_label_name(note),
        legacy_note_gmail_label_name(note),
    ]
    for candidate in candidates:
        label = next((item for item in labels if str(item.get("name") or "").strip() == candidate), None)
        if label:
            return label

    base_prefix = f"Condra Notes/{_note_label_base(note)} ["
    matches = []
    for label in labels:
        name = str(label.get("name") or "").strip()
        if name.startswith(base_prefix):
            matches.append(label)
    if not matches:
        return None
    matches.sort(key=lambda item: str(item.get("name") or ""))
    return matches[0]


def get_gmail_label_names(service) -> set:
    return set(str(label.get("name", "")).strip() for label in get_gmail_labels(service) if label.get("name"))


def gmail_note_label_exists(label_names: set, note: dict) -> bool:
    recorded_label_name = str((note or {}).get("gmail_label_name") or "").strip()
    generated_label_name = note_gmail_label_name(note)
    legacy_label_name = legacy_note_gmail_label_name(note)
    if recorded_label_name and recorded_label_name in label_names:
        return True
    if generated_label_name in label_names:
        return True
    if legacy_label_name in label_names:
        return True

    # Fallback for older notes whose saved objective_key/metadata may not match the
    # label that was actually created. Gmail labels are displayed by this prefix.
    base_prefix = f"Condra Notes/{_note_label_base(note)} ["
    return any(name.startswith(base_prefix) for name in label_names)


def gmail_note_label_name_for_sync(label_names: set, note: dict) -> str:
    recorded_label_name = str((note or {}).get("gmail_label_name") or "").strip()
    generated_label_name = note_gmail_label_name(note)
    legacy_label_name = legacy_note_gmail_label_name(note)
    if recorded_label_name and recorded_label_name in label_names:
        return recorded_label_name
    if generated_label_name in label_names:
        return generated_label_name
    if legacy_label_name in label_names:
        return legacy_label_name

    base_prefix = f"Condra Notes/{_note_label_base(note)} ["
    for name in sorted(label_names):
        if name.startswith(base_prefix):
            return name
    return recorded_label_name or generated_label_name


def gmail_note_label_for_sync(labels: list, label_names: set, note: dict):
    recorded_label_id = str((note or {}).get("gmail_label_id") or "").strip()
    if recorded_label_id:
        return get_label_from_list_by_id(labels, recorded_label_id)

    label_name = gmail_note_label_name_for_sync(label_names, note)
    if not label_name:
        return None
    for label in labels or []:
        if str(label.get("name") or "").strip() == label_name:
            return label
    return None


def _note_label_base(note: dict) -> str:
    topic = str((note or {}).get("topic", "")).strip()
    text = str((note or {}).get("text", "")).strip()
    base = topic or text or "Untitled Note"
    base = re.sub(r"\s+", " ", base)
    base = re.sub(r"[\r\n\t/\\]+", " ", base).strip()
    if len(base) > 54:
        base = base[:54].rstrip()
    return base or "Untitled Note"


def create_gmail_label(service, label_name: str, color: dict = None):
    existing_label_id = get_label_id(service, label_name)

    if existing_label_id:
        if color:
            patch_gmail_label(service, existing_label_id, label_name, color)
        return {
            "status": "exists",
            "label_id": existing_label_id,
            "label_name": label_name,
        }

    body = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    if color:
        body["color"] = color

    label = service.users().labels().create(
        userId="me",
        body=body,
    ).execute()

    return {
        "status": "created",
        "label_id": label.get("id"),
        "label_name": label.get("name"),
    }


def patch_gmail_label(service, label_id: str, label_name: str, color: dict = None):
    clean_id = str(label_id or "").strip()
    clean_name = str(label_name or "").strip()
    if not clean_id or not clean_name:
        return None

    body = {
        "name": clean_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    if color:
        body["color"] = color

    label = service.users().labels().patch(
        userId="me",
        id=clean_id,
        body=body,
    ).execute()

    return {
        "status": "updated",
        "label_id": label.get("id"),
        "label_name": label.get("name"),
    }


def delete_gmail_label(service, label_name: str):
    label_id = get_label_id(service, label_name)

    if not label_id:
        return {
            "status": "not_found",
            "label_name": label_name,
        }

    service.users().labels().delete(
        userId="me",
        id=label_id,
    ).execute()

    return {
        "status": "deleted",
        "label_name": label_name,
    }


def delete_gmail_label_by_id(service, label_id: str, label_name: str = ""):
    clean_id = str(label_id or "").strip()
    if not clean_id:
        return None

    service.users().labels().delete(
        userId="me",
        id=clean_id,
    ).execute()

    return {
        "status": "deleted",
        "label_id": clean_id,
        "label_name": label_name,
    }


def add_email_to_note_gmail_label(service, message_id: str, note: dict):
    label = get_existing_note_gmail_label(service, note)
    if not label:
        label_name = str((note or {}).get("gmail_label_name") or "").strip() or note_gmail_label_name(note)
        created = create_gmail_label(service, label_name, note_gmail_label_color(note))
        label = {
            "id": created.get("label_id"),
            "name": created.get("label_name"),
        }

    label_id = str(label.get("id") or "").strip()
    label_name = str(label.get("name") or "").strip()
    if not label_id:
        raise Exception(f"Could not resolve Gmail label for note: {label_name or note_gmail_label_name(note)}")

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": [label_id],
        },
    ).execute()

    return {
        "status": "added",
        "message_id": message_id,
        "label_name": label_name,
        "label_id": label_id,
    }


def get_outlook_categories(user_email: str) -> list:
    token = get_microsoft_access_token(user_email)
    response, body = microsoft_graph_get(
        token,
        "https://graph.microsoft.com/v1.0/me/outlook/masterCategories",
    )
    if not response.ok:
        body_text = json.dumps(body, indent=2) if body is not None else response.text[:1000]
        raise Exception(f"Microsoft Graph categories failed ({response.status_code}): {body_text}")
    return (body or {}).get("value") or []


def get_outlook_category_by_name(user_email: str, category_name: str):
    clean_name = str(category_name or "").strip()
    if not clean_name:
        return None
    for category in get_outlook_categories(user_email):
        if str(category.get("displayName") or "").strip() == clean_name:
            return category
    return None


def ensure_note_outlook_category(user_email: str, note: dict, note_number: int = None):
    note = dict(note or {})
    if note_number is not None:
        note["source_index"] = max(0, int(note_number) - 1)

    category_name = note_outlook_category_name(note, note_number)
    category_color = note_outlook_category_color(note, note_number)
    existing = get_outlook_category_by_name(user_email, category_name)
    if existing:
        return {
            "status": "exists",
            "label_id": str(existing.get("id") or existing.get("displayName") or category_name),
            "label_name": category_name,
            "provider": "outlook",
            "color": str(existing.get("color") or category_color),
        }

    token = get_microsoft_access_token(user_email)
    response, body = microsoft_graph_send(
        "POST",
        token,
        "https://graph.microsoft.com/v1.0/me/outlook/masterCategories",
        body={
            "displayName": category_name,
            "color": category_color,
        },
    )
    if not response.ok:
        body_text = json.dumps(body, indent=2) if body is not None else response.text[:1000]
        raise Exception(f"Microsoft Graph create category failed ({response.status_code}): {body_text}")

    return {
        "status": "created",
        "label_id": str((body or {}).get("id") or (body or {}).get("displayName") or category_name),
        "label_name": str((body or {}).get("displayName") or category_name),
        "provider": "outlook",
        "color": str((body or {}).get("color") or category_color),
    }


def add_email_to_note_outlook_category(user_email: str, message_id: str, note: dict):
    clean_message_id = str(message_id or "").strip()
    if not clean_message_id:
        return None

    category = ensure_note_outlook_category(user_email, note)
    category_name = str(category.get("label_name") or note_outlook_category_name(note)).strip()
    token = get_microsoft_access_token(user_email)
    encoded_message_id = urllib.parse.quote(clean_message_id, safe="")

    response, message = microsoft_graph_get(
        token,
        f"https://graph.microsoft.com/v1.0/me/messages/{encoded_message_id}",
        params={"$select": "id,categories"},
    )
    if not response.ok:
        body_text = json.dumps(message, indent=2) if message is not None else response.text[:1000]
        raise Exception(f"Microsoft Graph get message failed ({response.status_code}): {body_text}")

    categories = [str(item or "").strip() for item in (message or {}).get("categories", []) if str(item or "").strip()]
    if category_name not in categories:
        categories.append(category_name)
        response, body = microsoft_graph_send(
            "PATCH",
            token,
            f"https://graph.microsoft.com/v1.0/me/messages/{encoded_message_id}",
            body={"categories": categories},
        )
        if not response.ok:
            body_text = json.dumps(body, indent=2) if body is not None else response.text[:1000]
            raise Exception(f"Microsoft Graph apply category failed ({response.status_code}): {body_text}")

    return {
        "status": "added",
        "message_id": clean_message_id,
        "label_name": category_name,
        "label_id": category.get("label_id") or category_name,
        "provider": "outlook",
    }


def create_note_outlook_category(user_email: str, note: dict):
    return ensure_note_outlook_category(user_email, note)


def renumber_note_outlook_categories(user_email: str, notes: list) -> list:
    renumbered = []
    for idx, note in enumerate(notes or []):
        row = dict(note or {})
        row["source_index"] = idx
        label_result = ensure_note_outlook_category(user_email, row, idx + 1)
        renumbered.append(attach_gmail_label_to_note(row, label_result))
    return renumbered


def delete_note_outlook_category(user_email: str, note: dict):
    category_name = str((note or {}).get("gmail_label_name") or note_outlook_category_name(note)).strip()
    category = get_outlook_category_by_name(user_email, category_name)
    if not category:
        return {
            "status": "not_found",
            "label_name": category_name,
            "provider": "outlook",
        }

    category_id = str(category.get("id") or category.get("displayName") or category_name).strip()
    token = get_microsoft_access_token(user_email)
    response, body = microsoft_graph_send(
        "DELETE",
        token,
        f"https://graph.microsoft.com/v1.0/me/outlook/masterCategories/{urllib.parse.quote(category_id, safe='')}",
    )
    if not response.ok:
        body_text = json.dumps(body, indent=2) if body is not None else response.text[:1000]
        raise Exception(f"Microsoft Graph delete category failed ({response.status_code}): {body_text}")

    return {
        "status": "deleted",
        "label_id": category_id,
        "label_name": category_name,
        "provider": "outlook",
    }


def ensure_note_gmail_label(service, note: dict, note_number: int = None):
    note = dict(note or {})
    if note_number is not None:
        note["source_index"] = max(0, int(note_number) - 1)

    target_name = note_gmail_label_name(note, note_number)
    target_color = note_gmail_label_color(note, note_number)
    label = get_existing_note_gmail_label(service, note)
    if label:
        label_id = str(label.get("id") or "").strip()
        label_name = str(label.get("name") or "").strip()
        label_color = label.get("color") or {}
        if label_id and (label_name != target_name or label_color != target_color):
            try:
                return patch_gmail_label(service, label_id, target_name, target_color)
            except Exception as e:
                print(f"Gmail label rename/color update failed for {label_name!r}: {e}")
        return {
            "status": "exists",
            "label_id": label_id,
            "label_name": label_name,
        }

    return create_gmail_label(service, target_name, target_color)


def find_note_by_objective_key(user_email: str, objective_key: str):
    key = str(objective_key or "").strip()
    if not key or key.lower() == "none":
        return None
    for note in _attach_objective_keys(read_notes(user_email)):
        if str(note.get("objective_key", "")).strip() == key:
            return note
    return None


def add_objective_email_to_note_label(user_email: str, objective_key: str, message_id: str):
    note = find_note_by_objective_key(user_email, objective_key)
    if not note:
        return None
    if is_microsoft_cached_user(user_email):
        return add_email_to_note_outlook_category(user_email, message_id, note)
    service = get_gmail_service_for_user(user_email)
    return add_email_to_note_gmail_label(service, message_id, note)


def add_existing_objective_emails_to_note_label(user_email: str, note: dict) -> int:
    note_with_key = dict(note or {})
    note_with_key.setdefault("objective_key", _build_objective_key(note_with_key))
    objective_key = str(note_with_key.get("objective_key") or "").strip()
    if not objective_key:
        return 0

    rows = supabase_request(
        "GET",
        "emails",
        query_params={
            "select": "email_id",
            "user_email": f"eq.{user_email}",
            "objective_id": f"eq.{objective_key}",
        },
    ) or []
    message_ids = [str(row.get("email_id") or "").strip() for row in rows if isinstance(row, dict)]

    added = 0
    for message_id in message_ids:
        if not message_id:
            continue
        if is_microsoft_cached_user(user_email):
            add_email_to_note_outlook_category(user_email, message_id, note_with_key)
        else:
            service = get_gmail_service_for_user(user_email)
            add_email_to_note_gmail_label(service, message_id, note_with_key)
        added += 1
    return added


def backfill_objective_emails_to_note_labels(user_email: str) -> int:
    total = 0
    for note in _attach_objective_keys(read_notes(user_email)):
        try:
            total += add_existing_objective_emails_to_note_label(user_email, note)
        except Exception as e:
            print(f"[{user_email}] Objective email label backfill skipped for note: {e}")
    return total


def create_note_gmail_label(user_email: str, note: dict):
    if is_microsoft_cached_user(user_email):
        return create_note_outlook_category(user_email, note)
    service = get_gmail_service_for_user(user_email)
    return ensure_note_gmail_label(service, note)


def attach_gmail_label_to_note(note: dict, label_result: dict) -> dict:
    out = dict(note or {})
    label_name = str((label_result or {}).get("label_name") or note_gmail_label_name(out)).strip()
    label_id = str((label_result or {}).get("label_id") or "").strip()
    if label_name:
        out["gmail_label_name"] = label_name
    if label_id:
        out["gmail_label_id"] = label_id
    out["gmail_label_synced_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    return out


def renumber_note_gmail_labels(user_email: str, notes: list) -> list:
    if is_microsoft_cached_user(user_email):
        return renumber_note_outlook_categories(user_email, notes)
    service = get_gmail_service_for_user(user_email)
    renumbered = []
    for idx, note in enumerate(notes or []):
        row = dict(note or {})
        row["source_index"] = idx
        label_result = ensure_note_gmail_label(service, row, idx + 1)
        renumbered.append(attach_gmail_label_to_note(row, label_result))
    return renumbered


def delete_note_gmail_label(user_email: str, note: dict):
    if is_microsoft_cached_user(user_email):
        return delete_note_outlook_category(user_email, note)
    service = get_gmail_service_for_user(user_email)
    note = note or {}
    label_id = str(note.get("gmail_label_id") or "").strip()
    label_name = str(note.get("gmail_label_name") or "").strip() or note_gmail_label_name(note)

    if label_id:
        try:
            result = delete_gmail_label_by_id(service, label_id, label_name)
            if result:
                return result
        except Exception as e:
            print(f"[{user_email}] Gmail label delete by id failed ({label_id}), trying by name: {e}")

    result = delete_gmail_label(service, label_name)
    if result.get("status") == "deleted":
        return result

    labels = get_gmail_labels(service)
    possible_names = {label_name, note_gmail_label_name(note), legacy_note_gmail_label_name(note)}
    base_prefix = f"Condra Notes/{_note_label_base(note)} ["
    matching_labels = []
    for label in labels:
        name = str(label.get("name") or "").strip()
        if name in possible_names or name.startswith(base_prefix):
            matching_labels.append(label)

    deleted = []
    for label in matching_labels:
        lid = str(label.get("id") or "").strip()
        name = str(label.get("name") or "").strip()
        if not lid:
            continue
        service.users().labels().delete(userId="me", id=lid).execute()
        deleted.append({"label_id": lid, "label_name": name})

    if deleted:
        return {
            "status": "deleted",
            "label_name": label_name,
            "deleted_labels": deleted,
        }

    return result


def sync_notes_with_gmail_labels(user_email: str, include_debug: bool = False):
    if is_microsoft_cached_user(user_email):
        notes = _attach_objective_keys(read_notes(user_email))
        synced_notes = []
        debug_rows = []
        changed = False
        for idx, note in enumerate(notes):
            row = dict(note or {})
            row["source_index"] = idx
            label_result = ensure_note_outlook_category(user_email, row, idx + 1)
            synced = attach_gmail_label_to_note(row, label_result)
            if (
                synced.get("gmail_label_name") != row.get("gmail_label_name")
                or synced.get("gmail_label_id") != row.get("gmail_label_id")
            ):
                changed = True
            synced_notes.append(synced)
            debug_rows.append({
                "topic": str(row.get("topic") or ""),
                "expected_label_name": note_outlook_category_name(row, idx + 1),
                "matched_label_id": label_result.get("label_id", ""),
                "matched_label_name": label_result.get("label_name", ""),
                "exists_in_outlook": label_result.get("status") in {"exists", "created"},
            })
        if changed:
            write_notes(user_email, synced_notes)
        if include_debug:
            return {
                "notes": synced_notes,
                "debug": debug_rows,
                "outlook_categories": [str(item.get("displayName") or "") for item in get_outlook_categories(user_email)],
                "removed_labels": [],
            }
        return synced_notes

    notes = _attach_objective_keys(read_notes(user_email))
    if not notes:
        return {"notes": [], "debug": []} if include_debug else []

    service = get_gmail_service_for_user(user_email)
    labels = get_gmail_labels(service)
    label_names = set(str(label.get("name", "")).strip() for label in labels if label.get("name"))
    synced_notes = []
    removed_labels = []
    debug_rows = []
    changed = False

    for idx, note in enumerate(notes):
        note = dict(note)
        note["source_index"] = idx
        recorded_label_id = str(note.get("gmail_label_id") or "").strip()
        recorded_label_name = str(note.get("gmail_label_name") or "").strip()
        matched_label = gmail_note_label_for_sync(labels, label_names, note)
        label_name = str((matched_label or {}).get("name") or gmail_note_label_name_for_sync(label_names, note)).strip()
        label_id = str((matched_label or {}).get("id") or "").strip()
        exists = bool(matched_label)
        debug_rows.append({
            "topic": str(note.get("topic") or ""),
            "recorded_label_id": recorded_label_id,
            "recorded_label_name": recorded_label_name,
            "expected_label_name": note_gmail_label_name(note),
            "matched_label_id": label_id,
            "matched_label_name": label_name,
            "exists_in_gmail": bool(exists),
        })
        if exists:
            label_result = ensure_note_gmail_label(service, note, idx + 1)
            synced_label_name = str((label_result or {}).get("label_name") or label_name).strip()
            synced_label_id = str((label_result or {}).get("label_id") or note.get("gmail_label_id") or "").strip()
            if (
                not recorded_label_name
                or recorded_label_name != synced_label_name
                or str(note.get("gmail_label_id") or "").strip() != synced_label_id
            ):
                note["gmail_label_name"] = synced_label_name
                note["gmail_label_id"] = synced_label_id
                note["gmail_label_synced_at"] = datetime.datetime.now().isoformat(timespec="seconds")
                changed = True
            synced_notes.append(note)
        else:
            removed_labels.append(label_name)
            changed = True

    if changed:
        if synced_notes:
            try:
                synced_notes = renumber_note_gmail_labels(user_email, synced_notes)
            except Exception as e:
                print(f"[{user_email}] Gmail note label renumber skipped: {e}")
        write_notes(user_email, synced_notes)
        print(f"[{user_email}] Removed {len(removed_labels)} note(s) because their Gmail labels were deleted.")

    if include_debug:
        return {
            "notes": synced_notes,
            "debug": debug_rows,
            "gmail_condra_labels": sorted([name for name in label_names if name.startswith("Condra Notes/") or re.match(r"^Note \d+$", name)]),
            "removed_labels": removed_labels,
        }
    return synced_notes


def _attach_objective_keys(notes: list) -> list:
    out = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        row = dict(note)
        if not row.get("objective_key"):
            row["objective_key"] = _build_objective_key(row)
        out.append(row)
    return out


def get_numbered_notes(user_email: str):
    notes = _attach_objective_keys(read_notes(user_email))
    lines = []
    for i, note in enumerate(notes):
        topic = str(note.get("topic", "")).strip()
        expected_from = str(note.get("expected_from", "")).strip()
        ai_action = str(note.get("ai_action", "")).strip()
        text = str(note.get("text", "")).strip()
        objective_key = str(note.get("objective_key", "")).strip()
        key_prefix = f"[OBJECTIVE_KEY:{objective_key}] " if objective_key else ""
        if topic or expected_from or ai_action:
            lines.append(
                f"{i + 1}. {key_prefix}Topic: {topic or 'None'} | Expected From: {expected_from or 'None'} | AI Action: {ai_action or 'None'}"
            )
        elif text:
            lines.append(f"{i + 1}. {key_prefix}{text}")
    return lines


# =========================
# BACKGROUND EMAIL CHECKER (no session — uses user_email arg throughout)
# =========================



# =========================
# ROUTES
# =========================

@app.route("/extension/summaries")
def get_extension_summaries():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    requested_user = (request.args.get("user_email") or "").strip()
    user = require_extension_user(requested_user)
    if not isinstance(user, str):
        return user
    rows = get_email_rows(user, descending=True)
    if rows:
        return "\n---\n".join([str(r["raw_chunk"] or "") for r in rows if str(r["raw_chunk"] or "").strip()])

    return ""


@app.route("/load_microsoft_emails")
def load_microsoft_emails_route():
    signed_in_user = str(session.get("user_email") or "").strip()
    requested_user = str(request.args.get("user_email") or signed_in_user or "").strip()
    if not signed_in_user:
        return jsonify({
            "status": "error",
            "message": "Sign in at /sign first.",
        }), 401
    if requested_user and not _same_email(requested_user, signed_in_user):
        return jsonify({
            "error": "user_mismatch",
            "message": "The requested mailbox does not match the signed-in account.",
            "requested_user": requested_user,
            "signed_in_user": signed_in_user,
        }), 403

    ensure_user_registered(signed_in_user)
    return jsonify({
        "status": "save_worker_required",
        "user_email": signed_in_user,
        "loaded": 0,
        "message": "Email saving now runs independently. Start it with: python3 saveApp.py --user " + signed_in_user,
    }), 409


@app.route("/extension/print_recent_emails")
def extension_print_recent_emails():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    requested_user = str(request.args.get("user_email") or "").strip()
    limit = 3
    user = require_extension_user(requested_user)
    if not isinstance(user, str):
        return user

    emails = []
    for row in get_email_rows(user, descending=True):
        raw_chunk = str((row or {}).get("raw_chunk") or "").strip()
        if not raw_chunk:
            continue
        direction = _chunk_field(raw_chunk, "sent or received email").upper()
        if direction and direction != "RECEIVED":
            continue
        emails.append({
            "id": str((row or {}).get("email_id") or _chunk_field(raw_chunk, "ID") or ""),
            "time": _chunk_field(raw_chunk, "Time"),
            "from": _chunk_field(raw_chunk, "From"),
            "subject": _chunk_field(raw_chunk, "Subject") or "(No Subject)",
            "body_preview": _chunk_body_preview(raw_chunk),
        })
        if len(emails) >= limit:
            break

    print(f"\n[{user}] Last {len(emails)} received email(s) from local storage:")
    if not emails:
        print("  No received emails found.")
    for idx, email in enumerate(emails, start=1):
        print(f"  {idx}. Subject: {email['subject']}")
        print(f"     From: {email['from'] or 'Unknown sender'}")
        print(f"     Time: {email['time'] or 'Unknown time'}")
        print(f"     ID: {email['id'] or 'Unknown id'}")
        print(f"     Body: {email['body_preview'] or '(No body preview)'}")

    return jsonify({"status": "printed", "user_email": user, "count": len(emails)})


@app.route("/extension/repair_summary_backups")
def extension_repair_summary_backups():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    requested_user = str(request.args.get("user_email") or "").strip()
    user = require_extension_user(requested_user)
    if not isinstance(user, str):
        return user
    repaired_total = repair_summary_columns_for_user(user)
    repaired_users = [{"user_email": user, "repaired": repaired_total}]

    return jsonify({
        "status": "ok",
        "repaired": repaired_total,
        "users": repaired_users,
    })


@app.route("/extension/match_summary", methods=["POST"])
def extension_match_summary():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    started_at = time.monotonic()
    data = request.get_json(silent=True) or {}
    requested_user = str(data.get("user_email") or "").strip()
    subject = str(data.get("subject") or "").strip()
    snippet = str(data.get("snippet") or data.get("body_text") or "").strip()
    authorized_user = require_extension_user(requested_user)
    if not isinstance(authorized_user, str):
        return authorized_user

    if not subject and not snippet:
        return jsonify({"found": False, "raw_chunk": "", "score": 0, "user_email": authorized_user})

    match_cache_key = summary_match_cache_key(
        authorized_user,
        "",
        "",
        subject,
        snippet,
        "",
    )
    cached_match = _cache_get(_summary_match_cache, match_cache_key)
    if cached_match is not None:
        cached_match["cached"] = True
        cached_match["elapsed_ms"] = int((time.monotonic() - started_at) * 1000)
        return jsonify(cached_match)

    users = [authorized_user]
    search_passes = [("subject+snippet", subject, snippet, "")]

    try:
        for user in users:
            matched_by = ""
            matches = []
            prepared_rows = get_prepared_match_rows(user, descending=True, limit=EXTENSION_MATCH_ROW_LIMIT)
            for pass_name, pass_subject, pass_snippet, pass_time in search_passes:
                if matches:
                    break
                if not pass_subject and not pass_snippet and not pass_time:
                    continue
                pass_matches = []
                for row, fields in prepared_rows:
                    if supertest_matches_fields(fields, pass_time, pass_subject, pass_snippet):
                        pass_matches.append(row)
                if pass_matches:
                    matched_by = pass_name
                    matches = pass_matches
                    break

            if matches:
                best_row = matches[0]
                raw_chunk = str((best_row or {}).get("raw_chunk") or "").strip()
                elapsed_ms = int((time.monotonic() - started_at) * 1000)
                print(
                    f"[{user}] match_summary found {len(matches)} match(es) by {matched_by} "
                    f"in {elapsed_ms}ms subject={subject[:80]!r} snippet={snippet[:80]!r}"
                )
                response_payload = {
                    "elapsed_ms": elapsed_ms,
                    "found": True,
                    "raw_chunk": raw_chunk,
                    "summary": summary_payload_from_raw_chunk(raw_chunk),
                    "match_count": len(matches),
                    "matched_by": matched_by,
                    "email_id": str((best_row or {}).get("email_id") or _chunk_field(raw_chunk, "ID") or ""),
                    "user_email": user,
                }
                _cache_set(_summary_match_cache, match_cache_key, response_payload, CACHE_TTL_SUMMARY_MATCH_SECONDS)
                return jsonify(response_payload)

            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            print(
                f"[{user}] match_summary no match in {elapsed_ms}ms "
                f"subject={subject[:80]!r} snippet={snippet[:80]!r}"
            )
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "found": False,
            "raw_chunk": "",
            "match_count": 0,
            "user_email": requested_user,
            "error": "match_summary_failed",
            "message": str(e),
        }), 500

    response_payload = {"found": False, "raw_chunk": "", "match_count": 0, "user_email": authorized_user}
    _cache_set(_summary_match_cache, match_cache_key, response_payload, CACHE_TTL_SUMMARY_MATCH_SECONDS)
    return jsonify(response_payload)


@app.route("/extension/ask", methods=["POST"])
def extension_ask_ai():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    requested_user = ""
    user = ""
    try:
        data = request.get_json(silent=True) or {}
        requested_user = str(data.get("user_email") or "").strip()
        question = str(data.get("question") or "").strip()
        context_mode = str(data.get("context_mode") or "").strip().lower()
        use_email_context = bool(data.get("use_email_context", True))
        current_email = data.get("current_email") if isinstance(data.get("current_email"), dict) else {}
        if not question:
            return jsonify({"error": "missing_question", "message": "Ask command needs a question."}), 400

        current_email_user = str(current_email.get("user_email") or current_email.get("userEmail") or "").strip()
        if context_mode in {"current_email", "this_email", "open_email"}:
            mode = "current_email"
        elif context_mode in {"all_email", "email", "all"}:
            mode = "email"
        else:
            mode = "email" if use_email_context else "chat"

        if mode in {"current_email", "chat"}:
            user = (
                resolve_strict_extension_user(requested_user)
                or resolve_strict_extension_user(current_email_user)
                or requested_user
                or current_email_user
                or "gmail-local"
            )
        else:
            if not supabase_enabled():
                return jsonify({
                    "error": "supabase_not_configured",
                    "message": "All email Ask needs saved email memory, but Supabase is not configured. Switch Ask context to Current email or No email, or set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
                }), 400
            user = require_extension_user(requested_user)
            if not isinstance(user, str):
                return user

        if current_email_user and current_email_user.lower() not in {"outlook-local", "gmail-local", "local"}:
            known_current_user = resolve_strict_extension_user(current_email_user)
            if known_current_user and known_current_user.lower() != user.lower():
                return jsonify({
                    "error": "user_mismatch",
                    "message": "The open email account does not match the Ask account.",
                    "requested_user": user,
                    "current_email_user": current_email_user,
                }), 403
        payload = _ask_answer_for_user(user, question, mode, current_email_context=current_email)
        refs = enrich_refs_with_gmail_thread_ids(user, payload.get("refs", []))
        return jsonify({
            "answer": str(payload.get("text") or ""),
            "refs": refs,
            "user_email": user,
            "use_email_context": use_email_context,
            "context_mode": context_mode or mode,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": "ask_failed",
            "message": str(e),
            "user_email": user or requested_user,
        }), 500


@app.route("/extension/save_note", methods=["POST"])
def extension_save_note():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    requested_user = str(data.get("user_email") or "").strip()
    topic = str(data.get("topic") or "").strip()
    expected_from = str(data.get("expected_from") or "").strip()
    ai_action = str(data.get("ai_action") or "").strip()

    if not topic or not expected_from or not ai_action:
        return jsonify({"error": "empty", "message": "Please fill Topic, Expected From, and AI Action."}), 400

    text = f"Topic: {topic} | Expected From: {expected_from} | AI Action: {ai_action}"
    if len(text) > MAX_NOTE_LENGTH:
        return jsonify({"error": "too_long", "message": "Note too long."}), 400

    user = require_extension_user(requested_user)
    if not isinstance(user, str):
        return user
    notes = read_notes(user)
    note = {
        "text": text,
        "topic": topic,
        "expected_from": expected_from,
        "ai_action": ai_action,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    note["objective_key"] = _build_objective_key(note)
    note["source_index"] = len(notes)
    try:
        if not is_microsoft_cached_user(user):
            creds = get_user_credentials(user)
            missing = missing_google_scopes(creds, [
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/gmail.labels",
            ])
            if missing:
                return jsonify({
                    "error": "reauth_required",
                    "message": "Please re-connect at /sign to grant Gmail label permissions.",
                    "missing_scopes": missing,
                }), 403
        label_result = create_note_gmail_label(user, note)
    except Exception as e:
        return jsonify({
            "error": "label_create_failed",
            "message": f"Could not create the mail label/category for this note: {e}",
        }), 500
    note = attach_gmail_label_to_note(note, label_result)
    notes.append(note)
    dropped_notes = notes[:-MAX_NOTES] if len(notes) > MAX_NOTES else []
    notes = notes[-MAX_NOTES:]
    for dropped_note in dropped_notes:
        try:
            delete_note_gmail_label(user, dropped_note)
        except Exception as e:
            print(f"[{user}] Gmail label cleanup failed for dropped note: {e}")
    try:
        notes = renumber_note_gmail_labels(user, notes)
    except Exception as e:
        print(f"[{user}] Gmail note label renumber after save skipped: {e}")
    write_notes(user, notes)
    try:
        notes = sync_notes_with_gmail_labels(user)
    except Exception as e:
        print(f"[{user}] Gmail note label sync after save skipped: {e}")
    try:
        added_count = add_existing_objective_emails_to_note_label(user, note)
    except Exception as e:
        added_count = 0
        print(f"[{user}] Existing objective email label backfill failed: {e}")
    return jsonify({"status": "saved", "user_email": user, "mail_label": label_result, "labeled_email_count": added_count})


@app.route("/extension/notes")
def extension_notes():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    requested_user = str(request.args.get("user_email") or "").strip()
    user = require_extension_user(requested_user)
    if not isinstance(user, str):
        return user
    try:
        notes = sync_notes_with_gmail_labels(user)
    except Exception as e:
        print(f"[{user}] Gmail note label sync skipped: {e}")
        notes = read_notes(user)
    return jsonify({"notes": notes, "user_email": user})


@app.route("/extension/sync_note_labels", methods=["POST"])
def extension_sync_note_labels():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    requested_user = str(data.get("user_email") or "").strip()
    user = require_extension_user(requested_user)
    if not isinstance(user, str):
        return user

    try:
        payload = sync_notes_with_gmail_labels(user, include_debug=True)
        return jsonify({"status": "synced", "user_email": user, **payload})
    except Exception as e:
        return jsonify({"error": "sync_failed", "message": f"Could not sync notes with mail labels/categories: {e}"}), 500


@app.route("/extension/sync_objective_email_labels", methods=["POST"])
def extension_sync_objective_email_labels():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    requested_user = str(data.get("user_email") or "").strip()
    user = require_extension_user(requested_user)
    if not isinstance(user, str):
        return user

    try:
        count = backfill_objective_emails_to_note_labels(user)
        return jsonify({"status": "synced", "user_email": user, "labeled_email_count": count})
    except Exception as e:
        return jsonify({"error": "sync_failed", "message": f"Could not sync objective emails into mail labels/categories: {e}"}), 500


@app.route("/extension/delete_note", methods=["POST"])
def extension_delete_note():
    auth_error = require_extension_access()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    requested_user = str(data.get("user_email") or "").strip()
    try:
        index = int(data.get("index"))
    except (TypeError, ValueError):
        return jsonify({"error": "bad_index", "message": "Missing note index."}), 400

    user = require_extension_user(requested_user)
    if not isinstance(user, str):
        return user
    notes = read_notes(user)
    if index < 0 or index >= len(notes):
        return jsonify({"error": "bad_index", "message": "Note no longer exists."}), 400
    deleted_note = notes[index]
    try:
        label_result = delete_note_gmail_label(user, deleted_note)
    except Exception as e:
        return jsonify({"error": "label_delete_failed", "message": f"Could not delete the mail label/category for this note: {e}"}), 500
    notes = [note for i, note in enumerate(notes) if i != index]
    try:
        notes = renumber_note_gmail_labels(user, notes)
    except Exception as e:
        print(f"[{user}] Gmail note label renumber after delete skipped: {e}")
    write_notes(user, notes)
    try:
        notes = sync_notes_with_gmail_labels(user)
    except Exception as e:
        print(f"[{user}] Gmail note label sync after delete skipped: {e}")
    return jsonify({"status": "deleted", "notes": notes, "user_email": user, "mail_label": label_result})


def _ask_answer_for_user(user_email: str, question: str, mode: str = "email", email_id: str = "", use_internet_context: bool = False, current_email_context: dict = None) -> dict:
    mode = str(mode or "email").strip().lower()
    question = str(question or "").strip()
    if not question:
        raise ValueError("Use /ask?q=your question")

    def email_ref_from_chunk(chunk: str) -> dict:
        return {
            "id": _chunk_field(chunk, "ID"),
            "subject": _chunk_field(chunk, "Subject") or "(No Subject)",
            "sender": _chunk_field(chunk, "From"),
            "time": _chunk_field(chunk, "Time"),
            "web_link": _chunk_field(chunk, "WebLink"),
            "user_email": user_email,
        }

    if mode == "chat":
        prompt = (
            "You are Condra, a helpful AI assistant. "
            "Answer the user's question clearly and directly.\n\n"
            f"Question:\n{question}"
        )
        return {"text": ollama_chat(prompt), "refs": []}

    if mode == "current_email":
        current_email_context = current_email_context or {}
        sender = str(current_email_context.get("sender") or "").strip()
        subject = str(current_email_context.get("subject") or "").strip()
        time_text = str(current_email_context.get("time") or "").strip()
        body = str(current_email_context.get("body") or current_email_context.get("snippet") or "").strip()
        if not (sender or subject or body):
            raise ValueError("Open an email first, or switch context to All email.")

        selected = (
            f"From: {sender or '(Unknown Sender)'}\n"
            f"Subject: {subject or '(No Subject)'}\n"
            f"Time: {time_text or '(Unknown Time)'}\n"
            f"Body:\n{body[:20000]}"
        )
        ref = {
            "id": str(current_email_context.get("id") or current_email_context.get("message_id") or "").strip(),
            "subject": subject or "(No Subject)",
            "sender": sender,
            "time": time_text,
            "web_link": str(current_email_context.get("web_link") or current_email_context.get("url") or "").strip(),
            "user_email": user_email,
        }
        prompt = (
            "Answer the question using only the currently open email below. "
            "If the answer is not in this email, say that clearly.\n\n"
            f"Current email:\n{selected}\n\n"
            f"Question:\n{question}"
        )
        return {"text": ollama_chat(prompt), "refs": [ref] if (ref["id"] or ref["subject"] or ref["web_link"]) else []}

    email_chunks = get_email_chunks_for_retrieval(user_email)

    if mode == "this_email":
        if not email_id:
            raise ValueError("Open an email first and provide email_id.")
        selected = None
        for chunk in email_chunks:
            if _chunk_field(chunk, "ID") == email_id:
                selected = chunk
                break

        if not selected:
            raise ValueError("Could not find that email in memory.")

        prompt = (
            "Answer the question using only this one email. "
            "If the answer is not in this email, say that clearly.\n\n"
            f"Email:\n{selected}\n\n"
            f"Question:\n{question}"
        )
        ref = email_ref_from_chunk(selected)
        return {"text": ollama_chat(prompt), "refs": [ref] if ref.get("id") else []}

    relevant = []
    if supabase_vectors_enabled():
        try:
            backfill_supabase_embeddings_for_user(user_email, max_items=40)
            relevant = get_supabase_relevant_chunks(user_email, question, k=40)
        except Exception as e:
            print(f"[{user_email}] Local vector search failed, falling back to FAISS: {e}")

    if not relevant:
        index = get_synced_index(user_email, email_chunks)
        if index.ntotal == 0:
            return {"text": "No emails in memory yet", "refs": []}
        q_vector = np.array([embed_text(question)]).astype("float32")
        _, I = index.search(q_vector, k=min(40, index.ntotal))

        seen = set()
        for i in I[0]:
            if i < len(email_chunks):
                chunk = email_chunks[i]
                if chunk not in seen:
                    relevant.append(chunk)
                    seen.add(chunk)

    prompt = f"Answer the question using these emails.\n\nEmails:\n{relevant}\n\nQuestion:\n{question}"
    answer_text = ollama_chat(prompt)

    summary_id_by_subject_time = {}
    summary_unique_id_by_subject = {}
    summary_chunks = [str(r["raw_chunk"] or "") for r in get_email_rows(user_email, descending=False) if str(r["raw_chunk"] or "").strip()]
    if summary_chunks:
        for s_chunk in summary_chunks:
            sid = _chunk_field(s_chunk, "ID")
            subj = _chunk_field(s_chunk, "Subject")
            stime = _chunk_field(s_chunk, "Time")
            if sid and subj and stime and (subj, stime) not in summary_id_by_subject_time:
                summary_id_by_subject_time[(subj, stime)] = sid
            if sid and subj:
                if subj not in summary_unique_id_by_subject:
                    summary_unique_id_by_subject[subj] = sid
                elif summary_unique_id_by_subject[subj] != sid:
                    summary_unique_id_by_subject[subj] = ""

    refs = []
    seen_ids = set()
    for chunk in relevant[:12]:
        email_ref = {
            **email_ref_from_chunk(chunk)
        }
        if not email_ref["id"]:
            stime = _chunk_field(chunk, "Time")
            key = (email_ref["subject"], stime)
            email_ref["id"] = summary_id_by_subject_time.get(key, "") or summary_unique_id_by_subject.get(email_ref["subject"], "")
        if email_ref["id"] and email_ref["id"] not in seen_ids:
            refs.append(email_ref)
            seen_ids.add(email_ref["id"])

    return {"text": answer_text, "refs": refs}


def enrich_refs_with_gmail_thread_ids(user_email: str, refs: list) -> list:
    if not refs:
        return []
    try:
        service = get_gmail_service_for_user(user_email)
    except Exception:
        service = None

    enriched = []
    for ref in refs:
        row = dict(ref or {})
        msg_id = str(row.get("id") or "").strip()
        row["web_id"] = msg_id
        if service and msg_id:
            try:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="minimal",
                    fields="id,threadId"
                ).execute()
                row["thread_id"] = str(msg.get("threadId") or "")
                row["web_id"] = row["thread_id"] or msg_id
            except Exception:
                pass
        enriched.append(row)
    return enriched


def read_notes(user_email: str) -> list:
    global _notes_label_metadata_supported
    cached = _cache_get(_notes_cache, user_email)
    if cached is not None:
        return cached

    if _notes_label_metadata_supported:
        try:
            rows = supabase_request(
                "GET",
                "notes",
                query_params={
                    "select": "source_index,text,topic,expected_from,ai_action,created_at,gmail_label_name,gmail_label_id,gmail_label_synced_at",
                    "user_email": f"eq.{user_email}",
                    "order": "source_index.asc",
                },
            ) or []
        except Exception as e:
            _notes_label_metadata_supported = False
            print(f"[{user_email}] Notes label metadata columns unavailable, using basic notes schema: {e}")
            rows = []
    else:
        rows = []

    if not _notes_label_metadata_supported:
        rows = supabase_request(
            "GET",
            "notes",
            query_params={
                "select": "source_index,text,topic,expected_from,ai_action,created_at",
                "user_email": f"eq.{user_email}",
                "order": "source_index.asc",
            },
        ) or []
    out = []
    if isinstance(rows, list):
        for item in rows:
            try:
                source_index = int(item.get("source_index", len(out)))
            except (TypeError, ValueError):
                source_index = len(out)
            topic = str(item.get("topic", "")).strip()
            expected_from = str(item.get("expected_from", "")).strip()
            ai_action = str(item.get("ai_action", "")).strip()
            text = str(item.get("text", "")).strip()
            if not text and (topic or expected_from or ai_action):
                text = (
                    f"Topic: {topic or 'None'} | "
                    f"Expected From: {expected_from or 'None'} | "
                    f"AI Action: {ai_action or 'None'}"
                )
            if not text:
                continue
            created_at = str(item.get("created_at", "")).strip() or None
            out.append({
                "source_index": source_index,
                "text": text,
                "topic": topic,
                "expected_from": expected_from,
                "ai_action": ai_action,
                "created_at": created_at,
                "gmail_label_name": str(item.get("gmail_label_name", "")).strip(),
                "gmail_label_id": str(item.get("gmail_label_id", "")).strip(),
                "gmail_label_synced_at": str(item.get("gmail_label_synced_at", "")).strip(),
                "objective_key": _build_objective_key({
                    "text": text,
                    "topic": topic,
                    "expected_from": expected_from,
                    "ai_action": ai_action,
                    "created_at": created_at,
                }),
            })
    _cache_set(_notes_cache, user_email, out, CACHE_TTL_NOTES_SECONDS)
    return copy.deepcopy(out)


def write_notes(user_email: str, notes: list):
    global _notes_label_metadata_supported
    normalized = []
    for note in notes:
        if isinstance(note, dict):
            text = str(note.get("text", "")).strip()
            topic = str(note.get("topic", "")).strip()
            expected_from = str(note.get("expected_from", "")).strip()
            ai_action = str(note.get("ai_action", "")).strip()
            created_at = note.get("created_at")
            created_at = str(created_at).strip() if created_at is not None else None
            gmail_label_name = str(note.get("gmail_label_name", "")).strip()
            gmail_label_id = str(note.get("gmail_label_id", "")).strip()
            gmail_label_synced_at = str(note.get("gmail_label_synced_at", "")).strip()
        else:
            text = str(note).strip()
            topic = ""
            expected_from = ""
            ai_action = ""
            created_at = None
            gmail_label_name = ""
            gmail_label_id = ""
            gmail_label_synced_at = ""
        if not text and (topic or expected_from or ai_action):
            text = (
                f"Topic: {topic or 'None'} | "
                f"Expected From: {expected_from or 'None'} | "
                f"AI Action: {ai_action or 'None'}"
            )
        if not text:
            continue
        normalized.append({
            "text": text,
            "topic": topic,
            "expected_from": expected_from,
            "ai_action": ai_action,
            "created_at": created_at,
            "gmail_label_name": gmail_label_name,
            "gmail_label_id": gmail_label_id,
            "gmail_label_synced_at": gmail_label_synced_at,
        })

    supabase_request("DELETE", "notes", query_params={"user_email": f"eq.{user_email}"})
    if normalized:
        body = []
        for idx, n in enumerate(normalized):
            row = {
                "user_email": user_email,
                "source_index": idx,
                "text": n["text"],
                "topic": n["topic"],
                "expected_from": n["expected_from"],
                "ai_action": n["ai_action"],
                "created_at": n["created_at"] or datetime.datetime.now().isoformat(timespec="seconds"),
            }
            if _notes_label_metadata_supported:
                row["gmail_label_name"] = n["gmail_label_name"]
                row["gmail_label_id"] = n["gmail_label_id"]
                row["gmail_label_synced_at"] = n["gmail_label_synced_at"]
            body.append(row)
        if _notes_label_metadata_supported:
            try:
                supabase_request("POST", "notes", body=body, prefer="return=minimal")
            except Exception as e:
                _notes_label_metadata_supported = False
                print(f"[{user_email}] Notes label metadata write unavailable, using basic notes schema: {e}")
                fallback_body = []
                for row in body:
                    fallback = dict(row)
                    fallback.pop("gmail_label_name", None)
                    fallback.pop("gmail_label_id", None)
                    fallback.pop("gmail_label_synced_at", None)
                    fallback_body.append(fallback)
                supabase_request("POST", "notes", body=fallback_body, prefer="return=minimal")
        else:
            supabase_request("POST", "notes", body=body, prefer="return=minimal")
    _invalidate_notes_cache(user_email)


@app.route("/create_doc", methods=["POST"])
def create_doc():
    data = request.get_json() or {}
    user = str(session.get("user_email") or "").strip()
    if not user:
        return "Login required", 401
    requested_user = str(data.get("user_email", "")).strip()
    if requested_user and not _same_email(requested_user, user):
        return jsonify({
            "error": "user_mismatch",
            "message": "The requested account does not match the signed-in account.",
        }), 403

    title = str(data.get("title", "")).strip() or "AI Document"
    content = str(data.get("content", ""))
    share_with = str(data.get("share_with", "")).strip()

    try:
        creds = get_user_credentials(user)
        missing = missing_google_scopes(creds, [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive.file",
        ])
        if missing:
            return jsonify({
                "error": "reauth_required",
                "message": "Please re-connect at /sign to grant Google Docs permission.",
                "missing_scopes": missing,
            }), 403

        docs = get_docs_service_for_user(user)
        doc = docs.documents().create(body={"title": title}).execute()
        doc_id = doc.get("documentId")
        if not doc_id:
            return jsonify({"error": "create_failed", "message": "No document id returned"}), 500

        if content.strip():
            docs.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]}
            ).execute()

        if share_with:
            drive = get_drive_service_for_user(user)
            drive.permissions().create(
                fileId=doc_id,
                body={"type": "user", "role": "writer", "emailAddress": share_with},
                sendNotificationEmail=True
            ).execute()

        return jsonify({
            "status": "created",
            "document_id": doc_id,
            "url": f"https://docs.google.com/document/d/{doc_id}/edit"
        })
    except Exception as e:
        print("[create_doc] error:", traceback.format_exc())
        return google_error_response(e, "create_failed", "Failed to create Google Doc.")


# =========================
# STARTUP ROUTINE
# =========================

def initialize_background_threads():
    """Keep app.py independent from the email save worker."""
    print("[STARTUP] app.py is running JS/API routes only. Run saveApp.py separately for email saving.")

@app.route("/")
def ui():
    return render_template("index.html")


@app.route("/setup_status")
def setup_status():
    signed_in_user = str(session.get("user_email") or "").strip()
    users = []
    supabase_ok = supabase_enabled()
    supabase_error = ""

    if supabase_ok and signed_in_user:
        try:
            microsoft_cached = {item.lower() for item in get_microsoft_cached_user_emails()}
            rows = supabase_request(
                "GET",
                "users",
                query_params={
                    "select": "email,google_token_json,google_token_updated_at",
                    "order": "email.asc",
                },
            ) or []
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    email = str(row.get("email") or "").strip()
                    if not email:
                        continue
                    users.append({
                        "email": email,
                        "has_google_token": bool(str(row.get("google_token_json") or "").strip()),
                        "google_token_updated_at": str(row.get("google_token_updated_at") or "").strip(),
                        "has_microsoft_token": email.lower() in microsoft_cached,
                    })
        except Exception as e:
            supabase_ok = False
            supabase_error = str(e)

    return jsonify({
        "server": "ok",
        "supabase": {
            "configured": supabase_enabled(),
            "ok": supabase_ok,
            "url": get_supabase_url(),
            "error": supabase_error,
        },
        "microsoft": {
            "client_id": MICROSOFT_CLIENT_ID,
            "client_secret_present": bool(MICROSOFT_CLIENT_SECRET),
            "authority": MICROSOFT_AUTHORITY,
            "redirect_uri": urllib.parse.urljoin(request.url_root, "callback"),
            "token_cache_file": MICROSOFT_TOKEN_CACHE_FILE if signed_in_user else "",
            "scopes": MICROSOFT_SCOPES,
            "cached_accounts": get_microsoft_cached_user_emails() if signed_in_user else [],
        },
        "google": {
            "client_secret_file": CLIENT_SECRET_FILE,
            "client_secret_present": os.path.exists(CLIENT_SECRET_FILE),
            "redirect_uri": get_oauth_redirect_uri(),
            "client_secret_redirect_uris": get_google_client_redirect_uris(),
            "scopes": SCOPES,
        },
        "extension": {
            "remote_host": "https://condranew2.onrender.com",
            "api_key_required": bool(EXTENSION_API_KEY),
            "local_hosts": [
                "http://127.0.0.1:5050",
                "http://localhost:5050",
            ],
        },
        "encryption": {
            "enabled": True,
            "using_default_key": encryption_is_using_default(),
            "key_env": "CONDRA_ENCRYPTION_KEY",
        },
        "signed_in_user": signed_in_user,
        "users": users,
    })


# I am here 
# =========================
# START SERVER
# =========================

if __name__ == "__main__":
    initialize_background_threads()
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5050")),
        debug=False,
        threaded=True,
    )
