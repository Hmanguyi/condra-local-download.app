import os
import time
import threading
import traceback
import hashlib
import copy
import argparse
import numpy as np
import faiss
import re
import json
import datetime
import html as html_lib
import base64
import msal
import requests
import urllib.parse
import urllib.request
import urllib.error

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build

from security import (
    decrypt_file_payload,
    decrypt_json_text,
    decrypt_text,
    encrypt_file_payload,
    encrypt_json_text,
    encrypt_text,
)

OLLAMA_CHAT_URL = os.environ.get("OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
OLLAMA_SUMMARY_MODEL = os.environ.get("OLLAMA_SUMMARY_MODEL", os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:latest"))

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
MICROSOFT_TOKEN_CACHE_FILE = os.environ.get(
    "MICROSOFT_TOKEN_CACHE_FILE",
    os.path.join(os.getcwd(), "instance", "msal_token_cache.json"),
)
GMAIL_QUERY = os.environ.get("SAVE_APP_GMAIL_QUERY", "(in:inbox) OR (in:sent)")

SUPABASE_URL_DEFAULT = ""
SUPABASE_SERVICE_ROLE_KEY_DEFAULT = ""
SUPABASE_VECTOR_RPC_DEFAULT = "match_email_embeddings"

CACHE_TTL_EMAIL_ROWS_SECONDS = int(os.getenv("CACHE_TTL_EMAIL_ROWS_SECONDS", "4"))
CACHE_TTL_ASK_CHUNKS_SECONDS = int(os.getenv("CACHE_TTL_ASK_CHUNKS_SECONDS", "12"))
CACHE_TTL_EMBEDDING_SECONDS = int(os.getenv("CACHE_TTL_EMBEDDING_SECONDS", "3600"))
EMBED_CACHE_MAX_ITEMS = int(os.getenv("EMBED_CACHE_MAX_ITEMS", "512"))
CHECK_INTERVAL = int(os.getenv("SAVE_APP_CHECK_INTERVAL", "10"))

user_stored_ids: dict[str, set] = {}
active_threads: set[str] = set()
active_threads_lock = threading.Lock()
_cache_lock = threading.Lock()
_email_rows_cache = {}
_ask_chunks_cache = {}
_notes_lines_cache = {}
_embedding_cache = {}
_embedding_cache_order = []
_backfill_last_run = {}

_get_numbered_notes_callback = None
_add_objective_email_to_note_label_callback = None


def configure_email_saver(get_numbered_notes_func=None, add_objective_email_to_note_label_func=None):
    global _get_numbered_notes_callback, _add_objective_email_to_note_label_callback
    _get_numbered_notes_callback = get_numbered_notes_func
    _add_objective_email_to_note_label_callback = add_objective_email_to_note_label_func


def _build_objective_key(note: dict) -> str:
    topic = str(note.get("topic", "")).strip()
    expected_from = str(note.get("expected_from", "")).strip()
    ai_action = str(note.get("ai_action", "")).strip()
    text = str(note.get("text", "")).strip()
    created_at = str(note.get("created_at", "")).strip()
    seed = "\n".join([topic, expected_from, ai_action, text, created_at])
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _basic_numbered_notes_from_supabase(user_email: str):
    try:
        rows = supabase_request(
            "GET",
            "notes",
            query_params={
                "select": "source_index,text,topic,expected_from,ai_action,created_at",
                "user_email": f"eq.{user_email}",
                "order": "source_index.asc",
            },
        ) or []
    except Exception as e:
        print(f"[{user_email}] Could not load notes for saver: {e}")
        return []

    lines = []
    for i, note in enumerate(rows if isinstance(rows, list) else []):
        topic = str(note.get("topic", "")).strip()
        expected_from = str(note.get("expected_from", "")).strip()
        ai_action = str(note.get("ai_action", "")).strip()
        text = str(note.get("text", "")).strip()
        objective_key = _build_objective_key(note)
        key_prefix = f"[OBJECTIVE_KEY:{objective_key}] "
        if topic or expected_from or ai_action:
            lines.append(
                f"{i + 1}. {key_prefix}Topic: {topic or 'None'} | Expected From: {expected_from or 'None'} | AI Action: {ai_action or 'None'}"
            )
        elif text:
            lines.append(f"{i + 1}. {key_prefix}{text}")
    return lines


def get_numbered_notes(user_email: str):
    if _get_numbered_notes_callback:
        return _get_numbered_notes_callback(user_email)
    cache_key = str(user_email or "").strip().lower()
    cached = _cache_get(_notes_lines_cache, cache_key)
    if cached is not None:
        return cached
    notes = _basic_numbered_notes_from_supabase(user_email)
    _cache_set(_notes_lines_cache, cache_key, notes, 30)
    return notes


def add_objective_email_to_note_label(user_email: str, objective_key: str, message_id: str):
    if _add_objective_email_to_note_label_callback:
        return _add_objective_email_to_note_label_callback(user_email, objective_key, message_id)
    return None


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
            if isinstance(key, tuple) and key and key[0] == user_email:
                _email_rows_cache.pop(key, None)
        for key in list(_ask_chunks_cache.keys()):
            if isinstance(key, tuple) and key and key[0] == user_email:
                _ask_chunks_cache.pop(key, None)
        _backfill_last_run.pop(user_email, None)


def _safe_iso_now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def ollama_chat(prompt: str, system: str = "") -> str:
    messages = []
    if str(system or "").strip():
        messages.append({"role": "system", "content": str(system).strip()})
    messages.append({"role": "user", "content": str(prompt or "")})

    response = requests.post(
        OLLAMA_CHAT_URL,
        headers={"X-API-Key": OLLAMA_API_KEY},
        json={
            "model": OLLAMA_SUMMARY_MODEL,
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
    return bool(get_supabase_url() and get_supabase_key())


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
    if not supabase_enabled():
        raise RuntimeError("Supabase not configured")
    key = get_supabase_key()
    if key.startswith("sb_publishable_"):
        raise RuntimeError("Supabase key must be a service_role key for backend read/write.")

    params = query_params or {}
    qs = urllib.parse.urlencode(params, doseq=True)
    url = f"{get_supabase_url()}/rest/v1/{table}"
    if qs:
        url = f"{url}?{qs}"

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(_encrypt_supabase_body(table, body), ensure_ascii=False).encode("utf-8")
    if prefer:
        headers["Prefer"] = prefer

    req = urllib.request.Request(url=url, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            if not raw.strip():
                return None
            try:
                return _decrypt_supabase_result(table, json.loads(raw))
            except Exception:
                return raw
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = str(e)
        raise RuntimeError(f"Supabase {table} {method.upper()} failed: HTTP {e.code} {detail}") from e


def supabase_rpc(function_name: str, payload: dict):
    if not supabase_enabled():
        raise RuntimeError("Supabase not configured")
    key = get_supabase_key()
    if key.startswith("sb_publishable_"):
        raise RuntimeError("Supabase key must be a service_role key for backend read/write.")

    url = f"{get_supabase_url()}/rest/v1/rpc/{function_name}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            if not raw.strip():
                return []
            try:
                parsed = json.loads(raw)
                return _decrypt_supabase_result("email_embeddings", parsed) if isinstance(parsed, list) else []
            except Exception:
                return []
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = str(e)
        raise RuntimeError(f"Supabase RPC {function_name} failed: HTTP {e.code} {detail}") from e


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


def _is_noneish(value: str) -> bool:
    return str(value or "").strip().lower() in {"", "none", "null", "no action required", "n/a"}


def _parsed_summary_object(summary_text: str):
    try:
        parsed = _load_summary_json(summary_text or "")
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        json_raw = _extract_first_json_object(summary_text or "")
        if not json_raw:
            return None
        try:
            parsed = _load_summary_json(json_raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _replace_first_json_object(raw_text: str, replacement_obj: dict) -> str:
    raw = str(raw_text or "")
    start = raw.find("{")
    if start == -1:
        return raw
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
                    replacement = json.dumps(replacement_obj, ensure_ascii=False)
                    return raw[:start] + replacement + raw[i + 1:]
        escape = (ch == "\\") and not escape
        if ch != "\\":
            escape = False
    return raw


def ensure_objective_completion(summary_text: str, user_email: str, email_text: str, notes_block: str) -> str:
    fields = _parse_summary_fields(summary_text or "")
    objective_id = str(fields.get("objective_id") or "").strip()
    completion = str(fields.get("objective_completion") or "").strip()
    if _is_noneish(objective_id) or not _is_noneish(completion):
        return summary_text

    prompt = f"""
Return VALID JSON only.

The email matched this user objective key: {objective_id}

User notes/objectives:
{notes_block}

Email:
{email_text}

Generate the actual completion for the matched objective.
Use the note's AI Action and the email content.
Do not explain what to do. Perform the completion.

Format:
{{"completion of objective": "..."}}
"""
    try:
        completion_response = ollama_chat(prompt)
        parsed_completion = _parsed_summary_object(completion_response) or {}
        new_completion = parsed_completion.get("completion of objective") or parsed_completion.get("objective_completion") or ""
        if isinstance(new_completion, (dict, list)):
            new_completion = json.dumps(new_completion, ensure_ascii=False)
        new_completion = str(new_completion or "").strip()
        if _is_noneish(new_completion):
            print(f"[{user_email}] Objective {objective_id} completion still came back empty/None")
            return summary_text

        parsed_summary = _parsed_summary_object(summary_text) or {}
        parsed_summary["completion of objective"] = new_completion
        if "is Objective" not in parsed_summary:
            parsed_summary["is Objective"] = objective_id
        print(f"[{user_email}] Filled objective completion for {objective_id}: {_summary_preview(new_completion, 220)}")
        if _extract_first_json_object(summary_text or ""):
            return _replace_first_json_object(summary_text, parsed_summary)
        return json.dumps(parsed_summary, ensure_ascii=False)
    except Exception as e:
        print(f"[{user_email}] Failed to fill objective completion for {objective_id}: {e}")
        return summary_text


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


def get_email_rows(user_email: str, descending: bool = False):
    cache_key = (user_email, bool(descending))
    cached = _cache_get(_email_rows_cache, cache_key)
    if cached is not None:
        return cached

    order = "source_index.desc" if descending else "source_index.asc"
    rows = supabase_request(
        "GET",
        "emails",
        query_params={
            "select": "source_index,email_id,snippet,raw_chunk,is_read",
            "user_email": f"eq.{user_email}",
            "order": order,
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


def supertest_matches(row: dict, time_query: str, subject_query: str, snippet_query: str) -> bool:
    fields = supertest_row_fields(row)

    if time_query and supertest_norm(time_query) not in supertest_norm(fields["time"]):
        return False

    if subject_query and supertest_norm(subject_query) not in supertest_norm(fields["subject"]):
        return False

    if snippet_query:
        query_norm = supertest_norm(snippet_query)
        saved_snippet_norm = supertest_norm(fields["snippet"])
        haystack = supertest_norm(f"{fields['snippet']} {fields['body_preview']} {fields['raw']}")
        snippet_ok = bool(query_norm and query_norm in haystack)
        if not snippet_ok and saved_snippet_norm and query_norm:
            query_tokens = _email_match_tokens(query_norm)
            saved_tokens = _email_match_tokens(saved_snippet_norm)
            overlap = len(query_tokens & saved_tokens)
            snippet_ok = overlap >= max(3, min(8, len(query_tokens) // 3 if query_tokens else 3))
        if not snippet_ok:
            return False

    return True


def upsert_email_to_supabase(user_email: str, msg_id: str, sender: str, text: str, attachment: str, summary_text: str):
    subject = text.split("Subject:")[1].split("\n")[0].strip() if "Subject:" in text else ""
    time_raw = text.split("Time:")[1].split("\n")[0].strip() if "Time:" in text else ""
    bullet_points, excerpts, summary_fields = _summary_column_values(summary_text or "", text or "")
    saved_snippet = saved_email_snippet(text or "")
    raw_chunk = (
        f"ID: {msg_id}\n"
        f"{attachment}\n"
        f"{sender}\n"
        f"Snippet: {saved_snippet}\n"
        f"SummaryBulletPointsJSON: {json.dumps(bullet_points, ensure_ascii=False)}\n"
        f"SummaryExcerptsJSON: {json.dumps(excerpts, ensure_ascii=False)}\n"
        f"{summary_text}\n\n"
        f"{text}\n"
        f"0"
    )
    snippet, full_email = _chunk_snippet_and_full_email(raw_chunk)
    snippet = snippet or saved_snippet
    read_flag = _read_flag_from_chunk(raw_chunk)
    raw_sha = hashlib.sha256(raw_chunk.encode("utf-8", errors="ignore")).hexdigest()

    existing_rows = supabase_request(
        "GET",
        "emails",
        query_params={
            "select": "source_index",
            "user_email": f"eq.{user_email}",
            "email_id": f"eq.{msg_id}",
            "limit": "1",
        },
    ) or []
    existing_row = existing_rows[0] if isinstance(existing_rows, list) and existing_rows else None

    max_rows = supabase_request(
        "GET",
        "emails",
        query_params={
            "select": "source_index",
            "user_email": f"eq.{user_email}",
            "order": "source_index.desc",
            "limit": "1",
        },
    ) or []
    if existing_row:
        source_index = int(existing_row.get("source_index", 0) or 0)
    else:
        source_index = (int(max_rows[0].get("source_index", -1)) + 1) if isinstance(max_rows, list) and max_rows else 0
    row = {
        "user_email": user_email,
        "source_index": source_index,
        "email_id": msg_id,
        "sender": sender,
        "subject": subject,
        "time": time_raw,
        "snippet": snippet,
        "full_email": full_email,
        "bullet_points_json": bullet_points,
        "excerpts_json": excerpts,
        "bullet_count": len(bullet_points),
        "is_read": bool(read_flag),
        "objective_id": summary_fields["objective_id"],
        "objective_info": summary_fields["objective_info"],
        "objective_completion": summary_fields["objective_completion"],
        "type": summary_fields["type"],
        "raw_chunk": raw_chunk,
        "raw_sha256": raw_sha,
    }
    print(f"[{user_email}] Supabase save fields for {subject}: bullets={bullet_points}, excerpts={excerpts}")
    if existing_row:
        supabase_request(
            "PATCH",
            "emails",
            query_params={
                "user_email": f"eq.{user_email}",
                "email_id": f"eq.{msg_id}",
            },
            body=row,
            prefer="return=minimal",
        )
    else:
        supabase_request(
            "POST",
            "emails",
            body=[row],
            prefer="return=minimal",
        )
    _invalidate_email_caches(user_email)
    return {"source_index": source_index, "raw_chunk": raw_chunk}


def verify_email_summary_backed_up(user_email: str, msg_id: str):
    rows = supabase_request(
        "GET",
        "emails",
        query_params={
            "select": "source_index,email_id,subject,bullet_points_json,excerpts_json,bullet_count,raw_chunk",
            "user_email": f"eq.{user_email}",
            "email_id": f"eq.{msg_id}",
            "limit": "1",
        },
    ) or []
    if not isinstance(rows, list) or not rows:
        return None
    return rows[0]


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


def repair_missing_objective_completions_for_user(user_email: str, limit: int = 50) -> int:
    rows = supabase_request(
        "GET",
        "emails",
        query_params={
            "select": "source_index,email_id,raw_chunk,objective_id,objective_completion",
            "user_email": f"eq.{user_email}",
            "order": "source_index.desc",
            "limit": str(max(1, int(limit or 50))),
        },
    ) or []
    notes = get_numbered_notes(user_email)
    notes_block = "\n".join(notes) if notes else "No notes configured."
    repaired = 0

    for row in rows if isinstance(rows, list) else []:
        raw_chunk = str((row or {}).get("raw_chunk") or "").strip()
        msg_id = str((row or {}).get("email_id") or _chunk_field(raw_chunk, "ID") or "").strip()
        fields = _parse_summary_fields(raw_chunk)
        objective_id = str((row or {}).get("objective_id") or fields.get("objective_id") or "").strip()
        completion = str((row or {}).get("objective_completion") or fields.get("objective_completion") or "").strip()
        if not raw_chunk or not msg_id or _is_noneish(objective_id) or not _is_noneish(completion):
            continue

        updated_raw = ensure_objective_completion(raw_chunk, user_email, raw_chunk, notes_block)
        updated_fields = _parse_summary_fields(updated_raw)
        updated_completion = str(updated_fields.get("objective_completion") or "").strip()
        if _is_noneish(updated_completion):
            continue

        supabase_request(
            "PATCH",
            "emails",
            query_params={
                "user_email": f"eq.{user_email}",
                "email_id": f"eq.{msg_id}",
            },
            body={
                "objective_completion": updated_completion,
                "raw_chunk": updated_raw,
            },
            prefer="return=minimal",
        )
        repaired += 1

    _invalidate_email_caches(user_email)
    return repaired


def get_stored_ids(user_email: str) -> set:
    """Return the per-user processed-ID set from Supabase."""
    if user_email not in user_stored_ids:
        rows = supabase_request(
            "GET",
            "processed_ids",
            query_params={
                "select": "gmail_msg_id",
                "user_email": f"eq.{user_email}",
            },
        ) or []
        user_stored_ids[user_email] = set(
            str(r.get("gmail_msg_id", "")).strip()
            for r in rows
            if isinstance(r, dict) and str(r.get("gmail_msg_id", "")).strip()
        ) if isinstance(rows, list) else set()
    return user_stored_ids[user_email]


def mark_id_processed(user_email: str, msg_id: str):
    ids = get_stored_ids(user_email)
    ids.add(msg_id)
    supabase_request(
        "POST",
        "processed_ids",
        query_params={"on_conflict": "user_email,gmail_msg_id"},
        body=[{
            "user_email": user_email,
            "gmail_msg_id": msg_id,
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }],
        prefer="resolution=merge-duplicates,return=minimal",
    )


def ensure_user_registered(user_email: str):
    email = str(user_email or "").strip()
    if not email:
        return
    now_iso = _safe_iso_now()
    supabase_request(
        "POST",
        "users",
        query_params={"on_conflict": "email"},
        body=[{
            "email": email,
            "folder_path": "supabase",
            "migrated_at": now_iso,
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


def save_user_credentials(user_email: str, creds: Credentials):
    email = str(user_email or "").strip()
    if not email or not creds:
        return

    now_iso = _safe_iso_now()
    ensure_user_registered(email)
    supabase_request(
        "POST",
        "users",
        query_params={"on_conflict": "email"},
        body=[{
            "email": email,
            "folder_path": "supabase",
            "migrated_at": now_iso,
            "google_token_json": creds.to_json(),
            "google_token_updated_at": now_iso,
        }],
        prefer="resolution=merge-duplicates,return=minimal",
    )


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

    raise Exception("No saved Gmail token found for user. Sign in with app.py at /gmail/sign first.")


def get_gmail_service_for_user(user_email: str):
    creds = get_user_credentials(user_email)
    return build("gmail", "v1", credentials=creds)


def get_gmail_cached_user_emails() -> list[str]:
    try:
        rows = supabase_request(
            "GET",
            "users",
            query_params={
                "select": "email,google_token_json",
                "order": "email.asc",
            },
        ) or []
        out = []
        seen = set()
        for row in rows if isinstance(rows, list) else []:
            email = str((row or {}).get("email") or "").strip()
            token_json = str((row or {}).get("google_token_json") or "").strip()
            key = email.lower()
            if email and token_json and key not in seen:
                seen.add(key)
                out.append(email)
        return out
    except Exception as e:
        print(f"[Gmail] Could not read cached accounts: {e}")
        return []


def _decode_part_data(data: str) -> bytes:
    return base64.urlsafe_b64decode(str(data or "").encode("utf-8"))


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
    return {"body_text": body_text, "html_body": html_body}


def get_attachments(service, msg):
    attachments = []

    def walk_parts(parts):
        for part in parts:
            filename = part.get("filename")
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")
            headers = {h.get("name", "").lower(): h.get("value", "") for h in part.get("headers", [])}
            is_inline = "inline" in headers.get("content-disposition", "").lower()
            if filename and attachment_id and not is_inline:
                attachment = service.users().messages().attachments().get(
                    userId="me", messageId=msg["id"], id=attachment_id
                ).execute()
                data = attachment.get("data")
                if data:
                    attachments.append({"filename": filename, "data": _decode_part_data(data)})
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


def store_email_memory(user_email: str, text: str, sen: str, msg_id: str, attachment: str = "none"):
    chunk_text = f"ID: {msg_id}\n{text}" if msg_id else text

    # Summarise received emails only
    subject = text.split("Subject:")[1].split("\n")[0].strip() if "Subject:" in text else ""

    if "RECEIVED" in text and subject:
        started_at = time.time()
        notes = get_numbered_notes(user_email)
        notes_block = "\n".join(notes) if notes else "No notes configured."
        prompt = f"""
You must return your answer in VALID JSON only. No extra text.

Format:
{{
  "title": "...",
  "bullets": [
    {{
      "point": "...",
      "excerpt": "..."
    }}
  ],
  "is Objective": "...",
  "info about Objective": "...",
  "completion of objective": "...",
  "type": "..."
}}

Rules:
- 1 to 5 bullets
- most email of a normal length should have around 3 bullets, but use your judgement
- "point" = short summary (1 line)
- "excerpt" = EXACT quote from email (no paraphrasing, no subject line)
- If no excerpt exists, write "No exact excerpt"
- Do NOT include anything outside JSON
- "title": a short title you give for the email
- Every JSON value must use normal double-quoted JSON strings
- Escape quotation marks inside strings with backslash, like \"
- Do NOT use backticks anywhere in the JSON
- "excerpt" must be plain text ONLY
- User notes/objectives:
{notes_block}
- Objective matching rule:
  If the email clearly relates to one of the notes above, set "is Objective" to the exact OBJECTIVE_KEY value for that note.
  Output only the key value (example: "ab12cd34ef56"), not the note number.
  If a key is unavailable, you may fall back to the note number.
  The match MUST be based on email body content and meaning (not just subject line keyword overlap).
  If no note matches, set "is Objective" to "None".
  Set "info about Objective" to relevant extracted details for the matched note, or "None" if nothing useful.

"completion of objective":
- If the email contains a request, task, or objective that requires a response, action, or creation (such as writing an email, answering a question, or preparing something), you MUST generate the content needed to complete that objective.
- This may include writing a reply email, answering questions, drafting messages, providing requested information, or completing instructions from the email.
- The output should be directly usable (e.g., a full email reply, not a description of it).
- If "is Objective" is not "None", then "completion of objective" MUST NOT be "None". Use the matched note's AI Action and the email content to perform the completion.
- If no action is required, return "None"
Do NOT describe the completion. You must PERFORM the completion.

-set "type": "0" if the email is ad or newsletter or promotional material with no clear request, task, or objective. 
-set "type": "1" if the email is a personal or work email that is from teacher coworker friend ect
-set "type": "2" if the email is a receipt invoice bill or order confirmation ect

Email content:
{text}
attachments:
{attachment}
"""
        try:
            summary_text = ollama_chat(prompt)
        except Exception as e:
            print(f"[{user_email}] Summary generation ERROR for: {subject}: {e}")
            raise
        print(f"[{user_email}] Summary generated for {subject} in {time.time() - started_at:.1f}s")
        summary_text = ensure_objective_completion(summary_text, user_email, text, notes_block)
        print_summary_bullets_or_error(user_email, subject, summary_text)

        try:
            print(f"[{user_email}] Backing up summary to Supabase for: {subject} ({msg_id})")
            upserted = upsert_email_to_supabase(user_email, msg_id, sen, text, attachment, summary_text)
            verified = verify_email_summary_backed_up(user_email, msg_id)
            if not verified:
                print(f"[{user_email}] Supabase backup ERROR for {subject}: row was not found after save")
            else:
                saved_bullets = verified.get("bullet_points_json")
                saved_excerpts = verified.get("excerpts_json")
                if saved_bullets:
                    print(
                        f"[{user_email}] Supabase backup OK for {subject}: "
                        f"bullet_points_json={saved_bullets}, excerpts_json={saved_excerpts}"
                    )
                else:
                    print(
                        f"[{user_email}] Supabase backup WARNING for {subject}: "
                        f"row exists but bullet_points_json is empty. raw_chunk has backup arrays."
                    )
        except Exception as e:
            print(f"[{user_email}] Supabase backup ERROR for {subject}: {e}")
            raise
        objective_id = str(_parse_summary_fields(summary_text or "").get("objective_id", "") or "").strip()
        if objective_id and objective_id.lower() != "none":
            try:
                label_result = add_objective_email_to_note_label(user_email, objective_id, msg_id)
                if label_result:
                    provider = str(label_result.get("provider") or "gmail").strip()
                    print(f"[{user_email}] Added objective email {msg_id} to {provider} label/category {label_result.get('label_name')}")
            except Exception as e:
                print(f"[{user_email}] Failed to add objective email {msg_id} to mail label/category: {e}")
        if supabase_vectors_enabled():
            try:
                upsert_supabase_email_embedding(
                    user_email=user_email,
                    source_index=int((upserted or {}).get("source_index", 0)),
                    email_id=msg_id,
                    chunk_text=str((upserted or {}).get("raw_chunk") or "").strip() or chunk_text,
                )
            except Exception as e:
                print(f"[{user_email}] Supabase vector upsert failed: {e}")

        print(f"[{user_email}] Stored summary for: {subject}")
        print(f"[{user_email}] Finished email save for {subject} in {time.time() - started_at:.1f}s")

    if "SENT" in text:
        print(f"[{user_email}] Skipping sent email summary")


def gmail_message_time(msg: dict) -> str:
    internal_date = str((msg or {}).get("internalDate") or "").strip()
    if internal_date.isdigit():
        try:
            return datetime.datetime.fromtimestamp(int(internal_date) / 1000).isoformat(timespec="seconds")
        except Exception:
            pass
    return _safe_iso_now()


def process_gmail_message(user_email: str, service, msg: dict):
    msg_id = str((msg or {}).get("id") or "").strip()
    if not msg_id:
        return False

    headers = ((msg or {}).get("payload") or {}).get("headers", []) or []
    subject = next((h.get("value") for h in headers if h.get("name") == "Subject"), "(No Subject)") or "(No Subject)"
    sender = next((h.get("value") for h in headers if h.get("name") == "From"), "(Unknown Sender)") or "(Unknown Sender)"
    labels = msg.get("labelIds", []) or []
    direction = "SENT" if "SENT" in labels else "RECEIVED"
    parsed = extract_email_content(service, msg)
    full_body = parsed.get("body_text") or msg.get("snippet", "")
    email_text = (
        f"\nTime: {gmail_message_time(msg)}\n"
        f"sent or received email: {direction}\n"
        f"From: {sender}\n"
        f"Subject: {subject}\n"
        f"Body: {full_body[:20000]}\n"
    )

    attachment_text = process_attachments(get_attachments(service, msg))
    store_email_memory(user_email, email_text, sender, msg_id, attachment=attachment_text or "none")
    mark_id_processed(user_email, msg_id)
    print(f"[{user_email}] Gmail email summarized: {subject}")
    return True


def load_gmail_messages(user_email: str, limit: int = 10) -> int:
    started_at = time.time()
    service = get_gmail_service_for_user(user_email)
    stored_ids = get_stored_ids(user_email)
    results = service.users().messages().list(
        userId="me",
        q=GMAIL_QUERY,
        maxResults=max(1, min(int(limit or 10), 25)),
    ).execute()
    messages = results.get("messages", []) or []
    new_messages = [
        message for message in messages
        if str((message or {}).get("id") or "").strip()
        and str((message or {}).get("id") or "").strip() not in stored_ids
    ]
    print(f"[{user_email}] Gmail pull checked {len(messages)} message(s), {len(new_messages)} new")

    count = 0
    for item in reversed(new_messages):
        msg_id = str((item or {}).get("id") or "").strip()
        if not msg_id:
            continue
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        if process_gmail_message(user_email, service, msg):
            count += 1
    if count or new_messages:
        print(f"[{user_email}] Gmail pull finished in {time.time() - started_at:.1f}s, saved {count}")
    return count


def background_gmail_email_checker(user_email: str):
    thread_key = f"gmail:{user_email.lower()}"
    print(f"[{user_email}] Gmail save worker started")
    while True:
        try:
            load_gmail_messages(user_email, limit=5)
        except Exception as e:
            print(f"[{user_email}] Gmail save worker error:", traceback.format_exc())
            if isinstance(e, RefreshError) or "invalid_grant" in str(e):
                print(f"[{user_email}] Google token is expired/revoked. Reconnect this account at /gmail/sign.")
            with active_threads_lock:
                active_threads.discard(thread_key)
            return
        time.sleep(CHECK_INTERVAL)


def start_gmail_background_thread(user_email: str):
    user_email = str(user_email or "").strip()
    if not user_email:
        return False

    thread_key = f"gmail:{user_email.lower()}"
    with active_threads_lock:
        if thread_key in active_threads:
            return False
        active_threads.add(thread_key)

    thread = threading.Thread(target=background_gmail_email_checker, args=(user_email,), daemon=True)
    thread.start()
    return True


def run_gmail_save_worker(users=None, once: bool = False, limit: int = 10):
    selected_users = [str(user or "").strip() for user in (users or []) if str(user or "").strip()]
    if not selected_users:
        selected_users = get_gmail_cached_user_emails()
    if not selected_users:
        raise RuntimeError("No cached Gmail users found. Start app.py and sign in at /gmail/sign first.")

    if once:
        total = 0
        for user in selected_users:
            total += load_gmail_messages(user, limit=limit)
        return total

    for user in selected_users:
        start_gmail_background_thread(user)
    while True:
        time.sleep(3600)


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


def get_microsoft_access_token(user_email: str):
    cache = load_microsoft_token_cache()
    msal_app = build_microsoft_msal_app(cache)
    requested = str(user_email or "").strip().lower()
    account = None
    for candidate in msal_app.get_accounts():
        username = str(candidate.get("username") or "").strip().lower()
        if username and (not requested or username == requested):
            account = candidate
            break

    if not account:
        raise Exception(f"No saved Microsoft account found for {user_email or 'current user'}. Sign in with app.py at /sign first.")

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


def microsoft_sender_text(message: dict) -> str:
    sender = ((message or {}).get("from") or {}).get("emailAddress") or {}
    name = str(sender.get("name") or "").strip()
    address = str(sender.get("address") or "").strip()
    if name and address:
        return f"{name} <{address}>"
    return address or name or "(Unknown Sender)"


def microsoft_message_body_text(message: dict) -> str:
    body = (message or {}).get("body") or {}
    content = str(body.get("content") or "").strip()
    if content:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", content)
        text = re.sub(r"(?s)<br\s*/?>", "\n", text)
        text = re.sub(r"(?s)</p\s*>", "\n", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html_lib.unescape(text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = text.strip()
        if text:
            return text
    return str((message or {}).get("bodyPreview") or "").strip()


def process_microsoft_message(user_email: str, message: dict):
    msg_id = str((message or {}).get("id") or "").strip()
    if not msg_id:
        return False

    subject = str((message or {}).get("subject") or "(No Subject)").strip() or "(No Subject)"
    sender = microsoft_sender_text(message)
    received_time = str((message or {}).get("receivedDateTime") or _safe_iso_now()).strip()
    web_link = str((message or {}).get("webLink") or "").strip()
    body_text = microsoft_message_body_text(message)
    if not body_text:
        body_text = str((message or {}).get("bodyPreview") or "").strip()

    email_text = (
        f"\nTime: {received_time}\n"
        f"sent or received email: RECEIVED\n"
        f"From: {sender}\n"
        f"Subject: {subject}\n"
        f"WebLink: {web_link}\n"
        f"Body: {body_text[:20000]}\n"
    )

    store_email_memory(user_email, email_text, sender, msg_id, attachment="none")
    mark_id_processed(user_email, msg_id)
    print(f"[{user_email}] Microsoft email summarized: {subject}")
    return True


def get_microsoft_message_detail(token: str, message_id: str) -> dict:
    encoded_message_id = urllib.parse.quote(str(message_id or "").strip(), safe="")
    response, body = microsoft_graph_get(
        token,
        f"https://graph.microsoft.com/v1.0/me/messages/{encoded_message_id}",
        params={
            "$select": "id,subject,from,receivedDateTime,bodyPreview,body,webLink,isRead",
        },
    )
    if not response.ok:
        body_text = json.dumps(body, indent=2) if body is not None else response.text[:1000]
        raise Exception(f"Microsoft Graph message detail failed ({response.status_code}): {body_text}")
    return body or {}


def load_microsoft_messages(user_email: str, limit: int = 10) -> int:
    started_at = time.time()
    token = get_microsoft_access_token(user_email)
    stored_ids = get_stored_ids(user_email)
    response, body = microsoft_graph_get(
        token,
        "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
        params={
            "$top": max(1, min(int(limit or 10), 25)),
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,bodyPreview,webLink,isRead",
        },
    )
    if not response.ok:
        body_text = json.dumps(body, indent=2) if body is not None else response.text[:1000]
        raise Exception(f"Microsoft Graph inbox failed ({response.status_code}): {body_text}")

    messages = (body or {}).get("value") or []
    list_elapsed = time.time() - started_at
    new_messages = [
        message for message in messages
        if str((message or {}).get("id") or "").strip()
        and str((message or {}).get("id") or "").strip() not in stored_ids
    ]
    print(f"[{user_email}] Microsoft pull checked {len(messages)} message(s), {len(new_messages)} new, list took {list_elapsed:.1f}s")
    count = 0
    for message in reversed(new_messages):
        msg_id = str((message or {}).get("id") or "").strip()
        if not msg_id:
            continue
        detail_started = time.time()
        detailed_message = get_microsoft_message_detail(token, msg_id)
        print(f"[{user_email}] Microsoft detail fetched in {time.time() - detail_started:.1f}s for {str((message or {}).get('subject') or '')[:80]}")
        if process_microsoft_message(user_email, detailed_message or message):
            count += 1
    if count or new_messages:
        print(f"[{user_email}] Microsoft pull finished in {time.time() - started_at:.1f}s, saved {count}")
    return count


def background_microsoft_email_checker(user_email: str):
    thread_key = f"microsoft:{user_email.lower()}"
    print(f"[{user_email}] Microsoft save worker started")
    while True:
        try:
            load_microsoft_messages(user_email, limit=5)
        except Exception:
            print(f"[{user_email}] Microsoft save worker error:", traceback.format_exc())
            with active_threads_lock:
                active_threads.discard(thread_key)
            return
        time.sleep(CHECK_INTERVAL)


def start_microsoft_background_thread(user_email: str):
    user_email = str(user_email or "").strip()
    if not user_email:
        return False

    thread_key = f"microsoft:{user_email.lower()}"
    with active_threads_lock:
        if thread_key in active_threads:
            return False
        active_threads.add(thread_key)

    thread = threading.Thread(target=background_microsoft_email_checker, args=(user_email,), daemon=True)
    thread.start()
    return True


def run_microsoft_save_worker(users=None, once: bool = False, limit: int = 10):
    selected_users = [str(user or "").strip() for user in (users or []) if str(user or "").strip()]
    if not selected_users:
        selected_users = get_microsoft_cached_user_emails()
    if not selected_users:
        raise RuntimeError("No cached Microsoft users found. Start app.py and sign in at /sign first.")

    if once:
        total = 0
        for user in selected_users:
            total += load_microsoft_messages(user, limit=limit)
        return total

    for user in selected_users:
        start_microsoft_background_thread(user)
    while True:
        time.sleep(3600)


def selected_provider_users(provider: str, users=None, require_cached_for_requested: bool = False) -> list[str]:
    requested = [str(user or "").strip() for user in (users or []) if str(user or "").strip()]
    if requested:
        if require_cached_for_requested and provider in {"gmail", "microsoft"}:
            cached = (
                {email.lower() for email in get_gmail_cached_user_emails()}
                if provider == "gmail"
                else {email.lower() for email in get_microsoft_cached_user_emails()}
            )
            return [user for user in requested if user.lower() in cached]
        return requested
    if provider == "gmail":
        return get_gmail_cached_user_emails()
    if provider == "microsoft":
        return get_microsoft_cached_user_emails()
    out = []
    seen = set()
    for email in get_gmail_cached_user_emails() + get_microsoft_cached_user_emails():
        key = str(email or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(str(email).strip())
    return out


def run_save_worker(provider: str = "both", users=None, once: bool = False, limit: int = 10):
    provider = str(provider or "both").strip().lower()
    if provider not in {"gmail", "microsoft", "both"}:
        raise ValueError("provider must be gmail, microsoft, or both")

    if once:
        total = 0
        attempted = 0
        if provider in {"gmail", "both"}:
            gmail_users = selected_provider_users("gmail", users, require_cached_for_requested=(provider == "both"))
            try:
                attempted += len(gmail_users)
                total += run_gmail_save_worker(users=gmail_users, once=True, limit=limit)
            except RuntimeError:
                if provider == "gmail":
                    raise
        if provider in {"microsoft", "both"}:
            microsoft_users = selected_provider_users("microsoft", users, require_cached_for_requested=(provider == "both"))
            try:
                attempted += len(microsoft_users)
                total += run_microsoft_save_worker(users=microsoft_users, once=True, limit=limit)
            except RuntimeError:
                if provider == "microsoft":
                    raise
        if provider == "both" and not attempted:
            raise RuntimeError("No cached mail users found. Sign in with Gmail or Microsoft in app.py first.")
        return total

    started = 0
    if provider in {"gmail", "both"}:
        gmail_users = selected_provider_users("gmail", users, require_cached_for_requested=(provider == "both"))
        if provider == "gmail" and not gmail_users:
            raise RuntimeError("No cached Gmail users found. Start app.py and sign in at /gmail/sign first.")
        for user in gmail_users:
            if start_gmail_background_thread(user):
                started += 1

    if provider in {"microsoft", "both"}:
        microsoft_users = selected_provider_users("microsoft", users, require_cached_for_requested=(provider == "both"))
        if provider == "microsoft" and not microsoft_users:
            raise RuntimeError("No cached Microsoft users found. Start app.py and sign in at /sign first.")
        for user in microsoft_users:
            if start_microsoft_background_thread(user):
                started += 1

    if not started:
        raise RuntimeError("No cached mail users found. Sign in with Gmail or Microsoft in app.py first.")

    while True:
        time.sleep(3600)


def main():
    parser = argparse.ArgumentParser(description="Run the independent Condra email save worker.")
    parser.add_argument("--provider", choices=["gmail", "microsoft", "both"], default="both", help="Mail provider to poll.")
    parser.add_argument("--user", action="append", default=[], help="Account email to poll. Can be used more than once.")
    parser.add_argument("--once", action="store_true", help="Pull and summarize once, then exit.")
    parser.add_argument("--limit", type=int, default=10, help="Number of recent inbox messages to inspect per account.")
    parser.add_argument("--repair-completions", action="store_true", help="Fill missing objective completions for already-saved rows.")
    args = parser.parse_args()
    if args.repair_completions:
        users = selected_provider_users(args.provider, args.user)
        total = 0
        for user in users:
            total += repair_missing_objective_completions_for_user(user, limit=args.limit)
        print(f"Repaired {total} objective completion(s).")
        return
    count = run_save_worker(provider=args.provider, users=args.user, once=args.once, limit=args.limit)
    if args.once:
        print(f"Saved {count} new email(s).")


if __name__ == "__main__":
    main()
