"""FastAPI Dashboard backend — Pipeline status, approval ops, config.

5 route groups:
  /api/pipeline    — pipeline status & timeline
  /api/approval    — approval queue & operations
  /api/topics      — today's topic candidates
  /api/data        — analytics & charts
  /api/kb          — knowledge base search
  /api/config      — system configuration
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import (
    ACTIONS_DIR,
    CONFIG_DIR,
    FAILED_DIR,
    KB_DIR,
    PENDING_DIR,
    REVIEW_DIR,
    STATUS_DIR,
    PROJECT_ROOT,
)

app = FastAPI(title="稿定 Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ─────────────────────────────────────────────────────────
class ApproveRequest(BaseModel):
    action: str  # approve | reject | rewrite
    target_id: str
    reason: Optional[str] = None
    platform_versions: Optional[list[str]] = None


class ConfirmRequest(BaseModel):
    target_id: str
    action: str = "confirm"


class ConfigUpdate(BaseModel):
    key: str
    value: str | int | float | bool | list | dict


# ── Helpers ────────────────────────────────────────────────────────
def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_action(action: str, target_id: str, **kwargs):
    """Write an action file (triggers scan_actions processing)."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{action}_{target_id}_{stamp}.json"
    tmp = ACTIONS_DIR / f".{filename}.tmp"
    payload = {
        "action": action,
        "target_id": target_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **kwargs,
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    os.rename(tmp, ACTIONS_DIR / filename)
    return ACTIONS_DIR / filename


def _detect_timeout(status: dict, max_minutes: int = 30) -> bool:
    started = status.get("started_at", "")
    if not started:
        return False
    try:
        start = datetime.strptime(started.split(".")[0], "%Y%m%d_%H%M%S")
        elapsed = (datetime.now() - start).total_seconds() / 60
        return elapsed > max_minutes
    except (ValueError, TypeError):
        return False


def _load_schedule() -> dict:
    path = CONFIG_DIR / "schedule.json"
    if path.exists():
        return _read_json(path)
    return {
        "morning_scout": "09:00",
        "morning_writer": "09:30",
        "evening_scout": "14:00",
        "evening_writer": "14:30",
        "working_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "monthly_budget": 15.0,
        "quality_threshold": 70,
    }


# ── Routes: Pipeline ───────────────────────────────────────────────
@app.get("/api/pipeline/status")
def get_pipeline_status():
    """Read all status files and return aggregated view."""
    agents = {}
    for f in STATUS_DIR.glob("*.json"):
        data = _read_json(f)
        name = f.stem
        agents[name] = data
        # Timeout detection
        timeout = _detect_timeout(data)
        if timeout and data.get("progress_pct", 100) < 100:
            agents[name]["timeout"] = True

    return {"agents": agents, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/pipeline/timeline")
def get_pipeline_timeline():
    """Get recent pipeline sessions from kb/history/."""
    history_dir = KB_DIR / "history"
    if not history_dir.exists():
        return {"sessions": []}
    sessions = []
    for d in sorted(history_dir.iterdir(), reverse=True)[:14]:
        if d.is_dir():
            articles = list(d.glob("*.md"))
            sessions.append({
                "date": d.name,
                "article_count": len(articles),
                "articles": [a.stem for a in articles],
            })
    return {"sessions": sessions}


# ── Routes: Approval ───────────────────────────────────────────────
@app.get("/api/approval/queue")
def get_approval_queue():
    """List articles pending approval from queue/review/."""
    articles = []
    for f in sorted(REVIEW_DIR.glob("*.meta.json"), key=os.path.getmtime, reverse=True):
        meta = _read_json(f)
        article_id = f.stem.replace(".meta", "")
        article_path = REVIEW_DIR / f"{article_id}.md"
        article_content = article_path.read_text(encoding="utf-8") if article_path.exists() else ""
        articles.append({
            "id": article_id,
            "meta": meta,
            "content_preview": article_content[:500],
        })
    return {"articles": articles, "count": len(articles)}


@app.post("/api/approval/act")
def approval_act(req: ApproveRequest):
    """Write an approval action file."""
    if req.action not in ("approve", "reject", "rewrite"):
        raise HTTPException(400, f"Invalid action: {req.action}")
    path = _write_action(
        req.action, req.target_id,
        reason=req.reason,
        platform_versions=req.platform_versions or ["wechat"],
        trigger_agent="publisher" if req.action == "approve" else "writer",
    )
    return {"status": "ok", "action": req.action, "target_id": req.target_id, "path": str(path)}


# ── Routes: Topics ─────────────────────────────────────────────────
@app.get("/api/topics")
def get_topics():
    """List pending topic candidates from queue/pending/."""
    topics = []
    for f in sorted(PENDING_DIR.glob("topic_*.json"), key=os.path.getmtime, reverse=True):
        data = _read_json(f)
        data["id"] = f.stem
        data["filename"] = f.name
        topics.append(data)
    return {"topics": topics, "count": len(topics)}


@app.post("/api/topics/confirm")
def confirm_topic(req: ConfirmRequest):
    """Confirm a topic, triggering Writer on next cron."""
    path = _write_action("confirm", req.target_id)
    return {"status": "ok", "path": str(path)}


# ── Routes: Data ───────────────────────────────────────────────────
@app.get("/api/data/cost")
def get_cost_data():
    """Read cost tracking data from data/logs/cost.csv."""
    cost_path = PROJECT_ROOT / "data/logs/cost.csv"
    if not cost_path.exists():
        return {"daily": [], "monthly_total": 0}
    lines = cost_path.read_text().strip().split("\n")[1:]  # skip header
    daily: dict[str, float] = {}
    for line in lines:
        parts = line.split(",")
        if len(parts) >= 4:
            date = parts[0][:10]
            total_tokens = int(parts[3])
            # Estimate cost: ~$0.003 per 1K tokens for xiaomi
            cost = total_tokens * 0.003 / 1000
            daily[date] = daily.get(date, 0) + cost
    daily_list = [{"date": d, "cost": round(c, 4)} for d, c in sorted(daily.items())]
    monthly = round(sum(daily.values()), 4)
    return {"daily": daily_list, "monthly_total": monthly}


@app.get("/api/data/analytics")
def get_analytics():
    """Read kb/viral/ for analytics data."""
    viral_dir = KB_DIR / "viral"
    if not viral_dir.exists():
        return {"topics": [], "keywords": []}
    data = {}
    for f in viral_dir.glob("*.json"):
        data.update(_read_json(f))
    return data


# ── Routes: Knowledge Base ─────────────────────────────────────────
@app.get("/api/kb/search")
def search_kb(q: str = Query("", min_length=1)):
    """Search knowledge base by keyword (simple file name/content match)."""
    if not q:
        return {"results": []}
    results = []
    for path in KB_DIR.rglob("*.md"):
        if q.lower() in path.stem.lower():
            results.append({
                "path": str(path.relative_to(KB_DIR)),
                "title": path.stem,
                "type": path.parent.name,
            })
            continue
        # Check content
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if q.lower() in content.lower():
                # Find the matching line
                for line in content.split("\n"):
                    if q.lower() in line.lower():
                        results.append({
                            "path": str(path.relative_to(KB_DIR)),
                            "title": path.stem,
                            "type": path.parent.name,
                            "match": line.strip()[:100],
                        })
                        break
        except OSError:
            pass
    return {"results": results[:20]}


@app.get("/api/kb/sections")
def get_kb_sections():
    """List knowledge base sections and their article counts."""
    sections = []
    for d in sorted(KB_DIR.iterdir()):
        if d.is_dir() and d.name != "history":
            count = len(list(d.rglob("*.md")))
            sections.append({"name": d.name, "count": count, "path": str(d)})
    # History is special — date subdirectories
    history_dir = KB_DIR / "history"
    if history_dir.exists():
        total_history = sum(1 for _ in history_dir.rglob("*.md"))
        sections.append({"name": "history", "count": total_history, "path": str(history_dir)})
    return {"sections": sections}


# ── Routes: Config ─────────────────────────────────────────────────
@app.get("/api/config")
def get_config():
    """Read system configuration."""
    return _load_schedule()


@app.post("/api/config/update")
def update_config(update: ConfigUpdate):
    """Update a single configuration value."""
    path = CONFIG_DIR / "schedule.json"
    config = _load_schedule()
    config[update.key] = update.value
    tmp = CONFIG_DIR / ".schedule.json.tmp"
    tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    os.rename(tmp, path)
    return {"status": "ok", "key": update.key, "value": update.value}


# ── Routes: Health ─────────────────────────────────────────────────
@app.get("/api/health")
def health():
    """Basic health check."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue_sizes": {
            "pending": len(list(PENDING_DIR.glob("*.json"))),
            "review": len(list(REVIEW_DIR.glob("*.meta.json"))),
            "actions": len(list(ACTIONS_DIR.glob("*.json"))),
            "failed": len(list(Path(str(FAILED_DIR)).glob("*.json"))) if 'FAILED_DIR' in dir() else 0,
        },
    }


# ── Entry ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8710)
