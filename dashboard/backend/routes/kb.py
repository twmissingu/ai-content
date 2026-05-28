"""Knowledge base routes — search, sections, reindex."""

import logging
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
