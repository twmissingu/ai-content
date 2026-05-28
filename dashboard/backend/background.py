"""Background tasks — action scanner and budget monitor."""

import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from config.settings import ACTIONS_DIR, FAILED_DIR, PROCESSED_DIR, PROJECT_ROOT
from dashboard.backend.database import check_budget_limit
from dashboard.backend.feishu import alert_budget_warning

logger = logging.getLogger("gaoding.dashboard")

# Stop events for graceful shutdown
scanner_stop_event = threading.Event()
budget_stop_event = threading.Event()

DISPATCH_MAP = {
    "approve": ["python3", str(PROJECT_ROOT / "skills/publisher.py")],
    "reject": ["python3", str(PROJECT_ROOT / "skills/writer.py"), "--rewrite"],
    "rewrite": ["python3", str(PROJECT_ROOT / "skills/writer.py"), "--rewrite"],
}


def _dispatch_action(action: dict, file_path: Path) -> bool:
    """Dispatch an action to the appropriate agent script."""
    action_type = action.get("action")
    target_id = action.get("target_id", "")

    if action_type == "confirm":
        flag_file = PROJECT_ROOT / "queue/topics" / f"{target_id}.confirmed"
        flag_file.write_text(json.dumps(action, ensure_ascii=False, indent=2))
        return True

    cmd = DISPATCH_MAP.get(action_type)
    if not cmd:
        logger.warning(f"Unknown action type: {action_type}")
        return False

    full_cmd = cmd + [target_id]
    logger.info(f"Dispatching: {' '.join(full_cmd)}")
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True, text=True, timeout=300,
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            logger.error(f"Dispatch failed (rc={result.returncode}): {result.stderr[:200]}")
            return False
        logger.info(f"OK: {result.stdout[:100]}")
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout: {action_type}/{target_id}")
        return False
    except Exception as e:
        logger.error(f"Dispatch error: {e}")
        return False


def scan_loop():
    """Background thread: poll queue/actions/ every 10s."""
    while not scanner_stop_event.is_set():
        try:
            files = sorted(ACTIONS_DIR.glob("*.json"), key=os.path.getmtime)
            for f in files:
                try:
                    action = json.loads(f.read_text())
                    success = _dispatch_action(action, f)
                    dest = PROCESSED_DIR if success else FAILED_DIR
                    os.rename(f, dest / f.name)
                except (json.JSONDecodeError, OSError) as e:
                    logger.error(f"Error processing {f.name}: {e}")
                    os.rename(f, FAILED_DIR / f.name)
        except Exception as e:
            logger.error(f"Scanner loop error: {e}")
        scanner_stop_event.wait(10)


_last_budget_alert_time = 0


def budget_monitor_loop():
    """Background thread: monitor budget usage every 5 minutes."""
    global _last_budget_alert_time

    while not budget_stop_event.is_set():
        try:
            budget_status = check_budget_limit()
            current_time = time.time()

            if budget_status['is_warning'] and current_time - _last_budget_alert_time > 3600:
                alert_budget_warning(
                    budget_status['current_cost'],
                    budget_status['budget'],
                    budget_status['percentage'],
                )
                _last_budget_alert_time = current_time

            if budget_status['is_exceeded'] and current_time - _last_budget_alert_time > 1800:
                alert_budget_warning(
                    budget_status['current_cost'],
                    budget_status['budget'],
                    budget_status['percentage'],
                )
                _last_budget_alert_time = current_time

        except Exception as e:
            logger.error(f"Budget monitor error: {e}")

        budget_stop_event.wait(300)
