"""Database connection management, caching, and schema initialization."""

import functools
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, TypeVar

from config.settings import DATA_DIR

DATABASE_PATH = DATA_DIR / "analytics.db"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

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
            cache_key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"

            with _cache_lock:
                if cache_key in _query_cache:
                    timestamp, result = _query_cache[cache_key]
                    if time.time() - timestamp < ttl:
                        logger.debug(f"Cache hit: {func.__name__}")
                        return result

            result = func(*args, **kwargs)

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
    if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
        conn = sqlite3.connect(str(DATABASE_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
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

            -- 管线执行追踪（n8n 模式：每阶段 I/O 记录）
            CREATE TABLE IF NOT EXISTS pipeline_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                agent TEXT NOT NULL,
                stage TEXT NOT NULL,
                stage_name TEXT,
                input_summary TEXT,
                output_summary TEXT,
                status TEXT CHECK(status IN ('running', 'completed', 'failed', 'skipped')) DEFAULT 'running',
                duration_ms INTEGER,
                tokens_used INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES pipeline_sessions(id) ON DELETE SET NULL
            );

            -- 提示词版本管理
            CREATE TABLE IF NOT EXISTS prompt_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                template TEXT NOT NULL,
                variables TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, version)
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
            CREATE INDEX IF NOT EXISTS idx_pipeline_traces_session ON pipeline_traces(session_id);
            CREATE INDEX IF NOT EXISTS idx_pipeline_traces_agent ON pipeline_traces(agent);
            CREATE INDEX IF NOT EXISTS idx_prompt_versions_name ON prompt_versions(name);
            CREATE INDEX IF NOT EXISTS idx_prompt_versions_active ON prompt_versions(name, is_active);
        """)

        # Create FTS5 virtual table for knowledge base search
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
