"""Tests for dashboard/backend/search.py — FTS5 search service."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dashboard.backend.search import clean_text, index_kb_file, search_kb, get_index_stats


class TestCleanText:
    """Test clean_text function."""

    def test_headers_removed(self):
        assert clean_text("# Title\n## Subtitle") == "Title\nSubtitle"

    def test_bold_removed(self):
        assert clean_text("**bold** text") == "bold text"

    def test_italic_removed(self):
        assert clean_text("*italic* text") == "italic text"

    def test_links_extracted(self):
        assert clean_text("[text](url)") == "text"

    def test_code_blocks_removed(self):
        text = "before\n```python\ncode\n```\nafter"
        result = clean_text(text)
        assert "code" not in result
        assert "before" in result
        assert "after" in result

    def test_inline_code_cleaned(self):
        assert clean_text("use `code` here") == "use code here"

    def test_images_removed(self):
        result = clean_text("![alt](url)")
        # Image markdown should be removed or stripped
        assert "url" not in result

    def test_multiple_newlines_normalized(self):
        assert clean_text("a\n\n\n\nb") == "a\nb"

    def test_multiple_spaces_normalized(self):
        assert clean_text("a   b") == "a b"

    def test_empty_input(self):
        assert clean_text("") == ""

    def test_chinese_text_preserved(self):
        text = "这是中文内容，保持不变"
        assert clean_text(text) == text


class TestIndexKbFile:
    """Test index_kb_file function."""

    def test_index_new_file(self, tmp_path, monkeypatch):
        # Create a test markdown file
        kb_dir = tmp_path / "kb"
        section_dir = kb_dir / "topics"
        section_dir.mkdir(parents=True)
        test_file = section_dir / "test.md"
        test_file.write_text("# Test Title\n\nSome content here.", encoding="utf-8")

        # Mock KB_DIR
        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        # Mock get_db
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            result = index_kb_file(test_file)

        assert result is True
        mock_conn.execute.assert_called()

    def test_index_existing_file(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        section_dir = kb_dir / "topics"
        section_dir.mkdir(parents=True)
        test_file = section_dir / "test.md"
        test_file.write_text("# Updated Title\n\nUpdated content.", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ("topics/test.md",)
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            result = index_kb_file(test_file)

        assert result is True

    def test_index_file_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dashboard.backend.search.KB_DIR", tmp_path)

        # Non-existent file should return False
        result = index_kb_file(tmp_path / "nonexistent.md")
        assert result is False


class TestSearchKb:
    """Test search_kb function."""

    def test_basic_search(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            {
                "path": "topics/test.md",
                "title": "Test Title",
                "section": "topics",
                "match_snippet": "Test content here",
                "rank": -1.0,
            }
        ]
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            results = search_kb("test")

        assert len(results) == 1
        assert results[0]["title"] == "Test Title"

    def test_search_with_section_filter(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            results = search_kb("test", section="topics")

        assert len(results) == 0

    def test_search_empty_query(self):
        results = search_kb("")
        assert results == []

    def test_search_special_characters(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            results = search_kb('test "quote" *star*')

        assert len(results) == 0


class TestGetIndexStats:
    """Test get_index_stats function."""

    def test_returns_stats(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"count": 42}
        mock_conn.execute.return_value.fetchall.return_value = [
            {"section": "topics", "count": 20},
            {"section": "viral", "count": 22},
        ]
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            stats = get_index_stats()

        assert "total_indexed" in stats
        assert "by_section" in stats

    def test_empty_index(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"count": 0}
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            stats = get_index_stats()

        assert stats["total_indexed"] == 0
