"""Tests for writer_video module — 图文转视频管线 + Agnes AI 视频生成。"""

import json
import os
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import patch, MagicMock

import pytest

from skills.writer_video import (
    _load_video_count,
    split_article_into_segments,
    _get_audio_duration,
    generate_slideshow_video,
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
        styles = {"douyin_default": {"videos": 1}, "wechat_default": {"videos": 0}}
        (tmp_path / "writing_styles.json").write_text(json.dumps(styles))
        assert _load_video_count("douyin") == 1
        assert _load_video_count("wechat") == 0

    def test_returns_zero_for_unknown_platform(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        styles = {"douyin_default": {"videos": 1}}
        (tmp_path / "writing_styles.json").write_text(json.dumps(styles))
        assert _load_video_count("unknown") == 0

    def test_returns_zero_on_json_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text("not json{")
        assert _load_video_count("douyin") == 0


class TestSplitArticleIntoSegments:
    """Test split_article_into_segments()."""

    def test_returns_segments_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "image_styles.json").write_text(json.dumps({
            "tutorial": {"style": "flat illustration"},
        }))

        mock_result = {
            "segments": [
                {"tts_text": "开场白", "image_prompt": "opening scene"},
                {"tts_text": "正文", "image_prompt": "main content"},
                {"tts_text": "总结", "image_prompt": "conclusion"},
            ]
        }
        with patch("skills.llm.chat_structured", return_value=mock_result):
            segments = split_article_into_segments(
                "这是一篇测试文章", "测试标题", 3, "tutorial",
            )

        assert len(segments) == 3
        assert segments[0]["tts_text"] == "开场白"

    def test_returns_empty_on_llm_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "image_styles.json").write_text("{}")

        from skills.llm import LLMError
        with patch("skills.llm.chat_structured", side_effect=LLMError("fail")):
            segments = split_article_into_segments("text", "title", 3)

        assert segments == []

    def test_filters_invalid_segments(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "image_styles.json").write_text("{}")

        mock_result = {
            "segments": [
                {"tts_text": "ok", "image_prompt": "ok"},
                {"tts_text": "", "image_prompt": "missing text"},  # invalid
                {"image_prompt": "missing tts"},  # invalid
            ]
        }
        with patch("skills.llm.chat_structured", return_value=mock_result):
            segments = split_article_into_segments("text", "title", 3)

        assert len(segments) == 1  # only valid segment kept


class TestGetAudioDuration:
    """Test _get_audio_duration()."""

    def test_returns_duration_from_ffprobe(self, tmp_path):
        mock_audio = tmp_path / "test.wav"
        mock_audio.write_bytes(b"\x00" * 100)

        with patch("skills.writer_video.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="12.5\n", returncode=0)
            duration = _get_audio_duration(mock_audio)

        assert duration == 12.5

    def test_returns_fallback_on_error(self, tmp_path):
        mock_audio = tmp_path / "test.wav"
        mock_audio.write_bytes(b"\x00" * 100)

        with patch("skills.writer_video.subprocess.run", side_effect=OSError("fail")):
            duration = _get_audio_duration(mock_audio)

        assert duration == 5.0


class TestGenerateSlideshowVideo:
    """Test generate_slideshow_video()."""

    def test_returns_none_when_count_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text(json.dumps({
            "wechat_default": {"videos": 0},
        }))

        result = generate_slideshow_video(
            "text", "title", tmp_path, "20260101", worker_type="wechat",
        )
        assert result is None

    def test_returns_none_when_segmentation_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text(json.dumps({
            "douyin_default": {"videos": 1},
        }))
        (tmp_path / "image_styles.json").write_text("{}")

        with patch("skills.writer_video.split_article_into_segments", return_value=[]):
            result = generate_slideshow_video(
                "text", "title", tmp_path, "20260101", worker_type="douyin",
            )
        assert result is None


class TestGenerateVideo:
    """Test generate_video() entry point."""

    def test_uses_slideshow_pipeline_by_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text(json.dumps({
            "douyin_default": {"videos": 1},
        }))

        video_path = str(tmp_path / "20260101" / "video.mp4")

        with patch("skills.writer_video.generate_slideshow_video", return_value=video_path):
            result = generate_video(
                "text", "title", tmp_path, "20260101", worker_type="douyin",
            )

        assert result == video_path

    def test_falls_back_to_agnes_when_slideshow_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "writing_styles.json").write_text(json.dumps({
            "douyin_default": {"videos": 1},
        }))

        agnes_path = str(tmp_path / "20260101" / "video_1.mp4")

        with patch("skills.writer_video.generate_slideshow_video", return_value=None), \
             patch("skills.writer_video.generate_video_prompt", return_value="a prompt"), \
             patch("skills.writer_video.generate_video_agnes", return_value=agnes_path):
            result = generate_video(
                "text", "title", tmp_path, "20260101", worker_type="douyin",
            )

        assert result == agnes_path


class TestGenerateVideoPrompt:
    """Test generate_video_prompt()."""

    def test_returns_prompt_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "image_styles.json").write_text(json.dumps({
            "tutorial": {"style": "flat illustration"},
        }))

        mock_result = {"video_prompt": "A smooth animation"}
        with patch("skills.llm.chat_structured", return_value=mock_result), \
             patch("skills.common.load_prompt", return_value="generate"):
            prompt = generate_video_prompt("text", "title", "douyin", "tutorial", 5)

        assert prompt == "A smooth animation"

    def test_returns_empty_on_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.writer_video.CONFIG_DIR", tmp_path)
        (tmp_path / "image_styles.json").write_text("{}")

        from skills.llm import LLMError
        with patch("skills.llm.chat_structured", side_effect=LLMError("fail")), \
             patch("skills.common.load_prompt", return_value="generate"):
            prompt = generate_video_prompt("text", "title", "douyin", "tutorial", 5)

        assert prompt == ""


class TestGenerateVideoAgnes:
    """Test generate_video_agnes()."""

    def test_returns_path_on_success(self, tmp_path):
        mock_script = tmp_path / "video_gen.py"
        mock_script.write_text("# mock")
        output_file = tmp_path / "video_1.mp4"

        def fake_run(*args, **kwargs):
            output_file.write_bytes(b"\x00" * 2000)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch.dict(os.environ, {"AGNES_SCRIPT_PATH": str(mock_script)}), \
             patch("skills.writer_video.subprocess.run", side_effect=fake_run):
            result = generate_video_agnes("prompt", tmp_path, 5)

        assert result is not None

    def test_returns_none_when_script_not_found(self, tmp_path):
        with patch.dict(os.environ, {"AGNES_SCRIPT_PATH": str(tmp_path / "nope.py")}):
            result = generate_video_agnes("prompt", tmp_path, 5)
        assert result is None
