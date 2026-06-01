"""Scout scorer — LLM-based candidate scoring.

Implements the PRD 3.1 scoring formula with freshness, self-repeat,
source weight, and tier multiplier calculations.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config.settings import (
    CONFIG_DIR,
    DOMAIN,
    KB_DIR,
)
from skills.common import get_agent_logger, load_prompt
from skills.llm import chat_structured
from skills.topic_analyzer import analyze_topic_competition

logger = get_agent_logger("scout")

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

    result = dict(candidate)
    result.update({
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
    return result
