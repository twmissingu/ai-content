"""Prompt version management routes — CRUD for prompt templates with versioning."""

import logging

from fastapi import APIRouter, HTTPException

from dashboard.backend.database import (
    activate_prompt,
    delete_prompt_version,
    get_prompt,
    import_prompts_from_files,
    list_prompt_versions,
    list_prompts,
    save_prompt,
)
from dashboard.backend.models import PromptSaveRequest

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("")
def get_all_prompts():
    """List all prompt templates (latest active version)."""
    prompts = list_prompts()
    return {"prompts": prompts, "count": len(prompts)}


@router.get("/{name}")
def get_prompt_detail(name: str, version: int | None = None):
    """Get a specific prompt template, optionally at a specific version."""
    prompt = get_prompt(name, version=version)
    if not prompt:
        raise HTTPException(404, f"Prompt '{name}' not found")
    return prompt


@router.get("/{name}/versions")
def get_prompt_version_history(name: str):
    """List all versions of a prompt template."""
    versions = list_prompt_versions(name)
    if not versions:
        raise HTTPException(404, f"Prompt '{name}' not found")
    return {"name": name, "versions": versions, "count": len(versions)}


@router.post("")
def create_or_update_prompt(req: PromptSaveRequest):
    """Save a new version of a prompt template."""
    if not req.name or not req.template:
        raise HTTPException(400, "name and template are required")
    version = save_prompt(req.name, req.template, req.variables)
    return {"status": "ok", "name": req.name, "version": version}


@router.post("/{name}/activate")
def rollback_prompt(name: str, version: int):
    """Activate a specific version of a prompt (rollback)."""
    success = activate_prompt(name, version)
    if not success:
        raise HTTPException(404, f"Version {version} of prompt '{name}' not found")
    return {"status": "ok", "name": name, "active_version": version}


@router.delete("/{name}/{version}")
def remove_prompt_version(name: str, version: int):
    """Delete a specific (non-active) version of a prompt."""
    success = delete_prompt_version(name, version)
    if not success:
        raise HTTPException(400, f"Cannot delete version {version} of '{name}' (not found or is active)")
    return {"status": "ok"}


@router.post("/import")
def import_from_files():
    """Import prompt templates from config/prompts/ files into the database."""
    count = import_prompts_from_files()
    return {"status": "ok", "imported": count}
