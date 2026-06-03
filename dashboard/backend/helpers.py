"""Shared helper functions for dashboard routes."""

import json
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
    """Load schedule config via config_service (single source of truth)."""
    from dashboard.backend.config_service import get_schedule_config
    return get_schedule_config()
