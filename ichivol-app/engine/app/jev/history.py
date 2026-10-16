"""SQLite history for Ève Shadow evaluations (observe-only)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("/data/jev-shadow/history.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=5)
    db.execute(
        "CREATE TABLE IF NOT EXISTS evaluations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "created_at TEXT NOT NULL, "
        "symbol TEXT NOT NULL, "
        "timeframe TEXT NOT NULL, "
        "original_decision TEXT, "
        "jev_result TEXT NOT NULL, "
        "latency_ms REAL, "
        "provider TEXT, "
        "response_model TEXT)"
    )
    # Additive columns for DBs created before V1-A.
    cols = {row[1] for row in db.execute("PRAGMA table_info(evaluations)")}
    if "provider" not in cols:
        db.execute("ALTER TABLE evaluations ADD COLUMN provider TEXT")
    if "response_model" not in cols:
        db.execute("ALTER TABLE evaluations ADD COLUMN response_model TEXT")
    return db


def save_evaluation(
    symbol: str,
    timeframe: str,
    original_decision: Any,
    jev_result: Any,
    latency_ms: float,
    *,
    provider: str | None = None,
    response_model: str | None = None,
) -> None:
    with _connect() as db:
        db.execute(
            "INSERT INTO evaluations "
            "(created_at,symbol,timeframe,original_decision,jev_result,latency_ms,provider,response_model) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                symbol,
                timeframe,
                original_decision,
                json.dumps(jev_result),
                latency_ms,
                provider,
                response_model,
            ),
        )


def list_evaluations(limit: int = 50) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    with _connect() as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT * FROM evaluations ORDER BY id DESC LIMIT ?",
            (min(max(int(limit), 1), 100),),
        )
        return [dict(row) for row in rows]
