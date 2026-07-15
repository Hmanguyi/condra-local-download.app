"""Small SQLite-backed replacement for the PostgREST calls used by Condra.

Rows are stored as JSON so the existing application can keep its current data
shape without requiring a schema migration whenever an email field changes.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path


def database_path() -> Path:
    configured = str(os.getenv("CONDRA_LOCAL_DB", "")).strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(__file__).resolve().parent / "instance" / "condra.sqlite3").resolve()


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS local_records (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               table_name TEXT NOT NULL,
               data TEXT NOT NULL
           )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS local_records_table_idx ON local_records(table_name)"
    )
    return connection


def _records(connection: sqlite3.Connection, table: str):
    return [
        (int(row["id"]), json.loads(row["data"]))
        for row in connection.execute(
            "SELECT id, data FROM local_records WHERE table_name = ?", (table,)
        )
    ]


def _matches(row: dict, params: dict) -> bool:
    reserved = {"select", "order", "limit", "offset", "on_conflict"}
    for field, expression in params.items():
        if field in reserved:
            continue
        value = row.get(field)
        expression = str(expression)
        if expression.startswith("eq."):
            expected = expression[3:]
            if str(value if value is not None else "") != expected:
                return False
        else:
            if str(value if value is not None else "") != expression:
                return False
    return True


def _project(row: dict, select: str) -> dict:
    if not select or select == "*":
        return dict(row)
    fields = [field.strip() for field in select.split(",") if field.strip()]
    return {field: row.get(field) for field in fields}


def request(method: str, table: str, query_params=None, body=None, prefer: str = ""):
    """Execute the subset of PostgREST semantics used by app.py/saveApp.py."""
    del prefer
    method = method.upper()
    params = dict(query_params or {})
    with _connect() as connection:
        records = _records(connection, table)

        if method == "GET":
            rows = [row for _, row in records if _matches(row, params)]
            order = str(params.get("order", "")).strip()
            if order:
                field, _, direction = order.partition(".")
                rows.sort(
                    key=lambda row: (row.get(field) is None, row.get(field)),
                    reverse=direction.lower() == "desc",
                )
            offset = int(params.get("offset", 0) or 0)
            limit = params.get("limit")
            rows = rows[offset:offset + int(limit)] if limit is not None else rows[offset:]
            return [_project(row, str(params.get("select", "*"))) for row in rows]

        if method == "POST":
            incoming = body if isinstance(body, list) else [body]
            conflict_fields = [
                field.strip()
                for field in str(params.get("on_conflict", "")).split(",")
                if field.strip()
            ]
            returned = []
            for item in incoming:
                row = dict(item or {})
                existing = None
                if conflict_fields:
                    existing = next(
                        (
                            (record_id, saved)
                            for record_id, saved in records
                            if all(saved.get(field) == row.get(field) for field in conflict_fields)
                        ),
                        None,
                    )
                if existing:
                    record_id, saved = existing
                    saved.update(row)
                    connection.execute(
                        "UPDATE local_records SET data = ? WHERE id = ?",
                        (json.dumps(saved, ensure_ascii=False), record_id),
                    )
                    returned.append(saved)
                else:
                    cursor = connection.execute(
                        "INSERT INTO local_records(table_name, data) VALUES (?, ?)",
                        (table, json.dumps(row, ensure_ascii=False)),
                    )
                    records.append((int(cursor.lastrowid), row))
                    returned.append(row)
            return returned

        matching = [(record_id, row) for record_id, row in records if _matches(row, params)]
        if method == "PATCH":
            returned = []
            for record_id, row in matching:
                row.update(dict(body or {}))
                connection.execute(
                    "UPDATE local_records SET data = ? WHERE id = ?",
                    (json.dumps(row, ensure_ascii=False), record_id),
                )
                returned.append(row)
            return returned
        if method == "DELETE":
            connection.executemany(
                "DELETE FROM local_records WHERE id = ?",
                [(record_id,) for record_id, _ in matching],
            )
            return [row for _, row in matching]
        raise ValueError(f"Unsupported local storage method: {method}")


def _vector(value) -> list[float]:
    if isinstance(value, str):
        value = json.loads(value)
    return [float(item) for item in (value or [])]


def vector_match(payload: dict):
    """Local equivalent of match_email_embeddings, using cosine similarity."""
    user_email = payload.get("p_user_email") or payload.get("user_email") or ""
    query = _vector(payload.get("query_embedding"))
    match_count = int(payload.get("match_count", 40) or 40)
    if not query:
        return []
    query_norm = math.sqrt(sum(value * value for value in query)) or 1.0
    rows = request("GET", "email_embeddings", {"user_email": f"eq.{user_email}"})
    scored = []
    for row in rows:
        embedding = _vector(row.get("embedding"))
        if len(embedding) != len(query):
            continue
        norm = math.sqrt(sum(value * value for value in embedding)) or 1.0
        score = sum(a * b for a, b in zip(query, embedding)) / (query_norm * norm)
        result = dict(row)
        result["similarity"] = score
        scored.append(result)
    scored.sort(key=lambda row: row["similarity"], reverse=True)
    return scored[:match_count]
