"""Health and token logging routes."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from config.settings import ACTIONS_DIR, FAILED_DIR, PENDING_DIR, REVIEW_DIR, STATUS_DIR
from dashboard.backend.database import check_budget_limit, get_db, log_token_usage
from dashboard.backend.models import TokenLogRequest
from dashboard.backend.search import get_index_stats
from dashboard.backend.helpers import read_json

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(tags=["health"])


def _get_agent_last_runs() -> dict:
    """Get last run timestamps for each agent."""
    last_runs = {}
    for f in STATUS_DIR.glob("*.json"):
        data = read_json(f)
        name = f.stem
        completed = data.get("completed_at") or data.get("updated_at")
        if completed:
            last_runs[name] = completed
    return last_runs


def _get_disk_usage() -> dict:
    """Get disk usage for the data directory."""
    try:
        usage = shutil.disk_usage("/")
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent_used": round(usage.used / usage.total * 100, 1),
        }
    except Exception:
        return {}


@router.get("/api/health")
def health():
    """Comprehensive health check with database, budget, and service status."""
    health_status = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.7.0",
        "services": {},
        "queue_sizes": {},
        "budget": {},
        "disk": {},
        "agent_last_runs": {},
    }

    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        health_status["services"]["database"] = "ok"
    except Exception as e:
        health_status["services"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    try:
        index_stats = get_index_stats()
        health_status["services"]["search"] = {
            "status": "ok",
            "indexed_documents": index_stats.get("total_indexed", 0),
        }
    except Exception as e:
        health_status["services"]["search"] = f"error: {str(e)}"

    try:
        budget = check_budget_limit()
        health_status["budget"] = budget
        if budget.get("is_exceeded"):
            health_status["status"] = "warning"
    except Exception as e:
        health_status["budget"] = {"error": str(e)}

    health_status["queue_sizes"] = {
        "pending": len(list(PENDING_DIR.glob("*.json"))),
        "review": len(list(REVIEW_DIR.glob("*.meta.json"))),
        "actions": len(list(ACTIONS_DIR.glob("*.json"))),
        "failed": len(list(FAILED_DIR.glob("*.json"))),
    }

    if health_status["queue_sizes"]["failed"] > 50:
        health_status["status"] = "warning"

    health_status["disk"] = _get_disk_usage()
    if health_status["disk"].get("percent_used", 0) > 90:
        health_status["status"] = "warning"

    health_status["agent_last_runs"] = _get_agent_last_runs()

    return health_status


@router.post("/api/token/log")
def log_token(token_data: TokenLogRequest):
    """Log token usage from agents."""
    try:
        usage_id = log_token_usage(
            agent=token_data.agent,
            model=token_data.model,
            input_tokens=token_data.input_tokens,
            output_tokens=token_data.output_tokens,
            session_id=token_data.session_id,
        )
        return {"status": "ok", "id": usage_id}
    except Exception as e:
        logger.error(f"Failed to log token usage: {e}")
        raise HTTPException(500, "记录 token 用量失败")
