"""Tests for manual review (人工抽检) database and API."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(tempfile.mkdtemp()) / "test_analytics.db"


@pytest.fixture(autouse=True)
def mock_db_path(monkeypatch):
    """Mock database path for testing."""
    import dashboard.backend.database as db
    import dashboard.backend.database.core as db_core

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    import threading
    local = db_core._thread_local
    if hasattr(local, 'conn') and local.conn is not None:
        local.conn.close()
    local.conn = None

    monkeypatch.setattr(db, 'DATABASE_PATH', TEST_DB_PATH)
    monkeypatch.setattr(db_core, 'DATABASE_PATH', TEST_DB_PATH)
    db._invalidate_cache()
    db.init_db()
    yield

    if hasattr(local, 'conn') and local.conn is not None:
        local.conn.close()
        local.conn = None
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def client():
    from dashboard.backend.main import app
    return TestClient(app)


class TestCreateManualReview:
    """Test creating manual reviews."""

    def test_create_review_normal(self, client):
        resp = client.post("/api/reviews", json={
            "article_title": "Test Article",
            "llm_score": 80,
            "human_score": 78,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["score_diff"] == 2
        assert data["status"] == "normal"

    def test_create_review_warning(self, client):
        resp = client.post("/api/reviews", json={
            "article_title": "Test Article",
            "llm_score": 80,
            "human_score": 60,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["score_diff"] == 20
        assert data["status"] == "warning"

    def test_create_review_critical(self, client):
        resp = client.post("/api/reviews", json={
            "article_title": "Test Article",
            "llm_score": 90,
            "human_score": 50,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["score_diff"] == 40
        assert data["status"] == "critical"

    def test_create_review_without_llm_score(self, client):
        resp = client.post("/api/reviews", json={
            "article_title": "Test Article",
            "human_score": 75,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["score_diff"] == 0
        assert data["status"] == "normal"
        assert data["llm_score"] is None


class TestListReviews:
    """Test listing manual reviews."""

    def test_list_reviews_empty(self, client):
        resp = client.get("/api/reviews")
        assert resp.status_code == 200
        assert resp.json()["reviews"] == []

    def test_list_reviews_with_data(self, client):
        client.post("/api/reviews", json={
            "article_title": "Article 1", "llm_score": 80, "human_score": 78,
        })
        client.post("/api/reviews", json={
            "article_title": "Article 2", "llm_score": 90, "human_score": 50,
        })
        resp = client.get("/api/reviews")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_reviews_filter_by_status(self, client):
        client.post("/api/reviews", json={
            "article_title": "Normal", "llm_score": 80, "human_score": 78,
        })
        client.post("/api/reviews", json={
            "article_title": "Critical", "llm_score": 90, "human_score": 50,
        })
        resp = client.get("/api/reviews?status=critical")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["reviews"][0]["article_title"] == "Critical"


class TestReviewStats:
    """Test review statistics."""

    def test_stats_empty(self, client):
        resp = client.get("/api/reviews/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reviews"] == 0
        assert data["avg_score_diff"] == 0

    def test_stats_with_data(self, client):
        client.post("/api/reviews", json={
            "llm_score": 80, "human_score": 78,  # diff=2
        })
        client.post("/api/reviews", json={
            "llm_score": 90, "human_score": 50,  # diff=40
        })
        resp = client.get("/api/reviews/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reviews"] == 2
        assert data["avg_score_diff"] == 21.0
        assert data["warning_count"] == 0
        assert data["critical_count"] == 1


class TestPendingReviews:
    """Test pending review articles."""

    def test_pending_empty(self, client):
        resp = client.get("/api/reviews/pending")
        assert resp.status_code == 200
        assert resp.json()["articles"] == []
