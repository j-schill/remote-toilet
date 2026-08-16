from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("REMOTE_TOILET_DB_PATH", "remote_toilet.db"))


def get_db_path() -> Path:
    return Path(DB_PATH).expanduser()


def get_db_connection(
    db_path: str | os.PathLike[str] | None = None,
) -> sqlite3.Connection:
    target = Path(db_path) if db_path is not None else get_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_history (
            id TEXT PRIMARY KEY,
            robot_id TEXT NOT NULL,
            event_type TEXT,
            event_time TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_history_robot_time ON usage_history(robot_id, event_time)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_history_event_time ON usage_history(event_type, event_time)"
    )
    return conn


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OSError, TypeError, OverflowError, ValueError):
            return None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        candidate_formats = [
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in candidate_formats:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def _normalize_event_type(record: dict[str, Any]) -> str:
    for key in ("event_type", "type", "status", "name", "description"):
        value = record.get(key)
        if value:
            return str(value)
    return "usage"


def _pick_timestamp(record: dict[str, Any]) -> str | None:
    for key in (
        "timestamp",
        "time",
        "event_time",
        "date",
        "created_at",
        "last_updated",
    ):
        if key in record:
            dt = _coerce_datetime(record[key])
            if dt is not None:
                return dt.isoformat()
    return None


def _make_record_id(robot_id: str, record: dict[str, Any]) -> str:
    event_id = (
        record.get("id")
        or record.get("event_id")
        or record.get("cycle_id")
        or _pick_timestamp(record)
        or str(record)
    )
    raw = f"{robot_id}|{_normalize_event_type(record)}|{event_id}"
    return sha256(raw.encode("utf-8")).hexdigest()


def normalize_usage_record(robot_id: str, record: dict[str, Any]) -> dict[str, Any]:
    event_type = _normalize_event_type(record)
    event_time = _pick_timestamp(record) or datetime.utcnow().isoformat()
    return {
        "id": _make_record_id(robot_id, record),
        "robot_id": str(robot_id),
        "event_type": event_type,
        "event_time": event_time,
        "raw_json": json.dumps(record, default=str, sort_keys=True),
    }


def store_new_usage_records(
    conn: sqlite3.Connection, robot_id: str, records: Iterable[dict[str, Any]]
) -> int:
    inserted = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        normalized = normalize_usage_record(robot_id, record)
        cursor = conn.execute(
            "SELECT 1 FROM usage_history WHERE id = ?",
            (normalized["id"],),
        )
        if cursor.fetchone():
            continue

        conn.execute(
            """
            INSERT INTO usage_history (id, robot_id, event_type, event_time, raw_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                normalized["id"],
                normalized["robot_id"],
                normalized["event_type"],
                normalized["event_time"],
                normalized["raw_json"],
            ),
        )
        inserted += 1

    conn.commit()
    return inserted


def iter_recent_usage_records(days_back: int = 14) -> list[dict[str, Any]]:
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT robot_id, event_type, event_time, raw_json FROM usage_history WHERE event_time >= ? ORDER BY event_time ASC",
        (cutoff.isoformat(),),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def is_clean_cycle_complete(event_name: str | None) -> bool:
    if event_name is None:
        return False
    cleaned = event_name.strip().lower().replace("_", " ")
    return (
        "clean cycle complete" in cleaned
        or "clean cycle" in cleaned
        or "cycle complete" in cleaned
    )
