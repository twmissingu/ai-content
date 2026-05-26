"""Scout Agent — topic discovery and scoring.

Scans multiple channels (china-hot MCP, GitHub, RSS, Firecrawl, kb/materials),
scores each candidate using a two-layer model, enforces content diversity,
and writes the top candidates to queue/pending/.

Phase 1: single Worker, cold-start parameters.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import (
    ACTIONS_DIR,
    DOMAIN,
    KB_DIR,
    PENDING_DIR,
    STATUS_DIR,
    TMP_DIR,
)
from skills.action import write_topic_pending
from skills.llm import chat_structured

# ── Constants ──────────────────────────────────────────────────────
SAME_TOPIC_BLOCK_DAYS = 3
COLD_START_DAYS = 14
HISTORY_DIR = KB_DIR / "history"

# source_weight initial table (PRD 3.1)
SOURCE_WEIGHTS: dict[str, float] = {
    "twitter": 0.95,
    "rss": 0.85,
    "github": 0.80,
    "web_search": 0.75,
    "zhihu": 0.70,
    "kr36": 0.70,
    "materials": 0.90,
    "weibo": 0.50,
    "douyin": 0.45,
    "baidu": 0.40,
    "bilibili": 0.55,
    "toutiao": 0.50,
}

# Scoring thresholds (PRD 3.1)
ATTENTION_FLOOR = 40
FINAL_FLOOR = 55
STRONG_PUSH = 85
CANDIDATE_CAP = 10
MIN_CANDIDATES = 5
MAX_SUB_DIRECTIONS = 3  # diversity: at least 3 different sub-directions

# Phase 1: only morning/afternoon session
SESSION = sys.argv[1] if len(sys.argv) > 1 else "morning"
RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
RUN_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Status file ────────────────────────────────────────────────────
def _write_status(stage: str, progress_pct: int, detail: str, error: Any = None):
    """Write scout status file."""
    status = {
        "agent": "scout",
        "stage": stage,
        "progress_pct": progress_pct,
        "detail": detail,
        "started_at": RUN_TIMESTAMP,
        "error": str(error) if error else None,
    }
    path = STATUS_DIR / "scout.json"
    tmp = STATUS_DIR / ".scout.json.tmp"
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    os.rename(tmp, path)


# ── Source collectors ──────────────────────────────────────────────
def _call_china_hot(source: str) -> list[dict]:
    """Call china-hot-mcp tool via Hermes MCP.
    
    Each china-hot tool returns a list of trending items with at minimum
    a 'title' field. Returns empty list on any failure (network, tool not
    available, etc.) — never raises.
    """
    try:
        # Hermes MCP tools are invoked via hermes gateway
        result = subprocess.run(
            ["hermes", "mcp", "call", f"china-hot_{source}_trending"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
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
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []


def _call_firecrawl_search(query: str) -> list[dict]:
    """Search web via Firecrawl for trending AI/tech content."""
    try:
        result = subprocess.run(
            ["hermes", "mcp", "call", "firecrawl_web_search",
             "--params", json.dumps({"query": query, "count": 5})],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        items = json.loads(result.stdout)
        if isinstance(items, dict) and "data" in items:
            items = items["data"]
        return items if isinstance(items, list) else []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []


def _call_github_trending() -> list[dict]:
    """Fetch GitHub trending repos via API."""
    try:
        result = subprocess.run(
            ["curl", "-s",
             "https://api.github.com/search/repositories?q=created:>2026-05-20&sort=stars&order=desc&per_page=10"],
            capture_output=True, text=True, timeout=15,
        )
        data = json.loads(result.stdout)
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
    except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
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


# ── Dedup & Filter ─────────────────────────────────────────────────
def _is_same_topic(title_a: str, title_b: str) -> bool:
    """Simple title-level dedup: check significant word overlap."""
    words_a = set(re.findall(r'[\w\u4e00-\u9fff]{2,}', title_a.lower()))
    words_b = set(re.findall(r'[\w\u4e00-\u9fff]{2,}', title_b.lower()))
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
    return overlap > 0.4


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


def score_candidate(candidate: dict, cold_start: bool) -> dict | None:
    """Score a single candidate via LLM using PRD 3.1 formula.

    Returns scored candidate or None if below attention floor.
    """
    source = candidate.get("source", "web_search")
    source_weight = SOURCE_WEIGHTS.get(source, 0.5)

    # Determine freshness from lack of timestamp — use default
    freshness_score = 60  # default medium freshness

    # Call LLM to score
    prompt = f"""你是选题评分专家。请对以下选题进行评分，输出 JSON 格式。

选题: {candidate['title']}
来源: {source}
来源权重: {source_weight}
领域: {DOMAIN}

请从以下维度评分（0-100整数）:
1. viral_score: 该话题的热度/关注度
2. saturation_score: 行业内已有多少文章覆盖此话题（越高=越饱和）
3. novelty_score: 该选题是否有新颖的切入角度
4. feasibility_score: 该话题是否容易查到资料、产生独特观点

{"注意：系统处于冷启动阶段，尚无历史数据。请根据话题本身可讨论的深度来评估。" if cold_start else ""}

输出严格的 JSON 格式（不要 markdown）:
{{"viral_score": 0, "saturation_score": 0, "novelty_score": 0, "feasibility_score": 0, "direction": "方向分类标签", "rationale": "简要评分理由"}}
"""

    try:
        result = chat_structured(
            system_prompt="你是一个严谨的选题评分专家。必须返回合法 JSON。",
            user_prompt=prompt,
            temperature=0.4,
        )
    except Exception as e:
        return None

    # Extract scores
    viral = int(result.get("viral_score", 50))
    saturation = int(result.get("saturation_score", 50))
    novelty = int(result.get("novelty_score", 50))
    feasibility = int(result.get("feasibility_score", 50))
    direction = result.get("direction", "general")

    # Cold start overrides (PRD 3.1)
    if cold_start:
        viral = int(source_weight * 100)  # use source_weight instead
        saturation = 0  # no baseline yet
        # self_repeat_score not used in cold start

    # PRD formula
    attention = min(100,
        (source_weight ** 1.3) * 0.35
        + viral * 0.30
        + freshness_score * 0.35
    )

    if attention < ATTENTION_FLOOR:
        return None

    self_repeat = 100  # not repeating (we filtered already)
    increment = saturation * 0.40 + novelty * 0.35 + self_repeat * 0.25
    final_score = attention * 0.55 + increment * 0.25 + feasibility * 0.20

    candidate.update({
        "source_weight": round(source_weight, 2),
        "viral_score": viral,
        "freshness_score": freshness_score,
        "saturation_score": saturation,
        "novelty_score": novelty,
        "feasibility_score": feasibility,
        "attention_score": round(attention, 1),
        "increment_score": round(increment, 1),
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
        return scored

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
def main():
    _write_status("collecting", 5, f"Starting scout {SESSION} session")
    print(f"[scout] {SESSION} session started at {RUN_TIMESTAMP}")

    cold_start = _is_cold_start()
    print(f"[scout] Cold start mode: {cold_start}")

    # Step 1: Collect
    _write_status("collecting", 15, "Collecting from all sources")
    candidates = collect_all()
    print(f"[scout] Collected {len(candidates)} raw candidates")

    # Step 2: Dedup & filter
    _write_status("dedup", 35, f"Deduplicating {len(candidates)} candidates")
    candidates = dedup_and_filter(candidates)
    print(f"[scout] After dedup: {len(candidates)} unique")

    # Step 3: Score each candidate via LLM
    _write_status("scoring", 50, f"Scoring {len(candidates)} candidates via LLM")
    scored: list[dict] = []
    for i, c in enumerate(candidates):
        _write_status("scoring", 50 + int(30 * (i + 1) / max(len(candidates), 1)),
                      f"Scoring {i+1}/{len(candidates)}: {c['title'][:30]}")
        result = score_candidate(c, cold_start)
        if result:
            scored.append(result)

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    print(f"[scout] Scored candidates: {len(scored)}")

    # Step 4: Apply diversity constraint
    scored = _enforce_diversity(scored)
    print(f"[scout] After diversity: {len(scored)} candidates")

    # Step 5: Filter by threshold
    final = [c for c in scored if c["final_score"] >= FINAL_FLOOR][:CANDIDATE_CAP]
    print(f"[scout] Final candidates meeting threshold: {len(final)}")

    # Step 6: Write to pending
    _write_status("writing", 85, f"Writing {len(final)} candidates to queue/pending/")
    for c in final:
        write_topic_pending(c)

    # Step 7: Write summary status
    summary = {
        "agent": "scout",
        "stage": "completed",
        "progress_pct": 100,
        "detail": f"{SESSION} session: {len(final)} candidates pushed (from {len(candidates)} raw)",  # noqa: E501
        "started_at": RUN_TIMESTAMP,
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidate_count": len(final),
        "cold_start": cold_start,
        "session": SESSION,
        "error": None,
    }
    path = STATUS_DIR / "scout.json"
    tmp = STATUS_DIR / ".scout.json.tmp"
    tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    os.rename(tmp, path)

    print(f"[scout] Done. {len(final)} candidates written to pending/")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
