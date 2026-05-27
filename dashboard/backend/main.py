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
import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from contextlib import asynccontextmanager
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
    PROCESSED_DIR,
    PROJECT_ROOT,
    REVIEW_DIR,
    STATUS_DIR,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gaoding.dashboard")

# Import database layer
from dashboard.backend.database import (
    init_db,
    get_db,
    get_pipeline_sessions,
    update_platform_version,
    get_pending_versions,
    create_approval_record,
    log_token_usage,
    get_token_usage_stats,
    set_config_value,
    get_config_value,
    get_pending_config,
    get_all_config,
    check_budget_limit,
)

# Import search service
from dashboard.backend.search import (
    search_kb as search_kb_fts,
    index_all_kb,
    get_index_stats,
    auto_index_if_needed,
)

# Import Feishu notification
from dashboard.backend.feishu import (
    send_feishu_alert,
    alert_budget_warning,
)

# Import configuration service
from dashboard.backend.config_service import (
    get_schedule_config,
    get_writing_styles,
    get_quality_gates,
    get_source_config,
    get_model_config,
    get_budget_config,
    update_schedule,
    update_writing_style,
    update_quality_gates,
    update_source,
    update_budget,
    generate_style_prompt,
    get_all_config_summary,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, search index, and start background scanner on startup."""
    # Initialize database
    init_db()
    logger.info("SQLite database initialized")
    
    # Auto-index knowledge base
    try:
        index_stats = auto_index_if_needed()
        logger.info(f"Knowledge base index: {index_stats}")
    except Exception as e:
        logger.error(f"Error initializing search index: {e}")
    
    # Start background scanner
    thread = threading.Thread(target=_scan_loop, daemon=True, name="action-scanner")
    thread.start()
    logger.info("Background action scanner started (10s interval)")
    
    # Start budget monitor
    budget_thread = threading.Thread(target=_budget_monitor_loop, daemon=True, name="budget-monitor")
    budget_thread.start()
    logger.info("Budget monitor started")
    
    yield
    
    # Shutdown all background threads using events
    _scanner_stop_event.set()
    _budget_stop_event.set()
    logger.info("Background action scanner stopped")
    logger.info("Budget monitor stopped")


app = FastAPI(title="稿定 Dashboard", version="0.2.0", lifespan=lifespan)

# ── Rate Limiting ─────────────────────────────────────────────────
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed for the given IP."""
        now = time.time()
        minute_ago = now - 60
        
        with self._lock:
            # Clean old records
            self.requests[client_ip] = [
                t for t in self.requests[client_ip] if t > minute_ago
            ]
            
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                return False
            
            self.requests[client_ip].append(now)
            return True


rate_limiter = RateLimiter(requests_per_minute=120)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limiting."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/api/health":
            return await call_next(request)
        
        client_ip = request.client.host
        if not rate_limiter.is_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )
        
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

# CORS origins - configurable via environment variable
# Default to localhost for security; override for Docker/production
def _get_cors_origins() -> list[str]:
    """Get and validate CORS origins from environment."""
    env_value = os.getenv("CORS_ORIGINS", "")
    
    # Default origins for development
    default_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8710",
        "http://127.0.0.1:8710",
    ]
    
    if not env_value:
        return default_origins
    
    origins = [o.strip() for o in env_value.split(",") if o.strip()]
    
    # Security check: warn if wildcard in production
    environment = os.getenv("ENV", os.getenv("NODE_ENV", "development"))
    if "*" in origins and environment == "production":
        logger.warning(
            "CORS_ORIGINS='*' is not recommended for production! "
            "Consider restricting to specific domains."
        )
    
    # Validate origin format
    valid_origins = []
    for origin in origins:
        if origin == "*":
            valid_origins.append(origin)
        elif origin.startswith(("http://", "https://")):
            valid_origins.append(origin)
        else:
            logger.warning(f"Invalid CORS origin ignored: {origin}")
    
    return valid_origins if valid_origins else default_origins


CORS_ORIGINS = _get_cors_origins()
logger.info(f"CORS origins: {CORS_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Restrict methods
    allow_headers=["Content-Type", "Authorization"],  # Restrict headers
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


class TokenLogRequest(BaseModel):
    agent: str = "unknown"
    model: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0
    session_id: Optional[int] = None


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
    """Read all status files and return aggregated view with budget info."""
    agents = {}
    for f in STATUS_DIR.glob("*.json"):
        data = _read_json(f)
        name = f.stem
        agents[name] = data
        # Timeout detection
        timeout = _detect_timeout(data)
        if timeout and data.get("progress_pct", 100) < 100:
            agents[name]["timeout"] = True

    # Add budget status
    budget = check_budget_limit()
    
    return {
        "agents": agents, 
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "budget": budget,
    }


@app.get("/api/pipeline/timeline")
def get_pipeline_timeline():
    """Get recent pipeline sessions from database and filesystem."""
    sessions = []
    
    # Get from database
    db_result = get_pipeline_sessions(limit=14)
    for s in db_result.get('items', []):
        sessions.append({
            "id": s.get('id'),
            "date": s.get('date', ''),
            "period": s.get('period', ''),
            "topic": s.get('topic', ''),
            "status": s.get('status', 'unknown'),
            "article_count": 1,
            "articles": [s.get('topic', '')],
            "source": "database",
            "started_at": s.get('started_at'),
            "completed_at": s.get('completed_at'),
        })
    
    # Also get from kb/history for backward compatibility
    history_dir = KB_DIR / "history"
    if history_dir.exists():
        for d in sorted(history_dir.iterdir(), reverse=True)[:14]:
            if d.is_dir():
                articles = list(d.glob("*.md"))
                sessions.append({
                    "id": None,
                    "date": d.name,
                    "period": "",
                    "topic": "",
                    "status": "completed",
                    "article_count": len(articles),
                    "articles": [a.stem for a in articles],
                    "source": "filesystem",
                    "started_at": None,
                    "completed_at": None,
                })
    
    return {"sessions": sessions}


# ── Routes: Approval ───────────────────────────────────────────────
@app.get("/api/approval/queue")
def get_approval_queue():
    """List articles pending approval from queue/review/ and database."""
    articles = []
    
    # Get from filesystem (legacy support)
    for f in sorted(REVIEW_DIR.glob("*.meta.json"), key=os.path.getmtime, reverse=True):
        meta = _read_json(f)
        article_id = f.stem.replace(".meta", "")
        article_path = REVIEW_DIR / f"{article_id}.md"
        article_content = article_path.read_text(encoding="utf-8") if article_path.exists() else ""
        articles.append({
            "id": article_id,
            "meta": meta,
            "content_preview": article_content[:500],
            "source": "filesystem",
        })
    
    # Get pending versions from database
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
        print(f"[api] Error fetching pending versions: {e}")
    
    return {"articles": articles, "count": len(articles)}


@app.post("/api/approval/act")
def approval_act(req: ApproveRequest):
    """Write an approval action file and record in database."""
    if req.action not in ("approve", "reject", "rewrite"):
        raise HTTPException(400, f"Invalid action: {req.action}")
    
    # Write action file for scanner
    path = _write_action(
        req.action, req.target_id,
        reason=req.reason,
        platform_versions=req.platform_versions or ["wechat"],
        trigger_agent="publisher" if req.action == "approve" else "writer",
    )
    
    # Record in database if it's a database-tracked version
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
            print(f"[api] {db_warning}")
    
    response = {"status": "ok", "action": req.action, "target_id": req.target_id, "path": str(path)}
    if db_warning:
        response["status"] = "partial"
        response["warning"] = db_warning
    
    return response


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
    """Read cost tracking data from database."""
    try:
        stats = get_token_usage_stats(days=30)
        
        # Format daily data
        daily_list = []
        for row in stats.get('daily', []):
            daily_list.append({
                "date": row['date'],
                "cost": round(row.get('cost', 0), 4),
                "input_tokens": row.get('input_tokens', 0),
                "output_tokens": row.get('output_tokens', 0),
                "call_count": row.get('call_count', 0),
            })
        
        # Monthly total
        monthly = stats.get('monthly', {})
        monthly_total = round(monthly.get('cost', 0), 4)
        
        # Agent breakdown
        by_agent = stats.get('by_agent', [])
        
        return {
            "daily": daily_list, 
            "monthly_total": monthly_total,
            "by_agent": by_agent,
            "budget": check_budget_limit(),
        }
    except Exception as e:
        print(f"[api] Error getting cost data: {e}")
        # Fallback to CSV if database fails
        cost_path = PROJECT_ROOT / "data/logs/cost.csv"
        if not cost_path.exists():
            return {"daily": [], "monthly_total": 0, "error": str(e)}
        lines = cost_path.read_text().strip().split("\n")[1:]
        daily: dict[str, float] = {}
        for line in lines:
            parts = line.split(",")
            if len(parts) >= 4:
                date = parts[0][:10]
                total_tokens = int(parts[3])
                cost = total_tokens * 0.003 / 1000
                daily[date] = daily.get(date, 0) + cost
        daily_list = [{"date": d, "cost": round(c, 4)} for d, c in sorted(daily.items())]
        monthly = round(sum(daily.values()), 4)
        return {"daily": daily_list, "monthly_total": monthly, "source": "csv_fallback"}


@app.get("/api/data/analytics")
def get_analytics():
    """Read analytics data from database and kb/viral/."""
    data = {"topics": [], "keywords": []}
    
    # Get from kb/viral/
    viral_dir = KB_DIR / "viral"
    if viral_dir.exists():
        for f in viral_dir.glob("*.json"):
            data.update(_read_json(f))
    
    # Add pipeline statistics from database
    try:
        sessions_result = get_pipeline_sessions(limit=30)
        sessions = sessions_result.get('items', [])
        data['pipeline_stats'] = {
            'total_sessions': sessions_result.get('total', len(sessions)),
            'completed': sum(1 for s in sessions if s.get('status') == 'completed'),
            'failed': sum(1 for s in sessions if s.get('status') == 'failed'),
            'running': sum(1 for s in sessions if s.get('status') == 'running'),
        }
    except Exception as e:
        logger.error(f"Error getting pipeline stats: {e}")
    
    return data


# ── Routes: Knowledge Base ─────────────────────────────────────────
@app.get("/api/kb/search")
def search_kb(q: str = Query("", min_length=1), section: Optional[str] = None):
    """Search knowledge base using FTS5 with Chinese tokenization."""
    if not q:
        return {"results": []}
    
    try:
        # Use FTS5 search
        results = search_kb_fts(q, section=section, limit=20)
        return {
            "results": results,
            "count": len(results),
            "query": q,
            "section": section,
            "search_type": "fts5",
        }
    except Exception as e:
        print(f"[api] FTS5 search failed, using fallback: {e}")
        
        # Fallback to simple search
        results = []
        for path in KB_DIR.rglob("*.md"):
            if q.lower() in path.stem.lower():
                results.append({
                    "path": str(path.relative_to(KB_DIR)),
                    "title": path.stem,
                    "type": path.parent.name,
                })
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if q.lower() in content.lower():
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
        
        return {
            "results": results[:20],
            "count": len(results[:20]),
            "query": q,
            "search_type": "fallback",
        }


@app.get("/api/kb/sections")
def get_kb_sections():
    """List knowledge base sections and their article counts."""
    sections = []
    
    # Get from index stats if available
    try:
        index_stats = get_index_stats()
        indexed_sections = index_stats.get('by_section', {})
    except Exception:
        indexed_sections = {}
    
    # Scan filesystem
    if KB_DIR.exists():
        for d in sorted(KB_DIR.iterdir()):
            if d.is_dir() and d.name != "history":
                # Use index count if available, otherwise count files
                count = indexed_sections.get(d.name, len(list(d.rglob("*.md"))))
                sections.append({
                    "name": d.name, 
                    "count": count, 
                    "path": str(d),
                })
        
        # History is special — date subdirectories
        history_dir = KB_DIR / "history"
        if history_dir.exists():
            total_history = indexed_sections.get('history', sum(1 for _ in history_dir.rglob("*.md")))
            sections.append({
                "name": "history", 
                "count": total_history, 
                "path": str(history_dir),
            })
    
    return {"sections": sections}


@app.post("/api/kb/reindex")
def reindex_kb():
    """Force reindex knowledge base."""
    try:
        stats = index_all_kb(force=True)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        raise HTTPException(500, f"Reindex failed: {e}")


# ── Routes: Config ─────────────────────────────────────────────────
@app.get("/api/config")
def get_config():
    """Read all system configuration."""
    try:
        return get_all_config_summary()
    except Exception as e:
        print(f"[api] Error getting config: {e}")
        # Fallback to basic config
        return _load_schedule()


@app.get("/api/config/{section}")
def get_config_section(section: str):
    """Read specific configuration section."""
    section_map = {
        "schedule": get_schedule_config,
        "styles": get_writing_styles,
        "gates": get_quality_gates,
        "sources": get_source_config,
        "model": get_model_config,
        "budget": get_budget_config,
    }
    
    getter = section_map.get(section)
    if not getter:
        raise HTTPException(404, f"Unknown config section: {section}")
    
    try:
        return getter()
    except Exception as e:
        raise HTTPException(500, f"Error reading {section}: {e}")


@app.post("/api/config/schedule")
def update_schedule_config(update: ConfigUpdate):
    """Update schedule configuration.
    
    Note: Schedule changes are applied to the config file immediately,
    but require Hermes gateway restart to take effect for cron jobs.
    """
    try:
        # Apply the change immediately
        result = update_schedule(update.key, update.value)
        
        # Determine if Hermes restart is needed
        time_keys = {'morning_scout', 'morning_writer', 'evening_scout', 'evening_writer'}
        needs_restart = update.key in time_keys
        
        response = {
            "status": "ok",
            "key": update.key,
            "value": update.value,
        }
        
        if needs_restart:
            response["message"] = "配置已更新。需要重启 Hermes gateway 才能使新的调度时间生效。"
            response["needs_restart"] = True
        
        return response
            
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error updating schedule: {e}")


@app.post("/api/config/styles/{style_name}")
def update_style_config(style_name: str, updates: dict):
    """Update a writing style preset."""
    try:
        result = update_writing_style(style_name, updates)
        return {"status": "ok", "style": style_name, "config": result}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Error updating style: {e}")


@app.post("/api/config/gates")
def update_gates_config(updates: dict):
    """Update quality gate thresholds."""
    try:
        result = update_quality_gates(updates)
        return {"status": "ok", "config": result}
    except Exception as e:
        raise HTTPException(500, f"Error updating gates: {e}")


@app.post("/api/config/sources/{source_name}")
def update_source_config(source_name: str, updates: dict):
    """Update source configuration."""
    try:
        result = update_source(source_name, updates)
        return {"status": "ok", "source": source_name, "config": result}
    except Exception as e:
        raise HTTPException(500, f"Error updating source: {e}")


@app.post("/api/config/budget")
def update_budget_config(updates: dict):
    """Update budget configuration."""
    try:
        result = update_budget(updates)
        return {"status": "ok", "config": result}
    except Exception as e:
        raise HTTPException(500, f"Error updating budget: {e}")


@app.get("/api/config/style-prompt/{style_name}")
def get_style_prompt(style_name: str):
    """Get generated prompt for a writing style."""
    prompt = generate_style_prompt(style_name)
    if not prompt:
        raise HTTPException(404, f"Unknown style: {style_name}")
    return {"style": style_name, "prompt": prompt}


# ── Background action scanner ─────────────────────────────────────
_scanner_stop_event = threading.Event()
_budget_stop_event = threading.Event()

DISPATCH_MAP = {
    "approve": ["python3", str(PROJECT_ROOT / "skills/publisher.py")],
    "reject": ["python3", str(PROJECT_ROOT / "skills/writer.py"), "--rewrite"],
    "rewrite": ["python3", str(PROJECT_ROOT / "skills/writer.py"), "--rewrite"],
}


def _dispatch_action(action: dict, file_path: Path) -> bool:
    """Dispatch an action to the appropriate agent script."""
    action_type = action.get("action")
    target_id = action.get("target_id", "")

    if action_type == "confirm":
        # Write a .confirmed flag so Writer cron picks it up
        flag_file = PROJECT_ROOT / "queue/topics" / f"{target_id}.confirmed"
        flag_file.write_text(json.dumps(action, ensure_ascii=False, indent=2))
        return True

    cmd = DISPATCH_MAP.get(action_type)
    if not cmd:
        print(f"[scanner] Unknown action type: {action_type}")
        return False

    full_cmd = cmd + [target_id]
    print(f"[scanner] Dispatching: {' '.join(full_cmd)}")
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True, text=True, timeout=300,
            cwd=PROJECT_ROOT,
        )
        if result.returncode != 0:
            print(f"[scanner] Dispatch failed (rc={result.returncode}): {result.stderr[:200]}")
            return False
        print(f"[scanner] OK: {result.stdout[:100]}")
        return True
    except subprocess.TimeoutExpired:
        print(f"[scanner] Timeout: {action_type}/{target_id}")
        return False
    except Exception as e:
        print(f"[scanner] Error: {e}")
        return False


def _scan_loop():
    """Background thread: poll queue/actions/ every 10s."""
    while not _scanner_stop_event.is_set():
        try:
            files = sorted(ACTIONS_DIR.glob("*.json"), key=os.path.getmtime)
            for f in files:
                try:
                    action = json.loads(f.read_text())
                    ok = _dispatch_action(action, f)
                except (json.JSONDecodeError, OSError) as e:
                    print(f"[scanner] Error processing {f.name}: {e}")
                    ok = False
                # Always move processed files — never retry infinitely
                os.rename(f, PROCESSED_DIR / f.name)
        except Exception as e:
            print(f"[scanner] Loop error: {e}")
        # Use event.wait instead of time.sleep for faster shutdown
        _scanner_stop_event.wait(10)


# ── Budget monitor ────────────────────────────────────────────────
_last_budget_alert_time = 0

def _budget_monitor_loop():
    """Background thread: monitor budget usage every 5 minutes."""
    global _last_budget_alert_time
    
    while not _budget_stop_event.is_set():
        try:
            budget_status = check_budget_limit()
            
            # Check if we need to alert
            current_time = time.time()
            
            # Alert if over 80% (but not more than once per hour)
            if budget_status['is_warning'] and current_time - _last_budget_alert_time > 3600:
                alert_budget_warning(
                    budget_status['current_cost'],
                    budget_status['budget'],
                    budget_status['percentage'],
                )
                _last_budget_alert_time = current_time
            
            # Alert immediately if over 100%
            if budget_status['is_exceeded'] and current_time - _last_budget_alert_time > 1800:
                alert_budget_warning(
                    budget_status['current_cost'],
                    budget_status['budget'],
                    budget_status['percentage'],
                )
                _last_budget_alert_time = current_time
                
        except Exception as e:
            print(f"[budget] Monitor error: {e}")
        
        # Check every 5 minutes, use event.wait for faster shutdown
        _budget_stop_event.wait(300)





# ── Routes: Health ─────────────────────────────────────────────────
@app.get("/api/health")
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
    
    # Check database connectivity
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        health_status["services"]["database"] = "ok"
    except Exception as e:
        health_status["services"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check search index
    try:
        index_stats = get_index_stats()
        health_status["services"]["search"] = {
            "status": "ok",
            "indexed_documents": index_stats.get("total_indexed", 0),
        }
    except Exception as e:
        health_status["services"]["search"] = f"error: {str(e)}"
    
    # Check budget
    try:
        budget = check_budget_limit()
        health_status["budget"] = budget
        if budget.get("is_exceeded"):
            health_status["status"] = "warning"
    except Exception as e:
        health_status["budget"] = {"error": str(e)}
    
    # Queue sizes
    health_status["queue_sizes"] = {
        "pending": len(list(PENDING_DIR.glob("*.json"))),
        "review": len(list(REVIEW_DIR.glob("*.meta.json"))),
        "actions": len(list(ACTIONS_DIR.glob("*.json"))),
        "failed": len(list(FAILED_DIR.glob("*.json"))),
    }
    
    # Check if there are too many failed actions
    if health_status["queue_sizes"]["failed"] > 50:
        health_status["status"] = "warning"
    
    return health_status


@app.post("/api/token/log")
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


# ── Entry ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8710)
