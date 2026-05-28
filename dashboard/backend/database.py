"""SQLite database layer for Dashboard.

Implements 5 core tables from PRD 6.1:
- pipeline_sessions: 管线时段记录
- platform_versions: 各平台版本
- approval_records: 审批操作日志
- token_usage: Token消耗记录
- config_entries: 配置变更记录

Uses WAL mode + single worker to avoid write conflicts.
Thread-safe with connection pooling and query caching.
"""

import functools
import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from config.settings import DATA_DIR

DATABASE_PATH = DATA_DIR / "analytics.db"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Logger
logger = logging.getLogger("gaoding.database")

# Thread-local storage for connections
_thread_local = threading.local()

# Simple query cache (invalidated on writes)
_query_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 5.0  # seconds

F = TypeVar('F', bound=Callable)


def cached_query(ttl: float = CACHE_TTL) -> Callable[[F], F]:
    """Cache query results with TTL.
    
    Usage:
        @cached_query(ttl=10.0)
        def get_sessions(limit=30):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            
            # Check cache
            with _cache_lock:
                if cache_key in _query_cache:
                    timestamp, result = _query_cache[cache_key]
                    if time.time() - timestamp < ttl:
                        logger.debug(f"Cache hit: {func.__name__}")
                        return result
            
            # Execute query
            result = func(*args, **kwargs)
            
            # Store in cache
            with _cache_lock:
                _query_cache[cache_key] = (time.time(), result)
            
            return result
        return wrapper
    return decorator


def _invalidate_cache() -> None:
    """Invalidate all cached queries."""
    with _cache_lock:
        _query_cache.clear()
        logger.debug("Cache invalidated")


@contextmanager
def get_db():
    """Get database connection with WAL mode.
    
    Uses thread-local connections for better concurrency.
    """
    # Get or create thread-local connection
    if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
        conn = sqlite3.connect(str(DATABASE_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")  # Better performance with WAL
        conn.row_factory = sqlite3.Row
        _thread_local.conn = conn
    
    conn = _thread_local.conn
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    """Initialize database with all required tables."""
    with get_db() as conn:
        conn.executescript("""
            -- 管线时段记录
            CREATE TABLE IF NOT EXISTS pipeline_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                period TEXT CHECK(period IN ('am', 'pm')),
                topic TEXT,
                source_url TEXT,
                status TEXT CHECK(status IN ('draft', 'running', 'completed', 'failed', 'skipped')) DEFAULT 'draft',
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- 各平台版本
            CREATE TABLE IF NOT EXISTS platform_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                platform TEXT CHECK(platform IN ('wechat', 'xiaohongshu', 'douyin', 'toutiao', 'baijiahao', 'shipinhao')),
                status TEXT CHECK(status IN ('pending', 'approved', 'rejected', 'rewriting', 'distributed')) DEFAULT 'pending',
                content_path TEXT,
                meta_path TEXT,
                score REAL,
                rewrite_round INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES pipeline_sessions(id) ON DELETE CASCADE
            );
            
            -- 审批操作日志
            CREATE TABLE IF NOT EXISTS approval_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL,
                action TEXT CHECK(action IN ('pass', 'reject', 'defer', 'rewrite')),
                reason TEXT,
                operator TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (version_id) REFERENCES platform_versions(id) ON DELETE CASCADE
            );
            
            -- Token消耗记录
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                agent TEXT NOT NULL,
                model TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES pipeline_sessions(id) ON DELETE SET NULL
            );
            
            -- 配置变更记录（支持双版本预览）
            CREATE TABLE IF NOT EXISTS config_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT,
                effective_from TIMESTAMP,
                status TEXT CHECK(status IN ('current', 'pending', 'expired')) DEFAULT 'current',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- 创建索引
            CREATE INDEX IF NOT EXISTS idx_pipeline_sessions_date ON pipeline_sessions(date);
            CREATE INDEX IF NOT EXISTS idx_pipeline_sessions_status ON pipeline_sessions(status);
            CREATE INDEX IF NOT EXISTS idx_platform_versions_session ON platform_versions(session_id);
            CREATE INDEX IF NOT EXISTS idx_platform_versions_status ON platform_versions(status);
            CREATE INDEX IF NOT EXISTS idx_approval_records_version ON approval_records(version_id);
            CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage(session_id);
            CREATE INDEX IF NOT EXISTS idx_token_usage_created ON token_usage(created_at);
            CREATE INDEX IF NOT EXISTS idx_config_entries_key ON config_entries(key);
            CREATE INDEX IF NOT EXISTS idx_config_entries_status ON config_entries(status);
        """)
        
        # Create FTS5 virtual table for knowledge base search
        # Use trigram tokenizer for better Chinese support (SQLite 3.34+)
        # trigram tokenizer indexes all 3-character sequences, works well with CJK
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS kb_search 
            USING fts5(
                path, 
                title, 
                content, 
                section,
                tokenize='trigram'
            )
        """)
    
    logger.info(f"Initialized at {DATABASE_PATH}")


# ── Pipeline Sessions ──────────────────────────────────────────────

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
    """Get pipeline sessions with pagination and optional status filter.
    
    Args:
        limit: Maximum number of results
        offset: Number of results to skip
        status: Filter by status
        fields: List of fields to return (None for all)
    
    Returns:
        Dict with 'items', 'total', 'limit', 'offset'
    """
    # Validate fields
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
        # Get total count
        count_query = "SELECT COUNT(*) FROM pipeline_sessions"
        count_params = []
        if status:
            count_query += " WHERE status = ?"
            count_params.append(status)
        
        total = conn.execute(count_query, count_params).fetchone()[0]
        
        # Get paginated results
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


# ── Platform Versions ──────────────────────────────────────────────

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


# ── Approval Records ──────────────────────────────────────────────

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


# ── Token Usage ────────────────────────────────────────────────────

def _load_model_costs() -> tuple[dict[str, float], float]:
    """Load model cost rates from config/models.json."""
    import json as _json
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "models.json"
    default_cost = 0.003
    if not config_path.exists():
        return {}, default_cost
    try:
        data = _json.loads(config_path.read_text())
        models = data.get("models", {})
        costs = {name: cfg.get("cost_per_1k_tokens", default_cost) for name, cfg in models.items()}
        return costs, data.get("default_cost_per_1k", default_cost)
    except Exception:
        return {}, default_cost


_MODEL_COSTS, _DEFAULT_COST = _load_model_costs()


def log_token_usage(agent: str, model: str, input_tokens: int,
                   output_tokens: int, session_id: int = None) -> int:
    """Log token usage with cost estimation."""
    base_cost = _MODEL_COSTS.get(model, _DEFAULT_COST)
    estimated_cost = (input_tokens + output_tokens) * base_cost / 1000
    
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO token_usage (session_id, agent, model, input_tokens, output_tokens, estimated_cost)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, agent, model, input_tokens, output_tokens, estimated_cost))
        return cursor.lastrowid


def get_token_usage_stats(days: int = 30) -> dict:
    """Get token usage statistics for the last N days."""
    with get_db() as conn:
        # Daily breakdown
        daily = conn.execute("""
            SELECT 
                DATE(created_at) as date,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(estimated_cost) as cost,
                COUNT(*) as call_count
            FROM token_usage
            WHERE created_at >= DATE('now', ? || ' days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (f'-{days}',)).fetchall()
        
        # Agent breakdown
        by_agent = conn.execute("""
            SELECT 
                agent,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(estimated_cost) as cost,
                COUNT(*) as call_count
            FROM token_usage
            WHERE created_at >= DATE('now', ? || ' days')
            GROUP BY agent
            ORDER BY cost DESC
        """, (f'-{days}',)).fetchall()
        
        # Monthly total
        monthly = conn.execute("""
            SELECT 
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(estimated_cost) as cost,
                COUNT(*) as call_count
            FROM token_usage
            WHERE created_at >= DATE('now', 'start of month')
        """).fetchone()
        
        return {
            'daily': [dict(row) for row in daily],
            'by_agent': [dict(row) for row in by_agent],
            'monthly': dict(monthly) if monthly else {},
        }


def get_monthly_cost() -> float:
    """Get current month's total cost."""
    with get_db() as conn:
        result = conn.execute("""
            SELECT COALESCE(SUM(estimated_cost), 0) as total
            FROM token_usage
            WHERE created_at >= DATE('now', 'start of month')
        """).fetchone()
        return result['total']


# ── Config Entries ─────────────────────────────────────────────────

def set_config_value(key: str, value: Any, status: str = 'current',
                    effective_from: str = None):
    """Set a configuration value."""
    value_json = json.dumps(value, ensure_ascii=False)
    
    with get_db() as conn:
        # Expire old current values
        if status == 'current':
            conn.execute("""
                UPDATE config_entries 
                SET status = 'expired', updated_at = CURRENT_TIMESTAMP
                WHERE key = ? AND status = 'current'
            """, (key,))
        
        conn.execute("""
            INSERT INTO config_entries (key, value, status, effective_from)
            VALUES (?, ?, ?, ?)
        """, (key, value_json, status, effective_from))


def get_config_value(key: str, default: Any = None) -> Any:
    """Get current configuration value."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT value FROM config_entries 
            WHERE key = ? AND status = 'current'
            ORDER BY updated_at DESC LIMIT 1
        """, (key,)).fetchone()
        
        if row and row['value']:
            return json.loads(row['value'])
        return default


def get_pending_config(key: str = None) -> list[dict]:
    """Get pending configuration changes."""
    with get_db() as conn:
        if key:
            rows = conn.execute("""
                SELECT * FROM config_entries 
                WHERE key = ? AND status = 'pending'
                ORDER BY effective_from
            """, (key,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM config_entries 
                WHERE status = 'pending'
                ORDER BY key, effective_from
            """).fetchall()
        return [dict(row) for row in rows]


def get_all_config() -> dict:
    """Get all current configuration as a dict."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT key, value FROM config_entries 
            WHERE status = 'current'
        """).fetchall()
        
        config = {}
        for row in rows:
            config[row['key']] = json.loads(row['value']) if row['value'] else None
        return config


# ── Budget Control ─────────────────────────────────────────────────

def check_budget_limit(budget_usd: float = None) -> dict:
    """Check if monthly cost exceeds budget limit.
    
    Args:
        budget_usd: Budget limit in USD. If None, reads from config or uses default.
    
    Returns:
        Dictionary with budget status information.
    """
    # If no budget specified, try to read from config
    if budget_usd is None:
        try:
            config_value = get_config_value('budget')
            if config_value and isinstance(config_value, dict):
                budget_usd = config_value.get('monthly_limit_usd', 15.0)
            else:
                budget_usd = 15.0
        except Exception:
            budget_usd = 15.0
    
    current_cost = get_monthly_cost()
    percentage = (current_cost / budget_usd * 100) if budget_usd > 0 else 0
    
    return {
        'current_cost': round(current_cost, 4),
        'budget': budget_usd,
        'percentage': round(percentage, 2),
        'is_warning': percentage >= 80,
        'is_exceeded': percentage >= 100,
        'remaining': round(max(0, budget_usd - current_cost), 4),
    }


# ── Initialization ─────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("[database] Schema created successfully")
