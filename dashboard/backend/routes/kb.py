"""Knowledge base routes — search, sections, reindex, directory tree."""

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config.settings import KB_DIR
from dashboard.backend.search import (
    auto_index_if_needed,
    get_index_stats,
    index_all_kb,
    search_kb as search_kb_fts,
)

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/kb", tags=["kb"])

MAX_TREE_DEPTH = 3


@router.get("/search")
def search_kb(q: str = Query("", min_length=1), section: Optional[str] = None):
    """Search knowledge base using FTS5 with Chinese tokenization."""
    if not q:
        return {"results": []}

    try:
        results = search_kb_fts(q, section=section, limit=20)
        return {
            "results": results,
            "count": len(results),
            "query": q,
            "section": section,
            "search_type": "fts5",
        }
    except Exception as e:
        logger.warning(f"FTS5 search failed, using fallback: {e}")

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


@router.get("/sections")
def get_kb_sections():
    """List knowledge base sections and their article counts."""
    sections = []

    try:
        index_stats = get_index_stats()
        indexed_sections = index_stats.get('by_section', {})
    except Exception:
        indexed_sections = {}

    if KB_DIR.exists():
        for d in sorted(KB_DIR.iterdir()):
            if d.is_dir() and d.name != "history":
                count = indexed_sections.get(d.name, len(list(d.rglob("*.md"))))
                sections.append({
                    "name": d.name,
                    "count": count,
                    "path": str(d),
                })

        history_dir = KB_DIR / "history"
        if history_dir.exists():
            total_history = indexed_sections.get('history', sum(1 for _ in history_dir.rglob("*.md")))
            sections.append({
                "name": "history",
                "count": total_history,
                "path": str(history_dir),
            })

    return {"sections": sections}


@router.post("/reindex")
def reindex_kb():
    """Force reindex knowledge base."""
    try:
        stats = index_all_kb(force=True)
        return {"status": "ok", "stats": stats}
    except Exception as e:
        logger.error(f"Reindex failed: {e}")
        raise HTTPException(500, "重建索引失败")


def _build_tree(path: Path, depth: int = 0) -> list[dict]:
    """Recursively build directory tree, limited to MAX_TREE_DEPTH."""
    if depth >= MAX_TREE_DEPTH:
        return []
    entries = []
    try:
        children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return []
    for child in children:
        if child.name.startswith("."):
            continue
        if child.is_dir():
            entries.append({
                "name": child.name,
                "path": str(child.relative_to(KB_DIR)),
                "type": "directory",
                "children": _build_tree(child, depth + 1),
            })
        elif child.suffix in (".md", ".json", ".txt"):
            entries.append({
                "name": child.name,
                "path": str(child.relative_to(KB_DIR)),
                "type": "file",
                "size": child.stat().st_size,
            })
    return entries


@router.get("/tree")
def get_kb_tree(subpath: str = Query("", alias="path")):
    """Return directory tree of KB, optionally starting from subpath."""
    target = (KB_DIR / subpath).resolve() if subpath else KB_DIR.resolve()
    if not str(target).startswith(str(KB_DIR.resolve())):
        raise HTTPException(403, "禁止访问知识库以外的路径")
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, f"目录不存在: {subpath}")
    return {"tree": _build_tree(target), "root": subpath or "/"}


@router.get("/file")
def get_kb_file(path: str = Query(..., min_length=1)):
    """Return content of a single file in KB. Path traversal protected."""
    target = (KB_DIR / path).resolve()
    if not str(target).startswith(str(KB_DIR.resolve())):
        raise HTTPException(403, "禁止访问知识库以外的路径")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"文件不存在: {path}")
    if target.suffix not in (".md", ".json", ".txt"):
        raise HTTPException(403, "不支持的文件类型")
    content = target.read_text(encoding="utf-8", errors="replace")
    return {"path": path, "content": content, "size": target.stat().st_size}
