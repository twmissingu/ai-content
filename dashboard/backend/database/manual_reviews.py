"""Manual review (人工抽检) database operations.

Supports the quality calibration workflow:
- Record human scores for published articles
- Compare human vs LLM scores
- Flag deviations > 15% as warnings
"""

from .core import get_db


def create_manual_review(
    session_id: int | None = None,
    version_id: int | None = None,
    article_path: str | None = None,
    article_title: str | None = None,
    llm_score: int | None = None,
    human_score: int = 0,
    reviewer: str = "user",
    notes: str | None = None,
) -> dict:
    """Record a manual review score for an article.

    Returns the created review record.
    """
    score_diff = 0
    status = "normal"
    if llm_score is not None and human_score is not None:
        score_diff = abs(human_score - llm_score)
        if score_diff > 30:
            status = "critical"
        elif score_diff > 15:
            status = "warning"

    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO manual_reviews
               (session_id, version_id, article_path, article_title,
                llm_score, human_score, score_diff, status, reviewer, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, version_id, article_path, article_title,
             llm_score, human_score, score_diff, status, reviewer, notes),
        )
        review_id = cursor.lastrowid

    return {
        "id": review_id,
        "session_id": session_id,
        "version_id": version_id,
        "article_title": article_title,
        "llm_score": llm_score,
        "human_score": human_score,
        "score_diff": score_diff,
        "status": status,
        "reviewer": reviewer,
        "notes": notes,
    }


def get_manual_reviews(
    limit: int = 50,
    status: str | None = None,
) -> list[dict]:
    """Get manual review records, optionally filtered by status."""
    with get_db() as conn:
        if status:
            rows = conn.execute(
                """SELECT * FROM manual_reviews
                   WHERE status = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM manual_reviews
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_review_stats() -> dict:
    """Get manual review statistics.

    Returns summary stats including:
    - total_reviews: total number of reviews
    - avg_score_diff: average absolute score difference
    - warning_count: number of warnings (diff > 15)
    - critical_count: number of critical deviations (diff > 30)
    - recent_deviation_rate: % of recent reviews with diff > 15
    """
    with get_db() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) as total_reviews,
                COALESCE(AVG(score_diff), 0) as avg_score_diff,
                SUM(CASE WHEN status = 'warning' THEN 1 ELSE 0 END) as warning_count,
                SUM(CASE WHEN status = 'critical' THEN 1 ELSE 0 END) as critical_count
               FROM manual_reviews"""
        ).fetchone()

        # Recent deviation rate (last 30 reviews)
        recent = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN score_diff > 15 THEN 1 ELSE 0 END) as deviated
               FROM (
                   SELECT score_diff FROM manual_reviews
                   ORDER BY created_at DESC LIMIT 30
               )"""
        ).fetchone()

    total = row["total_reviews"] if row else 0
    recent_total = recent["total"] if recent else 0
    recent_deviated = recent["deviated"] if recent else 0
    deviation_rate = (recent_deviated / recent_total * 100) if recent_total > 0 else 0

    return {
        "total_reviews": total,
        "avg_score_diff": round(row["avg_score_diff"], 1) if row else 0,
        "warning_count": row["warning_count"] if row else 0,
        "critical_count": row["critical_count"] if row else 0,
        "recent_deviation_rate": round(deviation_rate, 1),
        "recent_review_count": recent_total,
    }


def get_pending_review_articles(limit: int = 10) -> list[dict]:
    """Get recently published articles that haven't been manually reviewed yet.

    Returns articles from platform_versions that are approved/distributed
    but have no corresponding manual_reviews entry.
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT pv.id as version_id, pv.session_id, pv.platform,
                      pv.content_path, pv.score as llm_score,
                      ps.topic, ps.completed_at
               FROM platform_versions pv
               JOIN pipeline_sessions ps ON pv.session_id = ps.id
               WHERE pv.status IN ('approved', 'distributed')
                 AND pv.id NOT IN (SELECT COALESCE(version_id, 0) FROM manual_reviews)
               ORDER BY ps.completed_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
