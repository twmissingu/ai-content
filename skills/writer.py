"""Writer Agent — 7-stage article production pipeline.

Phase 1: single Worker (wechat standard), sequential 7 stages.
Takes a confirmed topic from queue/pending/ or via CLI argument.
Outputs to queue/review/ with .md + .meta.json.

Uses AgentBase for unified status writing, logging, and metrics.
Stage logic delegated to writer_stages.py for testability.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

from config.settings import (
    ACTIONS_DIR,
    DOMAIN,
    IMAGES_DIR,
    PENDING_DIR,
    REVIEW_DIR,
    STATUS_DIR,
    VIDEOS_DIR,
)
from skills.agent_schemas import QualityGateResult
from skills.common import AgentBase, agent_main, load_prompt
from skills.writer_illustration import illustrate as _illustrate_fn
from skills.writer_video import generate_video as _generate_video_fn
from skills.writer_helpers import (
    parse_cli_args,
    run_critique_loop,
    validate_article_draft,
    write_output,
    execute_pipeline,
)
# Stage functions from decomposed writer_stages
from skills.writer_stages import (
    STAGES,
    TYPE,
    AI_SLOP_PATTERNS,
    load_quality_gates,
    load_ai_slop_patterns,
    sanitize_text,
    fetch_source,
    stage_draft,
    stage_proofread,
    stage_critique,
    stage_format,
    stage_titles,
)

# ── Re-export for backward compat (tests import from skills.writer) ──
_load_quality_gates = load_quality_gates


# ── Writer Agent ───────────────────────────────────────────────────
class WriterAgent(AgentBase):
    """Writer agent with 7-stage pipeline. Orchestrates staged functions."""

    name = "writer"
    version = "1.0.0"

    # Class-level cache shared with writer_stages — kept for test compat
    _AI_SLOP_PATTERNS = None

    def __init__(self, worker_type: str = "wechat"):
        # No session created here — dashboard background imports trace files
        super().__init__(enable_metrics=True, session_id=None)
        self.worker_type = worker_type
        self._status_path = STATUS_DIR / f"writer-worker-{worker_type}.json"
        self._run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._quality_gates = load_quality_gates()
        # Sync class-level cache reference
        WriterAgent._AI_SLOP_PATTERNS = AI_SLOP_PATTERNS

    def write_status(self, stage: str, progress_pct: int, detail: str,
                     error: Optional[str] = None, **extra) -> None:
        """Override to include worker type in status."""
        super().write_status(
            stage=stage,
            progress_pct=progress_pct,
            detail=detail,
            error=error,
            worker=self.worker_type,
            **extra
        )

    # ── Topic I/O ──────────────────────────────────────────────────

    def _read_topic(self, topic_id: Optional[str] = None) -> dict:
        """Read a topic from pending/ or from CLI arg."""
        if topic_id:
            path = PENDING_DIR / f"{topic_id}.json"
            if path.exists():
                return json.loads(path.read_text())
            # Maybe it's a topic_ prefix
            for f in PENDING_DIR.glob(f"topic_*{topic_id}*.json"):
                return json.loads(f.read_text())

        # Find the highest-scored unconfirmed topic
        files = sorted(PENDING_DIR.glob("topic_*.json"), key=os.path.getmtime, reverse=True)
        if not files:
            raise SystemExit("No topics found in queue/pending/")
        return json.loads(files[0].read_text())

    def _read_article_for_rewrite(self, target_id: str) -> tuple[str, dict, str]:
        """Read the original article + meta + reject reason for rewrite mode."""
        meta_path = REVIEW_DIR / f"{target_id}.meta.json"
        article_path = REVIEW_DIR / f"{target_id}.md"

        # Try alternate patterns
        if not meta_path.exists():
            for f in REVIEW_DIR.glob(f"*{target_id}*.meta.json"):
                meta_path = f
                article_path = REVIEW_DIR / f.stem.replace(".meta", "") + ".md"
                break

        if not meta_path.exists():
            self.logger.warning(f"Rewrite target not found: {target_id}")
            topic = self._read_topic(target_id)
            return "", topic, ""

        meta = json.loads(meta_path.read_text())
        content = article_path.read_text(encoding="utf-8") if article_path.exists() else ""

        # Try to find the reject action for the reason
        reject_reason = ""
        for f in sorted(ACTIONS_DIR.glob(f"reject_*{target_id}*.json"),
                         key=os.path.getmtime, reverse=True):
            try:
                action_data = json.loads(f.read_text())
                reject_reason = action_data.get("reason", "") or ""
                if reject_reason:
                    break
            except (json.JSONDecodeError, OSError):
                pass

        return content, meta, reject_reason

    # ── Backward-compat wrappers (delegate to writer_stages) ───────

    def _sanitize_text(self, text: str, max_length: int = 500) -> str:
        """Sanitize text. Delegates to writer_stages.sanitize_text."""
        return sanitize_text(text, max_length)

    def _fetch_source(self, url: str) -> str:
        """Stage 1: Fetch source material from URL."""
        return fetch_source(url, self.logger)

    def _load_ai_slop_patterns(self) -> list[tuple[str, int]]:
        """Load AI-slop patterns and cache on the class."""
        WriterAgent._AI_SLOP_PATTERNS = load_ai_slop_patterns()
        return WriterAgent._AI_SLOP_PATTERNS

    def _draft(self, topic: dict, source_material: str) -> str:
        """Stage 2: Generate first draft via LLM (delegates to writer_stages)."""
        return stage_draft(topic, source_material, self.record_llm_call)

    def _proofread(self, text: str) -> tuple[str, int]:
        """Stage 3: Remove AI-slop patterns and score."""
        self.start_stage("proofread")

        if WriterAgent._AI_SLOP_PATTERNS is None:
            self._load_ai_slop_patterns()

        cleaned, score = stage_proofread(
            text, WriterAgent._AI_SLOP_PATTERNS,
            self._quality_gates,
            self.record_llm_call, self.logger,
        )

        self.end_stage("proofread")

        # Validate quality gate result
        try:
            QualityGateResult(
                gate_name="proofread",
                score=score,
                threshold=self._quality_gates["proofread_threshold"],
                passed=score >= self._quality_gates["proofread_threshold"],
            )
        except Exception as e:
            self.logger.warning(f"QualityGateResult validation failed: {e}")

        return cleaned, score

    def _critique(self, text: str, topic_title: str, round_num: int) -> tuple[str, int, bool]:
        """Stage 4 delegate: multi-perspective editorial board review."""
        return stage_critique(
            text, topic_title, round_num,
            self._quality_gates, self.record_llm_call,
        )

    def _format(self, text: str) -> str:
        """Stage 5: Formatting — spaces, paragraphs, hashtags."""
        return stage_format(text)

    def _generate_titles(self, text: str, topic_title: str) -> tuple[str, list[dict]]:
        """Stage 6: Generate 3 candidate titles, score each, pick best."""
        return stage_titles(
            text, topic_title,
            self._quality_gates, self.record_llm_call, self.logger,
        )

    def _illustrate(self, text: str, topic_title: str) -> list[str]:
        """Stage 7: Generate illustrations via Agnes AI."""
        return _illustrate_fn(
            text, topic_title, IMAGES_DIR, self._run_timestamp, DOMAIN, self.logger,
            worker_type=self.worker_type,
        )

    def _generate_video(self, text: str, topic_title: str) -> Optional[str]:
        """Stage 7b: Generate video via Agnes AI (optional)."""
        return _generate_video_fn(
            text, topic_title, VIDEOS_DIR, self._run_timestamp,
            logger=self.logger,
            worker_type=self.worker_type,
        )

    # ── CLI & helpers ──────────────────────────────────────────────

    def _run_critique_loop(self, text: str, topic_title: str) -> tuple[str, list[int]]:
        """Run the critique loop with rewriting. Returns (text, critique_scores)."""
        return run_critique_loop(
            text, topic_title, self._quality_gates,
            self._critique, self.write_status,
            self.start_stage, self.end_stage, self.logger,
        )

    def _write_output(self, text, final_title, topic, source_url,
                      proofread_score, critique_scores, title_candidates,
                      images, extra_meta=None, videos=None, video_prompts=None):
        """Write final article + meta to REVIEW_DIR. Returns (article_path, meta_path)."""
        self.write_status("完成", 95, "写入输出文件")
        return write_output(
            text, final_title, topic, source_url,
            proofread_score, critique_scores, title_candidates, images,
            self.worker_type, self._run_timestamp,
            extra_meta=extra_meta, videos=videos, video_prompts=video_prompts,
            logger=self.logger,
        )

    # ── Main pipeline ──────────────────────────────────────────────
    def run(self, topic_id: Optional[str] = None, rewrite_mode: bool = False,
            rerun_from: Optional[int] = None):
        """Main pipeline execution."""
        topic_id, rewrite_mode, rewrite_target, rerun_from_arg, topic_file_arg, work_dir_arg = \
            parse_cli_args(topic_id, rewrite_mode, rerun_from)

        _topic_from_file = None
        if topic_file_arg and topic_file_arg.exists():
            _topic_from_file = json.loads(topic_file_arg.read_text())

        # ── Mode: Re-run from specific stage ─────────────────────────
        if rerun_from_arg and 1 <= rerun_from_arg <= 7:
            self._run_from_stage(rerun_from_arg)
            return

        # ── Mode: Rewrite ──────────────────────────────────────────
        if rewrite_mode and rewrite_target:
            topic, source_material, source_url = self._prepare_rewrite(rewrite_target)

        # ── Mode: Normal from topic ────────────────────────────────
        else:
            topic, source_material, source_url = self._prepare_normal(
                _topic_from_file, topic_id
            )

        # Execute the 7-stage pipeline
        text, proofread_score, critique_scores, final_title, title_candidates, images, videos, video_prompts = \
            execute_pipeline(
                topic, source_material,
                proofread_fn=self._proofread,
                critique_loop_fn=self._run_critique_loop,
                format_fn=self._format,
                generate_titles_fn=self._generate_titles,
                illustrate_fn=self._illustrate,
                generate_video_fn=self._generate_video,
                write_status_fn=self.write_status,
                start_stage_fn=self.start_stage,
                end_stage_fn=self.end_stage,
                logger=self.logger,
            )

        # Write output
        article_path, meta_path = self._write_output(
            text, final_title, topic, source_url,
            proofread_score, critique_scores, title_candidates, images,
            videos=videos,
            video_prompts=video_prompts,
        )

        self.write_completed(
            detail=f"管线完成 · 评分{proofread_score}/{critique_scores[-1] if critique_scores else 0}",
            article=str(article_path),
            meta=str(meta_path),
        )

        self.logger.info(f"Pipeline complete!")
        self.logger.info(f"Article: {article_path}")
        self.logger.info(f"Meta: {meta_path}")

    def _run_from_stage(self, rerun_from_arg: int):
        """Re-run pipeline from a specific stage."""
        self.logger.info(f"Re-run mode: starting from stage {rerun_from_arg}")
        self.write_status("重跑", 0, f"从阶段 {rerun_from_arg} 重新执行")

        review_files = sorted(REVIEW_DIR.glob("*.md"), key=os.path.getmtime, reverse=True)
        if not review_files:
            self.logger.error("No articles in review/ to re-run")
            return

        article_path = review_files[0]
        meta_path = REVIEW_DIR / f"{article_path.stem}.meta.json"
        if not meta_path.exists():
            self.logger.error(f"Meta not found: {meta_path}")
            return

        meta = json.loads(meta_path.read_text())
        text = article_path.read_text(encoding="utf-8")
        if text.startswith("# "):
            text = text.split("\n", 1)[1].strip()

        topic = {"title": meta.get("topic", "Unknown"), "description": ""}
        source_url = meta.get("source_url", "")
        proofread_score = meta.get("proofread_score", 70)
        critique_scores = meta.get("critique_scores", [])
        title_candidates = meta.get("title_candidates", [])
        videos: list[str] = []
        video_prompts: list[str] = []
        final_title = meta.get("topic", "Unknown")
        images = meta.get("images", [])

        if rerun_from_arg <= 2:
            self.write_status("LLM初稿", 20, "重新生成初稿")
            self.start_stage("draft")
            source_material = self._fetch_source(source_url) if source_url else "无原文"
            text = self._draft(topic, source_material)
            self.end_stage("draft")

        if rerun_from_arg <= 3:
            self.write_status("AI腔审校", 35, "检测并移除AI腔")
            text, proofread_score = self._proofread(text)

        if rerun_from_arg <= 4:
            self.write_status("批评修订", 50, "评委评分中")
            text, critique_scores = self._run_critique_loop(text, topic["title"])

        if rerun_from_arg <= 5:
            self.write_status("排版", 75, "格式化排版")
            self.start_stage("format")
            text = self._format(text)
            self.end_stage("format")

        if rerun_from_arg <= 6:
            self.write_status("标题优化", 85, "生成候选标题")
            self.start_stage("titles")
            final_title, title_candidates = self._generate_titles(text, topic["title"])
            self.end_stage("titles")

        if rerun_from_arg <= 7:
            self.write_status("配图", 92, "生成配图")
            self.start_stage("illustrate")
            images = self._illustrate(text, topic["title"])
            self.end_stage("illustrate")

            # Stage 7b: Video generation (optional)
            video_path = self._generate_video(text, topic["title"])
            videos = [video_path] if video_path else []
            video_prompts = []

        article_path, meta_path = self._write_output(
            text, final_title, topic, source_url,
            proofread_score, critique_scores, title_candidates, images,
            extra_meta={"rerun_from": rerun_from_arg},
            videos=videos,
            video_prompts=video_prompts,
        )
        self.write_completed(
            detail=f"从阶段{rerun_from_arg}重跑完成 · 评分{proofread_score}/{critique_scores[-1] if critique_scores else 0}",
            article=str(article_path),
            meta=str(meta_path),
        )

    def _prepare_rewrite(self, rewrite_target: str) -> tuple[dict, str, str]:
        """Prepare topic and source material for rewrite mode."""
        self.logger.info(f"Rewrite mode: {rewrite_target}")
        self.write_status("初始化", 0, f"重写模式: {rewrite_target}")
        original_text, topic, reject_reason = self._read_article_for_rewrite(rewrite_target)
        if reject_reason:
            self.logger.info(f"Reject reason: {reject_reason}")
            topic["reject_reason"] = reject_reason

        topic_title = topic.get("topic") or topic.get("title", rewrite_target)
        source_url = topic.get("source_url", topic.get("url", ""))

        self.write_status("抓原文", 5, "读取原文素材")
        self.start_stage("fetch_source")
        if source_url and not original_text:
            source_material = self._fetch_source(source_url)
        else:
            source_material = original_text or "无原文素材"
        self.end_stage("fetch_source")

        self.write_status("LLM初稿", 20, "根据反馈重写")
        self.start_stage("draft")
        prompt_extra = ""
        if reject_reason:
            prompt_extra = f"\n\n驳回原因（必须针对性改进）: {reject_reason}"
        text = self._draft(
            {"title": topic_title, "description": topic.get("topic", "") + prompt_extra},
            source_material,
        )
        self.end_stage("draft")

        return topic, source_material, source_url

    def _prepare_normal(self, _topic_from_file: Optional[dict], topic_id: Optional[str]) -> tuple[dict, str, str]:
        """Prepare topic and source material for normal mode."""
        self.write_status("初始化", 0, "读取选题配置")
        topic = _topic_from_file if _topic_from_file else self._read_topic(topic_id)
        self.logger.info(f"Starting pipeline for: {topic['title']}")
        source_url = topic.get("url", "")

        self.write_status("抓原文", 5, "抓取原文素材")
        self.start_stage("fetch_source")
        if source_url:
            source_material = self._fetch_source(source_url)
        else:
            source_material = "无原文链接。将基于选题方向生成。"
        self.end_stage("fetch_source")
        self.logger.info(f"Stage 1 done. Source: {len(source_material)} chars")

        self.write_status("LLM初稿", 20, "生成初稿")
        self.start_stage("draft")
        text = self._draft(topic, source_material)
        self.end_stage("draft")
        self.logger.info(f"Stage 2 done. Draft: {len(text)} chars")

        return topic, source_material, source_url

def main():
    """Entry point for backward compatibility."""
    agent = WriterAgent()
    agent.run()


if __name__ == "__main__":
    main()
