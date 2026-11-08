from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pulse import db, health, simulator

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    simulator.generate(connection, hours=24, interval_minutes=5, seed=42, now=NOW)
    yield connection
    connection.close()


def test_perfect_metrics_score_100():
    assert health.score_metrics("spark", 0.996, 1800.0, 4.0) == 100.0


def test_success_penalty_is_capped():
    assert health.score_metrics("spark", 0.94, 1800.0, 4.0) == 60.0
    assert health.score_metrics("spark", 0.10, 1800.0, 4.0) == 60.0


def test_latency_penalty():
    assert health.score_metrics("flink", 0.996, 900.0, 2.0) == 85.0


def test_queue_penalty():
    assert health.score_metrics("trino", 0.996, 2400.0, 100.0) == 90.0


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, "healthy"),
        (90.0, "healthy"),
        (89.9, "degraded"),
        (70.0, "degraded"),
        (69.9, "critical"),
        (0.0, "critical"),
    ],
)
def test_status_boundaries(score, expected):
    assert health.status_for(score) == expected


def test_service_health_no_data():
    empty = db.connect(":memory:")
    result = health.service_health(empty, "spark")
    assert result["status"] == "no_data"
    assert result["score"] is None
    assert result["samples"] == 0
    empty.close()


def test_window_controls_sample_count(conn):
    assert health.service_health(conn, "flink", window_minutes=30)["samples"] == 7
    assert health.service_health(conn, "flink", window_minutes=5)["samples"] == 2


def test_open_incident_counts(conn):
    assert health.service_health(conn, "spark")["open_incidents"] == 0
    assert health.service_health(conn, "trino")["open_incidents"] == 1
    assert health.service_health(conn, "flink")["open_incidents"] == 1


def test_platform_status_picks_worst():
    assert health.platform_status([{"status": "healthy"}, {"status": "degraded"}]) == "degraded"
    assert health.platform_status([{"status": "degraded"}, {"status": "critical"}]) == "critical"
    assert health.platform_status([{"status": "healthy"}]) == "healthy"


def test_platform_status_no_data():
    assert health.platform_status([{"status": "no_data"}]) == "no_data"
    assert health.platform_status([]) == "no_data"
