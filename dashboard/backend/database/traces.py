"""Pipeline execution trace logging (inspired by n8n execution history).

Records per-agent stage I/O for debugging and audit trails.
"""

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from .core import get_db

logger = logging.getLogger("gaoding.database")


def create_trace(session_id: Optional[int], agent: str, stage: str,
                stage_name: str = None, input_summary: str = None) -> int:
    """Start a new trace entry for a pipeline stage."""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO pipeline_traces (session_id, agent, stage, stage_name, input_summary, status)
            VALUES (?, ?, ?, ?, ?, 'running')
        """, (session_id, agent, stage, stage_name, input_summary))
        return cursor.lastrowid


def complete_trace(trace_id: int, output_summary: str = None,
                  status: str = 'completed', tokens_used: int = 0,
                  error_message: str = None):
    """Mark a trace entry as complete."""
    with get_db() as conn:
        conn.execute("""
            UPDATE pipeline_traces
            SET output_summary = ?, status = ?, tokens_used = ?,
                error_message = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (output_summary, status, tokens_used, error_message, trace_id))


def update_trace_duration(trace_id: int, duration_ms: int):
    """Update the duration of a trace entry."""
    with get_db() as conn:
        conn.execute("""
            UPDATE pipeline_traces SET duration_ms = ? WHERE id = ?
        """, (duration_ms, trace_id))


@contextmanager
def trace_stage(session_id: Optional[int], agent: str, stage: str,
               stage_name: str = None, input_summary: str = None):
    """Context manager that automatically traces a pipeline stage.

    Usage:
        with trace_stage(session_id, "writer", "draft", "LLM初稿", "topic: AI趋势") as t:
            text = generate_draft(topic)
            t["output"] = f"{len(text)} chars"
            t["tokens"] = 1500
    """
    trace_data = {"output": None, "tokens": 0}
    trace_id = create_trace(session_id, agent, stage, stage_name, input_summary)
    start_time = time.monotonic()

    try:
        yield trace_data
        duration_ms = int((time.monotonic() - start_time) * 1000)
        complete_trace(
            trace_id,
            output_summary=trace_data["output"],
            status="completed",
            tokens_used=trace_data["tokens"],
        )
        update_trace_duration(trace_id, duration_ms)
    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        complete_trace(
            trace_id,
            output_summary=trace_data["output"],
            status="failed",
            tokens_used=trace_data["tokens"],
            error_message=str(e),
        )
        update_trace_duration(trace_id, duration_ms)
        raise


def get_traces(session_id: Optional[int] = None, agent: str = None,
              limit: int = 100) -> list[dict]:
    """Get pipeline traces with optional filters."""
    with get_db() as conn:
        conditions = []
        params = []

        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if agent:
            conditions.append("agent = ?")
            params.append(agent)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        rows = conn.execute(f"""
            SELECT * FROM pipeline_traces
            {where}
            ORDER BY created_at DESC
            LIMIT ?
        """, params).fetchall()
        return [dict(row) for row in rows]


def get_trace_summary(session_id: int) -> dict:
    """Get a summary of traces for a session."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT agent, stage, stage_name, status, duration_ms, tokens_used, error_message
            FROM pipeline_traces
            WHERE session_id = ?
            ORDER BY created_at
        """, (session_id,)).fetchall()

        total_tokens = sum(r['tokens_used'] or 0 for r in rows)
        total_duration = sum(r['duration_ms'] or 0 for r in rows)
        failed_stages = [r['stage'] for r in rows if r['status'] == 'failed']

        return {
            'stages': [dict(r) for r in rows],
            'total_tokens': total_tokens,
            'total_duration_ms': total_duration,
            'failed_stages': failed_stages,
            'stage_count': len(rows),
        }


def get_trace_summaries_batch(session_ids: list[int]) -> dict[int, dict]:
    """Get trace summaries for multiple sessions in a single query."""
    if not session_ids:
        return {}
    with get_db() as conn:
        placeholders = ','.join('?' for _ in session_ids)
        rows = conn.execute(f"""
            SELECT session_id, agent, stage, stage_name, status, duration_ms, tokens_used, error_message
            FROM pipeline_traces
            WHERE session_id IN ({placeholders})
            ORDER BY session_id, created_at
        """, session_ids).fetchall()

        grouped: dict[int, list[dict]] = {}
        for r in rows:
            sid = r['session_id']
            grouped.setdefault(sid, []).append(dict(r))

        result = {}
        for sid, traces in grouped.items():
            total_tokens = sum(t.get('tokens_used') or 0 for t in traces)
            total_duration = sum(t.get('duration_ms') or 0 for t in traces)
            failed_stages = [t['stage'] for t in traces if t.get('status') == 'failed']
            result[sid] = {
                'stages': traces,
                'total_tokens': total_tokens,
                'total_duration_ms': total_duration,
                'failed_stages': failed_stages,
                'stage_count': len(traces),
            }
        return result
