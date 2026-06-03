"""Scout Agent — topic discovery and scoring.

Scans multiple channels (china-hot MCP, GitHub, RSS, Firecrawl, kb/materials),
scores each candidate using a two-layer model, enforces content diversity,
and writes the top candidates to queue/pending/.

Phase 1: single Worker, cold-start parameters.

Uses AgentBase for unified status writing, logging, and metrics.
"""

import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import (
    ACTIONS_DIR,
    QUEUE_DIR,
    CONFIG_DIR,
    DOMAIN,
    KB_DIR,
    PENDING_DIR,
    SOURCES_DIR,
    STATUS_DIR,
    TMP_DIR,
    TRAIL_DIR,
)
from skills.action import write_topic_pending
from skills.agent_schemas import ScoutOutput, TopicCandidate
from skills.common import AgentBase, agent_main, atomic_write_json, get_agent_logger, write_status as _write_status_fn
from skills.scout_collectors import collect_all, _save_raw_sources
from skills.scout_dedup import dedup_and_filter
from skills.scout_scorer import (
    score_candidate,
    _is_cold_start,
    COLD_START_FLOOR,
    FINAL_FLOOR,
)

# Module-level logger for standalone functions
logger = get_agent_logger("scout")

# Max workers for concurrent LLM scoring
MAX_SCORING_WORKERS = 5

# Diversity thresholds
CANDIDATE_CAP = 10
MIN_CANDIDATES = 5
MAX_SUB_DIRECTIONS = 3  # diversity: at least 3 different sub-directions

# Phase 1: only morning/afternoon session
_SESSION = None  # set at call time via main()
_RUN_TIMESTAMP = None  # set at call time via main()
_RUN_DATE = None  # set at call time via main()

# Stage name mapping for trace files
_STAGE_NAMES = {
    "collect": "采集选题",
    "dedup": "去重过滤",
    "scoring": "LLM 评分",
    "write": "写入队列",
}


def _write_status(stage: str, progress_pct: int, detail: str, error: Optional[str] = None) -> None:
    """Write scout agent status using the standalone write_status function."""
    _write_status_fn("scout", stage, progress_pct, detail, error, started_at=_RUN_TIMESTAMP)


class ScoutAgent(AgentBase):
    """Scout agent with stage tracking via AgentBase."""

    name = "scout"
    version = "1.0.0"

    def run(self) -> None:
        """Run the full scout pipeline using inherited stage tracking."""
        main(agent=self)


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


def main(agent: Optional[ScoutAgent] = None):
    """Run the scout pipeline.

    Args:
        agent: Optional ScoutAgent instance for stage tracking.
               If None, falls back to standalone _write_status.
    """
    global _SESSION, _RUN_TIMESTAMP, _RUN_DATE
    _SESSION = sys.argv[1] if len(sys.argv) > 1 else "morning"
    _RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _RUN_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # No session created here — dashboard background imports trail files
    session_id = None
    _write_status("collecting", 5, f"Starting scout {_SESSION} session")
    logger.info(f"{_SESSION} session started at {_RUN_TIMESTAMP}")

    cold_start = _is_cold_start()
    logger.info(f"Cold start mode: {cold_start}")

    # Step 1: Collect
    _write_status("collecting", 15, "Collecting from all sources")
    if agent:
        agent.start_stage("collect")
    try:
        candidates = collect_all()
    finally:
        if agent:
            agent.end_stage("collect")
    _save_raw_sources(candidates)
    logger.info(f"Collected {len(candidates)} raw candidates")

    # Step 2: Dedup & filter
    _write_status("dedup", 35, f"Deduplicating {len(candidates)} candidates")
    if agent:
        agent.start_stage("dedup")
    try:
        candidates = dedup_and_filter(candidates)
    finally:
        if agent:
            agent.end_stage("dedup")
    logger.info(f"After dedup: {len(candidates)} unique")

    # Step 3: Score candidates via LLM (concurrent)
    _write_status("scoring", 50, f"Scoring {len(candidates)} candidates via LLM")
    scored: list[dict] = []

    if agent:
        agent.start_stage("scoring")
    try:
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
    finally:
        if agent:
            agent.end_stage("scoring")

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
            validated_final.append(validated)
        except Exception as e:
            logger.warning(f"Schema validation failed for '{c.get('title', '?')[:30]}': {e}")

    # Step 7: Write to pending
    _write_status("writing", 85, f"Writing {len(validated_final)} candidates to queue/pending/")
    if agent:
        agent.start_stage("write")
    try:
        for c in validated_final:
            write_topic_pending(c)
    finally:
        if agent:
            agent.end_stage("write")

    # Step 8: Validate full output and write summary status
    try:
        ScoutOutput(
            session=_SESSION,
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
        "detail": f"{_SESSION} session: {len(validated_final)} candidates pushed (from {len(candidates)} raw)",
        "started_at": _RUN_TIMESTAMP,
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidate_count": len(validated_final),
        "cold_start": cold_start,
        "session": _SESSION,
        "error": None,
    }

    path = STATUS_DIR / "scout.json"
    atomic_write_json(path, summary)

    logger.info(f"Done. {len(final)} candidates written to pending/")
    logger.info(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
