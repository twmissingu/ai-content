"""Topic routes — candidate listing, detail, and confirmation."""

import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from config.settings import PENDING_DIR
from dashboard.backend.helpers import read_json
from skills.action import write_action
from dashboard.backend.models import ConfirmRequest

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/topics", tags=["topics"])


def _safe_topic_id(topic_id: str) -> str:
    """Sanitize topic_id to prevent path traversal."""
    if any(c in topic_id for c in ('/', '\\', '\0')):
        return ""
    safe = re.sub(r'\.\.', '', topic_id)
    target = PENDING_DIR / f"{safe}.json"
    try:
        target.resolve().relative_to(PENDING_DIR.resolve())
    except ValueError:
        return ""
    return safe


@router.get("")
def get_topics(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: str = Query(None, description="Filter by session: morning/evening"),
    min_score: float = Query(None, ge=0, le=100, description="Minimum final_score"),
    source: str = Query(None, description="Filter by source (rss, weibo, etc.)"),
):
    """List pending topic candidates from queue/pending/.

    Supports filtering by session, minimum score, and source.
    Uses scandir for efficient directory listing.
    """
    # Use scandir for efficient directory listing
    topic_files = []
    with os.scandir(PENDING_DIR) as it:
        for entry in it:
            if entry.is_file() and entry.name.startswith("topic_") and entry.name.endswith(".json"):
                topic_files.append(entry)
    topic_files.sort(key=lambda e: e.stat().st_mtime, reverse=True)

    topics = []
    total = 0
    needed = offset + limit
    for entry in topic_files:
        data = read_json(Path(entry.path))
        if not data:
            continue

        # Apply filters
        if session and data.get("session") != session:
            continue
        if min_score is not None and data.get("final_score", 0) < min_score:
            continue
        if source and data.get("source") != source:
            continue

        total += 1
        # Only collect what we need for the page
        if len(topics) < needed:
            data["id"] = entry.name.replace(".json", "")
            data["filename"] = entry.name
            topics.append(data)

    topics = topics[offset:offset + limit]
    return {"topics": topics, "count": len(topics), "total": total}


@router.get("/stats/summary")
def get_topic_stats():
    """Get summary statistics about pending topics."""
    files = list(PENDING_DIR.glob("topic_*.json"))
    if not files:
        return {
            "total": 0,
            "by_source": {},
            "by_session": {},
            "avg_score": 0,
            "top_score": 0,
        }

    by_source: dict[str, int] = {}
    by_session: dict[str, int] = {}
    scores: list[float] = []

    for f in files:
        data = read_json(f)
        if not data:
            continue

        source = data.get("source", "unknown")
        by_source[source] = by_source.get(source, 0) + 1

        session = data.get("session", "unknown")
        by_session[session] = by_session.get(session, 0) + 1

        score = data.get("final_score", 0)
        if score:
            scores.append(score)

    return {
        "total": len(files),
        "by_source": by_source,
        "by_session": by_session,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "top_score": round(max(scores), 1) if scores else 0,
    }


@router.get("/{topic_id}")
def get_topic_detail(topic_id: str):
    """Get detailed information about a specific topic candidate."""
    safe_id = _safe_topic_id(topic_id)
    if not safe_id:
        raise HTTPException(400, f"Invalid topic ID: {topic_id}")

    topic_path = PENDING_DIR / f"{safe_id}.json"
    if not topic_path.exists():
        raise HTTPException(404, f"Topic not found: {topic_id}")

    data = read_json(topic_path)
    data["id"] = safe_id
    data["filename"] = topic_path.name

    # Add scoring breakdown if available
    scoring_fields = [
        "attention_score", "increment_score", "final_score",
        "source_weight", "viral_score", "freshness_score",
        "saturation_score", "novelty_score", "self_repeat_score",
        "feasibility_score",
    ]
    scoring = {}
    for field in scoring_fields:
        if field in data:
            scoring[field] = data[field]
    if scoring:
        data["scoring_breakdown"] = scoring

    return data


@router.post("/confirm")
def confirm_topic(req: ConfirmRequest):
    """Confirm a topic, triggering Writer on next cron."""
    safe_id = _safe_topic_id(req.target_id)
    if not safe_id:
        raise HTTPException(400, f"Invalid topic ID: {req.target_id}")

    topic_path = PENDING_DIR / f"{safe_id}.json"
    if not topic_path.exists():
        raise HTTPException(404, f"Topic not found: {req.target_id}")

    path = write_action("confirm", safe_id)
    return {"status": "ok", "path": str(path)}
