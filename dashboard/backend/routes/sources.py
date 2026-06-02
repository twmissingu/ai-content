"""Sources routes — raw source feed browsing and stats."""

import json
import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from config.settings import SOURCES_DIR

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/sources", tags=["sources"])

# Module-level cache for source files (keyed by limit_files, stores (ts, result))
_sources_cache: dict[str, tuple[float, tuple[list[dict], int]]] = {}
_SOURCES_CACHE_TTL = 30.0  # seconds


def _load_all_sources(limit_files: int = 10) -> tuple[list[dict], int]:
    """Load recent source files and merge into a flat list.

    Returns (items, file_count) tuple.
    """
    global _sources_cache
    cache_key = f"sources_{limit_files}"
    now = time.time()
    if cache_key in _sources_cache:
        ts, cached_result = _sources_cache[cache_key]
        if (now - ts) < _SOURCES_CACHE_TTL:
            return cached_result

    files = sorted(SOURCES_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
    file_count = len(files)
    seen_urls: dict[str, int] = {}  # url -> index in all_items
    all_items: list[dict] = []
    for f in files[:limit_files]:
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(items, list):
                for item in items:
                    url = item.get("url", "")
                    if url and url in seen_urls:
                        # Keep the entry with higher stars
                        idx = seen_urls[url]
                        existing = all_items[idx]
                        if (item.get("stars") or 0) > (existing.get("stars") or 0):
                            all_items[idx] = item
                    elif url:
                        seen_urls[url] = len(all_items)
                        all_items.append(item)
                    else:
                        all_items.append(item)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read {f.name}: {e}")

    result = (all_items, file_count)
    _sources_cache[cache_key] = (now, result)
    return result


@router.get("")
def list_sources(
    source: str = Query("", description="Filter by source name"),
    min_score: float = Query(0, ge=0, description="Minimum final_score"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List raw source candidates with optional filters."""
    items, _ = _load_all_sources()

    if source:
        items = [i for i in items if i.get("source", "") == source]
    if min_score > 0:
        items = [i for i in items if (i.get("final_score") or i.get("raw_score") or 0) >= min_score]

    # Sort by hot_value or score descending
    items.sort(key=lambda x: x.get("hot_value") or x.get("final_score") or 0, reverse=True)

    total = len(items)
    items = items[offset:offset + limit]

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/stats")
def sources_stats():
    """Aggregate stats across all source files."""
    items, file_count = _load_all_sources(limit_files=20)

    source_counts: dict[str, int] = {}
    score_sum = 0.0
    score_count = 0

    for item in items:
        src = item.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
        score = item.get("final_score") or item.get("raw_score")
        if score:
            score_sum += score
            score_count += 1

    return {
        "total_items": len(items),
        "by_source": source_counts,
        "avg_score": round(score_sum / score_count, 1) if score_count else 0,
        "file_count": file_count,
    }
