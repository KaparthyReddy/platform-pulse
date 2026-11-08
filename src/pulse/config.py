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


SERVICES = ("spark", "airflow", "trino", "flink")
