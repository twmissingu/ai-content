#!/usr/bin/env python3
"""Action scanner — polls queue/actions/ every 30s and dispatches.

Runs as a background thread in Dashboard or as a standalone process.
Dispatching:
- approve → publisher.py
- reject  → writer.py --rewrite
- confirm → write pending topic → triggers writer on next cron
- rewrite → writer.py --rewrite

Each action file is moved to processed/ after handling.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import ACTIONS_DIR, PROCESSED_DIR, PROJECT_ROOT
from skills.action import ActionFile, scan_actions, mark_processed


SKILLS_DIR = PROJECT_ROOT / "skills"
DISPATCHER = {
    "approve": ["python3", str(SKILLS_DIR / "publisher.py")],
    "reject": ["python3", str(SKILLS_DIR / "writer.py"), "--rewrite"],
    "rewrite": ["python3", str(SKILLS_DIR / "writer.py"), "--rewrite"],
    "confirm": None,  # handled by cron, not immediate dispatch
}


def dispatch(action: ActionFile):
    """Execute the appropriate agent for this action."""
    action_type = action.get("action")
    target_id = action.get("target_id", "")

    if action_type == "confirm":
        # Set a flag for the next Writer cron tick
        topics_dir = PROJECT_ROOT / "queue/topics"
        flag_file = topics_dir / f"{target_id}.confirmed"
        tmp = topics_dir / f".{target_id}.confirmed.tmp"
        tmp.write_text(json.dumps(action, ensure_ascii=False, indent=2))
        os.rename(tmp, flag_file)
        return True

    cmd = DISPATCHER.get(action_type)
    if not cmd:
        print(f"[scan] Unknown action type: {action_type}")
        return False

    full_cmd = cmd + [target_id]
    print(f"[scan] Dispatching: {' '.join(full_cmd)}")
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"[scan] Dispatch failed (rc={result.returncode}): {result.stderr[:200]}")
            return False
        print(f"[scan] Dispatch OK: {result.stdout[:100]}")
        return True
    except subprocess.TimeoutExpired:
        print(f"[scan] Dispatch timed out: {action_type}/{target_id}")
        return False
    except Exception as e:
        print(f"[scan] Dispatch error: {e}")
        return False


def scan_once() -> int:
    """Scan and dispatch all pending actions. Returns count processed."""
    actions = scan_actions()
    count = 0
    for action in actions:
        ok = dispatch(action)
        if ok:
            # Find the original file path
            for f in ACTIONS_DIR.glob(f"{action['action']}_{action['target_id']}_*.json"):
                mark_processed(f)
                count += 1
                break
    return count


def main():
    """Standalone loop mode."""
    print("[scan] Action scanner started (30s interval)")
    while True:
        try:
            count = scan_once()
            if count:
                print(f"[scan] Processed {count} actions")
        except KeyboardInterrupt:
            print("\n[scan] Stopped")
            break
        except Exception as e:
            print(f"[scan] Error: {e}")
        time.sleep(30)


if __name__ == "__main__":
    if "--once" in sys.argv:
        scan_once()
    else:
        main()
