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
import threading
import time
from pathlib import Path

from config.settings import FAILED_DIR, PROJECT_ROOT, TOKENS_DIR, TRAIL_DIR
from dashboard.backend.database import check_budget_limit, log_token_usage, create_trace, complete_trace, update_trace_duration, create_pipeline_session
from dashboard.backend.feishu import alert_budget_warning
from skills.action import mark_processed, scan_actions

logger = logging.getLogger("gaoding.dashboard")

# Stop events for graceful shutdown
scanner_stop_event = threading.Event()
budget_stop_event = threading.Event()
token_import_stop_event = threading.Event()
trail_import_stop_event = threading.Event()

DISPATCH_MAP = {
    "confirm": ["python3", str(PROJECT_ROOT / "skills/writer_router.py")],
    "approve": ["python3", str(PROJECT_ROOT / "skills/publisher.py")],
    "reject": ["python3", str(PROJECT_ROOT / "skills/writer.py"), "--rewrite"],
    "rewrite": ["python3", str(PROJECT_ROOT / "skills/writer.py"), "--rewrite"],
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
        # Legacy confirm -> also write flag file for backward compat
        topics_dir = PROJECT_ROOT / "queue/topics"
        topics_dir.mkdir(parents=True, exist_ok=True)
        flag_file = topics_dir / f"{target_id}.confirmed"
        flag_file.write_text(json.dumps(action, ensure_ascii=False, indent=2))

    cmd = DISPATCH_MAP.get(action_type)
    if not cmd:
        logger.warning(f"Unknown action type: {action_type}")
        return -1

    full_cmd = cmd + [target_id]
    logger.info(f"Dispatching async: {' '.join(full_cmd)}")
    try:
        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT,
        )
        logger.info(f"Dispatched {action_type}/{target_id} (PID: {proc.pid})")
        return proc.pid
    except Exception as e:
        logger.error(f"Dispatch error for {action_type}/{target_id}: {e}")
        return -1


def scan_loop():
    """Background thread: poll queue/actions/ every 10s (non-blocking dispatch)."""
    while not scanner_stop_event.is_set():
        try:
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
        except Exception as e:
            logger.error(f"Scanner loop error: {e}")
        scanner_stop_event.wait(10)


def token_import_loop():
    """Background thread: poll queue/tokens/ every 15s, import into SQLite."""
    failed_dir = TOKENS_DIR / "failed"
    while not token_import_stop_event.is_set():
        try:
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
        except Exception as e:
            logger.error(f"Token import loop error: {e}")
        token_import_stop_event.wait(15)


def trail_import_loop():
    """Background thread: poll queue/trails/ every 15s, import into SQLite pipeline_traces.

    Expects paired files: {id}.start.json and {id}.end.json.
    On .start.json: create_trace()
    On .end.json: complete_trace() + update_trace_duration()
    """
    while not trail_import_stop_event.is_set():
        try:
            TRAIL_DIR.mkdir(parents=True, exist_ok=True)
            # Collect all start files
            start_files = list(TRAIL_DIR.glob("*.start.json"))

            # Process .start.json, check for matching .end.json
            processed = set()
            for f in sorted(start_files, key=lambda x: x.stat().st_mtime):
                trail_id = f.stem.replace(".start", "")
                if trail_id in processed:
                    continue
                end_file = TRAIL_DIR / f"{trail_id}.end.json"

                try:
                    start_data = json.loads(f.read_text())

                    if end_file.exists():
                        # Complete trail — generate synthetic session_id if none
                        _sid = start_data.get("session_id")
                        if _sid is None:
                            # Lazy-create a pipeline session from trail metadata
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
                        f.unlink()
                        end_file.unlink()
                        processed.add(trail_id)
                    # else: keep waiting for the .end.json
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

        except Exception as e:
            logger.error(f"Trail import loop error: {e}")
        trail_import_stop_event.wait(15)


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
