"""Tests for approval API routes."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with isolated paths."""
    review_dir = tmp_path / "queue" / "review"
    review_dir.mkdir(parents=True)
    actions_dir = tmp_path / "queue" / "actions"
    actions_dir.mkdir(parents=True)

    monkeypatch.setattr("dashboard.backend.routes.approval.REVIEW_DIR", review_dir)
    monkeypatch.setattr("dashboard.backend.routes.approval.ACTIONS_DIR", actions_dir)
    monkeypatch.setattr("dashboard.backend.helpers.ACTIONS_DIR", actions_dir)

    # Create test article
    article_id = "test-article-001"
    (review_dir / f"{article_id}.md").write_text("# Test Article\n\nContent here.")
    (review_dir / f"{article_id}.meta.json").write_text(json.dumps({
        "topic": "Test Topic",
        "platform": "wechat",
        "proofread_score": 85,
        "word_count": 1500,
    }))

    # Mock database functions
    monkeypatch.setattr("dashboard.backend.routes.approval.get_pending_versions", lambda: [])
    monkeypatch.setattr("dashboard.backend.routes.approval.get_platform_versions", lambda sid: [])
    monkeypatch.setattr("dashboard.backend.routes.approval.create_approval_record", lambda **kw: None)
    monkeypatch.setattr("dashboard.backend.routes.approval.update_platform_version", lambda **kw: None)
    monkeypatch.setattr("dashboard.backend.routes.approval.get_approval_records", lambda limit=50: [])

    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestApprovalQueue:
    def test_returns_articles(self, client):
        resp = client.get("/api/approval/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert "articles" in data
        assert data["count"] >= 1

    def test_article_has_content_preview(self, client):
        resp = client.get("/api/approval/queue")
        articles = resp.json()["articles"]
        fs_articles = [a for a in articles if a["source"] == "filesystem"]
        assert len(fs_articles) >= 1
        assert "content_preview" in fs_articles[0]

    def test_article_has_meta(self, client):
        resp = client.get("/api/approval/queue")
        articles = resp.json()["articles"]
        fs_articles = [a for a in articles if a["source"] == "filesystem"]
        assert fs_articles[0]["meta"]["topic"] == "Test Topic"


class TestApprovalAct:
    def test_invalid_action_rejected(self, client):
        resp = client.post("/api/approval/act", json={
            "action": "invalid",
            "target_id": "test",
        })
        assert resp.status_code == 400

    def test_approve_creates_action_file(self, client, tmp_path, monkeypatch):
        actions = tmp_path / "queue" / "actions"
        monkeypatch.setattr("dashboard.backend.routes.approval.ACTIONS_DIR", actions)
        monkeypatch.setattr("dashboard.backend.helpers.ACTIONS_DIR", actions)
        resp = client.post("/api/approval/act", json={
            "action": "approve",
            "target_id": "test-article-001",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_reject_with_reason(self, client):
        resp = client.post("/api/approval/act", json={
            "action": "reject",
            "target_id": "test-article-001",
            "reason": "AI腔太重",
        })
        assert resp.status_code == 200


class TestApprovalVersions:
    def test_get_versions(self, client):
        resp = client.get("/api/approval/versions/1")
        assert resp.status_code == 200
        assert "versions" in resp.json()


class TestApprovalRecords:
    def test_get_records(self, client):
        resp = client.get("/api/approval/records")
        assert resp.status_code == 200
        assert "records" in resp.json()
