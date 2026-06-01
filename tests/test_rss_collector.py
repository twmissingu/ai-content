"""Tests for skills/rss_collector.py — RSS feed collection and processing."""

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestParseEntry:
    """Test _parse_entry normalization."""

    def test_parses_valid_entry(self):
        from skills.rss_collector import _parse_entry
        entry = {
            "title": "Test Article Title",
            "link": "https://example.com/article1",
            "summary": "A brief description of the article.",
            "published_parsed": (2025, 1, 15, 10, 30, 0, 0, 0, 0),
        }
        result = _parse_entry(entry, source_label="test_feed", rss_type="direct")
        assert result is not None
        assert result["title"] == "Test Article Title"
        assert result["url"] == "https://example.com/article1"
        assert result["source"] == "rss"
        assert result["rss_source"] == "direct"
        assert result["rss_label"] == "test_feed"
        assert result["hot_value"] == 60
        assert "content_hash" in result
        assert "keywords" in result

    def test_rejects_empty_title(self):
        from skills.rss_collector import _parse_entry
        entry = {"title": "", "link": "https://example.com/"}
        result = _parse_entry(entry, "test", "direct")
        assert result is None

    def test_rejects_short_title(self):
        from skills.rss_collector import _parse_entry
        entry = {"title": "Hi", "link": "https://example.com/"}
        result = _parse_entry(entry, "test", "direct")
        assert result is None

    def test_uses_id_as_fallback_link(self):
        from skills.rss_collector import _parse_entry
        entry = {
            "title": "Article with no link field",
            "id": "https://example.com/fallback",
        }
        result = _parse_entry(entry, "test", "direct")
        assert result is not None
        assert result["url"] == "https://example.com/fallback"

    def test_uses_links_as_fallback(self):
        from skills.rss_collector import _parse_entry
        entry = {
            "title": "Article with links array",
            "links": [{"href": "https://example.com/links-fallback"}],
        }
        result = _parse_entry(entry, "test", "direct")
        assert result is not None
        assert result["url"] == "https://example.com/links-fallback"

    def test_truncates_long_description(self):
        from skills.rss_collector import _parse_entry
        entry = {
            "title": "Article with long description",
            "link": "https://example.com/",
            "summary": "x" * 1000,
        }
        result = _parse_entry(entry, "test", "direct")
        assert len(result["description"]) <= 500

    def test_generates_content_hash(self):
        from skills.rss_collector import _parse_entry
        entry = {"title": "Unique Title", "link": "https://example.com/unique"}
        result = _parse_entry(entry, "test", "direct")
        assert len(result["content_hash"]) == 16

    def test_same_entry_produces_same_hash(self):
        from skills.rss_collector import _parse_entry
        entry = {"title": "Same Title", "link": "https://example.com/same"}
        r1 = _parse_entry(entry, "test", "direct")
        r2 = _parse_entry(entry, "test", "direct")
        assert r1["content_hash"] == r2["content_hash"]

    def test_handles_missing_published(self):
        from skills.rss_collector import _parse_entry
        entry = {"title": "No Published Date", "link": "https://example.com/"}
        result = _parse_entry(entry, "test", "direct")
        assert result is not None
        assert "published_at" in result


class TestLoadCachedHashes:
    """Test _load_cached_hashes from cache directory."""

    def test_returns_empty_set_for_empty_dir(self, tmp_path):
        from skills.rss_collector import _load_cached_hashes
        with patch("skills.rss_collector.RSS_CACHE_DIR", tmp_path):
            hashes = _load_cached_hashes()
            assert hashes == set()

    def test_loads_hashes_from_files(self, tmp_path):
        from skills.rss_collector import _load_cached_hashes
        # Create cache files
        for h in ["abc123", "def456"]:
            (tmp_path / f"{h}.json").write_text(json.dumps({"content_hash": h}))

        with patch("skills.rss_collector.RSS_CACHE_DIR", tmp_path):
            hashes = _load_cached_hashes()
            assert "abc123" in hashes
            assert "def456" in hashes

    def test_skips_malformed_json(self, tmp_path):
        from skills.rss_collector import _load_cached_hashes
        (tmp_path / "bad.json").write_text("not valid json{{{")
        (tmp_path / "good.json").write_text(json.dumps({"content_hash": "good123"}))

        with patch("skills.rss_collector.RSS_CACHE_DIR", tmp_path):
            hashes = _load_cached_hashes()
            assert "good123" in hashes

    def test_skips_non_json_files(self, tmp_path):
        from skills.rss_collector import _load_cached_hashes
        (tmp_path / "notes.txt").write_text("not a json file")
        (tmp_path / "valid.json").write_text(json.dumps({"content_hash": "valid1"}))

        with patch("skills.rss_collector.RSS_CACHE_DIR", tmp_path):
            hashes = _load_cached_hashes()
            assert hashes == {"valid1"}


class TestSaveCached:
    """Test _save_cached write logic."""

    def test_writes_new_items(self, tmp_path):
        from skills.rss_collector import _save_cached
        items = [
            {"content_hash": "hash1", "title": "Article 1"},
            {"content_hash": "hash2", "title": "Article 2"},
        ]

        with patch("skills.rss_collector.RSS_CACHE_DIR", tmp_path):
            _save_cached(items)

        assert (tmp_path / "hash1.json").exists()
        assert (tmp_path / "hash2.json").exists()

    def test_skips_duplicate_hashes(self, tmp_path):
        from skills.rss_collector import _save_cached
        items = [{"content_hash": "dup1", "title": "First"}]
        with patch("skills.rss_collector.RSS_CACHE_DIR", tmp_path):
            _save_cached(items)
            # Write same hash again — should be skipped
            _save_cached([{"content_hash": "dup1", "title": "Duplicate"}])

        data = json.loads((tmp_path / "dup1.json").read_text())
        assert data["title"] == "First"  # Original preserved

    def test_empty_items_list(self, tmp_path):
        from skills.rss_collector import _save_cached
        with patch("skills.rss_collector.RSS_CACHE_DIR", tmp_path):
            _save_cached([])
        assert list(tmp_path.iterdir()) == []


class TestWriteCandidates:
    """Test _write_candidates batch writing."""

    def test_writes_batch_file(self, tmp_path):
        from skills.rss_collector import _write_candidates
        items = [{"content_hash": "h1", "title": "Item 1"}]

        with patch("skills.rss_collector.RSS_CANDIDATES_DIR", tmp_path):
            _write_candidates(items)

        batch_files = list(tmp_path.glob("batch-*.json"))
        assert len(batch_files) == 1
        data = json.loads(batch_files[0].read_text())
        assert len(data) == 1

    def test_cleans_old_candidates(self, tmp_path):
        from skills.rss_collector import _write_candidates
        # Create an old file (50 hours ago)
        old_file = tmp_path / "batch-old.json"
        old_file.write_text("[]")
        old_time = time.time() - 50 * 3600
        import os
        os.utime(old_file, (old_time, old_time))

        with patch("skills.rss_collector.RSS_CANDIDATES_DIR", tmp_path):
            _write_candidates([{"content_hash": "new1", "title": "New"}])

        assert not old_file.exists()
        assert len(list(tmp_path.glob("batch-*.json"))) == 1

    def test_preserves_recent_candidates(self, tmp_path):
        from skills.rss_collector import _write_candidates
        recent_file = tmp_path / "batch-recent.json"
        recent_file.write_text('[{"title": "recent"}]')

        with patch("skills.rss_collector.RSS_CANDIDATES_DIR", tmp_path):
            _write_candidates([{"content_hash": "new1", "title": "New"}])

        assert recent_file.exists()


class TestCollectOnce:
    """Test the main collect_once function."""

    def test_runs_without_error_on_empty_config(self, tmp_path):
        from skills.rss_collector import collect_once
        with patch("skills.rss_collector._load_rss_config", return_value={}), \
             patch("skills.rss_collector._load_rss_collector_config", return_value={"base_item_cap": 20}), \
             patch("skills.rss_collector.RSS_CANDIDATES_DIR", tmp_path), \
             patch("skills.rss_collector.RSS_CACHE_DIR", tmp_path / "cache"):
            (tmp_path / "cache").mkdir(exist_ok=True)
            collect_once()  # Should not raise
