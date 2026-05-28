"""Tests for health and topics API routes."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with isolated paths."""
    pending_dir = tmp_path / "queue" / "pending"
    pending_dir.mkdir(parents=True)
    review_dir = tmp_path / "queue" / "review"
    review_dir.mkdir(parents=True)
    actions_dir = tmp_path / "queue" / "actions"
    actions_dir.mkdir(parents=True)
    failed_dir = tmp_path / "queue" / "failed"
    failed_dir.mkdir(parents=True)

    monkeypatch.setattr("dashboard.backend.routes.health.PENDING_DIR", pending_dir)
    monkeypatch.setattr("dashboard.backend.routes.health.REVIEW_DIR", review_dir)
    monkeypatch.setattr("dashboard.backend.routes.health.ACTIONS_DIR", actions_dir)
    monkeypatch.setattr("dashboard.backend.routes.health.FAILED_DIR", failed_dir)

    # Create test topic
    (pending_dir / "topic_test-001.json").write_text(json.dumps({
        "title": "Test Topic",
        "source": "weibo",
        "final_score": 75.5,
        "direction": "AI应用",
    }))

    # Mock database and search
    monkeypatch.setattr("dashboard.backend.routes.health.get_db", lambda: MagicMock(__enter__=lambda s: MagicMock(execute=lambda *a: None), __exit__=lambda *a: None))
    monkeypatch.setattr("dashboard.backend.routes.health.check_budget_limit", lambda: {"is_exceeded": False})
    monkeypatch.setattr("dashboard.backend.routes.health.get_index_stats", lambda: {"total_indexed": 10})
    monkeypatch.setattr("dashboard.backend.routes.health.log_token_usage", lambda **kw: 1)

    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded", "warning")

    def test_health_has_services(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert "services" in data
        assert "database" in data["services"]

    def test_health_has_queue_sizes(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert "queue_sizes" in data

    def test_health_has_budget(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert "budget" in data


class TestTopics:
    def test_get_topics(self, client):
        resp = client.get("/api/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert data["count"] >= 1

    def test_topic_has_id(self, client):
        resp = client.get("/api/topics")
        topics = resp.json()["topics"]
        assert "id" in topics[0]
        assert "title" in topics[0]

    def test_confirm_topic(self, client):
        resp = client.post("/api/topics/confirm", json={
            "target_id": "topic_test-001",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestTokenLog:
    def test_log_token(self, client):
        resp = client.post("/api/token/log", json={
            "agent": "test",
            "model": "mimo-v2.5",
            "input_tokens": 100,
            "output_tokens": 50,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
