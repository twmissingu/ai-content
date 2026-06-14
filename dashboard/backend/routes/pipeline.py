"""Pipeline routes — agent status, timeline, session detail, and manual triggers."""

import logging
import os
import re
import subprocess
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from config.settings import KB_DIR, PROJECT_ROOT, REVIEW_DIR, STATUS_DIR, TRAIL_DIR
from dashboard.backend.database import check_budget_limit, get_pipeline_sessions, get_pipeline_session_by_id
from dashboard.backend.helpers import detect_timeout, read_json
from dashboard.backend.models import TriggerRequest, RerunRequest

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# Rate limiter for trigger endpoint
_trigger_timestamps: dict[str, list[float]] = defaultdict(list)
_trigger_lock = threading.Lock()
_TRIGGER_RATE_LIMIT = 5
_TRIGGER_RATE_WINDOW = 60
_TRIGGER_MAX_CLIENTS = 1000
_TOPIC_ID_RE = re.compile(r'^[\w\-]+$')

# Global concurrency limit for agent triggers
_MAX_CONCURRENT_AGENTS = 3
_running_agents = 0
_running_agents_lock = threading.Lock()

# Pipeline status cache (shared between REST and WebSocket)
_status_cache: dict | None = None
_status_cache_ts: float = 0
_status_cache_lock = threading.Lock()
_STATUS_CACHE_TTL = 2.0  # seconds


@router.get("/status")
def get_pipeline_status():
    """Read all status files and return aggregated view with budget info (cached)."""
    global _status_cache, _status_cache_ts
    now = time.time()

    with _status_cache_lock:
        if _status_cache and (now - _status_cache_ts) < _STATUS_CACHE_TTL:
            return _status_cache

    agents = {}
    for f in STATUS_DIR.glob("*.json"):
        data = read_json(f)
        name = f.stem
        agents[name] = data
        timeout = detect_timeout(data)
        if timeout and data.get("progress_pct", 100) < 100:
            agents[name]["timeout"] = True

    budget = check_budget_limit()
    result = {
        "agents": agents,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "budget": budget,
    }

    with _status_cache_lock:
        _status_cache = result
        _status_cache_ts = now

    return result


@router.get("/status/writer-workers")
def get_writer_workers():
    """Get aggregated status of all writer workers."""
    workers = {}

    # Check for writer-router.json first
    router_path = STATUS_DIR / "writer-router.json"
    if router_path.exists():
        router_data = read_json(router_path)
        if router_data:
            return router_data

    # Otherwise, aggregate from individual worker files
    for f in STATUS_DIR.glob("writer-worker-*.json"):
        data = read_json(f)
        if data:
            worker_name = f.stem.replace("writer-worker-", "")
            workers[worker_name] = data

    # Also check for main writer status
    writer_path = STATUS_DIR / "writer.json"
    if writer_path.exists():
        writer_data = read_json(writer_path)
        if writer_data:
            workers["main"] = writer_data

    return {
        "workers": workers,
        "worker_count": len(workers),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/timeline")
def get_pipeline_timeline(
    limit: int = Query(14, ge=1, le=50),
    status: str = Query(None, description="Filter by status: completed/failed/running"),
):
    """Get recent pipeline sessions from database and filesystem."""
    sessions = []

    db_result = get_pipeline_sessions(limit=limit)
    for s in db_result.get('items', []):
        session_status = s.get('status', 'unknown')
        if status and session_status != status:
            continue
        sessions.append({
            "id": s.get('id'),
            "date": s.get('date', ''),
            "period": s.get('period', ''),
            "topic": s.get('topic', ''),
            "status": session_status,
            "article_count": 1,
            "articles": [s.get('topic', '')],
            "source": "database",
            "started_at": s.get('started_at'),
            "completed_at": s.get('completed_at'),
        })

    history_dir = KB_DIR / "history"
    if history_dir.exists():
        for d in sorted(history_dir.iterdir(), reverse=True)[:limit]:
            if d.is_dir():
                articles = list(d.glob("*.md"))
                fs_status = "completed"
                if status and fs_status != status:
                    continue
                sessions.append({
                    "id": None,
                    "date": d.name,
                    "period": "",
                    "topic": "",
                    "status": fs_status,
                    "article_count": len(articles),
                    "articles": [a.stem for a in articles],
                    "source": "filesystem",
                    "started_at": None,
                    "completed_at": None,
                })

    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: int):
    """Get detailed information about a specific pipeline session."""
    from dashboard.backend.database import get_platform_versions

    try:
        session = get_pipeline_session_by_id(session_id)
        if not session:
            raise HTTPException(404, f"Session not found: {session_id}")

        # Get platform versions for this session
        versions = get_platform_versions(session_id)

        # Get trace data if available
        traces = []
        trail_dir = TRAIL_DIR
        if trail_dir.exists():
            for f in trail_dir.glob(f"*{session_id}*.json"):
                trace_data = read_json(f)
                if trace_data:
                    traces.append(trace_data)

        return {
            "session": session,
            "versions": versions,
            "traces": traces,
            "version_count": len(versions),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session detail: {e}")
        raise HTTPException(500, "获取会话详情失败")


@router.get("/stages")
def get_pipeline_stages():
    """Get the list of pipeline stages with descriptions."""
    return {
        "stages": [
            {"id": 1, "name": "抓原文", "key": "fetch_source", "description": "从选题 URL 抓取原始内容"},
            {"id": 2, "name": "LLM初稿", "key": "draft", "description": "根据素材生成初稿"},
            {"id": 3, "name": "AI腔审校", "key": "proofread", "description": "正则+LLM双检测去AI味"},
            {"id": 4, "name": "批评修订", "key": "critique", "description": "评委打分，低于阈值重写"},
            {"id": 5, "name": "排版", "key": "format", "description": "中英文空格、段落分割"},
            {"id": 6, "name": "标题优化", "key": "titles", "description": "生成3个候选标题，选最优"},
            {"id": 7, "name": "配图", "key": "illustrate", "description": "AI配图生成"},
        ]
    }


@router.post("/trigger")
def trigger_agent(req: TriggerRequest, request: Request):
    """Manually trigger an agent (scout or writer) to run immediately."""
    if req.agent not in ("scout", "writer"):
        raise HTTPException(400, f"Invalid agent: {req.agent}. Must be 'scout' or 'writer'.")

    client_ip = request.client.host if request.client else "unknown"
    import time as _time
    now = _time.time()

    with _trigger_lock:
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

    # Global concurrency limit
    global _running_agents
    with _running_agents_lock:
        if _running_agents >= _MAX_CONCURRENT_AGENTS:
            raise HTTPException(429, f"并发 agent 数已达上限 ({_MAX_CONCURRENT_AGENTS})，请稍后再试")
        _running_agents += 1

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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
            start_new_session=True,
        )
        logger.info(f"Triggered {req.agent} (PID: {process.pid})")

        # Decrement concurrency counter when process exits
        def _wait_and_release():
            global _running_agents
            try:
                process.wait()
            finally:
                with _running_agents_lock:
                    _running_agents = max(0, _running_agents - 1)

        threading.Thread(target=_wait_and_release, daemon=True).start()

        return {
            "status": "ok",
            "agent": req.agent,
            "pid": process.pid,
            "message": f"{req.agent} agent started",
        }
    except Exception as e:
        with _running_agents_lock:
            _running_agents = max(0, _running_agents - 1)
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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
