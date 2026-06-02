"""Tests for TTS module — MiMo-V2.5-TTS 语音合成。"""

import base64
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from skills.tts import (
    VOICES,
    STYLE_MAP,
    TTSError,
    synthesize_speech,
)


class TestVoices:
    """Test voice constants."""

    def test_default_voice_exists(self):
        assert "default" in VOICES
        assert VOICES["default"] == "mimo_default"

    def test_chinese_voices_exist(self):
        for name in ["冰糖", "茉莉", "苏打", "白桦"]:
            assert name in VOICES

    def test_english_voices_exist(self):
        for name in ["Mia", "Chloe", "Milo"]:
            assert name in VOICES


class TestStyleMap:
    """Test content type style mappings."""

    def test_all_content_types_have_styles(self):
        expected = ["news", "tutorial", "tool_update", "tech_science",
                    "insight", "opinion", "sharing", "roundup"]
        for ct in expected:
            assert ct in STYLE_MAP
            assert len(STYLE_MAP[ct]) > 10

    def test_styles_are_chinese(self):
        for ct, style in STYLE_MAP.items():
            assert any('一' <= c <= '鿿' for c in style), \
                f"Style for {ct} should contain Chinese characters"


class TestSynthesizeSpeech:
    """Test synthesize_speech function."""

    @pytest.fixture(autouse=True)
    def mock_api_key(self, monkeypatch):
        """Provide a fake API key for all tests."""
        monkeypatch.setattr("skills.tts.LLM_API_KEY", "sk-test-fake-key")
        monkeypatch.setattr("skills.tts.LLM_BASE_URL", "https://api.xiaomimimo.com/v1")

    def test_returns_path_on_success(self, tmp_path):
        """Verify successful TTS returns output path."""
        fake_audio = b"RIFF" + b"\x00" * 100  # Fake WAV header
        fake_b64 = base64.b64encode(fake_audio).decode()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "audio": {"data": fake_b64}
                }
            }]
        }

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = synthesize_speech(
                "测试文本", output, content_type="news",
            )

        assert result == str(output)
        assert output.exists()
        assert output.read_bytes() == fake_audio

    def test_uses_style_instruction_for_content_type(self, tmp_path):
        """Verify content_type maps to correct style instruction."""
        fake_b64 = base64.b64encode(b"RIFF\x00\x00").decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"audio": {"data": fake_b64}}}]
        }

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            synthesize_speech("测试", output, content_type="news")

            # Verify the request body
            call_args = mock_client.post.call_args
            body = call_args.kwargs.get("json") or call_args[1].get("json")
            messages = body["messages"]

            # Should have user message with style + assistant message with text
            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert "新闻播报" in messages[0]["content"]
            assert messages[1]["role"] == "assistant"
            assert messages[1]["content"] == "测试"

    def test_skips_user_message_when_no_style(self, tmp_path):
        """Verify no user message when style_instruction and content_type are None."""
        fake_b64 = base64.b64encode(b"RIFF\x00\x00").decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"audio": {"data": fake_b64}}}]
        }

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            synthesize_speech("测试", output)

            call_args = mock_client.post.call_args
            body = call_args.kwargs.get("json") or call_args[1].get("json")
            messages = body["messages"]

            # Only assistant message, no user message
            assert len(messages) == 1
            assert messages[0]["role"] == "assistant"

    def test_uses_custom_style_instruction_over_content_type(self, tmp_path):
        """Verify explicit style_instruction overrides content_type default."""
        fake_b64 = base64.b64encode(b"RIFF\x00\x00").decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"audio": {"data": fake_b64}}}]
        }

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            synthesize_speech(
                "测试", output,
                style_instruction="用激动的语气",
                content_type="news",
            )

            call_args = mock_client.post.call_args
            body = call_args.kwargs.get("json") or call_args[1].get("json")
            messages = body["messages"]

            # Custom style should override content_type
            assert messages[0]["content"] == "用激动的语气"

    def test_sets_correct_voice_in_request(self, tmp_path):
        """Verify voice ID is correctly set in audio config."""
        fake_b64 = base64.b64encode(b"RIFF\x00\x00").decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"audio": {"data": fake_b64}}}]
        }

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            synthesize_speech("测试", output, voice="苏打")

            call_args = mock_client.post.call_args
            body = call_args.kwargs.get("json") or call_args[1].get("json")
            assert body["audio"]["voice"] == "苏打"

    def test_returns_none_on_http_error(self, tmp_path):
        """Verify returns None on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.raise_for_status.side_effect = Exception("400")

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = synthesize_speech("测试", output)

        assert result is None

    def test_returns_none_on_empty_audio(self, tmp_path):
        """Verify returns None when API returns no audio data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"audio": {}}}]
        }

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = synthesize_speech("测试", output)

        assert result is None

    def test_uses_correct_api_endpoint(self, tmp_path):
        """Verify the correct endpoint URL is called."""
        fake_b64 = base64.b64encode(b"RIFF\x00\x00").decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"audio": {"data": fake_b64}}}]
        }

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls, \
             patch("skills.tts.LLM_BASE_URL", "https://api.xiaomimimo.com/v1"):
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            synthesize_speech("测试", output)

            call_args = mock_client.post.call_args
            url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url")
            assert "chat/completions" in url

    def test_request_body_has_correct_model(self, tmp_path):
        """Verify model is set to mimo-v2.5-tts."""
        fake_b64 = base64.b64encode(b"RIFF\x00\x00").decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"audio": {"data": fake_b64}}}]
        }

        output = tmp_path / "test.wav"
        with patch("skills.tts.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            synthesize_speech("测试", output)

            call_args = mock_client.post.call_args
            body = call_args.kwargs.get("json") or call_args[1].get("json")
            assert body["model"] == "mimo-v2.5-tts"
