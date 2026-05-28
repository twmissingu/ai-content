"""Tests for knowledge base API routes."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with isolated paths."""
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir(parents=True)
    (kb_dir / "tech").mkdir()
    (kb_dir / "tech" / "ai-basics.md").write_text("# AI Basics\n\n人工智能基础介绍。")
    (kb_dir / "history").mkdir()

    monkeypatch.setattr("dashboard.backend.routes.kb.KB_DIR", kb_dir)
    monkeypatch.setattr("dashboard.backend.routes.kb.search_kb_fts", lambda q, section=None, limit=20: [
        {"path": "tech/ai-basics.md", "title": "AI Basics", "snippet": "人工智能基础"},
    ])
    monkeypatch.setattr("dashboard.backend.routes.kb.get_index_stats", lambda: {
        "total_indexed": 10,
        "by_section": {"tech": 5, "history": 3},
    })
    monkeypatch.setattr("dashboard.backend.routes.kb.index_all_kb", lambda force=False: {
        "indexed": 10, "errors": 0,
    })

    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestKBSearch:
    def test_returns_results(self, client):
        resp = client.get("/api/kb/search?q=AI")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert data["count"] >= 1

    def test_has_query(self, client):
        resp = client.get("/api/kb/search?q=test")
        data = resp.json()
        assert data["query"] == "test"

    def test_search_type(self, client):
        resp = client.get("/api/kb/search?q=test")
        data = resp.json()
        assert data["search_type"] == "fts5"


class TestKBSections:
    def test_returns_sections(self, client):
        resp = client.get("/api/kb/sections")
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data

    def test_section_has_name(self, client):
        resp = client.get("/api/kb/sections")
        sections = resp.json()["sections"]
        names = [s["name"] for s in sections]
        assert "tech" in names


class TestKBReindex:
    def test_reindex(self, client):
        resp = client.post("/api/kb/reindex")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestKBSearchFallback:
    """Test KB search fallback when FTS5 fails."""

    @pytest.fixture
    def fallback_client(self, tmp_path, monkeypatch):
        """Client where FTS5 search raises an exception."""
        kb_dir = tmp_path / "kb"
        tech_dir = kb_dir / "tech"
        tech_dir.mkdir(parents=True)
        (tech_dir / "ai-guide.md").write_text("# AI Guide\n\n人工智能入门。", encoding="utf-8")
        (tech_dir / "python.md").write_text("# Python\n\nPython编程基础。", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.routes.kb.KB_DIR", kb_dir)

        # Make FTS5 search raise an exception
        def failing_search(q, section=None, limit=20):
            raise Exception("FTS5 not available")

        monkeypatch.setattr("dashboard.backend.routes.kb.search_kb_fts", failing_search)
        monkeypatch.setattr("dashboard.backend.routes.kb.get_index_stats", lambda: {"total_indexed": 0, "by_section": {}})
        monkeypatch.setattr("dashboard.backend.routes.kb.index_all_kb", lambda force=False: {"indexed": 0, "errors": 0})

        from dashboard.backend.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_fallback_search_returns_results(self, fallback_client):
        resp = fallback_client.get("/api/kb/search?q=人工智能")
        assert resp.status_code == 200
        data = resp.json()
        assert data["search_type"] == "fallback"

    def test_fallback_search_matches_filename(self, fallback_client):
        resp = fallback_client.get("/api/kb/search?q=ai-guide")
        data = resp.json()
        assert data["count"] >= 1
