"""Prompt version management — store, retrieve, and version prompt templates.

Inspired by Langfuse prompt management: every prompt change creates a new version,
old versions are preserved for rollback and A/B testing.
"""

import json
import threading
import time
from typing import Optional

from .core import get_db

# Prompt cache with 60s TTL — key = (name, version), value = (timestamp, result)
_prompt_cache: dict[tuple, tuple[float, dict | None]] = {}
_prompt_cache_lock = threading.Lock()
_PROMPT_CACHE_TTL = 60.0  # seconds


def _invalidate_prompt_cache(name: Optional[str] = None) -> None:
    """Invalidate prompt cache entries. If name given, clear only that name's keys."""
    with _prompt_cache_lock:
        if name is None:
            _prompt_cache.clear()
        else:
            keys_to_remove = [k for k in _prompt_cache if k[0] == name]
            for k in keys_to_remove:
                del _prompt_cache[k]


def get_prompt(template_name: str, version: Optional[int] = None) -> Optional[dict]:
    """Get a prompt template by name, optionally at a specific version.

    Returns dict with keys: name, version, template, variables, is_active, created_at
    or None if not found.
    """
    cache_key = (template_name, version)
    with _prompt_cache_lock:
        if cache_key in _prompt_cache:
            ts, result = _prompt_cache[cache_key]
            if time.time() - ts < _PROMPT_CACHE_TTL:
                return result

    with get_db() as conn:
        if version is not None:
            row = conn.execute(
                "SELECT name, version, template, variables, is_active, created_at "
                "FROM prompt_versions WHERE name = ? AND version = ?",
                (template_name, version),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT name, version, template, variables, is_active, created_at "
                "FROM prompt_versions WHERE name = ? AND is_active = 1 "
                "ORDER BY version DESC LIMIT 1",
                (template_name,),
            ).fetchone()

        if not row:
            result = None
        else:
            result = {
                "name": row["name"],
                "version": row["version"],
                "template": row["template"],
                "variables": json.loads(row["variables"]) if row["variables"] else [],
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"],
            }

    with _prompt_cache_lock:
        _prompt_cache[cache_key] = (time.time(), result)
    return result


def list_prompts() -> list[dict]:
    """List all prompt templates (latest active version of each)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name, version, template, variables, is_active, created_at "
            "FROM prompt_versions WHERE is_active = 1 "
            "ORDER BY name"
        ).fetchall()

        return [
            {
                "name": r["name"],
                "version": r["version"],
                "template": r["template"],
                "variables": json.loads(r["variables"]) if r["variables"] else [],
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def list_prompt_versions(template_name: str) -> list[dict]:
    """List all versions of a prompt template."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name, version, template, variables, is_active, created_at "
            "FROM prompt_versions WHERE name = ? ORDER BY version DESC",
            (template_name,),
        ).fetchall()

        return [
            {
                "name": r["name"],
                "version": r["version"],
                "template": r["template"][:200] + "..." if len(r["template"]) > 200 else r["template"],
                "variables": json.loads(r["variables"]) if r["variables"] else [],
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def save_prompt(template_name: str, template: str, variables: list[str] | None = None) -> int:
    """Save a new version of a prompt template.

    Deactivates previous version and creates a new one.
    Returns the new version number.
    """
    with get_db() as conn:
        # Get current max version
        row = conn.execute(
            "SELECT MAX(version) as max_ver FROM prompt_versions WHERE name = ?",
            (template_name,),
        ).fetchone()
        new_version = (row["max_ver"] or 0) + 1

        # Atomically deactivate previous versions and insert new version
        conn.execute(
            "UPDATE prompt_versions SET is_active = 0 WHERE name = ?",
            (template_name,),
        )
        conn.execute(
            "INSERT INTO prompt_versions (name, version, template, variables, is_active, created_at) "
            "VALUES (?, ?, ?, ?, 1, datetime('now'))",
            (
                template_name,
                new_version,
                template,
                json.dumps(variables or []),
            ),
        )
        _invalidate_prompt_cache(template_name)
        return new_version


def activate_prompt(template_name: str, version: int) -> bool:
    """Activate a specific version of a prompt (rollback)."""
    with get_db() as conn:
        # Verify version exists
        row = conn.execute(
            "SELECT 1 FROM prompt_versions WHERE name = ? AND version = ?",
            (template_name, version),
        ).fetchone()
        if not row:
            return False

        conn.execute(
            "UPDATE prompt_versions SET is_active = 0 WHERE name = ?",
            (template_name,),
        )
        conn.execute(
            "UPDATE prompt_versions SET is_active = 1 WHERE name = ? AND version = ?",
            (template_name, version),
        )
        _invalidate_prompt_cache(template_name)
        return True


def delete_prompt_version(template_name: str, version: int) -> bool:
    """Delete a specific version of a prompt."""
    with get_db() as conn:
        # Don't delete the active version
        row = conn.execute(
            "SELECT is_active FROM prompt_versions WHERE name = ? AND version = ?",
            (template_name, version),
        ).fetchone()
        if not row:
            return False
        if row["is_active"]:
            return False  # Can't delete active version

        conn.execute(
            "DELETE FROM prompt_versions WHERE name = ? AND version = ?",
            (template_name, version),
        )
        _invalidate_prompt_cache(template_name)
        return True


def import_prompts_from_files() -> int:
    """Import prompt templates from config/prompts/ files into the database.

    Only imports if no DB version exists for that template.
    Returns count of imported templates.
    """
    from config.settings import CONFIG_DIR
    import re

    prompts_dir = CONFIG_DIR / "prompts"
    if not prompts_dir.exists():
        return 0

    # Batch check: get all existing prompt names in one query
    existing_names = set()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT name FROM prompt_versions WHERE is_active = 1"
        ).fetchall()
        for row in rows:
            existing_names.add(row["name"])

    imported = 0
    for f in sorted(prompts_dir.glob("*.txt")):
        name = f.stem
        if name in existing_names:
            continue

        template = f.read_text(encoding="utf-8")
        # Extract variable names from {variable} patterns
        variables = list(set(re.findall(r'\{(\w+)\}', template)))
        save_prompt(name, template, variables)
        imported += 1

    return imported
