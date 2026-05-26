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

Atomic write convention: write to .tmp first, then rename → prevents partial reads.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from config.settings import ACTIONS_DIR, FAILED_ACTIONS_DIR, PROCESSED_DIR, PENDING_DIR

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
    """Write an action file atomically (write .tmp → rename).

    Returns the final file path.
    """
    stamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{action}_{target_id}_{stamp}.json"
    tmp_path = ACTIONS_DIR / f".{filename}.tmp"
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

    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    os.rename(tmp_path, final_path)  # atomic on same filesystem
    return final_path


# ── Read ───────────────────────────────────────────────────────────
def scan_actions() -> list[ActionFile]:
    """Scan queue/actions/ for unprocessed action files (sorted by mtime)."""
    files = sorted(ACTIONS_DIR.glob("*.json"), key=os.path.getmtime)
    results: list[ActionFile] = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            results.append(ActionFile(data))
        except (json.JSONDecodeError, OSError) as e:
            # Malformed file — move to failed actions dir
            failed_path = FAILED_ACTIONS_DIR / f.name
            os.rename(f, failed_path)
    return results


def mark_processed(path: Path) -> None:
    """Move a processed action file into the processed/ subdirectory."""
    os.rename(path, PROCESSED_DIR / path.name)


# ── Helpers ────────────────────────────────────────────────────────
def write_topic_pending(
    topic_data: dict,
    *,
    filename: Optional[str] = None,
) -> Path:
    """Write a Scout-recommended topic into queue/pending/."""
    if filename is None:
        filename = f"topic_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path = PENDING_DIR / filename
    tmp = PENDING_DIR / f".{filename}.tmp"
    tmp.write_text(json.dumps(topic_data, ensure_ascii=False, indent=2))
    os.rename(tmp, path)
    return path
