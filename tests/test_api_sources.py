"""Tests for sources API routes — /api/sources."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with isolated source files."""
    sources_dir = tmp_path / "queue" / "sources"
    sources_dir.mkdir(parents=True)

    # Create test source files
    source_data_1 = [
        {"title": "AI Agent 1", "source": "rss", "final_score": 85, "hot_value": 90},
        {"title": "Python Tips", "source": "rss", "final_score": 70, "hot_value": 60},
    ]
    source_data_2 = [
        {"title": "Vue 3 Guide", "source": "weibo", "final_score": 75, "raw_score": 65},
    ]
    (sources_dir / "sources_20260528.json").write_text(
        json.dumps(source_data_1, ensure_ascii=False)
    )
    (sources_dir / "sources_20260529.json").write_text(
        json.dumps(source_data_2, ensure_ascii=False)
    )

    monkeypatch.setattr("dashboard.backend.routes.sources.SOURCES_DIR", sources_dir)

    # Reset module-level cache
    import dashboard.backend.routes.sources as src_mod
    src_mod._sources_cache = {}
    src_mod._sources_cache_ts = 0

    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


class TestListSources:
    """Test GET /api/sources."""

    def test_returns_items(self, client):
        resp = client.get("/api/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3

    def test_filter_by_source(self, client):
        resp = client.get("/api/sources?source=rss")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["source"] == "rss"

    def test_filter_by_min_score(self, client):
        resp = client.get("/api/sources?min_score=80")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            score = item.get("final_score") or item.get("raw_score") or 0
            assert score >= 80

    def test_pagination(self, client):
        resp = client.get("/api/sources?limit=1&offset=0")
        data = resp.json()
        assert len(data["items"]) <= 1
        assert data["limit"] == 1
        assert data["offset"] == 0

    def test_items_sorted_by_score(self, client):
        resp = client.get("/api/sources")
        items = resp.json()["items"]
        scores = [i.get("hot_value") or i.get("final_score") or 0 for i in items]
        assert scores == sorted(scores, reverse=True)


class TestSourcesCaching:
    """Test caching behavior."""

    def test_cache_hit_returns_same_data(self, client):
        """Second call within TTL should return cached data."""
        resp1 = client.get("/api/sources")
        data1 = resp1.json()

        resp2 = client.get("/api/sources")
        data2 = resp2.json()

        assert data1 == data2

    def test_cache_expired_refreshes(self, client, tmp_path, monkeypatch):
        """After TTL expires, data should refresh."""
        resp1 = client.get("/api/sources")
        old_total = resp1.json()["total"]

        # Force cache expiry
        import dashboard.backend.routes.sources as src_mod
        src_mod._sources_cache.clear()

        # Add a new source file
        sources_dir = tmp_path / "queue" / "sources"
        new_data = [{"title": "New Item", "source": "test", "final_score": 99}]
        (sources_dir / "sources_new.json").write_text(json.dumps(new_data))

        resp2 = client.get("/api/sources")
        new_total = resp2.json()["total"]

        assert new_total >= old_total + 1

    def test_cache_stores_result(self, client):
        """Cache should store results after first call."""
        import dashboard.backend.routes.sources as src_mod

        client.get("/api/sources")

        assert "sources_10" in src_mod._sources_cache
        ts, _ = src_mod._sources_cache["sources_10"]
        assert ts > 0


class TestSourcesStats:
    """Test GET /api/sources/stats."""

    def test_returns_stats(self, client):
        resp = client.get("/api/sources/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_items" in data
        assert "by_source" in data
        assert "avg_score" in data
        assert "file_count" in data

    def test_by_source_counts(self, client):
        resp = client.get("/api/sources/stats")
        by_source = resp.json()["by_source"]
        assert "rss" in by_source
        assert by_source["rss"] >= 2

    def test_avg_score_is_numeric(self, client):
        resp = client.get("/api/sources/stats")
        assert isinstance(resp.json()["avg_score"], (int, float))
