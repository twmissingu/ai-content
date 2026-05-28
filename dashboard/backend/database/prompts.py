"""Prompt version management — store, retrieve, and version prompt templates.

Inspired by Langfuse prompt management: every prompt change creates a new version,
old versions are preserved for rollback and A/B testing.
"""

import json
import time
from typing import Optional

from .core import get_db


def get_prompt(template_name: str, version: Optional[int] = None) -> Optional[dict]:
    """Get a prompt template by name, optionally at a specific version.

    Returns dict with keys: name, version, template, variables, is_active, created_at
    or None if not found.
    """
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
            return None

        return {
            "name": row["name"],
            "version": row["version"],
            "template": row["template"],
            "variables": json.loads(row["variables"]) if row["variables"] else [],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
        }


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

        # Deactivate previous versions
        conn.execute(
            "UPDATE prompt_versions SET is_active = 0 WHERE name = ?",
            (template_name,),
        )

        # Insert new version
        conn.execute(
            "INSERT INTO prompt_versions (name, version, template, variables, is_active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (
                template_name,
                new_version,
                template,
                json.dumps(variables or []),
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ),
        )
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

    imported = 0
    for f in sorted(prompts_dir.glob("*.txt")):
        name = f.stem
        existing = get_prompt(name)
        if existing:
            continue

        template = f.read_text(encoding="utf-8")
        # Extract variable names from {variable} patterns
        variables = list(set(re.findall(r'\{(\w+)\)', template)))
        save_prompt(name, template, variables)
        imported += 1

    return imported
