"""Tests for writer_video module — Agnes AI video generation."""

import json
import os
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import patch, MagicMock

import pytest

from skills.writer_video import (
    _load_video_count,
    generate_video_prompt,
    generate_video_agnes,
    generate_video,
)


class TestLoadVideoCount:
    """Test _load_video_count()."""

    def test_returns_zero_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path / "nonexistent")
        assert _load_video_count("douyin") == 0

    def test_returns_count_for_platform(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        styles = {
            "douyin_default": {"videos": 1},
            "wechat_default": {"videos": 0},
        }
        (tmp_path / "writing_styles.json").write_text(json.dumps(styles))
        assert _load_video_count("douyin") == 1
        assert _load_video_count("wechat") == 0

    def test_returns_zero_for_unknown_platform(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        styles = {"douyin_default": {"videos": 1}}
        (tmp_path / "writing_styles.json").write_text(json.dumps(styles))
        assert _load_video_count("unknown_platform") == 0

    def test_returns_zero_on_json_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text("not json{")
        assert _load_video_count("douyin") == 0


class TestGenerateVideoPrompt:
    """Test generate_video_prompt()."""

    def test_returns_prompt_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "image_styles.json").write_text(json.dumps({
            "tutorial": {"style": "flat illustration, minimal"},
        }))

        mock_result = {"video_prompt": "A smooth animation of code on screen"}
        with patch("skills.llm.chat_structured", return_value=mock_result), \
             patch("skills.common.load_prompt", return_value="generate a video"):
            prompt = generate_video_prompt(
                "article text", "AI Tools", "douyin", "tutorial", 5,
            )

        assert prompt == "A smooth animation of code on screen"

    def test_returns_empty_on_llm_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "image_styles.json").write_text("{}")

        from skills.llm import LLMError
        with patch("skills.llm.chat_structured", side_effect=LLMError("fail")), \
             patch("skills.common.load_prompt", return_value="generate a video"):
            prompt = generate_video_prompt(
                "article text", "AI Tools", "douyin", "tutorial", 5,
            )

        assert prompt == ""

    def test_returns_empty_on_empty_result(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "image_styles.json").write_text("{}")

        with patch("skills.llm.chat_structured", return_value={}), \
             patch("skills.common.load_prompt", return_value="generate a video"):
            prompt = generate_video_prompt(
                "article text", "AI Tools", "douyin", "tutorial", 5,
            )

        assert prompt == ""


class TestGenerateVideoAgnes:
    """Test generate_video_agnes()."""

    def test_returns_path_on_success(self, tmp_path):
        """Verify Agnes script is called and path returned on success."""
        mock_script = tmp_path / "video_gen.py"
        mock_script.write_text("# mock")

        output_file = tmp_path / "video_1.mp4"
        # Simulate Agnes creating the output file
        def fake_run(*args, **kwargs):
            output_file.write_bytes(b"\x00" * 2000)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("skills.writer_video.Path") as mock_path_cls, \
             patch("skills.writer_video.subprocess.run", side_effect=fake_run):
            mock_path_cls.return_value = mock_script
            mock_path_cls.home.return_value = tmp_path
            # Re-point the script path resolution
            import os
            with patch.dict(os.environ, {"AGNES_SCRIPT_PATH": str(mock_script)}):
                result = generate_video_agnes(
                    "A test video prompt", tmp_path, 5,
                )

        assert result is not None
        assert "video_1.mp4" in result

    def test_returns_none_when_script_not_found(self, tmp_path):
        """Verify returns None when Agnes script doesn't exist."""
        with patch.dict(os.environ, {"AGNES_SCRIPT_PATH": str(tmp_path / "nonexistent.py")}):
            result = generate_video_agnes("prompt", tmp_path, 5)

        assert result is None

    def test_returns_none_on_timeout(self, tmp_path):
        """Verify graceful handling of timeout."""
        mock_script = tmp_path / "video_gen.py"
        mock_script.write_text("# mock")

        with patch.dict(os.environ, {"AGNES_SCRIPT_PATH": str(mock_script)}), \
             patch("skills.writer_video.subprocess.run", side_effect=TimeoutExpired("cmd", 900)):
            result = generate_video_agnes("prompt", tmp_path, 5)

        assert result is None

    def test_returns_none_on_nonzero_exit(self, tmp_path):
        """Verify returns None when script exits with error."""
        mock_script = tmp_path / "video_gen.py"
        mock_script.write_text("# mock")

        with patch.dict(os.environ, {"AGNES_SCRIPT_PATH": str(mock_script)}), \
             patch("skills.writer_video.subprocess.run",
                   return_value=MagicMock(returncode=1, stderr="API error")):
            result = generate_video_agnes("prompt", tmp_path, 5)

        assert result is None


class TestGenerateVideo:
    """Test generate_video() full pipeline."""

    def test_returns_video_path_on_success(self, tmp_path, monkeypatch):
        """Verify full pipeline: prompt → video."""
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text(json.dumps({
            "douyin_default": {"videos": 1},
        }))

        video_path = str(tmp_path / "video_1.mp4")

        with patch("skills.writer_video.generate_video_prompt",
                   return_value="A cool video prompt"), \
             patch("skills.writer_video.generate_video_agnes",
                   return_value=video_path):
            result = generate_video(
                "article text", "AI Tools", tmp_path, "20260101",
                worker_type="douyin",
            )

        assert result == video_path

    def test_returns_none_when_count_zero(self, tmp_path, monkeypatch):
        """Verify video generation is skipped when count is 0."""
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text(json.dumps({
            "wechat_default": {"videos": 0},
        }))

        result = generate_video(
            "article text", "AI Tools", tmp_path, "20260101",
            worker_type="wechat",
        )

        assert result is None

    def test_returns_none_when_prompt_empty(self, tmp_path, monkeypatch):
        """Verify returns None when LLM prompt generation fails."""
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text(json.dumps({
            "douyin_default": {"videos": 1},
        }))

        with patch("skills.writer_video.generate_video_prompt", return_value=""):
            result = generate_video(
                "article text", "AI Tools", tmp_path, "20260101",
                worker_type="douyin",
            )

        assert result is None

    def test_returns_none_when_agnes_fails(self, tmp_path, monkeypatch):
        """Verify returns None when Agnes video generation fails."""
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text(json.dumps({
            "douyin_default": {"videos": 1},
        }))

        with patch("skills.writer_video.generate_video_prompt",
                   return_value="A video prompt"), \
             patch("skills.writer_video.generate_video_agnes",
                   return_value=None):
            result = generate_video(
                "article text", "AI Tools", tmp_path, "20260101",
                worker_type="douyin",
            )

        assert result is None
