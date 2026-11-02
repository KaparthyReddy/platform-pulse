from __future__ import annotations

import json
import sqlite3
from typing import Any

from mcp.server.fastmcp import FastMCP

from pulse import db, health, runbooks
from pulse.config import SERVICES

mcp = FastMCP("platform-pulse")

_connection: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = db.connect()
    return _connection


def _check_service(service: str) -> str:
    value = service.lower()
    if value not in SERVICES:
        raise ValueError(f"unknown service '{service}'; expected one of {', '.join(SERVICES)}")
    return value


def _dump(payload: Any) -> str:
    return json.dumps(payload, default=str)


@mcp.tool()
def get_platform_health(window_minutes: int = 30) -> str:
    """Health score, status, success rate, p95 latency, queue depth and open incident count for every service."""
    return _dump(health.platform_health(_db(), window_minutes))


@mcp.tool()
def get_service_health(service: str, window_minutes: int = 30) -> str:
    """Health details for one service: spark, airflow, trino or flink."""
    return _dump(health.service_health(_db(), _check_service(service), window_minutes))


@mcp.tool()
def list_incidents(service: str | None = None, active_only: bool = True, limit: int = 20) -> str:
    """List incidents, newest first. Set active_only to false to include resolved incidents."""
    target = _check_service(service) if service else None
    return _dump(db.fetch_incidents(_db(), service=target, active_only=active_only, limit=limit))


@mcp.tool()
def get_incident(incident_id: int) -> str:
    """Full details for a single incident by id."""
    incident = db.get_incident(_db(), incident_id)
    if incident is None:
        return _dump({"error": f"incident {incident_id} not found"})
    return _dump(incident)


@mcp.tool()
def get_recent_logs(service: str, level: str | None = None, limit: int = 20) -> str:
    """Most recent log lines for a service. Optional level filter: INFO, WARN or ERROR."""
    return _dump(db.fetch_logs(_db(), service=_check_service(service), level=level, limit=limit))


@mcp.tool()
def search_runbooks(query: str, service: str | None = None, limit: int = 3) -> str:
    """Search operational runbooks by symptoms or keywords. Returns ranked matches with names."""
    target = _check_service(service) if service else None
    return _dump(runbooks.search_runbooks(query, service=target, limit=limit))


@mcp.tool()
def get_runbook(name: str) -> str:
    """Diagnosis, mitigation and escalation steps for a runbook, by name from search_runbooks."""
    runbook = runbooks.get_runbook(name)
    if runbook is None:
        return _dump({"error": f"runbook '{name}' not found"})
    return _dump(runbook)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
