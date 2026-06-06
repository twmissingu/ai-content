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

from config.settings import FAILED_DIR, PENDING_DIR, PROJECT_ROOT, REVIEW_DIR, SKIPPED_DIR, TOKENS_DIR, TRAIL_DIR
from dashboard.backend.config_service import get_quality_gates
from dashboard.backend.database import check_budget_limit, log_token_usage, create_pipeline_session, update_pipeline_session, import_trail_record
from dashboard.backend.feishu import alert_agent_error, alert_approval_timeout, alert_budget_warning, alert_topic_timeout
from dashboard.backend.helpers import read_json
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


def _handle_skip(target_id: str, reason: str = "") -> int:
    """Handle skip action: move review files from review/ to skipped/.

    Note: This function only handles filesystem operations.
    DB recording (if needed) is the caller's responsibility.
    Returns 0 on success, -1 on failure.
    """
    SKIPPED_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = REVIEW_DIR / f"{target_id}.meta.json"
    md_path = REVIEW_DIR / f"{target_id}.md"

    moved = False
    if meta_path.exists():
        meta_path.rename(SKIPPED_DIR / meta_path.name)
        moved = True
    if md_path.exists():
        md_path.rename(SKIPPED_DIR / md_path.name)
        moved = True

    if not moved:
        logger.warning(f"Skip handler: no review files found for {target_id}")
        return -1

    logger.info(f"Skipped article {target_id} -> {SKIPPED_DIR}")
    return 0


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

    # Handle skip inline (no subprocess needed)
    if action_type == "skip":
        return _handle_skip(target_id, reason=action.get("reason", ""))

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
    Uses import_trail_record() for single-transaction insert.
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
                trail_status = end_data.get("status", "completed")
                # Single-transaction: create trace + complete with duration
                import_trail_record(
                    session_id=_sid,
                    agent=start_data.get("agent", "unknown"),
                    stage=start_data.get("stage", "unknown"),
                    stage_name=start_data.get("stage_name"),
                    status=trail_status,
                    duration_ms=end_data.get("duration_ms"),
                )
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


def topic_timeout_target():
    """Scan queue/pending/ for topics older than timeout threshold.

    Auto-confirms the highest-score expired topic by writing a confirm action.
    Records the event in SQLite and sends a Feishu notification.
    """
    gates = get_quality_gates()
    timeout_min = gates.get("topic_timeout_minutes", 30)
    now = time.time()
    cutoff = now - (timeout_min * 60)

    expired = []
    for f in PENDING_DIR.glob("topic_*.json"):
        if f.stat().st_mtime < cutoff:
            data = read_json(f)
            data["_file"] = f
            expired.append(data)

    if not expired:
        return

    # Pick highest score
    best = max(expired, key=lambda d: d.get("score", 0))
    target_id = best["_file"].stem

    # Idempotency: check if already processed
    original_path = best["_file"]
    timeout_path = original_path.with_suffix(".timeout.json")
    if timeout_path.exists():
        return  # Already processed

    # Write confirm action — idempotency is handled by timeout_path.exists() check above
    write_action("confirm", target_id, trigger_agent="timeout-poller")

    # Rename .json -> .timeout.json so next poll skips it
    try:
        original_path.rename(timeout_path)
    except OSError:
        return  # Already renamed by concurrent poll

    # Record in SQLite (single transaction)
    try:
        from dashboard.backend.database import get_db as _get_db
        with _get_db() as _conn:
            cur = _conn.execute("""
                INSERT INTO pipeline_sessions (date, period, topic, status, started_at)
                VALUES (?, 'am', ?, 'running', CURRENT_TIMESTAMP)
            """, (time.strftime("%Y%m%d"), f"timeout-confirm:{target_id}"))
            session_id = cur.lastrowid
            cur = _conn.execute("""
                INSERT INTO pipeline_traces (session_id, agent, stage, stage_name, status)
                VALUES (?, 'timeout-poller', 'topic-timeout', '选题超时自动确认', 'running')
            """, (session_id,))
            trace_id = cur.lastrowid
            _conn.execute("""
                UPDATE pipeline_traces
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (trace_id,))
    except Exception as e:
        logger.warning(f"Failed to record topic timeout in SQLite: {e}")

    # Feishu notification
    try:
        alert_topic_timeout(
            topic_title=best.get("title", target_id),
            score=best.get("score", 0),
            timeout_minutes=timeout_min,
        )
    except Exception as e:
        logger.warning(f"Failed to send topic timeout alert: {e}")

    logger.info(f"Topic timeout: auto-confirmed {target_id} (score={best.get('score', 0)})")


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


def approval_timeout_target():
    """Scan queue/review/ for articles older than approval timeout threshold.

    Marks each expired article as skipped by writing a skip action.
    Records the event in SQLite and sends a Feishu notification.
    """
    gates = get_quality_gates()
    timeout_min = gates.get("approval_timeout_minutes", 120)
    now = time.time()
    cutoff = now - (timeout_min * 60)

    expired = []
    for f in REVIEW_DIR.glob("*.meta.json"):
        if f.stat().st_mtime < cutoff:
            article_id = f.stem.replace(".meta", "")
            expired.append(article_id)

    if not expired:
        return

    for article_id in expired:
        # Idempotency: check if already processed
        meta_path = REVIEW_DIR / f"{article_id}.meta.json"
        skipped_marker = REVIEW_DIR / f"{article_id}.skipped.json"
        if skipped_marker.exists():
            continue  # Already processed

        # Per-article: DB record + file operation together.
        # If DB fails, log and skip this article (next poll will retry).
        # If file operation fails after DB, the DB record is the audit trail.
        try:
            from dashboard.backend.database import get_db as _get_db
            with _get_db() as _conn:
                cur = _conn.execute("""
                    INSERT INTO pipeline_sessions (date, period, topic, status, started_at)
                    VALUES (?, 'am', ?, 'running', CURRENT_TIMESTAMP)
                """, (time.strftime("%Y%m%d"), f"timeout-skip:{article_id}"))
                session_id = cur.lastrowid
                cur = _conn.execute("""
                    INSERT INTO pipeline_traces (session_id, agent, stage, stage_name, status)
                    VALUES (?, 'timeout-poller', 'approval-timeout', '审批超时自动跳过', 'running')
                """, (session_id,))
                trace_id = cur.lastrowid
                _conn.execute("""
                    UPDATE pipeline_traces
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (trace_id,))
        except Exception as e:
            logger.warning(f"Failed to record approval timeout for {article_id} in SQLite: {e}")
            continue  # Skip this article, retry on next poll

        # Write skip action
        write_action("skip", article_id, trigger_agent="timeout-poller",
                      reason=f"审批超时({timeout_min}分钟)")

        # Rename .meta.json -> .skipped.json so next poll skips it
        if meta_path.exists():
            try:
                meta_path.rename(skipped_marker)
            except OSError:
                continue  # Already renamed by concurrent poll

        # Feishu notification
        try:
            alert_approval_timeout(
                article_id=article_id,
                timeout_minutes=timeout_min,
            )
        except Exception as e:
            logger.warning(f"Failed to send approval timeout alert: {e}")

        logger.info(f"Approval timeout: auto-skipped {article_id}")


# Register all pollers
_pollers = [
    Poller(name="action-scanner", interval=10, target=scan_actions_target),
    Poller(name="token-importer", interval=15, target=import_tokens_target),
    Poller(name="trail-importer", interval=15, target=import_trails_target),
    Poller(name="budget-monitor", interval=300, target=budget_monitor_target),
    Poller(name="topic-timeout", interval=60, target=topic_timeout_target),
    Poller(name="approval-timeout", interval=60, target=approval_timeout_target),
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
