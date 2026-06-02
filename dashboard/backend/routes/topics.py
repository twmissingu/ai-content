"""Topic routes — candidate listing and confirmation."""

import logging
import os

from fastapi import APIRouter, Query

from config.settings import PENDING_DIR
from dashboard.backend.helpers import read_json
from skills.action import write_action
from dashboard.backend.models import ConfirmRequest

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("")
def get_topics(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """List pending topic candidates from queue/pending/."""
    files = sorted(PENDING_DIR.glob("topic_*.json"), key=os.path.getmtime, reverse=True)
    total = len(files)
    topics = []
    for f in files[offset:offset + limit]:
        data = read_json(f)
        data["id"] = f.stem
        data["filename"] = f.name
        topics.append(data)
    return {"topics": topics, "count": len(topics), "total": total}


@router.post("/confirm")
def confirm_topic(req: ConfirmRequest):
    """Confirm a topic, triggering Writer on next cron."""
    path = write_action("confirm", req.target_id)
    return {"status": "ok", "path": str(path)}
