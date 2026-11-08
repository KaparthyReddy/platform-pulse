from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("PULSE_DB_PATH", str(ROOT / "data" / "pulse.db")))
RUNBOOK_DIR = ROOT / "runbooks"

PROVIDER = os.getenv("PULSE_PROVIDER", "auto")
MODEL = os.getenv("PULSE_MODEL", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_BASE_URL = os.getenv("PULSE_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("PULSE_API_KEY", "ollama")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
SLACK_ALERT_WEBHOOK_URL = os.getenv("SLACK_ALERT_WEBHOOK_URL", "")

SERVICES = ("spark", "airflow", "trino", "flink")
