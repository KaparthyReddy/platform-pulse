from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import Any

from pulse import db
from pulse.config import SERVICES

SLO_SUCCESS_RATE = 0.99
LATENCY_LIMIT_MS = {"spark": 3000.0, "airflow": 1500.0, "trino": 4000.0, "flink": 600.0}
QUEUE_LIMIT = {"spark": 20.0, "airflow": 20.0, "trino": 50.0, "flink": 10.0}

STATUS_RANK = {"healthy": 0, "degraded": 1, "critical": 2}


def status_for(score: float) -> str:
    if score >= 90:
        return "healthy"
    if score >= 70:
        return "degraded"
    return "critical"


def score_metrics(
    service: str, success_rate: float, p95_latency_ms: float, queue_depth: float
) -> float:
    success_penalty = min(40.0, max(0.0, SLO_SUCCESS_RATE - success_rate) * 1000)
    latency_penalty = min(30.0, max(0.0, p95_latency_ms / LATENCY_LIMIT_MS[service] - 1) * 30)
    queue_penalty = min(30.0, max(0.0, queue_depth / QUEUE_LIMIT[service] - 1) * 10)
    return round(100.0 - success_penalty - latency_penalty - queue_penalty, 1)


def service_health(
    conn: sqlite3.Connection,
    service: str,
    window_minutes: int = 30,
    reference_ts: str | None = None,
) -> dict[str, Any]:
    reference = reference_ts or db.latest_ts(conn)
    open_incidents = len(db.fetch_incidents(conn, service=service, active_only=True))
    empty: dict[str, Any] = {
        "service": service,
        "score": None,
        "status": "no_data",
        "success_rate": None,
        "p95_latency_ms": None,
        "queue_depth": None,
        "error_count": 0,
        "open_incidents": open_incidents,
        "samples": 0,
        "as_of": reference,
    }
    if reference is None:
        return empty

    since = db.to_ts(db.from_ts(reference) - timedelta(minutes=window_minutes))
    rows = db.fetch_metrics(conn, service=service, since=since, until=reference)
    if not rows:
        return empty

    count = len(rows)
    success = sum(r["success_rate"] for r in rows) / count
    latency = sum(r["p95_latency_ms"] for r in rows) / count
    queue = sum(r["queue_depth"] for r in rows) / count
    errors = sum(r["error_count"] for r in rows)
    score = score_metrics(service, success, latency, queue)

    return {
        "service": service,
        "score": score,
        "status": status_for(score),
        "success_rate": round(success, 4),
        "p95_latency_ms": round(latency, 1),
        "queue_depth": round(queue, 1),
        "error_count": errors,
        "open_incidents": open_incidents,
        "samples": count,
        "as_of": reference,
    }


def platform_health(conn: sqlite3.Connection, window_minutes: int = 30) -> list[dict[str, Any]]:
    return [service_health(conn, service, window_minutes) for service in SERVICES]


def platform_status(items: list[dict[str, Any]]) -> str:
    ranked = [STATUS_RANK[i["status"]] for i in items if i["status"] in STATUS_RANK]
    if not ranked:
        return "no_data"
    worst = max(ranked)
    return next(name for name, rank in STATUS_RANK.items() if rank == worst)
