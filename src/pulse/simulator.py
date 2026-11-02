from __future__ import annotations

import argparse
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pulse import db
from pulse.config import SERVICES

BASELINE = {
    "spark": {"latency": 1800.0, "queue": 4.0, "errors": 1.0},
    "airflow": {"latency": 900.0, "queue": 6.0, "errors": 0.8},
    "trino": {"latency": 2400.0, "queue": 8.0, "errors": 1.2},
    "flink": {"latency": 350.0, "queue": 2.0, "errors": 0.6},
}

INFO_LOGS = {
    "spark": "Stage completed successfully",
    "airflow": "DAG run completed",
    "trino": "Query finished",
    "flink": "Checkpoint completed",
}

RAMP_SECONDS = 900.0


@dataclass(frozen=True)
class Scenario:
    service: str
    title: str
    severity: str
    status: str
    start_hours_ago: float
    duration_hours: float | None
    log_level: str
    log_message: str
    summary: str


SCENARIOS = (
    Scenario(
        service="spark",
        title="Executors lost: containers killed for exceeding memory limits",
        severity="SEV2",
        status="resolved",
        start_hours_ago=20.0,
        duration_hours=2.0,
        log_level="ERROR",
        log_message="ExecutorLostFailure: Container killed by YARN for exceeding memory limits",
        summary=(
            "Spark executors were lost after YARN killed containers for exceeding memory limits. "
            "ETL jobs from three teams retried or failed. Resolved by raising memoryOverhead and "
            "increasing shuffle partitions."
        ),
    ),
    Scenario(
        service="airflow",
        title="Scheduler heartbeat stale; DAGs delayed",
        severity="SEV3",
        status="resolved",
        start_hours_ago=9.0,
        duration_hours=1.5,
        log_level="WARN",
        log_message="Scheduler heartbeat age exceeded 30s; tasks stuck in queued state",
        summary=(
            "The Airflow scheduler heartbeat went stale and scheduled DAGs started late. "
            "Resolved by restarting the scheduler and trimming slow DAG file parsing."
        ),
    ),
    Scenario(
        service="trino",
        title="Query queueing above 100 in main resource group",
        severity="SEV2",
        status="open",
        start_hours_ago=3.0,
        duration_hours=None,
        log_level="WARN",
        log_message="Query queued: resource group main exceeded hard concurrency limit",
        summary=(
            "Trino queries are queued behind the main resource group's concurrency limit. "
            "Analytics users report dashboard timeouts. One team's heavy queries dominate the group."
        ),
    ),
    Scenario(
        service="flink",
        title="Repeated checkpoint timeouts; consumer lag growing",
        severity="SEV1",
        status="open",
        start_hours_ago=1.5,
        duration_hours=None,
        log_level="ERROR",
        log_message="Checkpoint expired before completing; alignment timeout on sink operator",
        summary=(
            "Flink checkpoints are timing out repeatedly and the job is restarting in a loop. "
            "Consumer lag is growing for downstream streaming pipelines."
        ),
    ),
)


def _intensity(ts: datetime, start: datetime, end: datetime | None) -> float:
    if ts < start or (end is not None and ts > end):
        return 0.0
    ramp = min(1.0, (ts - start).total_seconds() / RAMP_SECONDS)
    if end is None:
        return ramp
    tail = min(1.0, (end - ts).total_seconds() / RAMP_SECONDS)
    return min(ramp, tail)


def generate(
    conn: sqlite3.Connection,
    hours: int = 24,
    interval_minutes: int = 5,
    seed: int = 42,
    now: datetime | None = None,
) -> dict[str, int]:
    rng = random.Random(seed)
    end = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    steps = int(hours * 60 / interval_minutes)
    timeline = [end - timedelta(minutes=interval_minutes * (steps - i)) for i in range(steps + 1)]

    windows: dict[str, tuple[Scenario, datetime, datetime | None]] = {}
    for scenario in SCENARIOS:
        start = end - timedelta(hours=scenario.start_hours_ago)
        stop = (
            None
            if scenario.duration_hours is None
            else start + timedelta(hours=scenario.duration_hours)
        )
        windows[scenario.service] = (scenario, start, stop)

    metric_rows: list[tuple[str, str, float, float, int, int]] = []
    log_rows: list[tuple[str, str, str, str]] = []

    for index, ts in enumerate(timeline):
        stamp = db.to_ts(ts)
        for service in SERVICES:
            base = BASELINE[service]
            window = windows.get(service)
            intensity = _intensity(ts, window[1], window[2]) if window else 0.0

            success = min(1.0, max(0.0, 0.996 - rng.uniform(0.0, 0.003) - 0.12 * intensity))
            latency = base["latency"] * rng.uniform(0.9, 1.1) * (1 + 2 * intensity)
            queue = int(max(0.0, rng.gauss(base["queue"], 1.5) + 60 * intensity))
            errors = int(max(0.0, rng.gauss(base["errors"], 1.0) + 30 * intensity))
            metric_rows.append((stamp, service, round(success, 4), round(latency, 1), queue, errors))

            if window and intensity > 0:
                log_rows.append((stamp, service, window[0].log_level, window[0].log_message))
            elif index % 6 == 0:
                log_rows.append((stamp, service, "INFO", INFO_LOGS[service]))

    db.insert_metrics(conn, metric_rows)
    db.insert_logs(conn, log_rows)

    for scenario, start, stop in windows.values():
        db.insert_incident(
            conn,
            scenario.service,
            scenario.title,
            scenario.severity,
            scenario.status,
            db.to_ts(start),
            db.to_ts(stop) if stop else None,
            scenario.summary,
        )

    return {
        "metrics": len(metric_rows),
        "logs": len(log_rows),
        "incidents": len(windows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed simulated platform telemetry.")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    conn = db.connect()
    db.reset(conn)
    counts = generate(conn, hours=args.hours, interval_minutes=args.interval, seed=args.seed)
    print(
        f"seeded {counts['metrics']} metrics, {counts['logs']} logs, "
        f"{counts['incidents']} incidents"
    )


if __name__ == "__main__":
    main()
