"""Manual review (人工抽检) API routes.

Endpoints for quality calibration workflow:
- POST /api/reviews — Submit a manual review score
- GET /api/reviews — List review history
- GET /api/reviews/stats — Get review statistics
- GET /api/reviews/pending — Get articles pending review
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dashboard.backend.database.manual_reviews import (
    create_manual_review,
    get_manual_reviews,
    get_pending_review_articles,
    get_review_stats,
)

logger = logging.getLogger("gaoding.dashboard")
router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class ManualReviewCreate(BaseModel):
    """Request body for creating a manual review."""
    session_id: Optional[int] = None
    version_id: Optional[int] = None
    article_path: Optional[str] = None
    article_title: Optional[str] = None
    llm_score: Optional[int] = Field(None, ge=0, le=100)
    human_score: int = Field(..., ge=0, le=100)
    reviewer: str = "user"
    notes: Optional[str] = None


@router.post("")
def submit_review(review: ManualReviewCreate):
    """Submit a manual review score for an article.

    Calculates score_diff and flags deviation:
    - diff > 30 → critical
    - diff > 15 → warning
    - diff <= 15 → normal
    """
    try:
        result = create_manual_review(
            session_id=review.session_id,
            version_id=review.version_id,
            article_path=review.article_path,
            article_title=review.article_title,
            llm_score=review.llm_score,
            human_score=review.human_score,
            reviewer=review.reviewer,
            notes=review.notes,
        )
        if result["status"] == "critical":
            logger.warning(
                f"Manual review CRITICAL deviation: "
                f"LLM={review.llm_score} Human={review.human_score} "
                f"Diff={result['score_diff']} Article={review.article_title}"
            )
        return result
    except Exception as e:
        logger.error(f"Error creating manual review: {e}")
        raise HTTPException(status_code=500, detail="操作失败")


@router.get("")
def list_reviews(
    limit: int = 50,
    status: Optional[str] = None,
):
    """List manual review history.

    Args:
        limit: Max results (default 50)
        status: Filter by status (normal/warning/critical)
    """
    allowed_statuses = {"normal", "warning", "critical"}
    if status and status not in allowed_statuses:
        raise HTTPException(400, f"Invalid status: {status}. Allowed: {allowed_statuses}")
    try:
        reviews = get_manual_reviews(limit=limit, status=status)
        return {"reviews": reviews, "total": len(reviews)}
    except Exception as e:
        logger.error(f"Error listing reviews: {e}")
        raise HTTPException(status_code=500, detail="操作失败")


@router.get("/stats")
def review_statistics():
    """Get manual review statistics.

    Returns:
    - total_reviews: Total review count
    - avg_score_diff: Average absolute score difference
    - warning_count: Reviews with diff > 15
    - critical_count: Reviews with diff > 30
    - recent_deviation_rate: % of last 30 reviews with diff > 15
    """
    try:
        stats = get_review_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting review stats: {e}")
        raise HTTPException(status_code=500, detail="获取统计数据失败")


@router.get("/pending")
def pending_reviews(limit: int = 10):
    """Get articles that have been published but not yet manually reviewed.

    Returns articles from platform_versions (approved/distributed)
    that have no corresponding manual_reviews entry.
    """
    try:
        articles = get_pending_review_articles(limit=limit)
        return {"articles": articles, "total": len(articles)}
    except Exception as e:
        logger.error(f"Error getting pending reviews: {e}")
        raise HTTPException(status_code=500, detail="获取待审文章失败")
