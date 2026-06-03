"""Background tasks — action scanner, token/trail importer, budget monitor.

All Agent-produced data flows through file queues:
- queue/actions/   → action scanner (non-blocking Popen dispatch)
- queue/tokens/    → token importer (into SQLite)
- queue/trails/    → trail importer (into SQLite pipeline_traces)
"""

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from config.settings import FAILED_DIR, PROJECT_ROOT, TOKENS_DIR, TRAIL_DIR
from dashboard.backend.database import check_budget_limit, log_token_usage, create_trace, complete_trace, update_trace_duration, create_pipeline_session, update_pipeline_session
from dashboard.backend.feishu import alert_budget_warning, alert_agent_error
from skills.action import mark_processed, scan_actions, write_action

logger = logging.getLogger("gaoding.dashboard")


class Poller:
    """Unified polling loop with configurable interval, stop event, and error handling.

    Wraps the common pattern of:
        while not stop_event.is_set():
            try:
                target()
            except Exception as e:
                logger.error(...)
            stop_event.wait(interval)
    """

    def __init__(self, name: str, interval: float, target, stop_event: threading.Event | None = None):
        self.name = name
        self.interval = interval
        self.target = target
        self._stop = stop_event or threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, name=f"poller-{self.name}", daemon=True)
        self._thread.start()
        logger.info(f"Poller[{self.name}] started ({self.interval}s interval)")

    def stop(self):
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.target()
            except Exception as e:
                logger.error(f"Poller[{self.name}] error: {e}")
                alert_agent_error(f"poller-{self.name}", str(e))
            self._stop.wait(self.interval)


_PYTHON = sys.executable or "python3"

DISPATCH_MAP = {
    "confirm": [_PYTHON, str(PROJECT_ROOT / "skills/writer_router.py")],
    "approve": [_PYTHON, str(PROJECT_ROOT / "skills/publisher.py")],
    "reject": [_PYTHON, str(PROJECT_ROOT / "skills/writer.py"), "--rewrite"],
    "rewrite": [_PYTHON, str(PROJECT_ROOT / "skills/writer.py"), "--rewrite"],
}


def _dispatch_action_async(action: dict) -> int:
    """Non-blocking dispatch: Popen and return PID immediately.

    Subprocess status is reported back via queue/status/ files.
    Does NOT block the scanner loop.
    """
    action_type = action.get("action")
    target_id = action.get("target_id", "")

    # Sanitize target_id: only allow safe characters to prevent injection
    if target_id and not re.fullmatch(r'[a-zA-Z0-9._-]+', target_id):
        logger.error(f"Rejected target_id with unsafe characters: {target_id!r}")
        return -1

    if action_type == "confirm":
        # Legacy confirm -> also write action file for backward compat
        write_action(
            "confirm", target_id,
            trigger_agent="dashboard",
        )

    cmd = DISPATCH_MAP.get(action_type)
    if not cmd:
        logger.warning(f"Unknown action type: {action_type}")
        return -1

    full_cmd = cmd + [target_id]
    logger.info(f"Dispatching async: {' '.join(full_cmd)}")
    try:
        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=PROJECT_ROOT,
        )
        logger.info(f"Dispatched {action_type}/{target_id} (PID: {proc.pid})")
        return proc.pid
    except Exception as e:
        logger.error(f"Dispatch error for {action_type}/{target_id}: {e}")
        alert_agent_error(f"dispatch-{action_type}", str(e))
        return -1


def scan_actions_target():
    """Polling target: scan queue/actions/ for new action files."""
    actions = scan_actions()
    for action in actions:
        source_path = Path(action.get("_source_path", ""))
        if not source_path.exists():
            continue
        pid = _dispatch_action_async(action)
        if pid >= 0:
            mark_processed(source_path)
        else:
            FAILED_DIR.mkdir(parents=True, exist_ok=True)
            source_path.rename(FAILED_DIR / source_path.name)


def import_tokens_target():
    """Polling target: import token usage JSON files into SQLite."""
    failed_dir = TOKENS_DIR / "failed"
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(TOKENS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    for f in files:
        try:
            data = json.loads(f.read_text())
            log_token_usage(
                agent=data.get("agent", "unknown"),
                model=data.get("model", "unknown"),
                input_tokens=data.get("input_tokens", 0),
                output_tokens=data.get("output_tokens", 0),
                session_id=data.get("session_id"),
            )
            f.unlink()
        except Exception as e:
            logger.warning(f"Token import failed for {f.name}, moving to failed/: {e}")
            f.rename(failed_dir / f.name)


def import_trails_target():
    """Polling target: import trail JSON files into SQLite pipeline_traces.

    Expects paired files: {id}.start.json and {id}.end.json.
    On .start.json: create_trace()
    On .end.json: complete_trace() + update_trace_duration()
    """
    TRAIL_DIR.mkdir(parents=True, exist_ok=True)
    start_files = list(TRAIL_DIR.glob("*.start.json"))

    processed = set()
    for f in sorted(start_files, key=lambda x: x.stat().st_mtime):
        trail_id = f.stem.replace(".start", "")
        if trail_id in processed:
            continue
        end_file = TRAIL_DIR / f"{trail_id}.end.json"

        try:
            start_data = json.loads(f.read_text())

            if end_file.exists():
                _sid = start_data.get("session_id")
                if _sid is None:
                    _sid = create_pipeline_session(
                        date=trail_id.split("-")[-1][:8] if any(c.isdigit() for c in trail_id) else "unknown",
                        period="manual",
                        topic=f"{start_data.get('agent', '?')}:{start_data.get('stage_name', start_data.get('stage', '?'))}",
                    )
                end_data = json.loads(end_file.read_text())
                trace_id = create_trace(
                    session_id=_sid,
                    agent=start_data.get("agent", "unknown"),
                    stage=start_data.get("stage", "unknown"),
                    stage_name=start_data.get("stage_name"),
                )
                complete_trace(
                    trace_id,
                    status=end_data.get("status", "completed"),
                )
                if end_data.get("duration_ms"):
                    update_trace_duration(trace_id, end_data["duration_ms"])
                trail_status = end_data.get("status", "completed")
                session_status = "completed" if trail_status == "completed" else "failed"
                try:
                    update_pipeline_session(
                        _sid,
                        status=session_status,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )
                except Exception as e:
                    logger.warning(f"Failed to update session {_sid} status: {e}")
                f.unlink()
                end_file.unlink()
                processed.add(trail_id)
        except Exception as e:
            logger.debug(f"Trail import failed for {trail_id}: {e}")

    # Cleanup stale .start.json files older than 2 hours with no matching .end.json
    now = time.time()
    for f in TRAIL_DIR.glob("*.start.json"):
        if now - f.stat().st_mtime > 7200:
            trail_id = f.stem.replace(".start", "")
            end_file = TRAIL_DIR / f"{trail_id}.end.json"
            if not end_file.exists():
                logger.warning(f"Removing stale trail start file: {f.name}")
                f.unlink()


_last_budget_alert_time = 0


def budget_monitor_target():
    """Polling target: check budget usage and alert if needed."""
    global _last_budget_alert_time

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


# Register all pollers
_pollers = [
    Poller(name="action-scanner", interval=10, target=scan_actions_target),
    Poller(name="token-importer", interval=15, target=import_tokens_target),
    Poller(name="trail-importer", interval=15, target=import_trails_target),
    Poller(name="budget-monitor", interval=300, target=budget_monitor_target),
]


def start_all_pollers() -> list[Poller]:
    """Start all registered pollers."""
    for p in _pollers:
        p.start()
    return _pollers


def stop_all_pollers():
    """Signal all pollers to stop."""
    for p in _pollers:
        p.stop()
