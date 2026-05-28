"""Pipeline session operations."""

from datetime import datetime, timezone
from typing import Optional

from .core import get_db, cached_query, _invalidate_cache


def create_pipeline_session(date: str, period: str, topic: str,
                          source_url: str = None) -> int:
    """Create a new pipeline session."""
    _invalidate_cache()
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO pipeline_sessions (date, period, topic, source_url, status, started_at)
            VALUES (?, ?, ?, ?, 'running', CURRENT_TIMESTAMP)
        """, (date, period, topic, source_url))
        return cursor.lastrowid


def update_pipeline_session(session_id: int, **kwargs):
    """Update pipeline session fields."""
    allowed_fields = {'status', 'topic', 'source_url', 'started_at',
                      'completed_at', 'error_message'}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return

    _invalidate_cache()
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [session_id]

    with get_db() as conn:
        conn.execute(f"""
            UPDATE pipeline_sessions
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, values)


@cached_query(ttl=10.0)
def get_pipeline_sessions(
    limit: int = 30,
    offset: int = 0,
    status: Optional[str] = None,
    fields: Optional[list[str]] = None
) -> dict:
    """Get pipeline sessions with pagination and optional status filter."""
    valid_fields = {
        'id', 'date', 'period', 'topic', 'source_url', 'status',
        'started_at', 'completed_at', 'error_message', 'created_at', 'updated_at'
    }

    if fields:
        select_fields = ', '.join(f for f in fields if f in valid_fields)
        if not select_fields:
            select_fields = 'id, date, period, topic, status'
    else:
        select_fields = '*'

    with get_db() as conn:
        count_query = "SELECT COUNT(*) FROM pipeline_sessions"
        count_params = []
        if status:
            count_query += " WHERE status = ?"
            count_params.append(status)

        total = conn.execute(count_query, count_params).fetchone()[0]

        query = f"SELECT {select_fields} FROM pipeline_sessions"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()

        return {
            'items': [dict(row) for row in rows],
            'total': total,
            'limit': limit,
            'offset': offset,
        }


def get_today_sessions() -> list[dict]:
    """Get today's pipeline sessions."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM pipeline_sessions
            WHERE date = ?
            ORDER BY period, created_at
        """, (today,)).fetchall()
        return [dict(row) for row in rows]
