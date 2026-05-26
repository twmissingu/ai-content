"""Feedback Agent — data collection and analysis.

Phase 1: placeholder. Actual implementation in Phase 3 after AiToEarn
data API verification. For now, this creates the status file structure
so Dashboard can show the agent exists.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DATA_DIR, KB_DIR, STATUS_DIR

RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def main():
    print("[feedback] Phase 1 — placeholder. Full implementation in Phase 3.")

    status = {
        "agent": "feedback",
        "stage": "placeholder",
        "progress_pct": 100,
        "detail": "Phase 1 placeholder — data collection not yet implemented",
        "started_at": RUN_TIMESTAMP,
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error": None,
    }
    path = STATUS_DIR / "feedback.json"
    tmp = STATUS_DIR / ".feedback.json.tmp"
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    os.rename(tmp, path)

    print("[feedback] Done (placeholder)")


if __name__ == "__main__":
    main()
