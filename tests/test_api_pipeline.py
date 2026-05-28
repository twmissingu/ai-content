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

    def test_successful_trigger_scout(self, client, tmp_path, monkeypatch):
        import subprocess
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        monkeypatch.setattr("dashboard.backend.routes.pipeline.subprocess", MagicMock(Popen=MagicMock(return_value=mock_proc)))
        monkeypatch.setattr("dashboard.backend.routes.pipeline.PROJECT_ROOT", tmp_path)
        resp = client.post("/api/pipeline/trigger", json={"agent": "scout", "session": "morning"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["agent"] == "scout"
        assert data["pid"] == 12345

    def test_successful_trigger_writer(self, client, tmp_path, monkeypatch):
        mock_proc = MagicMock()
        mock_proc.pid = 12346
        monkeypatch.setattr("dashboard.backend.routes.pipeline.subprocess", MagicMock(Popen=MagicMock(return_value=mock_proc)))
        monkeypatch.setattr("dashboard.backend.routes.pipeline.PROJECT_ROOT", tmp_path)
        resp = client.post("/api/pipeline/trigger", json={"agent": "writer"})
        assert resp.status_code == 200
        assert resp.json()["agent"] == "writer"

    def test_trigger_with_topic_id(self, client, tmp_path, monkeypatch):
        mock_proc = MagicMock()
        mock_proc.pid = 12347
        monkeypatch.setattr("dashboard.backend.routes.pipeline.subprocess", MagicMock(Popen=MagicMock(return_value=mock_proc)))
        monkeypatch.setattr("dashboard.backend.routes.pipeline.PROJECT_ROOT", tmp_path)
        resp = client.post("/api/pipeline/trigger", json={"agent": "writer", "topic_id": "topic-123"})
        assert resp.status_code == 200

    def test_trigger_subprocess_error(self, client, tmp_path, monkeypatch):
        from dashboard.backend.routes.pipeline import _trigger_timestamps
        _trigger_timestamps.clear()

        def raise_popen(*a, **kw):
            raise OSError("binary not found")
        monkeypatch.setattr("dashboard.backend.routes.pipeline.subprocess", MagicMock(Popen=raise_popen))
        monkeypatch.setattr("dashboard.backend.routes.pipeline.PROJECT_ROOT", tmp_path)
        resp = client.post("/api/pipeline/trigger", json={"agent": "scout"})
        assert resp.status_code == 500

    def test_rate_limiting(self, client, tmp_path, monkeypatch):
        mock_proc = MagicMock()
        mock_proc.pid = 12348
        monkeypatch.setattr("dashboard.backend.routes.pipeline.subprocess", MagicMock(Popen=MagicMock(return_value=mock_proc)))
        monkeypatch.setattr("dashboard.backend.routes.pipeline.PROJECT_ROOT", tmp_path)
        # Clear rate limiter
        from dashboard.backend.routes.pipeline import _trigger_timestamps
        _trigger_timestamps.clear()

        for _ in range(5):
            client.post("/api/pipeline/trigger", json={"agent": "scout"})
        resp = client.post("/api/pipeline/trigger", json={"agent": "scout"})
        assert resp.status_code == 429


class TestPipelineTimelineDB:
    def test_timeline_includes_db_sessions(self, client, monkeypatch):
        monkeypatch.setattr(
            "dashboard.backend.routes.pipeline.get_pipeline_sessions",
            lambda limit=14: {
                "items": [
                    {"id": 1, "date": "2026-05-28", "period": "morning", "topic": "AI趋势", "status": "completed", "started_at": None, "completed_at": None},
                ],
                "total": 1,
            },
        )
        resp = client.get("/api/pipeline/timeline")
        data = resp.json()
        db_sessions = [s for s in data["sessions"] if s["source"] == "database"]
        assert len(db_sessions) == 1
        assert db_sessions[0]["id"] == 1


class TestPipelineStatusTimeout:
    def test_timeout_flag_set(self, client, tmp_path, monkeypatch):
        import time
        status_dir = tmp_path / "queue" / "status"
        status_dir.mkdir(parents=True, exist_ok=True)
        # Create a status file with old started_at and incomplete progress
        (status_dir / "writer.json").write_text(json.dumps({
            "agent": "writer",
            "stage": "drafting",
            "progress_pct": 30,
            "started_at": "20200101_000000",  # very old
        }))
        monkeypatch.setattr("dashboard.backend.routes.pipeline.STATUS_DIR", status_dir)
        resp = client.get("/api/pipeline/status")
        data = resp.json()
        # writer should have timeout flag
        if "writer" in data["agents"]:
            assert data["agents"]["writer"].get("timeout") is True


class TestPipelineRerun:
    def test_rerun_valid_stage(self, client, monkeypatch):
        mock_popen = MagicMock()
        mock_popen.pid = 12345
        monkeypatch.setattr("dashboard.backend.routes.pipeline.subprocess.Popen", lambda *a, **kw: mock_popen)
        resp = client.post("/api/pipeline/rerun", json={"stage": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage"] == 3
        assert data["pid"] == 12345

    def test_rerun_invalid_stage_low(self, client):
        resp = client.post("/api/pipeline/rerun", json={"stage": 0})
        assert resp.status_code == 400

    def test_rerun_invalid_stage_high(self, client):
        resp = client.post("/api/pipeline/rerun", json={"stage": 8})
        assert resp.status_code == 400

    def test_rerun_subprocess_error(self, client, monkeypatch):
        monkeypatch.setattr(
            "dashboard.backend.routes.pipeline.subprocess.Popen",
            MagicMock(side_effect=OSError("spawn failed")),
        )
        resp = client.post("/api/pipeline/rerun", json={"stage": 2})
        assert resp.status_code == 500
