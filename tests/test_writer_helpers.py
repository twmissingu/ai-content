"""Unit tests for writer_helpers module.

Tests the extracted helper functions: parse_cli_args, run_critique_loop,
validate_article_draft, write_output, execute_pipeline.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestParseCliArgs:
    """Tests for parse_cli_args function."""

    def test_returns_defaults_when_no_args(self, monkeypatch):
        """Returns defaults when no CLI args present."""
        from skills.writer_helpers import parse_cli_args
        monkeypatch.setattr("sys.argv", ["writer.py"])
        topic_id, rewrite_mode, rewrite_target, rerun_from, topic_file, work_dir = \
            parse_cli_args(None, False, None)
        assert topic_id is None
        assert rewrite_mode is False
        assert rewrite_target is None
        assert rerun_from is None
        assert topic_file is None
        assert work_dir is None

    def test_parses_topic_id_from_argv(self, monkeypatch):
        """Parses topic_id from argv[1]."""
        from skills.writer_helpers import parse_cli_args
        monkeypatch.setattr("sys.argv", ["writer.py", "my-topic-123"])
        topic_id, _, _, _, _, _ = parse_cli_args(None, False, None)
        assert topic_id == "my-topic-123"

    def test_rewrite_mode_enables_rewrite_target(self, monkeypatch):
        """Rewrite mode sets rewrite_target to topic_id."""
        from skills.writer_helpers import parse_cli_args
        monkeypatch.setattr("sys.argv", ["writer.py", "topic-abc", "--rewrite"])
        topic_id, rewrite_mode, rewrite_target, _, _, _ = parse_cli_args(None, False, None)
        assert rewrite_mode is True
        assert rewrite_target == "topic-abc"

    def test_rerun_from_arg(self, monkeypatch):
        """Parses --rerun-from argument."""
        from skills.writer_helpers import parse_cli_args
        monkeypatch.setattr("sys.argv", ["writer.py", "--rerun-from", "3"])
        _, _, _, rerun_from, _, _ = parse_cli_args(None, False, None)
        assert rerun_from == 3

    def test_topic_file_arg(self, monkeypatch):
        """Parses --topic-file argument."""
        from skills.writer_helpers import parse_cli_args
        monkeypatch.setattr("sys.argv", ["writer.py", "--topic-file", "/tmp/topic.json"])
        _, _, _, _, topic_file, _ = parse_cli_args(None, False, None)
        assert topic_file == Path("/tmp/topic.json")

    def test_explicit_topic_id_preserved(self, monkeypatch):
        """Explicit topic_id is preserved over argv."""
        from skills.writer_helpers import parse_cli_args
        monkeypatch.setattr("sys.argv", ["writer.py", "other-topic"])
        topic_id, _, _, _, _, _ = parse_cli_args("explicit-id", False, None)
        assert topic_id == "explicit-id"


class TestRunCritiqueLoop:
    """Tests for run_critique_loop function."""

    def test_passes_immediately(self):
        """Stops when first round passes."""
        from skills.writer_helpers import run_critique_loop
        critique_fn = MagicMock(return_value=("improved text", 85, True))
        write_status = MagicMock()
        start_stage = MagicMock()
        end_stage = MagicMock()
        logger = MagicMock()
        gates = {"max_rewrite_rounds": 3}

        text, scores = run_critique_loop(
            "original", "title", gates, critique_fn,
            write_status, start_stage, end_stage, logger,
        )
        assert text == "improved text"
        assert scores == [85]
        critique_fn.assert_called_once()

    def test_retries_until_pass(self):
        """Retries until pass or max rounds."""
        from skills.writer_helpers import run_critique_loop
        critique_fn = MagicMock(side_effect=[
            ("v1", 50, False),
            ("v2", 65, False),
            ("v3", 80, True),
        ])
        write_status = MagicMock()
        start_stage = MagicMock()
        end_stage = MagicMock()
        logger = MagicMock()
        gates = {"max_rewrite_rounds": 3}

        text, scores = run_critique_loop(
            "original", "title", gates, critique_fn,
            write_status, start_stage, end_stage, logger,
        )
        assert text == "v3"
        assert scores == [50, 65, 80]
        assert critique_fn.call_count == 3

    def test_stops_at_max_rounds(self):
        """Stops at max rounds even if not passed."""
        from skills.writer_helpers import run_critique_loop
        critique_fn = MagicMock(return_value=("v1", 40, False))
        write_status = MagicMock()
        start_stage = MagicMock()
        end_stage = MagicMock()
        logger = MagicMock()
        gates = {"max_rewrite_rounds": 2}

        text, scores = run_critique_loop(
            "original", "title", gates, critique_fn,
            write_status, start_stage, end_stage, logger,
        )
        assert len(scores) == 2
        assert critique_fn.call_count == 2


class TestValidateArticleDraft:
    """Tests for validate_article_draft function."""

    def test_valid_draft(self):
        """Returns ArticleDraft for valid input."""
        from skills.writer_helpers import validate_article_draft
        logger = MagicMock()
        result = validate_article_draft(
            title="Test Title",
            text="Test content here",
            topic={"title": "Topic"},
            source_url="https://example.com",
            proofread_score=85,
            critique_scores=[80, 85],
            title_candidates=[{"title": "Test Title", "score": 90}],
            images=["img1.jpg"],
            worker_type="wechat",
            logger=logger,
        )
        assert result is not None
        assert result.title == "Test Title"
        assert result.platform == "wechat"

    def test_invalid_draft_returns_none(self):
        """Returns None for invalid input."""
        from skills.writer_helpers import validate_article_draft
        logger = MagicMock()
        result = validate_article_draft(
            title=123,  # invalid: should be string
            text="content",
            topic={"title": "t"},
            source_url="",
            proofread_score=80,
            critique_scores=[],
            title_candidates=[],
            images=[],
            worker_type="wechat",
            logger=logger,
        )
        assert result is None
        logger.warning.assert_called_once()


class TestWriteOutput:
    """Tests for write_output function."""

    def test_creates_files(self, tmp_path):
        """Creates article and meta files."""
        from skills.writer_helpers import write_output
        import config.settings
        original_review = config.settings.REVIEW_DIR
        config.settings.REVIEW_DIR = tmp_path
        try:
            article_path, meta_path = write_output(
                text="Test article content",
                final_title="Test Title",
                topic={"title": "Topic"},
                source_url="https://example.com",
                proofread_score=85,
                critique_scores=[80, 85],
                title_candidates=[{"title": "Test Title", "score": 90}],
                images=["img1.jpg"],
                worker_type="wechat",
                run_timestamp="20260606_120000",
                logger=MagicMock(),
            )
            assert article_path.exists()
            assert meta_path.exists()
            assert "# Test Title" in article_path.read_text()
            meta = json.loads(meta_path.read_text())
            assert meta["status"] == "completed"
            assert meta["word_count"] > 0
        finally:
            config.settings.REVIEW_DIR = original_review

    def test_includes_extra_meta(self, tmp_path):
        """Merges extra_meta into output."""
        from skills.writer_helpers import write_output
        import config.settings
        original_review = config.settings.REVIEW_DIR
        config.settings.REVIEW_DIR = tmp_path
        try:
            _, meta_path = write_output(
                text="content",
                final_title="Title",
                topic={"title": "T"},
                source_url="",
                proofread_score=70,
                critique_scores=[],
                title_candidates=[],
                images=[],
                worker_type="wechat",
                run_timestamp="20260606_120000",
                extra_meta={"rerun_from": 3},
                logger=MagicMock(),
            )
            meta = json.loads(meta_path.read_text())
            assert meta["rerun_from"] == 3
        finally:
            config.settings.REVIEW_DIR = original_review


class TestExecutePipeline:
    """Tests for execute_pipeline function."""

    def test_calls_all_stages(self):
        """Calls stages 3-7 in order."""
        from skills.writer_helpers import execute_pipeline
        topic = {"title": "Test Topic"}
        source_material = "Source content"

        proofread_fn = MagicMock(return_value=("proofread text", 85))
        critique_loop_fn = MagicMock(return_value=("critiqued text", [80, 85]))
        format_fn = MagicMock(return_value="formatted text")
        generate_titles_fn = MagicMock(return_value=("Best Title", [{"title": "Best Title", "score": 90}]))
        illustrate_fn = MagicMock(return_value=["img1.jpg"])
        generate_video_fn = MagicMock(return_value=None)
        write_status = MagicMock()
        start_stage = MagicMock()
        end_stage = MagicMock()
        logger = MagicMock()

        result = execute_pipeline(
            topic, source_material,
            proofread_fn, critique_loop_fn, format_fn,
            generate_titles_fn, illustrate_fn, generate_video_fn,
            write_status, start_stage, end_stage, logger,
        )

        text, proofread_score, critique_scores, final_title, title_candidates, images, videos, video_prompts = result
        assert text == "formatted text"
        assert proofread_score == 85
        assert critique_scores == [80, 85]
        assert final_title == "Best Title"
        assert images == ["img1.jpg"]
        assert videos == []
        proofread_fn.assert_called_once_with(source_material)
        critique_loop_fn.assert_called_once_with("proofread text", "Test Topic")
        format_fn.assert_called_once_with("critiqued text")
        generate_titles_fn.assert_called_once_with("formatted text", "Test Topic")
        illustrate_fn.assert_called_once()

    def test_includes_video_when_generated(self):
        """Includes video when generate_video returns a path."""
        from skills.writer_helpers import execute_pipeline
        result = execute_pipeline(
            {"title": "T"}, "src",
            MagicMock(return_value=("t", 80)),
            MagicMock(return_value=("t", [80])),
            MagicMock(return_value="t"),
            MagicMock(return_value=("T", [])),
            MagicMock(return_value=[]),
            MagicMock(return_value="/path/video.mp4"),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(),
        )
        _, _, _, _, _, _, videos, _ = result
        assert videos == ["/path/video.mp4"]
