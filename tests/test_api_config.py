"""Tests for config API routes."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def client(monkeypatch):
    """Create a test client with mocked config services."""
    monkeypatch.setattr("dashboard.backend.routes.config.get_all_config_summary", lambda: {
        "schedule": {"morning_scout": "09:00"},
        "styles": {"default": {"tone": "professional"}},
        "gates": {"proofread_threshold": 60},
    })
    monkeypatch.setattr("dashboard.backend.routes.config.get_schedule_config", lambda: {
        "morning_scout": "09:00",
        "morning_writer": "09:30",
    })
    monkeypatch.setattr("dashboard.backend.routes.config.get_writing_styles", lambda: {
        "default": {"tone": "professional"},
    })
    monkeypatch.setattr("dashboard.backend.routes.config.get_quality_gates", lambda: {
        "proofread_threshold": 60,
        "critique_threshold": 70,
    })
    monkeypatch.setattr("dashboard.backend.routes.config.get_source_config", lambda: {
        "weibo": {"enabled": True},
    })
    monkeypatch.setattr("dashboard.backend.routes.config.get_model_config", lambda: {
        "model": "mimo-v2.5",
    })
    monkeypatch.setattr("dashboard.backend.routes.config.get_budget_config", lambda: {
        "monthly_budget": 15.0,
    })
    monkeypatch.setattr("dashboard.backend.routes.config.update_schedule", lambda k, v: {k: v})
    monkeypatch.setattr("dashboard.backend.routes.config.update_writing_style", lambda n, u: u)
    monkeypatch.setattr("dashboard.backend.routes.config.update_quality_gates", lambda u: u)
    monkeypatch.setattr("dashboard.backend.routes.config.update_source", lambda n, u: u)
    monkeypatch.setattr("dashboard.backend.routes.config.update_budget", lambda u: u)
    monkeypatch.setattr("dashboard.backend.routes.config.generate_style_prompt", lambda n: "test prompt" if n == "default" else None)

    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestGetConfig:
    def test_returns_all_config(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "schedule" in data
        assert "styles" in data


class TestGetConfigSection:
    def test_get_schedule(self, client):
        resp = client.get("/api/config/schedule")
        assert resp.status_code == 200
        assert "morning_scout" in resp.json()

    def test_get_styles(self, client):
        resp = client.get("/api/config/styles")
        assert resp.status_code == 200

    def test_get_gates(self, client):
        resp = client.get("/api/config/gates")
        assert resp.status_code == 200
        assert "proofread_threshold" in resp.json()

    def test_get_sources(self, client):
        resp = client.get("/api/config/sources")
        assert resp.status_code == 200

    def test_get_model(self, client):
        resp = client.get("/api/config/model")
        assert resp.status_code == 200

    def test_get_budget(self, client):
        resp = client.get("/api/config/budget")
        assert resp.status_code == 200

    def test_unknown_section_404(self, client):
        resp = client.get("/api/config/nonexistent")
        assert resp.status_code == 404


class TestUpdateSchedule:
    def test_update_key(self, client):
        resp = client.post("/api/config/schedule", json={"key": "morning_scout", "value": "10:00"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_time_key_needs_restart(self, client):
        resp = client.post("/api/config/schedule", json={"key": "morning_scout", "value": "10:00"})
        data = resp.json()
        assert data.get("needs_restart") is True


class TestUpdateGates:
    def test_update_gates(self, client):
        resp = client.post("/api/config/gates", json={"proofread_threshold": 70})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestUpdateBudget:
    def test_update_budget(self, client):
        resp = client.post("/api/config/budget", json={"monthly_budget": 20.0})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestStylePrompt:
    def test_known_style(self, client):
        resp = client.get("/api/config/style-prompt/default")
        assert resp.status_code == 200
        assert "prompt" in resp.json()

    def test_unknown_style_404(self, client):
        resp = client.get("/api/config/style-prompt/nonexistent")
        assert resp.status_code == 404
