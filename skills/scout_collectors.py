"""Scout collectors — fetch candidates from various sources.

Provides collector functions for china-hot MCP, GitHub trending,
Firecrawl web search, kb/materials, and RSS candidates.
"""

import concurrent.futures
import json
import logging
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config.settings import (
    CONFIG_DIR,
    DOMAIN,
    KB_DIR,
    QUEUE_DIR,
    SOURCES_DIR,
)
from skills.common import atomic_write_json, get_agent_logger, write_status as _write_status_fn

logger = get_agent_logger("scout")

# Allowed source names for china-hot MCP (security whitelist)
ALLOWED_CHINA_HOT_SOURCES = frozenset({
    "weibo", "zhihu", "bilibili", "baidu", "douyin", "toutiao", "kr36"
})

_COLLECT_STARTED_AT = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _write_status(stage: str, progress_pct: int, detail: str, error: Optional[str] = None) -> None:
    """Write scout agent status."""
    _write_status_fn("scout", stage, progress_pct, detail, error, started_at=_COLLECT_STARTED_AT)


# ── Source collectors ──────────────────────────────────────────────
def _call_china_hot(source: str) -> list[dict]:
    """Call china-hot-mcp tool via Hermes MCP.

    Each china-hot tool returns a list of trending items with at minimum
    a 'title' field. Returns empty list on any failure (network, tool not
    available, etc.) — never raises.

    Security: Validates source name against whitelist to prevent injection.
    """
    # Security: Validate source name
    if source not in ALLOWED_CHINA_HOT_SOURCES:
        logger.warning(f"Invalid source rejected: {source}")
        return []

    try:
        # Hermes MCP tools are invoked via hermes gateway
        # Source name is validated above, safe to use in command
        cmd = ["hermes", "mcp", "call", f"china-hot_{source}_trending"]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.debug(f"china-hot {source} returned non-zero: {result.returncode}")
            return []
        # Parse output — Hermes MCP returns JSON
        output = result.stdout.strip()
        if not output:
            return []
        # Try to find JSON in the output (may have log noise)
        match = re.search(r'\[.*?\]', output, re.DOTALL)
        if match:
            items = json.loads(match.group())
        else:
            items = json.loads(output)
        if isinstance(items, dict) and "data" in items:
            items = items["data"]
        return items if isinstance(items, list) else []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        logger.debug(f"china-hot {source} failed: {e}")
        return []


def _call_firecrawl_search(query: str) -> list[dict]:
    """Search web via Firecrawl for trending AI/tech content."""
    # Sanitize query to prevent injection
    if not query or len(query) > 500:
        logger.warning(f"Invalid query length: {len(query) if query else 0}")
        return []

    try:
        # Build safe command arguments
        params = json.dumps({"query": query, "count": 5})
        cmd = ["hermes", "mcp", "call", "firecrawl_web_search", "--params", params]

        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.debug(f"Firecrawl search returned non-zero: {result.returncode}")
            return []
        items = json.loads(result.stdout)
        if isinstance(items, dict) and "data" in items:
            items = items["data"]
        return items if isinstance(items, list) else []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        logger.debug(f"Firecrawl search failed: {e}")
        return []


def _call_github_trending() -> list[dict]:
    """Fetch GitHub trending repos via API (last 7 days)."""
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

    # Validate date format
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', since):
        logger.error(f"Invalid date format: {since}")
        return []

    try:
        # Use httpx instead of curl for better security and error handling
        import httpx
        url = f"https://api.github.com/search/repositories?q=created:>{since}&sort=stars&order=desc&per_page=10"

        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers={"Accept": "application/vnd.github.v3+json"})
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        return [
            {
                "title": item["name"],
                "description": item.get("description", "") or "",
                "url": item["html_url"],
                "source": "github",
                "stars": item.get("stargazers_count", 0),
            }
            for item in items[:5]
        ]
    except Exception as e:
        logger.debug(f"GitHub trending failed: {e}")
        return []


def _collect_materials() -> list[dict]:
    """Read kb/materials/ for manually curated topics."""
    materials_dir = KB_DIR / "materials"
    if not materials_dir.exists():
        return []
    items = []
    for f in sorted(materials_dir.glob("*.md"))[:5]:
        text = f.read_text(encoding="utf-8", errors="ignore")
        title = text.split("\n")[0].removeprefix("# ").strip() or f.stem
        items.append({
            "title": title,
            "description": text[:200],
            "url": f"file://{f}",
            "source": "materials",
        })
    return items


def collect_all() -> list[dict]:
    """Run all collectors and return deduplicated candidates."""
    _write_status("collecting", 10, "Collecting from all sources")

    candidates: list[dict] = []

    # Run independent collectors in parallel (subprocess + httpx calls)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        # china-hot sources (7 independent subprocess calls)
        china_hot_futures = {
            pool.submit(_call_china_hot, s): s
            for s in ["weibo", "zhihu", "bilibili", "baidu", "douyin", "toutiao", "kr36"]
        }
        for future in concurrent.futures.as_completed(china_hot_futures):
            source = china_hot_futures[future]
            try:
                for item in future.result()[:3]:  # top 3 per source
                    title = item.get("title", "") or item.get("name", "") or ""
                    if title:
                        candidates.append({
                            "title": title,
                            "description": item.get("description", "") or item.get("desc", "") or "",
                            "url": item.get("url", "") or item.get("link", "") or "",
                            "source": source,
                            "hot_value": item.get("hot_value", 0) or item.get("score", 50),
                        })
            except Exception:
                logger.debug(f"china-hot {source} collector failed unexpectedly")

        # GitHub trending + kb/materials + Firecrawl searches (all independent)
        github_fut = pool.submit(_call_github_trending)
        materials_fut = pool.submit(_collect_materials)
        firecrawl_queries = [f"今日科技热点 {DOMAIN}", "AI 最新动态"]
        firecrawl_futures = {
            pool.submit(_call_firecrawl_search, q): q for q in firecrawl_queries
        }

        for item in github_fut.result():
            candidates.append(item)

        for item in materials_fut.result():
            candidates.append(item)

        for future in concurrent.futures.as_completed(firecrawl_futures):
            try:
                for item in future.result():
                    title = item.get("title", "") or ""
                    if title:
                        candidates.append({
                            "title": title,
                            "description": item.get("description", "") or item.get("content", "") or "",
                            "url": item.get("url", "") or item.get("link", "") or "",
                            "source": "web_search",
                            "hot_value": 50,
                        })
            except Exception:
                logger.debug("Firecrawl search collector failed unexpectedly")


    # RSS candidates from rss_collector (pre-collected, cached)
    rss_dir = QUEUE_DIR / "rss_candidates"
    if rss_dir.exists():
        seen_urls = {c.get("url", "") for c in candidates if c.get("url")}
        rss_files = sorted(rss_dir.glob("*.json"), reverse=True)[:5]  # latest 5 batches
        pre_count = len(candidates)
        for rf in rss_files:
            try:
                rss_items = json.loads(rf.read_text())
                for item in rss_items:
                    url = item.get("url", "") or ""
                    title = item.get("title", "") or ""
                    if not title:
                        continue
                    if url and url in seen_urls:
                        continue
                    seen_urls.add(url)
                    candidates.append({
                        "title": title,
                        "description": item.get("description", "") or "",
                        "url": url,
                        "source": "rss",
                        "rss_label": item.get("rss_label", ""),
                        "rss_source": item.get("rss_source", ""),
                        "keywords": item.get("keywords", []),
                        "hot_value": item.get("hot_value", 60),
                        "published_at": item.get("published_at", ""),
                    })
            except (json.JSONDecodeError, OSError):
                continue
        rss_added = len(candidates) - pre_count
        if rss_added:
            logger.info(f"Added {rss_added} RSS candidates")
    _write_status("collecting", 30, f"Collected {len(candidates)} raw candidates")
    return candidates


def _save_raw_sources(candidates: list[dict]) -> None:
    """Save raw candidates to queue/sources/ for the dashboard sources page."""
    if not candidates:
        return
    date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = SOURCES_DIR / f"{date_str}.json"
    atomic_write_json(out_path, candidates)
    logger.info(f"Saved {len(candidates)} raw sources to {out_path}")
