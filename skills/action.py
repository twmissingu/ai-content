"""Action file protocol — read/write queue/actions/*.json with atomic writes.

Every action file follows the JSON Schema from PRD 2.6:
{
  "action": "confirm|approve|reject|rewrite|test_scout",
  "target_id": "...",
  "timestamp": "ISO8601",
  "reason": null | "驳回原因",
  "platform_versions": ["wechat", ...],
  "trigger_agent": "scout|writer|publisher|feedback"
}

Atomic write convention: uses tempfile + fsync + rename for crash safety.
All writes are thread-safe and use atomic file operations.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from config.settings import ACTIONS_DIR, FAILED_ACTIONS_DIR, PROCESSED_DIR, PENDING_DIR

# Import atomic write from common module
try:
    from skills.common import atomic_write_json, validate_action, validate_platform
except ImportError:
    # Fallback for standalone usage
    import tempfile
    
    def atomic_write_json(path: Path, data: dict, indent: int = 2) -> None:
        """Fallback atomic write implementation."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
                f.flush()
                os.fsync(f.fileno())
            os.rename(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    
    def validate_action(action: str) -> str:
        allowed = {"confirm", "approve", "reject", "rewrite", "test_scout"}
        if action not in allowed:
            raise ValueError(f"Invalid action: {action}")
        return action
    
    def validate_platform(platform: str) -> str:
        allowed = {"wechat", "xiaohongshu", "douyin", "kuaishou", "toutiao", "baijiahao", "shipinhao"}
        if platform not in allowed:
            raise ValueError(f"Invalid platform: {platform}")
        return platform


# Logger
logger = logging.getLogger("gaoding.action")

# ── Types ──────────────────────────────────────────────────────────
ActionType = str  # "confirm" | "approve" | "reject" | "rewrite" | "test_scout"


class ActionFile(dict):
    """Minimal typed wrapper around the action JSON schema."""

    action: ActionType
    target_id: str
    timestamp: str
    reason: Optional[str] = None
    platform_versions: Optional[list[str]] = None
    trigger_agent: Optional[str] = None

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


# ── Write ──────────────────────────────────────────────────────────
def write_action(
    action: ActionType,
    target_id: str,
    *,
    reason: Optional[str] = None,
    platform_versions: Optional[list[str]] = None,
    trigger_agent: Optional[str] = None,
) -> Path:
    """Write an action file atomically (write .tmp → fsync → rename).

    Returns the final file path.
    
    Raises:
        ValueError: If action type is invalid
    """
    # Validate action type
    validate_action(action)
    
    # Validate platform versions if provided
    if platform_versions:
        for platform in platform_versions:
            validate_platform(platform)
    
    stamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{action}_{target_id}_{stamp}.json"
    final_path = ACTIONS_DIR / filename

    payload: dict[str, Any] = {
        "action": action,
        "target_id": target_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if reason is not None:
        payload["reason"] = reason
    if platform_versions is not None:
        payload["platform_versions"] = platform_versions
    if trigger_agent is not None:
        payload["trigger_agent"] = trigger_agent

    # Use atomic write with fsync
    atomic_write_json(final_path, payload)
    
    logger.info(f"Action written: {action} -> {final_path.name}")
    return final_path


# ── Read ───────────────────────────────────────────────────────────
def scan_actions() -> list[ActionFile]:
    """Scan queue/actions/ for unprocessed action files (sorted by mtime).
    
    Files that fail to parse are moved to failed actions directory.
    """
    ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    files = sorted(ACTIONS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    results: list[ActionFile] = []
    
    for f in files:
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            results.append(ActionFile(data))
        except (json.JSONDecodeError, OSError) as e:
            # Malformed file — move to failed actions dir
            logger.warning(f"Failed to parse action file {f.name}: {e}")
            try:
                FAILED_ACTIONS_DIR.mkdir(parents=True, exist_ok=True)
                failed_path = FAILED_ACTIONS_DIR / f.name
                os.rename(f, failed_path)
                logger.info(f"Moved malformed file to: {failed_path}")
            except OSError as move_err:
                logger.error(f"Failed to move malformed file {f.name}: {move_err}")
    
    return results


def mark_processed(path: Path) -> None:
    """Move a processed action file into the processed/ subdirectory.
    
    Uses atomic rename for safety.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROCESSED_DIR / path.name
    
    # Handle case where destination already exists
    if dest.exists():
        # Add timestamp suffix to avoid collision
        stem = path.stem
        suffix = path.suffix
        dest = PROCESSED_DIR / f"{stem}_{int(time.time())}{suffix}"
    
    try:
        os.rename(path, dest)
        logger.debug(f"Marked processed: {path.name} -> {dest.name}")
    except OSError as e:
        logger.error(f"Failed to mark processed {path.name}: {e}")
        raise


# ── Helpers ────────────────────────────────────────────────────────
def write_topic_pending(
    topic_data: dict,
    *,
    filename: Optional[str] = None,
) -> Path:
    """Write a Scout-recommended topic into queue/pending/.
    
    Uses atomic write for crash safety.
    """
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    
    if filename is None:
        filename = f"topic_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1000000:06d}.json"
    
    path = PENDING_DIR / filename
    atomic_write_json(path, topic_data)
    
    logger.info(f"Topic pending written: {path.name}")
    return path


def cleanup_old_actions(days: int = 7) -> int:
    """Clean up processed action files older than N days.
    
    Returns number of files cleaned up.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    cutoff_time = time.time() - (days * 24 * 60 * 60)
    cleaned = 0
    
    for f in PROCESSED_DIR.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff_time:
                f.unlink()
                cleaned += 1
        except OSError as e:
            logger.warning(f"Failed to clean up {f.name}: {e}")
    
    if cleaned > 0:
        logger.info(f"Cleaned up {cleaned} old action files")
    
    return cleaned
