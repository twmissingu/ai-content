"""Tests for dashboard/backend/feishu.py — Feishu webhook notifications."""

import json
from unittest.mock import MagicMock, patch

import pytest

from dashboard.backend.feishu import send_feishu_alert, send_text_message, _get_webhook_url


class TestGetWebhookUrl:
    """Test _get_webhook_url function."""

    def test_returns_empty_when_not_set(self, monkeypatch):
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        assert _get_webhook_url() == ""

    def test_returns_url_when_set(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")
        assert _get_webhook_url() == "https://example.com/webhook"


class TestSendFeishuAlert:
    """Test send_feishu_alert function."""

    def test_returns_false_when_no_webhook(self, monkeypatch):
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        result = send_feishu_alert("Test", "Content")
        assert result is False

    def test_sends_card_message(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            result = send_feishu_alert("Test Title", "Test Content", "info")

        assert result is True

    def test_sends_warning_level(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            result = send_feishu_alert("Warning", "Content", "warning")

        assert result is True

    def test_sends_error_level(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            result = send_feishu_alert("Error", "Content", "error")

        assert result is True

    def test_handles_api_error(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 1, "msg": "error"}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = send_feishu_alert("Test", "Content")

        assert result is False

    def test_handles_network_error(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            result = send_feishu_alert("Test", "Content")

        assert result is False


class TestSendTextMessage:
    """Test send_text_message function."""

    def test_returns_false_when_no_webhook(self, monkeypatch):
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        result = send_text_message("Hello")
        assert result is False

    def test_sends_text_message(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = send_text_message("Hello World")

        assert result is True


class TestBudgetAlerts:
    """Test budget-specific alert functions."""

    def test_alert_budget_warning(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            from dashboard.backend.feishu import alert_budget_warning
            # These functions don't return values, just verify no exception
            alert_budget_warning(12.5, 15.0, 83.3)

    def test_alert_service_down(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            from dashboard.backend.feishu import alert_service_down
            alert_service_down("dashboard")

    def test_alert_publish_success(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            from dashboard.backend.feishu import alert_publish_success
            alert_publish_success("Test Topic", ["wechat", "xiaohongshu"])

    def test_alert_approval_needed(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            from dashboard.backend.feishu import alert_approval_needed
            alert_approval_needed("Test Topic", 85)

    def test_alert_agent_error(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"code": 0}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            from dashboard.backend.feishu import alert_agent_error
            alert_agent_error("writer", "LLM timeout")
