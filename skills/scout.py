"""Scout Agent — topic discovery and scoring.

Scans multiple channels (china-hot MCP, GitHub, RSS, Firecrawl, kb/materials),
scores each candidate using a two-layer model, enforces content diversity,
and writes the top candidates to queue/pending/.

Phase 1: single Worker, cold-start parameters.

Uses AgentBase for unified status writing, logging, and metrics.
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import (
    ACTIONS_DIR,
    CONFIG_DIR,
    DOMAIN,
    KB_DIR,
    PENDING_DIR,
    SOURCES_DIR,
    STATUS_DIR,
    TMP_DIR,
)
from skills.action import write_topic_pending
from skills.agent_schemas import ScoutOutput, TopicCandidate
from skills.common import AgentBase, agent_main, get_agent_logger, load_prompt, write_status as _write_status_fn
from skills.llm import chat_structured, set_current_agent
from skills.topic_analyzer import analyze_topic_competition

# Module-level logger for standalone functions
logger = get_agent_logger("scout")

# Allowed source names for china-hot MCP (security whitelist)
ALLOWED_CHINA_HOT_SOURCES = frozenset({
    "weibo", "zhihu", "bilibili", "baidu", "douyin", "toutiao", "kr36"
})

# Max workers for concurrent LLM scoring
MAX_SCORING_WORKERS = 5

# ── Constants ──────────────────────────────────────────────────────
SAME_TOPIC_BLOCK_DAYS = 3
COLD_START_DAYS = 14
HISTORY_DIR = KB_DIR / "history"

# ── Source config loader ───────────────────────────────────────────
def _load_sources_config() -> dict:
    """Load source weights and tier config from config/sources.json."""
    config_path = CONFIG_DIR / "sources.json"
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load sources config: {e}, using defaults")
        return {
            "sources": {},
            "tier_multipliers": {"T1": 1.15, "T1.5": 1.08, "T2": 1.0},
            "default_weight": 0.5,
            "default_tier": "T2",
        }

_SOURCES_CONFIG = _load_sources_config()
SOURCE_WEIGHTS: dict[str, float] = {
    name: info["weight"] for name, info in _SOURCES_CONFIG["sources"].items()
}
_SOURCE_TIERS: dict[str, str] = {
    name: info["tier"] for name, info in _SOURCES_CONFIG["sources"].items()
}
TIER_MULTIPLIERS: dict[str, float] = _SOURCES_CONFIG["tier_multipliers"]
DEFAULT_WEIGHT: float = _SOURCES_CONFIG.get("default_weight", 0.5)
DEFAULT_TIER: str = _SOURCES_CONFIG.get("default_tier", "T2")

# Scoring thresholds (PRD 3.1)
ATTENTION_FLOOR = 40
FINAL_FLOOR = 55
COLD_START_FLOOR = 45  # lower bar during cold start when few sources available
STRONG_PUSH = 85
CANDIDATE_CAP = 10
MIN_CANDIDATES = 5
MAX_SUB_DIRECTIONS = 3  # diversity: at least 3 different sub-directions

# Phase 1: only morning/afternoon session
SESSION = sys.argv[1] if len(sys.argv) > 1 else "morning"
RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
RUN_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _write_status(stage: str, progress_pct: int, detail: str, error: Optional[str] = None) -> None:
    """Write scout agent status using the standalone write_status function."""
    _write_status_fn("scout", stage, progress_pct, detail, error, started_at=RUN_TIMESTAMP)


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

    # china-hot sources (may fail, graceful degrade)
    for source in ["weibo", "zhihu", "bilibili", "baidu", "douyin", "toutiao", "kr36"]:
        items = _call_china_hot(source)
        for item in items[:3]:  # top 3 per source
            title = item.get("title", "") or item.get("name", "") or ""
            if title:
                candidates.append({
                    "title": title,
                    "description": item.get("description", "") or item.get("desc", "") or "",
                    "url": item.get("url", "") or item.get("link", "") or "",
                    "source": source,
                    "hot_value": item.get("hot_value", 0) or item.get("score", 50),
                })

    # GitHub
    for item in _call_github_trending():
        candidates.append(item)

    # kb/materials
    for item in _collect_materials():
        candidates.append(item)

    # Firecrawl web search
    for query in [f"今日科技热点 {DOMAIN}", "AI 最新动态"]:
        for item in _call_firecrawl_search(query):
            title = item.get("title", "") or ""
            if title:
                candidates.append({
                    "title": title,
                    "description": item.get("description", "") or item.get("content", "") or "",
                    "url": item.get("url", "") or item.get("link", "") or "",
                    "source": "web_search",
                    "hot_value": 50,
                })

    _write_status("collecting", 30, f"Collected {len(candidates)} raw candidates")
    return candidates


def _save_raw_sources(candidates: list[dict]) -> None:
    """Save raw candidates to queue/sources/ for the dashboard sources page."""
    if not candidates:
        return
    date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = SOURCES_DIR / f"{date_str}.json"
    tmp_path = out_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    tmp_path.rename(out_path)
    logger.info(f"Saved {len(candidates)} raw sources to {out_path}")


# ── Dedup & Filter ─────────────────────────────────────────────────
def _is_same_topic(title_a: str, title_b: str) -> bool:
    """Simple title-level dedup: check significant word overlap.

    Uses both word-level and character-level matching for better CJK support.
    """
    # Word-level matching (for mixed Chinese/English)
    words_a = set(re.findall(r'[\w\u4e00-\u9fff]{2,}', title_a.lower()))
    words_b = set(re.findall(r'[\w\u4e00-\u9fff]{2,}', title_b.lower()))

    if words_a and words_b:
        word_overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
        if word_overlap > 0.5:
            return True

    # Character-level matching (better for Chinese)
    chars_a = set(re.findall(r'[\u4e00-\u9fff]', title_a))
    chars_b = set(re.findall(r'[\u4e00-\u9fff]', title_b))

    # Require significant character overlap (at least 3 chars in common)
    if chars_a and chars_b and len(chars_a & chars_b) >= 3:
        char_overlap = len(chars_a & chars_b) / max(len(chars_a | chars_b), 1)
        if char_overlap > 0.6:
            return True

    # Check if one title contains the other (require 50% containment)
    clean_a = re.sub(r'[^\w\u4e00-\u9fff]', '', title_a.lower())
    clean_b = re.sub(r'[^\w\u4e00-\u9fff]', '', title_b.lower())
    if len(clean_a) >= 4 and len(clean_b) >= 4:
        shorter = min(len(clean_a), len(clean_b))
        longer = max(len(clean_a), len(clean_b))
        if shorter / longer > 0.5:
            if clean_a in clean_b or clean_b in clean_a:
                return True

    return False


def _recent_topics(days: int = SAME_TOPIC_BLOCK_DAYS) -> set[str]:
    """Return set of topic titles written in the past N days."""
    recent = set()
    if HISTORY_DIR.exists():
        for d in list(HISTORY_DIR.iterdir()):
            if d.is_dir():
                for f in d.glob("*.md"):
                    text = f.read_text(encoding="utf-8", errors="ignore")
                    title = text.split("\n")[0].removeprefix("# ").strip()
                    if title:
                        recent.add(title)
    # Also check pending
    for f in PENDING_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("title"):
                recent.add(data["title"])
        except (json.JSONDecodeError, OSError):
            pass
    return recent


def dedup_and_filter(candidates: list[dict]) -> list[dict]:
    """Remove duplicates and topics written recently."""
    recent = _recent_topics()
    unique: list[dict] = []
    seen_titles: list[str] = []

    for c in candidates:
        title = c["title"].strip()
        if not title or len(title) < 4:
            continue

        # Check recent topics
        if any(_is_same_topic(title, rt) for rt in recent):
            continue

        # Check previously seen in this batch
        if any(_is_same_topic(title, st) for st in seen_titles):
            continue

        seen_titles.append(title)
        unique.append(c)

    return unique


# ── LLM scoring ────────────────────────────────────────────────────
def _is_cold_start() -> bool:
    """Check if system is in cold start (first 2 weeks)."""
    history_count = sum(1 for _ in HISTORY_DIR.rglob("*.md")) if HISTORY_DIR.exists() else 0
    return history_count < 5  # less than 5 articles → cold start


def calculate_freshness(candidate: dict) -> int:
    """Calculate freshness score based on available timestamp or hot_value.

    Scoring (PRD 3.1):
      1h 内  → 90（爆发期）
      6h 内  → 75
      24h 内 → 60
      48h 内 → 40
      >48h   → 20（已过期）
    Falls back to hot_value mapping or default 60.
    """
    now = datetime.now(timezone.utc)

    # Try explicit timestamp fields
    for key in ("published_at", "created_at", "timestamp", "date"):
        raw = candidate.get(key)
        if not raw:
            continue
        try:
            if isinstance(raw, (int, float)):
                dt = datetime.fromtimestamp(raw, tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(str(raw))
            hours = (now - dt).total_seconds() / 3600
            if hours <= 1:
                return 90
            if hours <= 6:
                return 75
            if hours <= 24:
                return 60
            if hours <= 48:
                return 40
            return 20
        except (ValueError, TypeError, OSError):
            continue

    # Fallback: map hot_value to freshness (higher hot → more recent/trending)
    hot = candidate.get("hot_value", 0)
    if hot and isinstance(hot, (int, float)):
        if hot >= 90:
            return 90
        if hot >= 70:
            return 75
        if hot >= 50:
            return 60
        if hot >= 30:
            return 40
        return 20

    return 60  # default medium freshness


def calculate_self_repeat(title: str) -> int:
    """Check KB history for same-entity articles to compute self_repeat score.

    Returns:
      10 — same entity, same direction (highly repetitive)
      50 — same entity, different direction
      100 — novel topic
    """
    if not HISTORY_DIR.exists():
        return 100

    from skills.topic_analyzer import extract_keywords, get_history_articles

    keywords = extract_keywords(title)
    if not keywords:
        return 100

    recent = get_history_articles(days=SAME_TOPIC_BLOCK_DAYS)
    best_overlap = 0.0

    for art in recent:
        art_keywords = extract_keywords(art.get("title", ""))
        if not art_keywords:
            continue
        overlap = len(keywords & art_keywords) / len(keywords | art_keywords)
        best_overlap = max(best_overlap, overlap)

    if best_overlap >= 0.25:
        return 10   # same entity, same direction
    if best_overlap >= 0.12:
        return 50   # same entity, different direction
    return 100       # novel


def get_tier(source: str) -> str:
    """Get tier for a source (T1, T1.5, T2)."""
    return _SOURCE_TIERS.get(source, DEFAULT_TIER)


def score_candidate(candidate: dict, cold_start: bool) -> dict | None:
    """Score a single candidate via LLM using PRD 3.1 formula.

    Returns scored candidate or None if below attention floor.
    """
    source = candidate.get("source", "web_search")
    source_weight = SOURCE_WEIGHTS.get(source, DEFAULT_WEIGHT)

    freshness_score = calculate_freshness(candidate)

    # Call LLM to score
    cold_start_note = "## 注意：系统刚启动，历史数据不足。请重点评估话题本身的价值和可讨论深度，saturation一律给0分。" if cold_start else ""
    prompt = load_prompt(
        "scout_scoring",
        domain=DOMAIN,
        title=candidate['title'],
        source=source,
        description=candidate.get('description', '无')[:200],
        cold_start_note=cold_start_note,
    )

    try:
        result = chat_structured(
            system_prompt="你是一个严谨的选题评分专家。评分必须基于实际判断，不要给所有选题相近的分数。必须返回合法 JSON，不要返回 markdown 代码块。",
            user_prompt=prompt,
            temperature=0.3,
        )
    except Exception as e:
        return None

    # Extract scores
    viral = int(result.get("viral_score", 50))
    saturation = int(result.get("saturation_score", 50))
    novelty = int(result.get("novelty_score", 50))

    # Adjust saturation with actual history analysis
    try:
        competition = analyze_topic_competition(candidate['title'], source)
        history_saturation = competition['saturation']['saturation_score']
        # Blend LLM saturation (60%) with history-based saturation (40%)
        saturation = int(saturation * 0.6 + history_saturation * 0.4)
        if competition['recommendation'] == 'skip':
            logger.info(f"Topic '{candidate['title'][:30]}' flagged as oversaturated: {competition['reason']}")
    except Exception:
        pass  # History analysis is supplementary, not blocking
    feasibility = int(result.get("feasibility_score", 50))
    direction = result.get("direction", "general")

    # Cold start overrides (PRD 3.1)
    if cold_start:
        viral = int(source_weight * 100)  # use source_weight instead
        saturation = 0  # no baseline yet
        self_repeat = 100  # no history to compare
    else:
        self_repeat = calculate_self_repeat(candidate['title'])

    # PRD formula
    attention = min(100,
        (source_weight ** 1.3) * 0.35
        + viral * 0.30
        + freshness_score * 0.35
    )

    if attention < ATTENTION_FLOOR:
        return None

    increment = saturation * 0.40 + novelty * 0.35 + self_repeat * 0.25
    raw_score = attention * 0.55 + increment * 0.25 + feasibility * 0.20

    # Apply tier multiplier (PRD 3.1)
    tier = get_tier(source)
    tier_multiplier = TIER_MULTIPLIERS.get(tier, 1.0)
    final_score = raw_score * tier_multiplier

    candidate.update({
        "source_weight": round(source_weight, 2),
        "viral_score": viral,
        "freshness_score": freshness_score,
        "saturation_score": saturation,
        "novelty_score": novelty,
        "feasibility_score": feasibility,
        "self_repeat_score": self_repeat,
        "attention_score": round(attention, 1),
        "increment_score": round(increment, 1),
        "raw_score": round(raw_score, 1),
        "tier": tier,
        "tier_multiplier": tier_multiplier,
        "final_score": round(final_score, 1),
        "direction": direction,
    })
    return candidate


def _enforce_diversity(scored: list[dict]) -> list[dict]:
    """Ensure at least 3 different sub-directions in top candidates.

    If a direction dominates, pick the highest-scored from each direction
    and fill remaining slots by score.
    """
    if len(scored) <= MAX_SUB_DIRECTIONS:
        # Still sort by score even for small lists
        return sorted(scored, key=lambda x: x.get("final_score", 0), reverse=True)

    # Group by direction
    by_dir: dict[str, list[dict]] = {}
    for c in scored:
        d = c.get("direction", "general")
        by_dir.setdefault(d, []).append(c)

    result: list[dict] = []
    # Take top from each direction
    for d, items in by_dir.items():
        items.sort(key=lambda x: x["final_score"], reverse=True)
        result.append(items[0])

    # Fill remaining slots by score
    taken_ids = {id(c) for c in result}
    remaining = [c for c in scored if id(c) not in taken_ids]
    remaining.sort(key=lambda x: x["final_score"], reverse=True)
    result.extend(remaining[:CANDIDATE_CAP - len(result)])

    result.sort(key=lambda x: x["final_score"], reverse=True)
    return result


# ── Main ───────────────────────────────────────────────────────────
def _score_candidate_wrapper(args: tuple[dict, bool]) -> Optional[dict]:
    """Wrapper for score_candidate to use with ThreadPoolExecutor."""
    candidate, cold_start = args
    try:
        return score_candidate(candidate, cold_start)
    except Exception as e:
        logger.warning(f"Failed to score candidate '{candidate.get('title', '?')[:30]}': {e}")
        return None


def main():
    # Try to create a pipeline session for tracing
    session_id = None
    try:
        from dashboard.backend.database import create_pipeline_session
        session_id = create_pipeline_session(
            date=RUN_DATE,
            period="am" if SESSION == "morning" else "pm",
            topic=f"Scout {SESSION}",
        )
    except Exception:
        pass

    _write_status("collecting", 5, f"Starting scout {SESSION} session")
    logger.info(f"{SESSION} session started at {RUN_TIMESTAMP}")

    cold_start = _is_cold_start()
    logger.info(f"Cold start mode: {cold_start}")

    # Step 1: Collect
    _write_status("collecting", 15, "Collecting from all sources")
    try:
        from dashboard.backend.database import trace_stage
        with trace_stage(session_id, "scout", "collect", "采集选题") as t:
            candidates = collect_all()
            t["output"] = f"{len(candidates)} raw candidates"
    except Exception:
        candidates = collect_all()
    _save_raw_sources(candidates)
    logger.info(f"Collected {len(candidates)} raw candidates")

    # Step 2: Dedup & filter
    _write_status("dedup", 35, f"Deduplicating {len(candidates)} candidates")
    try:
        with trace_stage(session_id, "scout", "dedup", "去重过滤") as t:
            candidates = dedup_and_filter(candidates)
            t["output"] = f"{len(candidates)} unique"
    except Exception:
        candidates = dedup_and_filter(candidates)
    logger.info(f"After dedup: {len(candidates)} unique")

    # Step 3: Score candidates via LLM (concurrent)
    _write_status("scoring", 50, f"Scoring {len(candidates)} candidates via LLM")
    scored: list[dict] = []

    if candidates:
        # Use ThreadPoolExecutor for concurrent scoring
        with ThreadPoolExecutor(max_workers=MAX_SCORING_WORKERS) as executor:
            # Prepare tasks
            tasks = [(c, cold_start) for c in candidates]

            # Submit all tasks
            future_to_candidate = {
                executor.submit(_score_candidate_wrapper, task): task[0]
                for task in tasks
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_candidate):
                completed += 1
                candidate = future_to_candidate[future]

                # Update progress
                _write_status(
                    "scoring",
                    50 + int(30 * completed / max(len(candidates), 1)),
                    f"Scoring {completed}/{len(candidates)}: {candidate['title'][:30]}"
                )

                try:
                    result = future.result(timeout=60)
                    if result:
                        scored.append(result)
                except Exception as e:
                    logger.warning(f"Scoring failed for '{candidate['title'][:30]}': {e}")

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    logger.info(f"Scored candidates: {len(scored)}")

    # Step 4: Apply diversity constraint
    scored = _enforce_diversity(scored)
    logger.info(f"After diversity: {len(scored)} candidates")

    # Step 5: Filter by threshold (lower bar during cold start)
    threshold = COLD_START_FLOOR if cold_start else FINAL_FLOOR
    final = [c for c in scored if c["final_score"] >= threshold][:CANDIDATE_CAP]
    logger.info(f"Final candidates meeting threshold: {len(final)}")

    # Step 6: Validate via schema
    validated_final = []
    for c in final:
        try:
            validated = TopicCandidate.model_validate(c)
            validated_final.append(c)
        except Exception as e:
            logger.warning(f"Schema validation failed for '{c.get('title', '?')[:30]}': {e}")

    # Step 7: Write to pending
    _write_status("writing", 85, f"Writing {len(validated_final)} candidates to queue/pending/")
    try:
        with trace_stage(session_id, "scout", "write", "写入队列") as t:
            for c in validated_final:
                write_topic_pending(c)
            t["output"] = f"{len(validated_final)} candidates"
    except Exception:
        for c in validated_final:
            write_topic_pending(c)

    # Step 8: Validate full output and write summary status
    try:
        ScoutOutput(
            session=SESSION,
            topics=[TopicCandidate.model_validate(c) for c in validated_final],
            total_collected=len(candidates),
            total_selected=len(validated_final),
            sources_used=list({c.get("source", "unknown") for c in validated_final}),
        )
    except Exception as e:
        logger.warning(f"ScoutOutput validation failed: {e}")

    summary = {
        "agent": "scout",
        "stage": "completed",
        "progress_pct": 100,
        "detail": f"{SESSION} session: {len(validated_final)} candidates pushed (from {len(candidates)} raw)",
        "started_at": RUN_TIMESTAMP,
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidate_count": len(validated_final),
        "cold_start": cold_start,
        "session": SESSION,
        "error": None,
    }
    
    from skills.common import atomic_write_json
    path = STATUS_DIR / "scout.json"
    atomic_write_json(path, summary)

    logger.info(f"Done. {len(final)} candidates written to pending/")
    logger.info(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
