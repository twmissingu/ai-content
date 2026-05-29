"""Tests for dashboard/backend/main.py — RateLimiter, CORS, lifespan, WebSocket."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRateLimiter:
    def test_allows_under_limit(self):
        from dashboard.backend.main import RateLimiter
        rl = RateLimiter(requests_per_minute=5)
        for _ in range(5):
            assert rl.is_allowed("1.2.3.4") is True

    def test_blocks_over_limit(self):
        from dashboard.backend.main import RateLimiter
        rl = RateLimiter(requests_per_minute=3)
        for _ in range(3):
            rl.is_allowed("1.2.3.4")
        assert rl.is_allowed("1.2.3.4") is False

    def test_different_ips_independent(self):
        from dashboard.backend.main import RateLimiter
        rl = RateLimiter(requests_per_minute=2)
        rl.is_allowed("1.1.1.1")
        rl.is_allowed("1.1.1.1")
        assert rl.is_allowed("1.1.1.1") is False
        assert rl.is_allowed("2.2.2.2") is True

    def test_window_expires(self):
        from dashboard.backend.main import RateLimiter
        rl = RateLimiter(requests_per_minute=2)
        # Manually set old timestamps
        rl.requests["1.2.3.4"] = [time.time() - 61, time.time() - 61]
        assert rl.is_allowed("1.2.3.4") is True

    def test_evicts_stale_clients(self):
        from dashboard.backend.main import RateLimiter
        rl = RateLimiter(requests_per_minute=120)
        rl._MAX_CLIENTS = 2
        # Add 3 clients, 2 stale
        rl.requests["stale1"] = [time.time() - 120]
        rl.requests["stale2"] = [time.time() - 120]
        rl.requests["active"] = [time.time()]
        # Trigger eviction by calling is_allowed on a new IP
        rl.is_allowed("new_ip")
        assert "stale1" not in rl.requests
        assert "stale2" not in rl.requests


class TestGetCorsOrigins:
    def test_default_origins(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        from dashboard.backend.main import _get_cors_origins
        origins = _get_cors_origins()
        assert "http://localhost:5173" in origins
        assert len(origins) == 4

    def test_custom_origins(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://a.com,https://b.com")
        from dashboard.backend.main import _get_cors_origins
        origins = _get_cors_origins()
        assert "https://a.com" in origins
        assert "https://b.com" in origins

    def test_empty_string_returns_defaults(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "")
        from dashboard.backend.main import _get_cors_origins
        origins = _get_cors_origins()
        assert "http://localhost:5173" in origins

    def test_invalid_origin_filtered(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "not-a-url,https://valid.com")
        from dashboard.backend.main import _get_cors_origins
        origins = _get_cors_origins()
        assert "not-a-url" not in origins
        assert "https://valid.com" in origins

    def test_wildcard_accepted(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "*")
        monkeypatch.setenv("ENV", "development")
        from dashboard.backend.main import _get_cors_origins
        origins = _get_cors_origins()
        assert "*" in origins


class TestRateLimitMiddleware:
    @pytest.fixture
    def client_no_auth(self, monkeypatch):
        """Test client with auth disabled and rate limiter reset."""
        monkeypatch.delenv("API_KEY", raising=False)
        from dashboard.backend.main import app, rate_limiter
        # Reset rate limiter state
        rate_limiter.requests.clear()
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_health_endpoint_skips_rate_limit(self, client_no_auth):
        """Health endpoint should bypass rate limiting."""
        for _ in range(130):
            resp = client_no_auth.get("/api/health")
        assert resp.status_code == 200


class TestLifespan:
    def test_app_starts_successfully(self, monkeypatch):
        """Verify the app can start (lifespan runs without error)."""
        monkeypatch.delenv("API_KEY", raising=False)
        from dashboard.backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_ws_endpoint_connects(self, monkeypatch):
        """Verify WebSocket endpoint accepts connections."""
        monkeypatch.delenv("API_KEY", raising=False)
        from dashboard.backend.main import app, ws_manager
        from fastapi.testclient import TestClient
        monkeypatch.setattr(ws_manager, "_build_status", lambda: {
            "type": "pipeline_status", "agents": {}, "budget": {}
        })
        client = TestClient(app)
        with client.websocket_connect("/ws/pipeline") as ws:
            data = ws.receive_text()
            status = json.loads(data)
            assert status["type"] == "pipeline_status"

    def test_ws_ping_pong(self, monkeypatch):
        """Verify WebSocket responds to ping."""
        monkeypatch.delenv("API_KEY", raising=False)
        from dashboard.backend.main import app, ws_manager
        from fastapi.testclient import TestClient
        monkeypatch.setattr(ws_manager, "_build_status", lambda: {
            "type": "pipeline_status", "agents": {}, "budget": {}
        })
        client = TestClient(app)
        with client.websocket_connect("/ws/pipeline") as ws:
            ws.receive_text()  # initial status
            ws.send_text("ping")
            resp = ws.receive_text()
            assert json.loads(resp)["type"] == "pong"


class TestAuthIntegration:
    @pytest.fixture
    def client_with_auth(self, monkeypatch):
        """Test client with API_KEY set."""
        monkeypatch.setenv("API_KEY", "test-secret-key")
        # Need to recreate app with new API_KEY
        from dashboard.backend import main as main_mod
        from dashboard.backend.auth import AuthMiddleware
        # Patch the middleware's api_key
        monkeypatch.setattr(
            "dashboard.backend.main.AuthMiddleware",
            lambda app, api_key=None: AuthMiddleware(app, api_key="test-secret-key"),
        )
        from fastapi.testclient import TestClient
        return TestClient(main_mod.app)

    def test_public_endpoint_without_key(self, monkeypatch):
        """Health endpoint should work without auth."""
        monkeypatch.delenv("API_KEY", raising=False)
        from dashboard.backend.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
