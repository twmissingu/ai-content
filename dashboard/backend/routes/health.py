"""Health and token logging routes."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from config.settings import ACTIONS_DIR, FAILED_DIR, PENDING_DIR, REVIEW_DIR
from dashboard.backend.database import check_budget_limit, get_db, log_token_usage
from dashboard.backend.models import TokenLogRequest
from dashboard.backend.search import get_index_stats

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health():
    """Comprehensive health check with database, budget, and service status."""
    health_status = {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.3.0",
        "services": {},
        "queue_sizes": {},
        "budget": {},
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
        raise HTTPException(500, f"Failed to log token usage: {e}")
