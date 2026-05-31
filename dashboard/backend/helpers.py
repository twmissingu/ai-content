"""Shared helper functions for dashboard routes."""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from config.settings import CONFIG_DIR

logger = logging.getLogger("gaoding.dashboard")


def read_json(path: Path) -> dict:
    """Read and parse a JSON file, returning empty dict on failure."""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def detect_timeout(status: dict, max_minutes: int = 30) -> bool:
    """Detect if an agent has timed out based on its started_at timestamp."""
    started = status.get("started_at", "")
    if not started:
        return False
    try:
        start = datetime.strptime(started.split(".")[0], "%Y%m%d_%H%M%S")
        elapsed = (datetime.now() - start).total_seconds() / 60
        return elapsed > max_minutes
    except (ValueError, TypeError):
        return False


def load_schedule() -> dict:
    """Load schedule config, falling back to defaults."""
    path = CONFIG_DIR / "schedule.json"
    if path.exists():
        return read_json(path)
    return {
        "morning_scout": "09:00",
        "morning_writer": "09:30",
        "evening_scout": "14:00",
        "evening_writer": "14:30",
        "working_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "monthly_budget": 15.0,
        "quality_threshold": 70,
    }
