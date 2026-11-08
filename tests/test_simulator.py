from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pulse import db, health, simulator
from pulse.config import SERVICES

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
POINTS_PER_SERVICE = 24 * 60 // 5 + 1


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    simulator.generate(connection, hours=24, interval_minutes=5, seed=42, now=NOW)
    yield connection
    connection.close()


def test_metric_row_count(conn):
    assert len(db.fetch_metrics(conn)) == POINTS_PER_SERVICE * len(SERVICES)


def test_latest_timestamp(conn):
    assert db.latest_ts(conn) == "2026-11-01T12:00:00Z"


def test_metric_ranges(conn):
    for row in db.fetch_metrics(conn):
        assert 0.0 <= row["success_rate"] <= 1.0
        assert row["p95_latency_ms"] > 0
        assert row["queue_depth"] >= 0
        assert row["error_count"] >= 0


def test_incidents_seeded(conn):
    assert len(db.fetch_incidents(conn)) == 4
    active = {i["service"] for i in db.fetch_incidents(conn, active_only=True)}
    assert active == {"trino", "flink"}


def test_error_logs_present(conn):
    assert db.fetch_logs(conn, service="flink", level="ERROR")
    assert db.fetch_logs(conn, service="spark", level="ERROR")


def test_health_reflects_scenarios(conn):
    statuses = {item["service"]: item["status"] for item in health.platform_health(conn)}
    assert statuses == {
        "spark": "healthy",
        "airflow": "healthy",
        "trino": "critical",
        "flink": "critical",
    }
    assert health.platform_status(health.platform_health(conn)) == "critical"


def test_same_seed_is_deterministic():
    first = db.connect(":memory:")
    second = db.connect(":memory:")
    simulator.generate(first, seed=7, now=NOW)
    simulator.generate(second, seed=7, now=NOW)
    assert db.fetch_metrics(first) == db.fetch_metrics(second)
    first.close()
    second.close()


def test_different_seed_differs():
    first = db.connect(":memory:")
    second = db.connect(":memory:")
    simulator.generate(first, seed=1, now=NOW)
    simulator.generate(second, seed=2, now=NOW)
    assert db.fetch_metrics(first) != db.fetch_metrics(second)
    first.close()
    second.close()
