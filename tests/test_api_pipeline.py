"""Tests for pipeline API routes."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with isolated paths."""
    # Set up isolated paths
    status_dir = tmp_path / "queue" / "status"
    status_dir.mkdir(parents=True)
    pending_dir = tmp_path / "queue" / "pending"
    pending_dir.mkdir(parents=True)
    review_dir = tmp_path / "queue" / "review"
    review_dir.mkdir(parents=True)
    actions_dir = tmp_path / "queue" / "actions"
    actions_dir.mkdir(parents=True)
    kb_dir = tmp_path / "kb" / "history"
    kb_dir.mkdir(parents=True)

    monkeypatch.setattr("dashboard.backend.routes.pipeline.STATUS_DIR", status_dir)
    monkeypatch.setattr("dashboard.backend.routes.pipeline.KB_DIR", tmp_path / "kb")

    # Create test status file
    (status_dir / "scout.json").write_text(json.dumps({
        "agent": "scout",
        "stage": "completed",
        "progress_pct": 100,
        "detail": "Found 5 topics",
        "started_at": "20260528_090000",
    }))

    # Mock database functions
    monkeypatch.setattr("dashboard.backend.routes.pipeline.check_budget_limit", lambda: {
        "current_cost": 5.0,
        "budget": 15.0,
        "percentage": 33.3,
        "is_warning": False,
        "is_exceeded": False,
        "remaining": 10.0,
    })
    monkeypatch.setattr("dashboard.backend.routes.pipeline.get_pipeline_sessions", lambda limit=14: {
        "items": [],
        "total": 0,
    })

    # Patch lifespan to avoid starting background threads
    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestPipelineStatus:
    def test_returns_agents(self, client):
        resp = client.get("/api/pipeline/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert "scout" in data["agents"]
        assert data["agents"]["scout"]["progress_pct"] == 100

    def test_returns_budget(self, client):
        resp = client.get("/api/pipeline/status")
        data = resp.json()
        assert "budget" in data
        assert data["budget"]["budget"] == 15.0

    def test_returns_timestamp(self, client):
        resp = client.get("/api/pipeline/status")
        data = resp.json()
        assert "timestamp" in data


class TestPipelineTimeline:
    def test_returns_sessions(self, client):
        resp = client.get("/api/pipeline/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data

    def test_includes_filesystem_sessions(self, client, tmp_path, monkeypatch):
        # Create a history directory
        history_dir = tmp_path / "kb" / "history" / "2026-05-28"
        history_dir.mkdir(parents=True)
        (history_dir / "test-article.md").write_text("# Test")

        monkeypatch.setattr("dashboard.backend.routes.pipeline.KB_DIR", tmp_path / "kb")
        resp = client.get("/api/pipeline/timeline")
        data = resp.json()
        # Should have at least one session from filesystem
        fs_sessions = [s for s in data["sessions"] if s["source"] == "filesystem"]
        assert len(fs_sessions) >= 1


class TestPipelineTrigger:
    def test_invalid_agent_rejected(self, client):
        resp = client.post("/api/pipeline/trigger", json={"agent": "invalid"})
        assert resp.status_code == 400

    def test_invalid_session_rejected(self, client):
        resp = client.post("/api/pipeline/trigger", json={"agent": "scout", "session": "invalid"})
        assert resp.status_code == 400

    def test_invalid_topic_id_rejected(self, client):
        resp = client.post("/api/pipeline/trigger", json={"agent": "writer", "topic_id": "../../../etc"})
        assert resp.status_code == 400
