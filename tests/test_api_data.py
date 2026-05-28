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


class TestCostDataCSVFallback:
    """Test cost data CSV fallback path."""

    @pytest.fixture
    def csv_client(self, tmp_path, monkeypatch):
        """Client that triggers CSV fallback."""
        # Make get_token_usage_stats raise an exception
        monkeypatch.setattr("dashboard.backend.routes.data.get_token_usage_stats", lambda days=30: (_ for _ in ()).throw(Exception("DB error")))
        monkeypatch.setattr("dashboard.backend.routes.data.check_budget_limit", lambda: {"is_exceeded": False})

        # Create a CSV file
        cost_dir = tmp_path / "data" / "logs"
        cost_dir.mkdir(parents=True)
        csv_path = cost_dir / "cost.csv"
        csv_path.write_text(
            "timestamp,prompt_tokens,completion_tokens,total_tokens,model,agent\n"
            "2026-05-28T10:00:00,1000,500,1500,mimo-v2.5,scout\n"
            "2026-05-28T11:00:00,2000,1000,3000,mimo-v2.5,writer\n"
            "2026-05-27T10:00:00,500,250,750,mimo-v2.5,scout\n"
        )
        monkeypatch.setattr("dashboard.backend.routes.data.PROJECT_ROOT", tmp_path)

        from dashboard.backend.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_csv_fallback_returns_daily(self, csv_client):
        resp = csv_client.get("/api/data/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily" in data
        assert data["source"] == "csv_fallback"

    def test_csv_fallback_groups_by_date(self, csv_client):
        resp = csv_client.get("/api/data/cost")
        data = resp.json()
        # Should have 2 dates: 2026-05-28 and 2026-05-27
        dates = [d["date"] for d in data["daily"]]
        assert "2026-05-28" in dates
        assert "2026-05-27" in dates

    def test_csv_fallback_calculates_monthly(self, csv_client):
        resp = csv_client.get("/api/data/cost")
        data = resp.json()
        assert data["monthly_total"] > 0
