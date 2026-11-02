from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("PULSE_DB_PATH", str(ROOT / "data" / "pulse.db")))
RUNBOOK_DIR = ROOT / "runbooks"

MODEL = os.getenv("PULSE_MODEL", "claude-sonnet-5-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
SLACK_ALERT_WEBHOOK_URL = os.getenv("SLACK_ALERT_WEBHOOK_URL", "")

SERVICES = ("spark", "airflow", "trino", "flink")
