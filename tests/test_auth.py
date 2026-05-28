"""Tests for dashboard/backend/auth.py — API authentication middleware."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from starlette.requests import Request
from starlette.responses import JSONResponse


class TestAuthMiddleware:
    """Test AuthMiddleware class."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock ASGI app."""
        app = MagicMock()
        return app

    def test_skips_auth_when_no_key(self, mock_app):
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app, api_key="")
        assert middleware._api_key == ""

    def test_sets_key_from_env(self, mock_app, monkeypatch):
        monkeypatch.setenv("API_KEY", "test-secret-key")
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app)
        assert middleware._api_key == "test-secret-key"
        monkeypatch.delenv("API_KEY", raising=False)

    def test_explicit_key_overrides_env(self, mock_app, monkeypatch):
        monkeypatch.setenv("API_KEY", "env-key")
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app, api_key="explicit-key")
        assert middleware._api_key == "explicit-key"
        monkeypatch.delenv("API_KEY", raising=False)

    @pytest.mark.asyncio
    async def test_public_path_skips_auth(self, mock_app):
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app, api_key="secret")

        # Create mock request for public path
        request = MagicMock()
        request.url.path = "/api/health"
        call_next = AsyncMock(return_value=JSONResponse({"status": "ok"}))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_options_skips_auth(self, mock_app):
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app, api_key="secret")

        request = MagicMock()
        request.url.path = "/api/pipeline/status"
        request.method = "OPTIONS"
        call_next = AsyncMock(return_value=JSONResponse({}))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_key_passes(self, mock_app):
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app, api_key="secret-key")

        request = MagicMock()
        request.url.path = "/api/pipeline/status"
        request.method = "GET"
        request.headers = {"X-API-Key": "secret-key"}
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_key_returns_401(self, mock_app):
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app, api_key="secret-key")

        request = MagicMock()
        request.url.path = "/api/pipeline/status"
        request.method = "GET"
        request.headers = {"X-API-Key": "wrong-key"}
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 401
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_key_returns_401(self, mock_app):
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app, api_key="secret-key")

        request = MagicMock()
        request.url.path = "/api/pipeline/status"
        request.method = "GET"
        request.headers = {}
        call_next = AsyncMock()

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_key_configured_skips_all(self, mock_app):
        from dashboard.backend.auth import AuthMiddleware

        middleware = AuthMiddleware(mock_app, api_key="")

        request = MagicMock()
        request.url.path = "/api/pipeline/status"
        request.method = "GET"
        request.headers = {}
        call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

        response = await middleware.dispatch(request, call_next)
        call_next.assert_called_once()
