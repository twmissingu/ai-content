"""Approval routes — queue, approve/reject, version management."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from config.settings import ACTIONS_DIR, REVIEW_DIR
from dashboard.backend.database import (
    create_approval_record,
    get_approval_records,
    get_pending_versions,
    get_platform_versions,
    update_platform_version,
)
from dashboard.backend.helpers import read_json, write_action
from dashboard.backend.models import ApproveRequest

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/approval", tags=["approval"])


@router.get("/queue")
def get_approval_queue():
    """List articles pending approval from queue/review/ and database."""
    articles = []

    for f in sorted(REVIEW_DIR.glob("*.meta.json"), key=os.path.getmtime, reverse=True):
        meta = read_json(f)
        article_id = f.stem.replace(".meta", "")
        article_path = REVIEW_DIR / f"{article_id}.md"
        article_content = article_path.read_text(encoding="utf-8") if article_path.exists() else ""
        articles.append({
            "id": article_id,
            "meta": meta,
            "content_preview": article_content[:500],
            "source": "filesystem",
        })

    try:
        pending_versions = get_pending_versions()
        for pv in pending_versions:
            articles.append({
                "id": f"db_{pv['id']}",
                "meta": {
                    "platform": pv['platform'],
                    "topic": pv.get('topic', ''),
                    "score": pv.get('score', 0),
                },
                "content_preview": "",
                "source": "database",
                "db_version_id": pv['id'],
            })
    except Exception as e:
        logger.error(f"Error fetching pending versions: {e}")

    return {"articles": articles, "count": len(articles)}


@router.post("/act")
def approval_act(req: ApproveRequest):
    """Write an approval action file and record in database."""
    if req.action not in ("approve", "reject", "rewrite"):
        raise HTTPException(400, f"Invalid action: {req.action}")

    path = write_action(
        req.action, req.target_id,
        reason=req.reason,
        platform_versions=req.platform_versions or ["wechat"],
        trigger_agent="publisher" if req.action == "approve" else "writer",
    )

    db_warning = None
    if req.target_id.startswith("db_"):
        try:
            version_id = int(req.target_id.replace("db_", ""))
            action_map = {"approve": "pass", "reject": "reject", "rewrite": "rewrite"}
            create_approval_record(
                version_id=version_id,
                action=action_map.get(req.action, req.action),
                reason=req.reason,
            )
            update_platform_version(
                version_id=version_id,
                status="approved" if req.action == "approve" else "rejected",
            )
        except Exception as e:
            db_warning = f"Database recording failed: {e}"
            logger.error(db_warning)

    response = {"status": "ok", "action": req.action, "target_id": req.target_id, "path": str(path)}
    if db_warning:
        response["status"] = "partial"
        response["warning"] = db_warning

    return response


@router.get("/versions/{session_id}")
def get_session_versions(session_id: int):
    """Get all platform versions for a specific pipeline session."""
    try:
        versions = get_platform_versions(session_id)
        return {"versions": versions, "count": len(versions)}
    except Exception as e:
        logger.error(f"Error fetching versions for session {session_id}: {e}")
        raise HTTPException(500, "获取版本列表失败")


@router.post("/version/{version_id}/approve")
def approve_version(version_id: int):
    """Approve a specific platform version."""
    try:
        update_platform_version(version_id, status="approved")
        create_approval_record(version_id, action="pass")
        logger.info(f"Version {version_id} approved")
        return {"status": "ok", "version_id": version_id, "action": "approved"}
    except Exception as e:
        logger.error(f"Error approving version {version_id}: {e}")
        raise HTTPException(500, "审批通过操作失败")


@router.post("/version/{version_id}/reject")
def reject_version(version_id: int):
    """Reject a specific platform version."""
    try:
        update_platform_version(version_id, status="rejected")
        create_approval_record(version_id, action="reject")
        logger.info(f"Version {version_id} rejected")
        return {"status": "ok", "version_id": version_id, "action": "rejected"}
    except Exception as e:
        logger.error(f"Error rejecting version {version_id}: {e}")
        raise HTTPException(500, "驳回操作失败")


@router.get("/records")
def get_all_approval_records(limit: int = Query(50, ge=1, le=200)):
    """Get recent approval records across all versions."""
    try:
        records = get_approval_records(limit=limit)
        return {"records": records, "count": len(records)}
    except Exception as e:
        logger.error(f"Error fetching approval records: {e}")
        raise HTTPException(500, "获取审批记录失败")
