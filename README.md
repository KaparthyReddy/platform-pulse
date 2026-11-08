# platform-pulse

Customer-experience observability for a data platform. A Streamlit dashboard, a Slack bot, and an LLM triage agent all read the same telemetry through one MCP server.

Telemetry is simulated: metrics, logs, and incidents for Spark, Airflow, Trino, and Flink-style services. No real platform is required.

## Features

- Per-service health score (0-100) from success rate, p95 latency, and queue depth, with healthy / degraded / critical status.
- Streamlit dashboard: status banner, service cards, trend charts with SLO line, incident table, log viewer, and an agent panel.
- MCP server exposing health, incident, log, and runbook tools over stdio.
- Tool-calling triage agent that checks health, reads incidents, searches runbooks, and cites the runbook it used. Falls back to a deterministic offline summary when no API key is set or the API call fails.
- Slack bot (Socket Mode): `/platform-health`, `/incidents`, `/triage`, plus webhook alerts.
- Keyword-ranked runbook search over markdown files in `runbooks/`.

## Layout

```
src/pulse/
  simulator.py   seeded telemetry and incident scenarios
  db.py          SQLite schema and queries
  health.py      scoring and status rules
  runbooks.py    runbook parsing and ranked search
  mcp_server.py  FastMCP server (7 tools)
  agent.py       MCP client plus LLM tool-calling loop
  slack_bot.py   slash commands and webhook alerts
  dashboard.py   Streamlit app
runbooks/        markdown runbooks (Services, Keywords, Symptoms, Diagnosis, Mitigation, Escalation)
tests/           health, runbooks, simulator
```

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
make install
cp .env.example .env
make seed
make test
make dashboard
```

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Enables the LLM agent; offline mode without it | empty |
| `PULSE_MODEL` | Model used by the agent | `claude-sonnet-5-5` |
| `PULSE_DB_PATH` | SQLite file | `data/pulse.db` |
| `SLACK_BOT_TOKEN` | Bot token (`xoxb-`) for slash commands | empty |
| `SLACK_APP_TOKEN` | App-level token (`xapp-`) for Socket Mode | empty |
| `SLACK_ALERT_WEBHOOK_URL` | Incoming webhook for alerts | empty |

## Agent

```bash
python -m pulse.agent "Why is flink unhealthy and what should I do?"
```

The agent starts the MCP server as a subprocess, lists its tools, and loops until the model stops calling tools. Output ends with the mode (`llm` or `offline`) and the tools used.

## MCP server

```bash
python -m pulse.mcp_server
```

Tools: `get_platform_health`, `get_service_health`, `list_incidents`, `get_incident`, `get_recent_logs`, `search_runbooks`, `get_runbook`.

Any MCP client can use it, for example by registering the command `python -m pulse.mcp_server`.

## Slack setup

1. Create a Slack app and enable Socket Mode. Generate an app-level token with `connections:write` and set it as `SLACK_APP_TOKEN`.
2. Add the `commands` bot scope, install the app, and set the bot token as `SLACK_BOT_TOKEN`.
3. Create slash commands: `/platform-health`, `/incidents`, `/triage`.
4. Run `make bot`.
5. For alerts, add an incoming webhook, set `SLACK_ALERT_WEBHOOK_URL`, and run `python -m pulse.slack_bot --alert`.

Usage:

- `/platform-health`
- `/incidents trino` or `/incidents all`
- `/triage 4` or `/triage why is trino queueing?`

## Health scoring

Score starts at 100 and loses points for:

- success rate below the 99% SLO (up to 40)
- p95 latency above the per-service limit (up to 30)
- queue depth above the per-service limit (up to 30)

90 and above is healthy, 70 to 89.9 is degraded, below 70 is critical. Scores average the last 30 minutes by default.

## Simulated scenarios

| Service | Scenario | State |
| --- | --- | --- |
| spark | Executors killed for exceeding memory limits | resolved |
| airflow | Scheduler heartbeat stale | resolved |
| trino | Query queueing in main resource group | open |
| flink | Repeated checkpoint timeouts | open |

`python -m pulse.simulator --seed 7 --hours 12` regenerates data deterministically.

## Development

```bash
make test
make lint
```

CI runs ruff and pytest on Python 3.10, 3.11, and 3.12.

## Limitations

- Telemetry is synthetic; there are no real Prometheus, Splunk, or PagerDuty connectors.
- Runbook search is keyword scoring, not embeddings.
- The dashboard and bot read one local SQLite file.
