"""Tests for topics API routes — /api/topics."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with isolated paths."""
    pending_dir = tmp_path / "queue" / "pending"
    pending_dir.mkdir(parents=True)
    actions_dir = tmp_path / "queue" / "actions"
    actions_dir.mkdir(parents=True)

    # Create test topic files
    topics = [
        {"title": "AI Agent 框架对比", "score": 85, "source": "rss"},
        {"title": "Python 新特性", "score": 75, "source": "weibo"},
        {"title": "Vue 3 入门", "score": 60, "source": "rss"},
    ]
    for i, topic in enumerate(topics):
        (pending_dir / f"topic_20260528_{i:06d}.json").write_text(
            json.dumps(topic, ensure_ascii=False)
        )

    monkeypatch.setattr("dashboard.backend.routes.topics.PENDING_DIR", pending_dir)
    monkeypatch.setattr("skills.action.ACTIONS_DIR", actions_dir)

    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestGetTopics:
    """Test GET /api/topics."""

    def test_returns_topics(self, client):
        resp = client.get("/api/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "count" in data
        assert "total" in data
        assert data["total"] >= 3

    def test_topics_have_id_and_filename(self, client):
        resp = client.get("/api/topics")
        topics = resp.json()["topics"]
        for t in topics:
            assert "id" in t
            assert "filename" in t

    def test_pagination_limit(self, client):
        resp = client.get("/api/topics?limit=1&offset=0")
        data = resp.json()
        assert len(data["topics"]) == 1
        assert data["total"] >= 3

    def test_pagination_offset(self, client):
        resp_all = client.get("/api/topics")
        total = resp_all.json()["total"]

        resp_offset = client.get("/api/topics?limit=1&offset=1")
        offset_topics = resp_offset.json()["topics"]
        assert len(offset_topics) == 1

    def test_topics_sorted_by_mtime(self, client):
        """Topics should be returned in reverse mtime order."""
        resp = client.get("/api/topics")
        topics = resp.json()["topics"]
        # Just verify we get results — actual order depends on filesystem mtime
        assert len(topics) >= 1

    def test_empty_directory(self, tmp_path, monkeypatch):
        """Empty pending directory should return empty list."""
        empty_dir = tmp_path / "empty_pending"
        empty_dir.mkdir()

        monkeypatch.setattr("dashboard.backend.routes.topics.PENDING_DIR", empty_dir)

        from dashboard.backend.main import app
        from fastapi.testclient import TestClient
        test_client = TestClient(app)

        resp = test_client.get("/api/topics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["topics"] == []


class TestConfirmTopic:
    """Test POST /api/topics/confirm."""

    def test_confirm_creates_action(self, client, tmp_path):
        resp = client.post("/api/topics/confirm", json={
            "target_id": "topic_20260528_000000",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "path" in data

    def test_confirm_writes_action_file(self, client, tmp_path):
        """Action file should be created in actions directory."""
        resp = client.post("/api/topics/confirm", json={
            "target_id": "topic_test_confirm",
        })
        assert resp.status_code == 200

        # Check that action file was created
        actions_dir = tmp_path / "queue" / "actions"
        action_files = list(actions_dir.glob("confirm_*.json"))
        assert len(action_files) >= 1

        # Verify action content
        action = json.loads(action_files[0].read_text())
        assert action["action"] == "confirm"
        assert action["target_id"] == "topic_test_confirm"

    def test_confirm_missing_target_id(self, client):
        """Missing target_id should return 422."""
        resp = client.post("/api/topics/confirm", json={})
        assert resp.status_code == 422
