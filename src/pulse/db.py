from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pulse import config

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    ts TEXT NOT NULL,
    service TEXT NOT NULL,
    success_rate REAL NOT NULL,
    p95_latency_ms REAL NOT NULL,
    queue_depth INTEGER NOT NULL,
    error_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_service_ts ON metrics (service, ts);

CREATE TABLE IF NOT EXISTS logs (
    ts TEXT NOT NULL,
    service TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_service_ts ON logs (service, ts);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    resolved_at TEXT,
    summary TEXT NOT NULL
);
"""


def to_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(TS_FORMAT)


def from_ts(ts: str) -> datetime:
    return datetime.strptime(ts, TS_FORMAT).replace(tzinfo=timezone.utc)


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = str(path) if path is not None else str(config.DB_PATH)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def reset(conn: sqlite3.Connection) -> None:
    conn.executescript("DELETE FROM metrics; DELETE FROM logs; DELETE FROM incidents;")
    conn.commit()


def insert_metrics(
    conn: sqlite3.Connection, rows: list[tuple[str, str, float, float, int, int]]
) -> None:
    conn.executemany("INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?)", rows)
    conn.commit()


def insert_logs(conn: sqlite3.Connection, rows: list[tuple[str, str, str, str]]) -> None:
    conn.executemany("INSERT INTO logs VALUES (?, ?, ?, ?)", rows)
    conn.commit()


def insert_incident(
    conn: sqlite3.Connection,
    service: str,
    title: str,
    severity: str,
    status: str,
    opened_at: str,
    resolved_at: str | None,
    summary: str,
) -> int:
    cursor = conn.execute(
        "INSERT INTO incidents (service, title, severity, status, opened_at, resolved_at, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (service, title, severity, status, opened_at, resolved_at, summary),
    )
    conn.commit()
    return int(cursor.lastrowid or 0)


def latest_ts(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(ts) AS ts FROM metrics").fetchone()
    return row["ts"] if row and row["ts"] else None


def fetch_metrics(
    conn: sqlite3.Connection,
    service: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if service:
        clauses.append("service = ?")
        params.append(service)
    if since:
        clauses.append("ts >= ?")
        params.append(since)
    if until:
        clauses.append("ts <= ?")
        params.append(until)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    cursor = conn.execute(f"SELECT * FROM metrics{where} ORDER BY ts", params)
    return [dict(row) for row in cursor.fetchall()]


def fetch_logs(
    conn: sqlite3.Connection,
    service: str | None = None,
    level: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if service:
        clauses.append("service = ?")
        params.append(service)
    if level:
        clauses.append("level = ?")
        params.append(level.upper())
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    cursor = conn.execute(f"SELECT * FROM logs{where} ORDER BY ts DESC LIMIT ?", params)
    return [dict(row) for row in cursor.fetchall()]


def fetch_incidents(
    conn: sqlite3.Connection,
    service: str | None = None,
    status: str | None = None,
    active_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if service:
        clauses.append("service = ?")
        params.append(service)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if active_only:
        clauses.append("status != 'resolved'")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    cursor = conn.execute(
        f"SELECT * FROM incidents{where} ORDER BY opened_at DESC, id DESC LIMIT ?", params
    )
    return [dict(row) for row in cursor.fetchall()]


def get_incident(conn: sqlite3.Connection, incident_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    return dict(row) if row else None
