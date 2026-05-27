"""SQLite database layer for Dashboard.

Implements 5 core tables from PRD 6.1:
- pipeline_sessions: 管线时段记录
- platform_versions: 各平台版本
- approval_records: 审批操作日志
- token_usage: Token消耗记录
- config_entries: 配置变更记录

Uses WAL mode + single worker to avoid write conflicts.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import DATA_DIR

DATABASE_PATH = DATA_DIR / "analytics.db"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    """Get database connection with WAL mode."""
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS kb_search 
            USING fts5(
                path, 
                title, 
                content, 
                section,
                tokenize='unicode61'
            )
        """)
    
    print(f"[database] Initialized at {DATABASE_PATH}")


# ── Pipeline Sessions ──────────────────────────────────────────────

def create_pipeline_session(date: str, period: str, topic: str, 
                          source_url: str = None) -> int:
    """Create a new pipeline session."""
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
    
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [session_id]
    
    with get_db() as conn:
        conn.execute(f"""
            UPDATE pipeline_sessions 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, values)


def get_pipeline_sessions(limit: int = 30, status: str = None) -> list[dict]:
    """Get pipeline sessions with optional status filter."""
    with get_db() as conn:
        if status:
            rows = conn.execute("""
                SELECT * FROM pipeline_sessions 
                WHERE status = ?
                ORDER BY date DESC, created_at DESC
                LIMIT ?
            """, (status, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM pipeline_sessions 
                ORDER BY date DESC, created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(row) for row in rows]


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

def log_token_usage(agent: str, model: str, input_tokens: int, 
                   output_tokens: int, session_id: int = None) -> int:
    """Log token usage with cost estimation."""
    # Cost estimation (approximate for common models)
    cost_per_1k = {
        'claude-sonnet-4': 0.003,
        'gpt-4o': 0.005,
        'deepseek-v3': 0.001,
        'mimo-v2.5': 0.002,
    }
    
    base_cost = cost_per_1k.get(model, 0.003)
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
