"""Unit tests for skills/writer_xhs.py — Xiaohongshu writer worker."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── _generate_titles ─────────────────────────────────────────────────
class TestGenerateTitles:
    """Test Xiaohongshu title generation."""

    @patch("skills.writer_xhs.chat_structured")
    def test_returns_best_title(self, mock_chat):
        from skills.writer_xhs import _generate_titles

        mock_chat.return_value = {
            "candidates": [
                {"title": "标题A", "score": 80, "rationale": "好", "formula": "数字型"},
                {"title": "标题B", "score": 90, "rationale": "更好", "formula": "提问型"},
                {"title": "标题C", "score": 70, "rationale": "一般", "formula": "反差型"},
            ]
        }

        title, candidates = _generate_titles("文章内容", "原始选题")

        assert title == "标题B"
        assert len(candidates) == 3
        # Should be sorted by score descending
        assert candidates[0]["score"] >= candidates[1]["score"]

    @patch("skills.writer_xhs.chat_structured")
    def test_falls_back_to_topic_title(self, mock_chat):
        from skills.writer_xhs import _generate_titles

        mock_chat.return_value = {"candidates": []}

        title, candidates = _generate_titles("文章内容", "原始选题")

        assert title == "原始选题"
        assert candidates == []

    @patch("skills.writer_xhs.chat_structured")
    def test_handles_missing_score(self, mock_chat):
        from skills.writer_xhs import _generate_titles

        mock_chat.return_value = {
            "candidates": [
                {"title": "标题A", "rationale": "好"},  # missing score
                {"title": "标题B", "score": 85, "rationale": "好"},
            ]
        }

        title, candidates = _generate_titles("文章内容", "选题")

        # Should still work, missing score defaults to 0
        assert title == "标题B"

    @patch("skills.writer_xhs.chat_structured")
    def test_system_prompt_mentions_xiaohongshu(self, mock_chat):
        """System prompt should mention Xiaohongshu."""
        from skills.writer_xhs import _generate_titles

        mock_chat.return_value = {"candidates": []}

        _generate_titles("内容", "选题")

        call_kwargs = mock_chat.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt", "")
        assert "小红书" in system_prompt

    @patch("skills.writer_xhs.chat_structured")
    def test_user_prompt_contains_content_preview(self, mock_chat):
        """User prompt should contain beginning of content."""
        from skills.writer_xhs import _generate_titles

        mock_chat.return_value = {"candidates": []}
        long_content = "A" * 500

        _generate_titles(long_content, "选题")

        call_kwargs = mock_chat.call_args
        user_prompt = call_kwargs.kwargs.get("user_prompt", "")
        # Should contain first 300 chars of content
        assert "A" * 100 in user_prompt


# ── _draft ───────────────────────────────────────────────────────────
class TestDraft:
    """Test Xiaohongshu draft generation."""

    @patch("skills.writer_xhs.chat")
    def test_returns_string(self, mock_chat):
        from skills.writer_xhs import _draft

        mock_chat.return_value = "这是一篇小红书笔记的正文内容。"

        result = _draft({"title": "测试选题", "description": "描述"})

        assert isinstance(result, str)
        assert len(result) > 0
        mock_chat.assert_called_once()

    @patch("skills.writer_xhs.chat")
    def test_passes_topic_to_prompt(self, mock_chat):
        from skills.writer_xhs import _draft

        mock_chat.return_value = "笔记内容"

        _draft({"title": "AI工具推荐", "description": "最好用的AI工具"})

        call_kwargs = mock_chat.call_args
        assert "AI工具推荐" in call_kwargs.kwargs.get("user_prompt", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else "")

    @patch("skills.writer_xhs.chat")
    def test_handles_missing_description(self, mock_chat):
        from skills.writer_xhs import _draft

        mock_chat.return_value = "笔记内容"

        result = _draft({"title": "测试选题"})

        assert isinstance(result, str)

    @patch("skills.writer_xhs.chat")
    def test_system_prompt_mentions_xiaohongshu(self, mock_chat):
        """System prompt should mention Xiaohongshu."""
        from skills.writer_xhs import _draft

        mock_chat.return_value = "笔记内容"

        _draft({"title": "测试"})

        call_kwargs = mock_chat.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt", "")
        assert "小红书" in system_prompt

    @patch("skills.writer_xhs.chat")
    def test_user_prompt_contains_domain(self, mock_chat):
        """User prompt should contain domain context."""
        from skills.writer_xhs import _draft

        mock_chat.return_value = "笔记内容"

        _draft({"title": "测试"})

        call_kwargs = mock_chat.call_args
        user_prompt = call_kwargs.kwargs.get("user_prompt", "")
        # Should have domain-specific guidance
        assert len(user_prompt) > 100


# ── _parse_args ──────────────────────────────────────────────────────
class TestParseArgs:
    """Tests for _parse_args function."""

    def test_parses_topic_file_and_work_dir(self, tmp_path):
        """Should parse --topic-file and --work-dir arguments."""
        topic_file = tmp_path / "topic.json"
        topic_file.write_text(json.dumps({"title": "测试"}))
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        with patch("skills.writer_xhs.sys", MagicMock(argv=[
            "writer_xhs.py",
            "--topic-file", str(topic_file),
            "--work-dir", str(work_dir),
        ])):
            from skills.writer_xhs import _parse_args
            topic, wd = _parse_args()

        assert topic["title"] == "测试"
        assert wd == work_dir

    def test_raises_when_no_args_and_no_topics(self, tmp_path):
        """Should raise SystemExit when no args and no pending topics."""
        import skills.writer_xhs
        with patch.object(skills.writer_xhs, "sys", MagicMock(argv=["writer_xhs.py"])):
            with patch("config.settings.PENDING_DIR", tmp_path):
                from skills.writer_xhs import _parse_args
                with pytest.raises(SystemExit):
                    _parse_args()


# ── main ─────────────────────────────────────────────────────────────
class TestMain:
    """Tests for main function."""

    def test_generates_output_files(self, tmp_path):
        """Should generate .md and .meta.json files."""
        topic_file = tmp_path / "topic.json"
        topic_file.write_text(json.dumps({"title": "测试选题", "description": "描述"}))
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        mock_title_result = {
            "candidates": [
                {"title": "爆款标题", "score": 90, "rationale": "好", "formula": "数字型"},
            ]
        }

        with patch("skills.writer_xhs.sys", MagicMock(argv=[
            "writer_xhs.py",
            "--topic-file", str(topic_file),
            "--work-dir", str(work_dir),
        ])):
            with patch("skills.writer_xhs.chat", return_value="笔记正文内容"):
                with patch("skills.writer_xhs.chat_structured", return_value=mock_title_result):
                    from skills.writer_xhs import main
                    main()

        md_files = list(work_dir.glob("*.md"))
        meta_files = list(work_dir.glob("*.meta.json"))

        assert len(md_files) == 1
        assert len(meta_files) == 1

        meta = json.loads(meta_files[0].read_text())
        assert meta["topic"] == "测试选题"
        assert meta["platform_standard"] == "xiaohongshu"
        assert meta["status"] == "completed"

    def test_markdown_contains_title_and_content(self, tmp_path):
        """Generated markdown should contain title and content."""
        topic_file = tmp_path / "topic.json"
        topic_file.write_text(json.dumps({"title": "测试选题"}))
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        mock_title_result = {
            "candidates": [
                {"title": "爆款标题", "score": 90, "rationale": "好"},
            ]
        }

        with patch("skills.writer_xhs.sys", MagicMock(argv=[
            "writer_xhs.py",
            "--topic-file", str(topic_file),
            "--work-dir", str(work_dir),
        ])):
            with patch("skills.writer_xhs.chat", return_value="这是笔记正文"):
                with patch("skills.writer_xhs.chat_structured", return_value=mock_title_result):
                    from skills.writer_xhs import main
                    main()

        md_file = list(work_dir.glob("*.md"))[0]
        content = md_file.read_text()

        assert "爆款标题" in content
        assert "这是笔记正文" in content

    def test_meta_contains_title_candidates(self, tmp_path):
        """Meta file should contain title candidates."""
        topic_file = tmp_path / "topic.json"
        topic_file.write_text(json.dumps({"title": "测试选题"}))
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        mock_title_result = {
            "candidates": [
                {"title": "标题A", "score": 90, "rationale": "好"},
                {"title": "标题B", "score": 80, "rationale": "一般"},
            ]
        }

        with patch("skills.writer_xhs.sys", MagicMock(argv=[
            "writer_xhs.py",
            "--topic-file", str(topic_file),
            "--work-dir", str(work_dir),
        ])):
            with patch("skills.writer_xhs.chat", return_value="笔记内容"):
                with patch("skills.writer_xhs.chat_structured", return_value=mock_title_result):
                    from skills.writer_xhs import main
                    main()

        meta_file = list(work_dir.glob("*.meta.json"))[0]
        meta = json.loads(meta_file.read_text())

        assert "title_candidates" in meta
        assert len(meta["title_candidates"]) == 2
        assert meta["title_score"] == 90


# ── Output format ────────────────────────────────────────────────────
class TestOutputFormat:
    """Test that the module defines expected constants."""

    def test_type_constant(self):
        from skills.writer_xhs import TYPE
        assert TYPE == "xiaohongshu"

    def test_run_timestamp_format(self):
        from skills.writer_xhs import RUN_TIMESTAMP
        # Should be YYYYMMDD_HHMMSS format
        assert len(RUN_TIMESTAMP) == 15
        assert RUN_TIMESTAMP[8] == "_"
