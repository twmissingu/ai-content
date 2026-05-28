"""Platform version and approval record operations."""

import logging
from .core import get_db

logger = logging.getLogger("gaoding.database")


def create_platform_version(session_id: int, platform: str,
                          content_path: str = None, meta_path: str = None) -> int:
    """Create a platform version entry."""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO platform_versions (session_id, platform, content_path, meta_path)
            VALUES (?, ?, ?, ?)
        """, (session_id, platform, content_path, meta_path))
        return cursor.lastrowid


def update_platform_version(version_id: int, **kwargs):
    """Update platform version fields."""
    allowed_fields = {'status', 'content_path', 'meta_path', 'score', 'rewrite_round'}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        return

    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [version_id]

    with get_db() as conn:
        conn.execute(f"""
            UPDATE platform_versions
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, values)


def get_platform_versions(session_id: int) -> list[dict]:
    """Get all platform versions for a session."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM platform_versions
            WHERE session_id = ?
            ORDER BY platform
        """, (session_id,)).fetchall()
        return [dict(row) for row in rows]


def get_pending_versions() -> list[dict]:
    """Get all pending platform versions for approval queue."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT pv.*, ps.topic, ps.date, ps.period
            FROM platform_versions pv
            JOIN pipeline_sessions ps ON pv.session_id = ps.id
            WHERE pv.status = 'pending'
            ORDER BY ps.date DESC, ps.created_at DESC
        """).fetchall()
        return [dict(row) for row in rows]


def create_approval_record(version_id: int, action: str,
                          reason: str = None, operator: str = 'user') -> int:
    """Create an approval record."""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO approval_records (version_id, action, reason, operator)
            VALUES (?, ?, ?, ?)
        """, (version_id, action, reason, operator))
        return cursor.lastrowid


def get_approval_records(version_id: int = None, limit: int = 100) -> list[dict]:
    """Get approval records with optional version filter."""
    with get_db() as conn:
        if version_id:
            rows = conn.execute("""
                SELECT * FROM approval_records
                WHERE version_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (version_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT ar.*, pv.platform, ps.topic
                FROM approval_records ar
                JOIN platform_versions pv ON ar.version_id = pv.id
                JOIN pipeline_sessions ps ON pv.session_id = ps.id
                ORDER BY ar.created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_quality_flywheel_data(days: int = 30) -> dict:
    """Analyze approval history to recommend quality gate adjustments.

    Returns:
        - approved_scores: list of scores for approved articles
        - rejected_scores: list of scores for rejected articles
        - recommended_thresholds: suggested quality gate values
        - sample_size: number of data points used
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT pv.score, ar.action, pv.platform
            FROM approval_records ar
            JOIN platform_versions pv ON ar.version_id = pv.id
            WHERE ar.created_at >= datetime('now', ?)
              AND pv.score IS NOT NULL
            ORDER BY ar.created_at DESC
        """, (f"-{days} days",)).fetchall()

    if not rows:
        return {
            "approved_scores": [],
            "rejected_scores": [],
            "recommended_thresholds": None,
            "sample_size": 0,
            "message": "数据不足，需要更多审批记录才能生成推荐",
        }

    approved = [r["score"] for r in rows if r["action"] == "pass"]
    rejected = [r["score"] for r in rows if r["action"] == "reject"]

    result = {
        "approved_scores": approved,
        "rejected_scores": rejected,
        "sample_size": len(rows),
    }

    # Only recommend if we have enough data
    if len(approved) < 5 or len(rejected) < 3:
        result["recommended_thresholds"] = None
        result["message"] = f"已收集 {len(approved)} 条通过 / {len(rejected)} 条驳回，建议阈值需要更多数据"
        return result

    # Calculate recommended thresholds
    approved_sorted = sorted(approved)
    rejected_sorted = sorted(rejected)

    # Use the 25th percentile of approved as the new proofread threshold
    proofread_idx = max(0, len(approved_sorted) // 4)
    proofread_threshold = int(approved_sorted[proofread_idx])

    # Use the 75th percentile of rejected as the critique threshold
    critique_idx = max(0, len(rejected_sorted) * 3 // 4)
    critique_threshold = int(rejected_sorted[critique_idx])

    # Title threshold: average of approved scores minus buffer
    title_threshold = int(sum(approved) / len(approved) * 0.9)

    # Clamp to reasonable ranges
    proofread_threshold = max(50, min(80, proofread_threshold))
    critique_threshold = max(60, min(85, critique_threshold))
    title_threshold = max(65, min(85, title_threshold))

    result["recommended_thresholds"] = {
        "proofread_threshold": proofread_threshold,
        "critique_threshold": critique_threshold,
        "title_threshold": title_threshold,
        "max_rewrite_rounds": 3,
    }
    result["message"] = (
        f"基于 {len(approved)} 条通过 / {len(rejected)} 条驳回记录，"
        f"推荐调整质量门禁阈值"
    )

    return result
