"""Tests for skills/publisher_webbridge.py — WebBridge publisher."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.publisher_webbridge import (
    WebBridgePublisher,
    WebBridgeError,
    check_webbridge_available,
)


@pytest.fixture
def publisher():
    """Create a WebBridgePublisher instance."""
    return WebBridgePublisher()


class TestWebBridgeCall:
    """Test _call() with mocked httpx."""

    def test_valid_action_sends_payload(self, publisher):
        """Valid action should send correct JSON payload via httpx."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("skills.publisher_webbridge.httpx.Client", return_value=mock_client):
            result = publisher._call("navigate", {"url": "https://example.com"})

        assert result == {"result": "ok"}
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert payload["action"] == "navigate"
        assert payload["args"] == {"url": "https://example.com"}
        assert payload["session"] == "publish"

    def test_invalid_action_raises_error(self, publisher):
        """Unknown action should raise WebBridgeError."""
        with pytest.raises(WebBridgeError, match="Unknown WebBridge action"):
            publisher._call("invalid_action", {})

    def test_non_dict_args_raises_error(self, publisher):
        """Non-dict args should raise WebBridgeError."""
        with pytest.raises(WebBridgeError, match="args must be a dict"):
            publisher._call("navigate", "not a dict")

    def test_connect_error_raises_webbridge_error(self, publisher):
        """httpx.ConnectError should be converted to WebBridgeError."""
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("skills.publisher_webbridge.httpx.Client", return_value=mock_client):
            with pytest.raises(WebBridgeError, match="WebBridge call failed"):
                publisher._call("navigate", {"url": "https://example.com"})

    def test_http_error_raises_webbridge_error(self, publisher):
        """HTTP error response should raise WebBridgeError."""
        import httpx

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("skills.publisher_webbridge.httpx.Client", return_value=mock_client):
            with pytest.raises(WebBridgeError, match="WebBridge call failed"):
                publisher._call("navigate", {"url": "https://example.com"})

    def test_custom_session(self, publisher):
        """Custom session name should be passed in payload."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("skills.publisher_webbridge.httpx.Client", return_value=mock_client):
            publisher._call("snapshot", {}, session="custom-session")

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"] if "json" in call_args[1] else call_args[0][1]
        assert payload["session"] == "custom-session"


class TestPublishXiaohongshu:
    """Test publish_xiaohongshu() with mocked _call."""

    def test_successful_publish(self, publisher):
        """Successful publish should return status=success."""
        publisher._call = MagicMock(return_value={"result": "ok"})
        publisher._wait_for_page_ready = MagicMock(return_value=True)
        publisher._wait_for_settle = MagicMock(return_value=True)
        publisher._inject_files = MagicMock(return_value=True)

        result = publisher.publish_xiaohongshu(
            title="Test Title", content="Test content", images=["/path/to/img.png"]
        )

        assert result["status"] == "success"
        assert result["error"] is None

    def test_publish_without_images(self, publisher):
        """Publish without images should skip upload step."""
        publisher._call = MagicMock(return_value={"result": "ok"})
        publisher._wait_for_page_ready = MagicMock(return_value=True)
        publisher._wait_for_settle = MagicMock(return_value=True)

        result = publisher.publish_xiaohongshu(
            title="Title", content="Content", images=[]
        )

        assert result["status"] == "success"

    def test_publish_webbridge_error(self, publisher):
        """WebBridgeError during publish should return status=failed."""
        publisher._call = MagicMock(side_effect=WebBridgeError("Connection lost"))

        result = publisher.publish_xiaohongshu(
            title="Title", content="Content", images=[]
        )

        assert result["status"] == "failed"
        assert "Connection lost" in result["error"]

    def test_publish_unexpected_error(self, publisher):
        """Unexpected exception should return status=failed."""
        publisher._call = MagicMock(side_effect=RuntimeError("Unknown error"))

        result = publisher.publish_xiaohongshu(
            title="Title", content="Content", images=[]
        )

        assert result["status"] == "failed"
        assert "Unknown error" in result["error"]

    def test_publish_closes_tab_in_finally(self, publisher):
        """close_tab should be called even on error."""
        call_log = []

        def mock_call(action, args, session="publish"):
            call_log.append(action)
            if action == "navigate":
                raise WebBridgeError("nav failed")
            return {"result": "ok"}

        publisher._call = mock_call

        result = publisher.publish_xiaohongshu(
            title="T", content="C", images=[]
        )

        assert result["status"] == "failed"
        assert "close_tab" in call_log

    def test_publish_image_upload_fallback(self, publisher):
        """When _inject_files fails, evaluate fallback should be attempted."""
        publisher._wait_for_page_ready = MagicMock(return_value=True)
        publisher._wait_for_settle = MagicMock(return_value=True)
        publisher._inject_files = MagicMock(return_value=False)

        call_actions = []

        def mock_call(action, args, session="publish"):
            call_actions.append(action)
            return {"result": "ok"}

        publisher._call = mock_call

        result = publisher.publish_xiaohongshu(
            title="T", content="C", images=["/img.png"]
        )

        assert result["status"] == "success"
        assert "evaluate" in call_actions


class TestPublishDouyin:
    """Test publish_douyin() with mocked _call."""

    def test_successful_publish(self, publisher):
        """Successful publish should return status=success."""
        publisher._call = MagicMock(return_value={"result": "ok"})
        publisher._wait_for_page_ready = MagicMock(return_value=True)
        publisher._wait_for_settle = MagicMock(return_value=True)
        publisher._inject_files = MagicMock(return_value=True)

        result = publisher.publish_douyin(
            title="Test Title", content="Test content", images=["/path/to/img.png"]
        )

        assert result["status"] == "success"
        assert result["error"] is None

    def test_publish_without_images(self, publisher):
        """Publish without images should skip upload step."""
        publisher._call = MagicMock(return_value={"result": "ok"})
        publisher._wait_for_page_ready = MagicMock(return_value=True)
        publisher._wait_for_settle = MagicMock(return_value=True)

        result = publisher.publish_douyin(
            title="Title", content="Content", images=[]
        )

        assert result["status"] == "success"

    def test_publish_webbridge_error(self, publisher):
        """WebBridgeError during publish should return status=failed."""
        publisher._call = MagicMock(side_effect=WebBridgeError("Timeout"))

        result = publisher.publish_douyin(
            title="Title", content="Content", images=[]
        )

        assert result["status"] == "failed"
        assert "Timeout" in result["error"]

    def test_publish_closes_tab_in_finally(self, publisher):
        """close_tab should be called even on error."""
        call_log = []

        def mock_call(action, args, session="publish"):
            call_log.append(action)
            if action == "navigate":
                raise WebBridgeError("nav failed")
            return {"result": "ok"}

        publisher._call = mock_call

        result = publisher.publish_douyin(
            title="T", content="C", images=[]
        )

        assert result["status"] == "failed"
        assert "close_tab" in call_log


class TestWebBridgeError:
    """Test WebBridgeError exception class."""

    def test_is_exception(self):
        assert issubclass(WebBridgeError, Exception)

    def test_message_preserved(self):
        err = WebBridgeError("test message")
        assert str(err) == "test message"

    def test_can_be_caught_as_exception(self):
        with pytest.raises(Exception):
            raise WebBridgeError("test")


class TestCheckWebbridgeAvailable:
    """Test check_webbridge_available() with mocked httpx."""

    def test_returns_true_when_available(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("skills.publisher_webbridge.httpx.Client", return_value=mock_client):
            result = check_webbridge_available()

        assert result is True

    def test_returns_false_on_connect_error(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("skills.publisher_webbridge.httpx.Client", return_value=mock_client):
            result = check_webbridge_available()

        assert result is False

    def test_returns_false_on_server_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("skills.publisher_webbridge.httpx.Client", return_value=mock_client):
            result = check_webbridge_available()

        assert result is False

    def test_returns_true_for_4xx_error(self):
        """4xx errors mean server is running, just bad request."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("skills.publisher_webbridge.httpx.Client", return_value=mock_client):
            result = check_webbridge_available()

        assert result is True
