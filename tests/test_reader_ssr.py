"""Tests for dashboard/backend/routes/reader.py — SSRF protection."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException


class TestStripHtmlTags:
    """Test _strip_html_tags helper."""

    def test_strips_script_tags(self):
        from dashboard.backend.routes.reader import _strip_html_tags
        html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        result = _strip_html_tags(html)
        assert "alert" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strips_style_tags(self):
        from dashboard.backend.routes.reader import _strip_html_tags
        html = '<style>body{color:red}</style><p>Text</p>'
        result = _strip_html_tags(html)
        assert "color" not in result
        assert "Text" in result

    def test_converts_block_elements_to_newlines(self):
        from dashboard.backend.routes.reader import _strip_html_tags
        html = "<p>Para1</p><p>Para2</p>"
        result = _strip_html_tags(html)
        assert "\n" in result

    def test_decodes_entities(self):
        from dashboard.backend.routes.reader import _strip_html_tags
        html = "&amp; &lt; &gt; &quot; &#39; &nbsp;"
        result = _strip_html_tags(html)
        assert "&" in result
        assert "<" in result
        assert ">" in result

    def test_collapses_whitespace(self):
        from dashboard.backend.routes.reader import _strip_html_tags
        html = "<p>  multiple   spaces  </p>"
        result = _strip_html_tags(html)
        assert "  multiple" not in result

    def test_empty_input(self):
        from dashboard.backend.routes.reader import _strip_html_tags
        assert _strip_html_tags("") == ""

    def test_nested_tags(self):
        from dashboard.backend.routes.reader import _strip_html_tags
        html = '<div><span><a href="#">Link</a></span></div>'
        result = _strip_html_tags(html)
        assert "Link" in result
        assert "<" not in result


class TestIsPrivateIp:
    """Test _is_private_ip helper."""

    def test_loopback_ipv4(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("127.0.0.1") is True

    def test_loopback_ipv6(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("::1") is True

    def test_private_10(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("10.0.0.1") is True

    def test_private_172(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("172.16.0.1") is True

    def test_private_192(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("192.168.1.1") is True

    def test_link_local(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("169.254.1.1") is True

    def test_public_ip(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("8.8.8.8") is False

    def test_public_ipv6(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("2001:4860:4860::8888") is False

    def test_invalid_ip(self):
        from dashboard.backend.routes.reader import _is_private_ip
        assert _is_private_ip("not-an-ip") is True  # Invalid = blocked


class TestResolveAndCheck:
    """Test _resolve_and_check DNS resolution + IP validation."""

    def test_blocks_private_ip(self):
        from dashboard.backend.routes.reader import _resolve_and_check
        with patch("dashboard.backend.routes.reader.socket.getaddrinfo") as mock:
            mock.return_value = [(2, 1, 6, '', ('10.0.0.1', 80))]
            with pytest.raises(HTTPException) as exc_info:
                _resolve_and_check("evil.com")
            assert exc_info.value.status_code == 403

    def test_allows_public_ip(self):
        from dashboard.backend.routes.reader import _resolve_and_check
        with patch("dashboard.backend.routes.reader.socket.getaddrinfo") as mock:
            mock.return_value = [(2, 1, 6, '', ('93.184.216.34', 80))]
            ip = _resolve_and_check("example.com")
            assert ip == "93.184.216.34"

    def test_blocks_dns_failure(self):
        from dashboard.backend.routes.reader import _resolve_and_check
        import socket
        with patch("dashboard.backend.routes.reader.socket.getaddrinfo") as mock:
            mock.side_effect = socket.gaierror("DNS failure")
            with pytest.raises(HTTPException) as exc_info:
                _resolve_and_check("nonexistent.invalid")
            assert exc_info.value.status_code == 400

    def test_blocks_loopback(self):
        from dashboard.backend.routes.reader import _resolve_and_check
        with patch("dashboard.backend.routes.reader.socket.getaddrinfo") as mock:
            mock.return_value = [(2, 1, 6, '', ('127.0.0.1', 80))]
            with pytest.raises(HTTPException) as exc_info:
                _resolve_and_check("localhost.alias")
            assert exc_info.value.status_code == 403


class TestFetchUrlEndpoint:
    """Test the /api/reader/fetch endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from dashboard.backend.routes.reader import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_rejects_non_http_urls(self, client):
        resp = client.get("/api/reader/fetch", params={"url": "file:///etc/passwd"})
        assert resp.status_code == 400

    def test_rejects_ftp_urls(self, client):
        resp = client.get("/api/reader/fetch", params={"url": "ftp://example.com"})
        assert resp.status_code == 400

    def test_blocks_localhost(self, client):
        resp = client.get("/api/reader/fetch", params={"url": "http://localhost/admin"})
        assert resp.status_code == 403

    def test_blocks_127_0_0_1(self, client):
        resp = client.get("/api/reader/fetch", params={"url": "http://127.0.0.1/admin"})
        assert resp.status_code == 403

    def test_blocks_private_ip_in_url(self, client):
        resp = client.get("/api/reader/fetch", params={"url": "http://192.168.1.1/admin"})
        assert resp.status_code == 403

    def test_blocks_private_ip_resolution(self, client):
        """DNS resolves to private IP — should be blocked."""
        with patch("dashboard.backend.routes.reader.socket.getaddrinfo") as mock:
            mock.return_value = [(2, 1, 6, '', ('10.0.0.1', 80))]
            resp = client.get("/api/reader/fetch", params={"url": "http://evil.example.com/"})
            assert resp.status_code == 403

    def test_success_with_public_url(self, client):
        """Valid public URL should succeed (mocked httpx)."""
        with patch("dashboard.backend.routes.reader.socket.getaddrinfo") as mock_dns, \
             patch("httpx.AsyncClient") as mock_client:
            mock_dns.return_value = [(2, 1, 6, '', ('93.184.216.34', 80))]

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "text/html"}
            mock_resp.text = "<p>Hello World</p>"
            mock_resp.raise_for_status = MagicMock()

            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_resp)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_async_client

            resp = client.get("/api/reader/fetch", params={"url": "http://example.com/"})
            assert resp.status_code == 200
            data = resp.json()
            assert "Hello World" in data["content"]

    def test_truncates_long_content(self, client):
        """Content over 10000 chars should be truncated."""
        with patch("dashboard.backend.routes.reader.socket.getaddrinfo") as mock_dns, \
             patch("httpx.AsyncClient") as mock_client:
            mock_dns.return_value = [(2, 1, 6, '', ('93.184.216.34', 80))]

            long_text = "x" * 15000
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "text/plain"}
            mock_resp.text = long_text
            mock_resp.raise_for_status = MagicMock()

            mock_async_client = AsyncMock()
            mock_async_client.get = AsyncMock(return_value=mock_resp)
            mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
            mock_async_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_async_client

            resp = client.get("/api/reader/fetch", params={"url": "http://example.com/"})
            data = resp.json()
            assert data["truncated"] is True
            assert len(data["content"]) <= 10000
