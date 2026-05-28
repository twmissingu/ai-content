"""Trace routes — pipeline execution history and stage details."""

import logging

from fastapi import APIRouter, HTTPException, Query

from dashboard.backend.database import get_traces, get_trace_summary, get_trace_summaries_batch, get_pipeline_sessions

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/pipeline/traces", tags=["traces"])


@router.get("")
def list_traces(
    session_id: int | None = Query(None, description="Filter by session ID"),
    agent: str | None = Query(None, description="Filter by agent name"),
    limit: int = Query(100, ge=1, le=500),
):
    """List pipeline execution traces with optional filters."""
    try:
        traces = get_traces(session_id=session_id, agent=agent, limit=limit)
        return {"traces": traces, "total": len(traces)}
    except Exception as e:
        logger.error(f"Error listing traces: {e}")
        raise HTTPException(500, "加载执行记录失败")


@router.get("/summary/{session_id}")
def trace_summary(session_id: int):
    """Get aggregated trace summary for a pipeline session."""
    try:
        summary = get_trace_summary(session_id)
        return summary
    except Exception as e:
        logger.error(f"Error getting trace summary for session {session_id}: {e}")
        raise HTTPException(500, "加载执行摘要失败")


@router.get("/sessions")
def trace_sessions(
    limit: int = Query(20, ge=1, le=100),
):
    """List recent pipeline sessions with their trace counts."""
    try:
        result = get_pipeline_sessions(limit=limit)
        sessions = result.get("items", [])
        session_ids = [s["id"] for s in sessions]
        summaries = get_trace_summaries_batch(session_ids)
        enriched = []
        for s in sessions:
            summary = summaries.get(s["id"], {
                "stage_count": 0, "total_tokens": 0,
                "total_duration_ms": 0, "failed_stages": [],
            })
            enriched.append({
                **s,
                "stage_count": summary["stage_count"],
                "total_tokens": summary["total_tokens"],
                "total_duration_ms": summary["total_duration_ms"],
                "failed_stages": summary["failed_stages"],
            })
        return {"sessions": enriched}
    except Exception as e:
        logger.error(f"Error listing trace sessions: {e}")
        raise HTTPException(500, "加载执行记录失败")
