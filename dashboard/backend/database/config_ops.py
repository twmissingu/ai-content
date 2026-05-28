"""Configuration entry operations."""

import json
from typing import Any

from .core import get_db


def set_config_value(key: str, value: Any, status: str = 'current',
                    effective_from: str = None):
    """Set a configuration value."""
    value_json = json.dumps(value, ensure_ascii=False)

    with get_db() as conn:
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
