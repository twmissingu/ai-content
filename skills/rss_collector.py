"""RSS Collector — independent pre-collection daemon for RSS feeds.

Fetches items from three types of RSS sources:
  1. RSSHub — 大V社交账号（Twitter/微博/B站等）
  2. wewe-rss — 微信公众号文章
  3. 直连 feedparser — 技术博客/新闻站

Runs as a standalone process. Writes to queue/rss_candidates/ for Scout to consume.
Designed for extension: start small (~20 feeds), scale up easily.

Usage:
    python3 skills/rss_collector.py          # Run once and exit
    python3 skills/rss_collector.py --daemon # Run as daemon (every 30 min)
"""

import hashlib
import json
import logging
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import feedparser
import httpx

# Ensure config is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import (
    CONFIG_DIR,
    QUEUE_DIR,
    RSSHUB_BASE_URL,
    WEWE_RSS_BASE_URL,
    RSS_COLLECTOR_INTERVAL,
    RSS_CACHE_DIR,
)
from skills.topic_analyzer import extract_keywords

logger = logging.getLogger("rss_collector")

# ── Paths ───────────────────────────────────────────────────────────
# RSS_CACHE_DIR imported from config.settings
RSS_CANDIDATES_DIR = QUEUE_DIR / "rss_candidates"  # processed for Scout

for _d in [RSS_CACHE_DIR, RSS_CANDIDATES_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── Config ─────────────────────────────────────────────────────────
def _load_rss_config() -> dict:
    """Load RSS feed configuration from config/sources.json."""
    config_path = CONFIG_DIR / "sources.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("rss_feeds", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load RSS config: {e}")
        return {"direct": [], "wewe_rss": {"enabled": False}, "rsshub": {"enabled": False}}


def _load_rss_collector_config() -> dict:
    """Load RSS collector settings from sources.json."""
    config_path = CONFIG_DIR / "sources.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("rss_collector", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {"base_item_cap": 20, "cache_ttl_hours": 24}


# ── Feed fetchers ───────────────────────────────────────────────────
def _fetch_feed(url: str, timeout: int = 30) -> list[dict]:
    """Fetch and parse an RSS/Atom feed. Returns list of entries."""
    try:
        parsed = feedparser.parse(url)
        if parsed.bozo and not parsed.entries:
            logger.warning(f"Feed parse error for {url}: {parsed.bozo_exception}")
            return []
        return parsed.entries
    except Exception as e:
        logger.warning(f"Failed to fetch feed {url}: {e}")
        return []


def _fetch_rsshub_feed(route: str, params: Optional[dict] = None) -> list[dict]:
    """Fetch a feed from RSSHub by route path.

    RSSHub routes: /twitter/user/:id, /weibo/user/:id, /bilibili/user/video/:id, etc.
    """
    path = route.lstrip("/")
    url = f"{RSSHUB_BASE_URL}/{path}"
    if params:
        qs = urllib.parse.urlencode(params)
        url = f"{url}?{qs}"
    return _fetch_feed(url)


def _fetch_wewe_rss_feed(feed_id: str) -> list[dict]:
    """Fetch a WeChat official account feed from wewe-rss.

    wewe-rss exposes feeds at /feeds/{feed_id}.rss
    """
    url = f"{WEWE_RSS_BASE_URL}/feeds/{feed_id}.rss"
    return _fetch_feed(url)


# ── Entry parsing ───────────────────────────────────────────────────
def _parse_entry(entry: dict, source_label: str, rss_type: str) -> Optional[dict]:
    """Normalize a feedparser entry into a standard candidate dict."""
    title = (entry.get("title") or "").strip()
    if not title or len(title) < 4:
        return None

    # Extract the best available link
    link = ""
    for key in ("link", "id"):
        val = entry.get(key)
        if val:
            link = val
            break
    if not link and entry.get("links"):
        link = entry["links"][0].get("href", "")

    # Published timestamp
    published = None
    for key in ("published_parsed", "updated_parsed"):
        tp = entry.get(key)
        if tp:
            try:
                published = datetime(*tp[:6], tzinfo=timezone.utc).isoformat()
            except (ValueError, TypeError):
                pass
            break
    if not published:
        published = datetime.now(timezone.utc).isoformat()

    # Description / summary
    description = (entry.get("summary") or entry.get("description") or "")[:500]

    # Content hash for dedup
    content_hash = hashlib.sha256((title + link).encode()).hexdigest()[:16]

    # Keywords / entities
    keywords = sorted(extract_keywords(title))

    return {
        "title": title,
        "url": link,
        "description": description,
        "source": "rss",
        "rss_source": rss_type,
        "rss_label": source_label,
        "published_at": published,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "keywords": keywords,
        "content_hash": content_hash,
        "hot_value": 60,  # RSS items start at a moderate hot_value
    }


def _load_cached_hashes() -> set[str]:
    """Load all existing content hashes from cache directory into memory."""
    hashes = set()
    if not RSS_CACHE_DIR.exists():
        return hashes
    for f in RSS_CACHE_DIR.iterdir():
        if f.suffix == ".json":
            try:
                data = json.loads(f.read_text())
                h = data.get("content_hash")
                if h:
                    hashes.add(h)
            except (json.JSONDecodeError, OSError):
                continue
    return hashes


def _save_cached(items: list[dict]):
    """Save fetched items to RSS_CACHE_DIR (persistent, for reuse).

    Builds an in-memory set of known hashes once, then checks each item
    against it — O(n+m) instead of O(n×m).
    """
    known_hashes = _load_cached_hashes()
    for item in items:
        if item["content_hash"] in known_hashes:
            continue
        path = RSS_CACHE_DIR / f"{item['content_hash']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(item, ensure_ascii=False, indent=2))
        tmp.rename(path)
        known_hashes.add(item["content_hash"])


def _write_candidates(items: list[dict]):
    """Write deduplicated items to RSS_CANDIDATES_DIR for Scout consumption.

    Scout reads all files from rss_candidates/ and merges them.
    Old candidates are cleaned up by timestamp.
    """
    # Clean up candidates older than 48 hours
    cutoff = time.time() - 48 * 3600
    for f in RSS_CANDIDATES_DIR.iterdir():
        if f.suffix == ".json" and f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)

    # Write new candidates
    batch_time = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RSS_CANDIDATES_DIR / f"batch-{batch_time}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2))
    tmp.rename(path)
    logger.info(f"Wrote {len(items)} candidates to {path.name}")


# ── Collectors ──────────────────────────────────────────────────────
def _collect_from_rsshub(rsshub_config: dict) -> list[dict]:
    """Collect from RSSHub — each route is a social account or feed."""
    if not rsshub_config.get("enabled", False):
        return []

    routes = rsshub_config.get("routes", [])
    all_items = []
    seen_hashes = set()

    for route_cfg in routes:
        route = route_cfg.get("route", "")
        label = route_cfg.get("label", route)
        if not route:
            continue

        entries = _fetch_rsshub_feed(route)
        logger.info(f"  RSSHub [{label}]: {len(entries)} entries")

        for entry in entries:
            parsed = _parse_entry(entry, label, "rsshub")
            if parsed and parsed["content_hash"] not in seen_hashes:
                seen_hashes.add(parsed["content_hash"])
                all_items.append(parsed)

    return all_items


def _collect_from_wewe_rss(wewe_config: dict) -> list[dict]:
    """Collect from wewe-rss — each feed is a WeChat official account."""
    if not wewe_config.get("enabled", False):
        return []

    feeds = wewe_config.get("feeds", [])
    all_items = []
    seen_hashes = set()

    for feed_cfg in feeds:
        feed_id = feed_cfg.get("feed_id", "")
        label = feed_cfg.get("label", feed_id)
        if not feed_id:
            continue

        entries = _fetch_wewe_rss_feed(feed_id)
        logger.info(f"  wewe-rss [{label}]: {len(entries)} entries")

        for entry in entries:
            parsed = _parse_entry(entry, label, "wewe_rss")
            if parsed and parsed["content_hash"] not in seen_hashes:
                seen_hashes.add(parsed["content_hash"])
                all_items.append(parsed)

    return all_items


def _collect_from_direct(direct_config: list[dict]) -> list[dict]:
    """Collect from direct RSS/Atom feeds (tech blogs, news sites)."""
    if not direct_config:
        return []

    all_items = []
    seen_hashes = set()

    for feed_cfg in direct_config:
        if not feed_cfg.get("enabled", False):
            continue
        url = feed_cfg.get("url", "")
        label = feed_cfg.get("label", url)
        if not url:
            continue

        entries = _fetch_feed(url)
        logger.info(f"  Direct [{label}]: {len(entries)} entries")

        for entry in entries:
            parsed = _parse_entry(entry, label, "direct")
            if parsed and parsed["content_hash"] not in seen_hashes:
                seen_hashes.add(parsed["content_hash"])
                all_items.append(parsed)

    return all_items


# ── Main ────────────────────────────────────────────────────────────
def collect_once():
    """Run one collection cycle: fetch all feeds, dedupe, write candidates."""
    logger.info("RSS collection starting...")

    rss_config = _load_rss_config()
    collector_config = _load_rss_collector_config()
    max_items = collector_config.get("base_item_cap", 20)

    all_items = []

    # RSSHub
    logger.info("Collecting from RSSHub...")
    items = _collect_from_rsshub(rss_config.get("rsshub", {}))
    all_items.extend(items[:max_items * 5])  # cap overall

    # wewe-rss
    logger.info("Collecting from wewe-rss...")
    items = _collect_from_wewe_rss(rss_config.get("wewe_rss", {}))
    all_items.extend(items[:max_items * 3])

    # Direct feeds
    logger.info("Collecting from direct feeds...")
    items = _collect_from_direct(rss_config.get("direct", []))
    all_items.extend(items[:max_items * 3])

    # Save to cache (persistent, for future dedup)
    _save_cached(all_items)

    # Write candidates (Scout consumes these)
    _write_candidates(all_items)

    logger.info(f"RSS collection done. {len(all_items)} new candidates")
    return all_items


def _setup_logging():
    """Configure logging for standalone or daemon mode."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    _setup_logging()

    if "--daemon" in sys.argv:
        logger.info(f"Starting RSS collector daemon (interval={RSS_COLLECTOR_INTERVAL}min)")
        while True:
            try:
                collect_once()
            except Exception as e:
                logger.error(f"Collection cycle failed: {e}", exc_info=True)
            time.sleep(RSS_COLLECTOR_INTERVAL * 60)
    else:
        collect_once()


if __name__ == "__main__":
    main()
