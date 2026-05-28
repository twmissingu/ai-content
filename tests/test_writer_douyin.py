"""Unit tests for skills/writer_douyin.py — Douyin video script writer."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── _generate_script ─────────────────────────────────────────────────
class TestGenerateScript:
    """Test Douyin script generation."""

    @patch("skills.writer_douyin.chat_structured")
    def test_returns_valid_structure(self, mock_chat):
        from skills.writer_douyin import _generate_script

        mock_chat.return_value = {
            "hook": "你知道吗？90%的人不知道这个功能",
            "script": [
                {"time_sec": 0, "text": "开场白", "visual": "特写镜头", "duration": 3, "mood": "好奇"},
                {"time_sec": 3, "text": "核心内容", "visual": "屏幕录制", "duration": 10, "mood": "专业"},
            ],
            "cta": "点赞关注不迷路",
            "hashtags": ["#AI", "#科技"],
            "total_duration_sec": 30,
            "target_audience": "科技爱好者",
        }

        result = _generate_script({"title": "测试选题", "description": "描述"})

        assert "hook" in result
        assert "script" in result
        assert "cta" in result
        assert isinstance(result["script"], list)
        assert len(result["script"]) > 0

    @patch("skills.writer_douyin.chat_structured")
    def test_script_scenes_have_required_fields(self, mock_chat):
        from skills.writer_douyin import _generate_script

        mock_chat.return_value = {
            "hook": "开场",
            "script": [
                {"time_sec": 0, "text": "旁白", "visual": "画面", "duration": 5, "mood": "语气"}
            ],
            "cta": "结尾",
            "hashtags": [],
            "total_duration_sec": 5,
        }

        result = _generate_script({"title": "选题"})

        scene = result["script"][0]
        assert "time_sec" in scene
        assert "text" in scene
        assert "visual" in scene
        assert "duration" in scene

    @patch("skills.writer_douyin.chat_structured")
    def test_handles_missing_fields(self, mock_chat):
        from skills.writer_douyin import _generate_script

        mock_chat.return_value = {"hook": "开场"}

        result = _generate_script({"title": "选题"})

        # Should handle missing fields gracefully
        assert result.get("hook") == "开场"
        assert result.get("script", []) == []

    @patch("skills.writer_douyin.chat_structured")
    def test_passes_domain_context(self, mock_chat):
        from skills.writer_douyin import _generate_script

        mock_chat.return_value = {
            "hook": "开场",
            "script": [],
            "cta": "结尾",
        }

        _generate_script({"title": "AI写作", "description": "AI辅助写作"})

        call_kwargs = mock_chat.call_args
        user_prompt = call_kwargs.kwargs.get("user_prompt", "")
        assert "AI写作" in user_prompt

    @patch("skills.writer_douyin.chat_structured")
    def test_handles_missing_description(self, mock_chat):
        """Should handle topic without description."""
        from skills.writer_douyin import _generate_script

        mock_chat.return_value = {"hook": "test", "script": [], "cta": "test"}

        result = _generate_script({"title": "测试"})
        assert result is not None

    @patch("skills.writer_douyin.chat_structured")
    def test_system_prompt_contains_douyin(self, mock_chat):
        """System prompt should mention Douyin."""
        from skills.writer_douyin import _generate_script

        mock_chat.return_value = {"hook": "test", "script": [], "cta": "test"}

        _generate_script({"title": "测试"})

        call_kwargs = mock_chat.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt", "")
        assert "抖音" in system_prompt


# ── Constants ────────────────────────────────────────────────────────
class TestConstants:
    """Test module constants."""

    def test_type_constant(self):
        from skills.writer_douyin import TYPE
        assert TYPE == "douyin"

    def test_run_timestamp_format(self):
        from skills.writer_douyin import RUN_TIMESTAMP
        assert len(RUN_TIMESTAMP) == 15
        assert RUN_TIMESTAMP[8] == "_"


# ── _parse_args ──────────────────────────────────────────────────────
class TestParseArgs:
    """Tests for _parse_args function."""

    def test_parses_topic_file_and_work_dir(self, tmp_path):
        """Should parse --topic-file and --work-dir arguments."""
        topic_file = tmp_path / "topic.json"
        topic_file.write_text(json.dumps({"title": "测试"}))
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        with patch("skills.writer_douyin.sys", MagicMock(argv=[
            "writer_douyin.py",
            "--topic-file", str(topic_file),
            "--work-dir", str(work_dir),
        ])):
            from skills.writer_douyin import _parse_args
            topic, wd = _parse_args()

        assert topic["title"] == "测试"
        assert wd == work_dir

    def test_raises_when_no_args_and_no_topics(self, tmp_path):
        """Should raise SystemExit when no args and no pending topics."""
        import skills.writer_douyin
        import config.settings
        original_pending = config.settings.PENDING_DIR
        config.settings.PENDING_DIR = tmp_path
        try:
            with patch.object(skills.writer_douyin, "sys", MagicMock(argv=["writer_douyin.py"])):
                from skills.writer_douyin import _parse_args
                with pytest.raises(SystemExit):
                    _parse_args()
        finally:
            config.settings.PENDING_DIR = original_pending


# ── main ─────────────────────────────────────────────────────────────
class TestMain:
    """Tests for main function."""

    def test_generates_output_files(self, tmp_path):
        """Should generate .md and .meta.json files."""
        topic_file = tmp_path / "topic.json"
        topic_file.write_text(json.dumps({"title": "测试选题", "description": "描述"}))
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        mock_script = {
            "hook": "测试Hook",
            "script": [
                {"time_sec": 0, "text": "开场", "visual": "画面", "duration": 3, "mood": "好奇"},
            ],
            "cta": "关注我",
            "hashtags": ["#test"],
            "total_duration_sec": 15,
        }

        with patch("skills.writer_douyin.sys", MagicMock(argv=[
            "writer_douyin.py",
            "--topic-file", str(topic_file),
            "--work-dir", str(work_dir),
        ])):
            with patch("skills.writer_douyin.chat_structured", return_value=mock_script):
                from skills.writer_douyin import main
                main()

        md_files = list(work_dir.glob("*.md"))
        meta_files = list(work_dir.glob("*.meta.json"))

        assert len(md_files) == 1
        assert len(meta_files) == 1

        meta = json.loads(meta_files[0].read_text())
        assert meta["topic"] == "测试选题"
        assert meta["platform_standard"] == "douyin"
        assert meta["status"] == "completed"

    def test_markdown_contains_hook_and_cta(self, tmp_path):
        """Generated markdown should contain hook and CTA."""
        topic_file = tmp_path / "topic.json"
        topic_file.write_text(json.dumps({"title": "测试选题"}))
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        mock_script = {
            "hook": "测试Hook标题",
            "script": [
                {"time_sec": 0, "text": "开场白", "visual": "画面", "duration": 3, "mood": "好奇"},
            ],
            "cta": "关注我获取更多",
            "hashtags": ["#test"],
            "total_duration_sec": 15,
        }

        with patch("skills.writer_douyin.sys", MagicMock(argv=[
            "writer_douyin.py",
            "--topic-file", str(topic_file),
            "--work-dir", str(work_dir),
        ])):
            with patch("skills.writer_douyin.chat_structured", return_value=mock_script):
                from skills.writer_douyin import main
                main()

        md_file = list(work_dir.glob("*.md"))[0]
        content = md_file.read_text()

        assert "测试Hook标题" in content
        assert "关注我获取更多" in content
        assert "开场白" in content
