"""Unit tests for skills/llm.py — LLM utility module."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock
import threading


# ── Thread-local state ───────────────────────────────────────────────
class TestThreadLocalState:
    """Test agent name and model tracking."""

    def test_set_and_get_current_agent(self):
        from skills.llm import set_current_agent, get_current_agent

        set_current_agent("scout")
        assert get_current_agent() == "scout"

    def test_default_agent_is_unknown(self):
        from skills.llm import get_current_agent

        # Should return 'unknown' when not set (or from previous test)
        agent = get_current_agent()
        assert isinstance(agent, str)

    def test_get_last_model_returns_default(self):
        from skills.llm import get_last_model

        model = get_last_model()
        assert isinstance(model, str)
        assert len(model) > 0

    def test_thread_isolation(self):
        from skills.llm import set_current_agent, get_current_agent

        results = {}

        def worker(name):
            set_current_agent(name)
            import time
            time.sleep(0.01)
            results[name] = get_current_agent()

        threads = [threading.Thread(target=worker, args=(f"agent_{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for name in results:
            assert results[name] == name


# ── Fallback chain ───────────────────────────────────────────────────
class TestFallbackChain:
    """Test fallback chain loading."""

    def test_fallback_chain_is_list(self):
        from skills.llm import FALLBACK_CHAIN
        assert isinstance(FALLBACK_CHAIN, list)

    def test_fallback_chain_items_are_dicts(self):
        from skills.llm import FALLBACK_CHAIN
        for item in FALLBACK_CHAIN:
            assert isinstance(item, dict)


# ── chat() ───────────────────────────────────────────────────────────
class TestChat:
    """Test the chat function."""

    @patch("skills.llm._get_client")
    @patch("skills.llm._record_usage")
    def test_chat_returns_string(self, mock_record, mock_get_client):
        from skills.llm import chat

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = chat("system", "user", track_cost=False)

        assert result == "Hello world"

    @patch("skills.llm._get_client")
    def test_chat_strips_whitespace(self, mock_get_client):
        from skills.llm import chat

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "  padded response  "}}],
            "usage": {},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = chat("system", "user", track_cost=False)

        assert result == "padded response"

    @patch("skills.llm._get_client")
    def test_chat_raises_on_empty_choices(self, mock_get_client):
        from skills.llm import chat, LLMError

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": []}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        with pytest.raises(LLMError):
            chat("system", "user", track_cost=False)

    @patch("skills.llm._get_client")
    def test_chat_json_mode(self, mock_get_client):
        from skills.llm import chat

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value"}'}}],
            "usage": {},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = chat("system", "user", json_mode=True, track_cost=False)

        assert result == '{"key": "value"}'


# ── chat_structured() ────────────────────────────────────────────────
class TestChatStructured:
    """Test the chat_structured function."""

    @patch("skills.llm.chat")
    def test_returns_parsed_json(self, mock_chat):
        from skills.llm import chat_structured

        mock_chat.return_value = '{"score": 85, "reason": "good"}'

        result = chat_structured("system", "user")

        assert result == {"score": 85, "reason": "good"}

    @patch("skills.llm.chat")
    def test_handles_markdown_wrapped_json(self, mock_chat):
        from skills.llm import chat_structured

        mock_chat.return_value = '```json\n{"key": "value"}\n```'

        result = chat_structured("system", "user")

        assert result == {"key": "value"}

    @patch("skills.llm.chat")
    def test_raises_on_invalid_json(self, mock_chat):
        from skills.llm import chat_structured, LLMError

        mock_chat.return_value = "not json at all"

        with pytest.raises(LLMError):
            chat_structured("system", "user")


# ── _HTTPClientManager ───────────────────────────────────────────────
class TestHTTPClientManager:
    """Test HTTP client manager."""

    def test_reset_clears_client(self):
        from skills.llm import _client_manager

        _client_manager.reset()
        # After reset, internal state should be None
        assert _client_manager._client is None


# ── reset_client ─────────────────────────────────────────────────────
class TestResetClient:
    """Test reset_client function."""

    def test_reset_client_works(self):
        from skills.llm import reset_client

        # Should not raise
        reset_client()


# ── chat() error handling ─────────────────────────────────────────────
class TestChatErrors:
    """Test chat function error handling."""

    @patch("skills.llm._get_client")
    def test_chat_raises_on_http_error(self, mock_get_client):
        import httpx
        from skills.llm import chat, LLMError

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_response
        )
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        with pytest.raises(LLMError, match="429"):
            chat("system", "user", model="single-model", track_cost=False)

    @patch("skills.llm._get_client")
    def test_chat_raises_on_timeout(self, mock_get_client):
        import httpx
        from skills.llm import chat, LLMError

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
        mock_get_client.return_value = mock_client

        with pytest.raises(LLMError, match="timed out"):
            chat("system", "user", model="single-model", track_cost=False)

    @patch("skills.llm._get_client")
    def test_chat_raises_on_generic_error(self, mock_get_client):
        from skills.llm import chat, LLMError

        mock_client = MagicMock()
        mock_client.post.side_effect = ConnectionError("Network unreachable")
        mock_get_client.return_value = mock_client

        with pytest.raises(LLMError, match="failed"):
            chat("system", "user", model="single-model", track_cost=False)

    @patch("skills.llm._get_client")
    def test_chat_json_mode_sets_response_format(self, mock_get_client):
        from skills.llm import chat

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"k":"v"}'}}],
            "usage": {},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        result = chat("system", "user", json_mode=True, track_cost=False)
        body = mock_client.post.call_args[1]["json"]
        assert body["response_format"] == {"type": "json_object"}

    @patch("skills.llm._get_client")
    def test_chat_with_explicit_model(self, mock_get_client):
        from skills.llm import chat

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        chat("system", "user", model="custom-model", track_cost=False)
        body = mock_client.post.call_args[1]["json"]
        assert body["model"] == "custom-model"

    @patch("skills.llm._get_client")
    def test_chat_with_custom_max_tokens(self, mock_get_client):
        from skills.llm import chat

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        chat("system", "user", max_tokens=100, track_cost=False)
        body = mock_client.post.call_args[1]["json"]
        assert body["max_tokens"] == 100


# ── _record_usage ────────────────────────────────────────────────────
class TestRecordUsage:
    """Test usage recording."""

    @patch("skills.llm.LOGS_DIR")
    def test_record_usage_creates_csv(self, mock_logs_dir, tmp_path):
        from skills.llm import _record_usage

        mock_logs_dir.__truediv__ = lambda self, x: tmp_path / x

        data = {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            }
        }

        # Should not raise
        _record_usage(data, agent="test")

    def test_record_usage_skips_empty(self):
        from skills.llm import _record_usage

        # Should not raise, should be a no-op
        _record_usage({}, agent="test")
        _record_usage({"usage": {}}, agent="test")
