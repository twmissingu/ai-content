"""Writer helper functions — extracted from WriterAgent for modularity.

These functions handle CLI parsing, pipeline execution, output writing,
and article validation. They are pure functions (no class dependency)
extracted from the WriterAgent god class to improve testability and
reduce cognitive load.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

from config.settings import ACTIONS_DIR, REVIEW_DIR
from skills.agent_schemas import ArticleDraft


# ── CLI Argument Parsing ─────────────────────────────────────────────

def parse_cli_args(
    topic_id: Optional[str],
    rewrite_mode: bool,
    rerun_from: Optional[int],
) -> tuple:
    """Parse CLI arguments for WriterAgent.

    Returns:
        (topic_id, rewrite_mode, rewrite_target, rerun_from_arg, topic_file_arg, work_dir_arg)
    """
    topic_file_arg = None
    work_dir_arg = None
    rerun_from_arg = rerun_from
    for i, arg in enumerate(sys.argv):
        if arg == "--topic-file" and i + 1 < len(sys.argv):
            topic_file_arg = Path(sys.argv[i + 1])
        elif arg == "--work-dir" and i + 1 < len(sys.argv):
            work_dir_arg = Path(sys.argv[i + 1])
        elif arg == "--rerun-from" and i + 1 < len(sys.argv):
            rerun_from_arg = int(sys.argv[i + 1])

    if topic_id is None:
        topic_id = sys.argv[1] if len(sys.argv) > 1 else None

    if not rewrite_mode:
        rewrite_mode = "--rewrite" in sys.argv

    rewrite_target = topic_id if rewrite_mode else None
    return topic_id, rewrite_mode, rewrite_target, rerun_from_arg, topic_file_arg, work_dir_arg


# ── Critique Loop ─────────────────────────────────────────────────────

def run_critique_loop(
    text: str,
    topic_title: str,
    quality_gates: dict,
    critique_fn,
    write_status_fn,
    start_stage_fn,
    end_stage_fn,
    logger,
) -> tuple[str, list[int]]:
    """Run the critique loop with rewriting.

    Args:
        text: Current article text.
        topic_title: Topic title for context.
        quality_gates: Quality gate thresholds.
        critique_fn: Callable(text, title, round) -> (text, score, passed).
        write_status_fn: Callable(stage, pct, detail).
        start_stage_fn: Callable(stage_name).
        end_stage_fn: Callable(stage_name).
        logger: Logger instance.

    Returns:
        (text, critique_scores)
    """
    start_stage_fn("critique")
    critique_scores: list[int] = []
    for round_num in range(1, quality_gates["max_rewrite_rounds"] + 1):
        text, score, passed = critique_fn(text, topic_title, round_num)
        critique_scores.append(score)
        write_status_fn("批评修订", 50 + round_num * 10, f"第{round_num}轮: 评分{score}")
        logger.info(f"Stage 4 round {round_num}: score={score}, passed={passed}")
        if passed:
            break
        if round_num < quality_gates["max_rewrite_rounds"]:
            write_status_fn("批评修订", 50 + round_num * 10, f"第{round_num}轮未通过，开始第{round_num + 1}轮")
    end_stage_fn("critique")
    return text, critique_scores


# ── Article Validation ────────────────────────────────────────────────

def validate_article_draft(
    title: str,
    text: str,
    topic: dict,
    source_url: str,
    proofread_score: int,
    critique_scores: list[int],
    title_candidates: list[dict],
    images: list[str],
    worker_type: str,
    logger,
) -> Optional[ArticleDraft]:
    """Validate output via ArticleDraft schema.

    Returns:
        Validated ArticleDraft or None if validation fails.
    """
    try:
        return ArticleDraft.model_validate({
            "title": title,
            "content": text,
            "word_count": len(text),
            "topic": topic["title"],
            "platform": worker_type,
            "proofread_score": proofread_score,
            "critique_scores": critique_scores,
            "title_candidates": title_candidates,
            "source_url": source_url,
            "images": images,
        })
    except Exception as e:
        logger.warning(f"ArticleDraft validation failed: {e}")
        return None


# ── Output Writing ────────────────────────────────────────────────────

def write_output(
    text: str,
    final_title: str,
    topic: dict,
    source_url: str,
    proofread_score: int,
    critique_scores: list[int],
    title_candidates: list[dict],
    images: list[str],
    worker_type: str,
    run_timestamp: str,
    extra_meta: Optional[dict] = None,
    videos: Optional[list[str]] = None,
    video_prompts: Optional[list[str]] = None,
    logger=None,
) -> tuple[Path, Path]:
    """Write final article + meta to REVIEW_DIR.

    Returns:
        (article_path, meta_path)
    """
    article_path = REVIEW_DIR / f"{run_timestamp}-{worker_type}.md"
    meta_path = REVIEW_DIR / f"{run_timestamp}-{worker_type}.meta.json"

    try:
        article_path.write_text(f"# {final_title}\n\n{text}", encoding="utf-8")
    except OSError as e:
        if logger:
            logger.error(f"Failed to write article {article_path}: {e}")
        raise

    title_score = title_candidates[0]["score"] if title_candidates else 0
    meta = {
        "topic": topic["title"],
        "source_url": source_url,
        "platform_standard": worker_type,
        "proofread_score": proofread_score,
        "critique_scores": critique_scores,
        "revised_rounds": len(critique_scores),
        "title_score": title_score,
        "title_candidates": title_candidates,
        "word_count": len(text),
        "images": images,
        "image_generation_method": "agnes",
        "videos": videos or [],
        "video_prompts": video_prompts or [],
        "video_generation_method": "agnes" if videos else "",
        "status": "completed",
    }
    if extra_meta:
        meta.update(extra_meta)
    try:
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    except OSError as e:
        if logger:
            logger.error(f"Failed to write meta {meta_path}: {e}")
        raise

    validate_article_draft(
        final_title, text, topic, source_url,
        proofread_score, critique_scores, title_candidates, images,
        worker_type, logger,
    )
    return article_path, meta_path


# ── Pipeline Execution (Stages 3-7) ──────────────────────────────────

def execute_pipeline(
    topic: dict,
    source_material: str,
    proofread_fn,
    critique_loop_fn,
    format_fn,
    generate_titles_fn,
    illustrate_fn,
    generate_video_fn,
    write_status_fn,
    start_stage_fn,
    end_stage_fn,
    logger,
) -> tuple:
    """Execute stages 3-7 of the writer pipeline.

    Returns:
        (text, proofread_score, critique_scores, final_title, title_candidates, images, videos, video_prompts)
    """
    # Stage 3: Proofread
    write_status_fn("AI腔审校", 35, "检测并移除AI腔")
    text, proofread_score = proofread_fn(source_material)
    logger.info(f"Stage 3 done. Proofread score: {proofread_score}")

    # Stage 4: Critique & rewrite loop
    write_status_fn("批评修订", 50, "评委评分中")
    text, critique_scores = critique_loop_fn(text, topic["title"])

    # Stage 5: Format
    write_status_fn("排版", 75, "格式化排版")
    start_stage_fn("format")
    text = format_fn(text)
    end_stage_fn("format")
    logger.info("Stage 5 done. Formatted.")

    # Stage 6: Titles
    write_status_fn("标题优化", 85, "生成候选标题")
    start_stage_fn("titles")
    final_title, title_candidates = generate_titles_fn(text, topic["title"])
    end_stage_fn("titles")
    logger.info(f"Stage 6 done. Best title: {final_title}")

    # Stage 7: Illustrations
    write_status_fn("配图", 92, "生成配图")
    start_stage_fn("illustrate")
    images = illustrate_fn(text, topic["title"])
    end_stage_fn("illustrate")
    logger.info(f"Stage 7 done. Images: {len(images)}")

    # Stage 7b: Video generation (optional)
    video_path = generate_video_fn(text, topic["title"])
    videos = [video_path] if video_path else []
    video_prompts = []
    if videos:
        logger.info(f"Stage 7b done. Videos: {len(videos)}")

    return text, proofread_score, critique_scores, final_title, title_candidates, images, videos, video_prompts
