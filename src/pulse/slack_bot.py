from __future__ import annotations

import argparse
import sqlite3
import threading
from typing import Any

import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from pulse import agent, config, db, health
from pulse.config import SERVICES

STATUS_ICON = {
    "healthy": ":large_green_circle:",
    "degraded": ":large_yellow_circle:",
    "critical": ":red_circle:",
    "no_data": ":white_circle:",
}

_lock = threading.Lock()
_connection: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _connection
    with _lock:
        if _connection is None:
            _connection = db.connect()
        return _connection


def format_health(items: list[dict[str, Any]]) -> str:
    overall = health.platform_status(items)
    lines = [f"{STATUS_ICON[overall]} *Platform status: {overall}*"]
    for item in items:
        icon = STATUS_ICON.get(item["status"], STATUS_ICON["no_data"])
        if item["score"] is None:
            lines.append(f"{icon} *{item['service']}*: no data")
            continue
        lines.append(
            f"{icon} *{item['service']}* score {item['score']} | "
            f"success {item['success_rate'] * 100:.1f}% | "
            f"p95 {item['p95_latency_ms']:.0f} ms | "
            f"queue {item['queue_depth']:.0f} | "
            f"open incidents {item['open_incidents']}"
        )
    return "\n".join(lines)


def format_incidents(incidents: list[dict[str, Any]]) -> str:
    if not incidents:
        return "No matching incidents."
    lines = []
    for item in incidents:
        marker = ":white_check_mark:" if item["status"] == "resolved" else ":rotating_light:"
        lines.append(
            f"{marker} *#{item['id']} {item['severity']} {item['service']}*: {item['title']} "
            f"(opened {item['opened_at']}, {item['status']})"
        )
    return "\n".join(lines)


def build_alert_text(items: list[dict[str, Any]]) -> str | None:
    affected = [i for i in items if i["status"] in ("degraded", "critical")]
    if not affected:
        return None
    lines = [":rotating_light: *Platform Pulse alert*"]
    for item in affected:
        icon = STATUS_ICON[item["status"]]
        lines.append(
            f"{icon} *{item['service']}* is {item['status']} (score {item['score']}, "
            f"open incidents {item['open_incidents']})"
        )
    lines.append("Run `/triage` for next steps.")
    return "\n".join(lines)


def post_alert(text: str, url: str | None = None) -> None:
    target = url or config.SLACK_ALERT_WEBHOOK_URL
    if not target:
        raise RuntimeError("SLACK_ALERT_WEBHOOK_URL is not set")
    response = requests.post(target, json={"text": text}, timeout=10)
    response.raise_for_status()


def _footer(result: agent.AgentResult) -> str:
    tools = ", ".join(result.tools_used) or "none"
    return f"\n_via {result.mode} agent | tools: {tools}_"


def _parse_incident_args(text: str) -> tuple[str | None, bool]:
    tokens = text.lower().split()
    service = next((t for t in tokens if t in SERVICES), None)
    return service, "all" not in tokens


def build_app() -> App:
    app = App(token=config.SLACK_BOT_TOKEN)

    @app.command("/platform-health")
    def platform_health_command(ack, respond):
        ack()
        respond(text=format_health(health.platform_health(_db())), response_type="in_channel")

    @app.command("/incidents")
    def incidents_command(ack, respond, command):
        ack()
        service, active_only = _parse_incident_args(command.get("text", ""))
        incidents = db.fetch_incidents(_db(), service=service, active_only=active_only)
        respond(text=format_incidents(incidents), response_type="in_channel")

    @app.command("/triage")
    def triage_command(ack, respond, command):
        ack()
        text = command.get("text", "").strip()
        respond(text="Triaging, one moment...", response_type="in_channel")
        try:
            if text.lstrip("#").isdigit():
                result = agent.triage_incident(int(text.lstrip("#")))
            else:
                result = agent.ask(text or agent.DEFAULT_QUESTION)
        except Exception as error:
            respond(text=f"Triage failed: {error}", response_type="in_channel")
            return
        respond(text=result.answer + _footer(result), response_type="in_channel")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Platform Pulse Slack bot.")
    parser.add_argument("--alert", action="store_true", help="post one alert via webhook and exit")
    args = parser.parse_args()

    if args.alert:
        text = build_alert_text(health.platform_health(_db()))
        if text is None:
            print("all services healthy; no alert sent")
            return
        post_alert(text)
        print("alert sent")
        return

    if not config.SLACK_BOT_TOKEN or not config.SLACK_APP_TOKEN:
        raise SystemExit("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set")
    SocketModeHandler(build_app(), config.SLACK_APP_TOKEN).start()


if __name__ == "__main__":
    main()
