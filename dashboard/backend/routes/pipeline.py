"""Pipeline routes — agent status, timeline, and manual triggers."""

import logging
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from config.settings import KB_DIR, PROJECT_ROOT, STATUS_DIR
from dashboard.backend.database import check_budget_limit, get_pipeline_sessions
from dashboard.backend.helpers import detect_timeout, read_json
from dashboard.backend.models import TriggerRequest, RerunRequest

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# Rate limiter for trigger endpoint
_trigger_timestamps: dict[str, list[float]] = defaultdict(list)
_TRIGGER_RATE_LIMIT = 5
_TRIGGER_RATE_WINDOW = 60
_TRIGGER_MAX_CLIENTS = 1000
_TOPIC_ID_RE = re.compile(r'^[\w\-]+$')


@router.get("/status")
def get_pipeline_status():
    """Read all status files and return aggregated view with budget info."""
    agents = {}
    for f in STATUS_DIR.glob("*.json"):
        data = read_json(f)
        name = f.stem
        agents[name] = data
        timeout = detect_timeout(data)
        if timeout and data.get("progress_pct", 100) < 100:
            agents[name]["timeout"] = True

    budget = check_budget_limit()
    return {
        "agents": agents,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "budget": budget,
    }


@router.get("/timeline")
def get_pipeline_timeline():
    """Get recent pipeline sessions from database and filesystem."""
    sessions = []

    db_result = get_pipeline_sessions(limit=14)
    for s in db_result.get('items', []):
        sessions.append({
            "id": s.get('id'),
            "date": s.get('date', ''),
            "period": s.get('period', ''),
            "topic": s.get('topic', ''),
            "status": s.get('status', 'unknown'),
            "article_count": 1,
            "articles": [s.get('topic', '')],
            "source": "database",
            "started_at": s.get('started_at'),
            "completed_at": s.get('completed_at'),
        })

    history_dir = KB_DIR / "history"
    if history_dir.exists():
        for d in sorted(history_dir.iterdir(), reverse=True)[:14]:
            if d.is_dir():
                articles = list(d.glob("*.md"))
                sessions.append({
                    "id": None,
                    "date": d.name,
                    "period": "",
                    "topic": "",
                    "status": "completed",
                    "article_count": len(articles),
                    "articles": [a.stem for a in articles],
                    "source": "filesystem",
                    "started_at": None,
                    "completed_at": None,
                })

    return {"sessions": sessions}


@router.post("/trigger")
def trigger_agent(req: TriggerRequest, request: Request):
    """Manually trigger an agent (scout or writer) to run immediately."""
    if req.agent not in ("scout", "writer"):
        raise HTTPException(400, f"Invalid agent: {req.agent}. Must be 'scout' or 'writer'.")

    client_ip = request.client.host if request.client else "unknown"
    import time as _time
    now = _time.time()

    # Evict stale clients when map grows too large
    if len(_trigger_timestamps) > _TRIGGER_MAX_CLIENTS:
        cutoff = now - _TRIGGER_RATE_WINDOW
        stale = [ip for ip, ts in _trigger_timestamps.items()
                 if not ts or ts[-1] < cutoff]
        for ip in stale:
            del _trigger_timestamps[ip]

    timestamps = _trigger_timestamps[client_ip]
    _trigger_timestamps[client_ip] = [t for t in timestamps if now - t < _TRIGGER_RATE_WINDOW]
    if len(_trigger_timestamps[client_ip]) >= _TRIGGER_RATE_LIMIT:
        raise HTTPException(429, "触发频率过高，请稍后再试")
    _trigger_timestamps[client_ip].append(now)

    if req.topic_id and not _TOPIC_ID_RE.match(req.topic_id):
        raise HTTPException(400, f"Invalid topic_id format: {req.topic_id}")

    if req.session and req.session not in ("morning", "evening"):
        raise HTTPException(400, f"Invalid session: {req.session}. Must be 'morning' or 'evening'.")

    skills_dir = PROJECT_ROOT / "skills"
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"

    if req.agent == "scout":
        script = skills_dir / "scout.py"
        session = req.session or "morning"
        cmd = [str(venv_python), str(script), session]
    else:
        script = skills_dir / "writer.py"
        if req.topic_id:
            cmd = [str(venv_python), str(script), req.topic_id]
        else:
            cmd = [str(venv_python), str(script)]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        logger.info(f"Triggered {req.agent} (PID: {process.pid})")
        return {
            "status": "ok",
            "agent": req.agent,
            "pid": process.pid,
            "message": f"{req.agent} agent started",
        }
    except Exception as e:
        logger.error(f"Failed to trigger {req.agent}: {e}")
        raise HTTPException(500, f"触发 {req.agent} 失败")


@router.post("/rerun")
def rerun_from_stage(req: RerunRequest, request: Request):
    """Re-run the writer pipeline from a specific stage (1-7).

    Stages: 1=抓原文, 2=初稿, 3=审校, 4=批评修订, 5=排版, 6=标题, 7=配图
    """
    if not 1 <= req.stage <= 7:
        raise HTTPException(400, f"Invalid stage: {req.stage}. Must be 1-7.")

    skills_dir = PROJECT_ROOT / "skills"
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    script = skills_dir / "writer.py"

    cmd = [str(venv_python), str(script), "--rerun-from", str(req.stage)]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        logger.info(f"Re-run from stage {req.stage} (PID: {process.pid})")
        return {
            "status": "ok",
            "agent": "writer",
            "stage": req.stage,
            "pid": process.pid,
            "message": f"Writer re-run from stage {req.stage}",
        }
    except Exception as e:
        logger.error(f"Failed to re-run from stage {req.stage}: {e}")
        raise HTTPException(500, "重新执行失败")
