"""Tests for data API routes."""

import json
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with isolated paths."""
    monkeypatch.setattr("dashboard.backend.routes.data.get_token_usage_stats", lambda days=30: {
        "daily": [
            {"date": "2026-05-28", "cost": 1.23, "input_tokens": 5000, "output_tokens": 2000, "call_count": 10},
            {"date": "2026-05-27", "cost": 0.85, "input_tokens": 3000, "output_tokens": 1500, "call_count": 7},
        ],
        "monthly": {"cost": 5.5},
        "by_agent": [
            {"agent": "scout", "cost": 2.0},
            {"agent": "writer", "cost": 3.5},
        ],
    })
    monkeypatch.setattr("dashboard.backend.routes.data.check_budget_limit", lambda: {
        "current_cost": 5.5,
        "budget": 15.0,
        "percentage": 36.7,
        "is_exceeded": False,
    })
    monkeypatch.setattr("dashboard.backend.routes.data.KB_DIR", tmp_path / "kb")

    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestCostData:
    def test_returns_daily(self, client):
        resp = client.get("/api/data/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily" in data
        assert len(data["daily"]) == 2

    def test_returns_monthly_total(self, client):
        resp = client.get("/api/data/cost")
        data = resp.json()
        assert data["monthly_total"] == 5.5

    def test_returns_by_agent(self, client):
        resp = client.get("/api/data/cost")
        data = resp.json()
        assert "by_agent" in data
        assert len(data["by_agent"]) == 2

    def test_returns_budget(self, client):
        resp = client.get("/api/data/cost")
        data = resp.json()
        assert "budget" in data
        assert data["budget"]["budget"] == 15.0

    def test_daily_has_required_fields(self, client):
        resp = client.get("/api/data/cost")
        day = resp.json()["daily"][0]
        assert "date" in day
        assert "cost" in day


class TestAnalytics:
    def test_returns_topics(self, client):
        resp = client.get("/api/data/analytics")
        assert resp.status_code == 200
        assert "topics" in resp.json()

    def test_returns_keywords(self, client):
        resp = client.get("/api/data/analytics")
        assert "keywords" in resp.json()

    def test_returns_pipeline_stats(self, client):
        resp = client.get("/api/data/analytics")
        data = resp.json()
        assert "pipeline_stats" in data
        assert "total_sessions" in data["pipeline_stats"]
