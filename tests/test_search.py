"""Tests for dashboard/backend/search.py — FTS5 search service."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dashboard.backend.search import (
    clean_text, index_kb_file, search_kb, get_index_stats,
    index_all_kb, _escape_fts5_token, _fallback_search,
    delete_from_index, auto_index_if_needed
)


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


class TestEscapeFts5Token:
    """Test _escape_fts5_token function."""

    def test_normal_text(self):
        assert _escape_fts5_token("hello") == "hello"

    def test_double_quotes_escaped(self):
        assert _escape_fts5_token('test"quote') == 'test""quote'

    def test_special_chars_removed(self):
        assert _escape_fts5_token("test*()") == "test"

    def test_chinese_text(self):
        assert _escape_fts5_token("中文测试") == "中文测试"

    def test_empty_string(self):
        assert _escape_fts5_token("") == ""


class TestIndexAllKb:
    """Test index_all_kb function."""

    def test_returns_stats_structure(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            stats = index_all_kb()

        assert "total_files" in stats
        assert "indexed" in stats
        assert "skipped" in stats
        assert "errors" in stats

    def test_handles_nonexistent_kb_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dashboard.backend.search.KB_DIR", tmp_path / "nonexistent")

        stats = index_all_kb()
        assert stats["total_files"] == 0

    def test_indexes_files(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        section_dir = kb_dir / "topics"
        section_dir.mkdir(parents=True)
        (section_dir / "test.md").write_text("# Test\nContent", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            stats = index_all_kb(force=True)

        assert stats["total_files"] == 1


class TestDeleteFromIndex:
    """Test delete_from_index function."""

    def test_deletes_path(self, monkeypatch):
        mock_conn = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            delete_from_index("topics/test.md")

        mock_conn.execute.assert_called_once()


class TestAutoIndexIfNeeded:
    """Test auto_index_if_needed function."""

    def test_rebuilds_when_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dashboard.backend.search.KB_DIR", tmp_path / "nonexistent")

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"count": 0}
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            with patch("dashboard.backend.search.index_all_kb") as mock_index:
                mock_index.return_value = {"total_files": 0, "indexed": 0, "skipped": 0, "errors": 0}
                auto_index_if_needed()

        mock_index.assert_called_once_with(force=True)

    def test_skips_when_index_populated(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"count": 100}
        mock_conn.execute.return_value.fetchall.return_value = [
            {"path": "topics/test.md"}
        ]
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            result = auto_index_if_needed()

        # Should not rebuild when index is populated
        assert result is None or result.get("total_files", 0) == 0

    def test_updates_when_new_files_found(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        section_dir = kb_dir / "topics"
        section_dir.mkdir(parents=True)
        for i in range(10):
            (section_dir / f"new-{i}.md").write_text(f"# New {i}\nContent", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"count": 50}
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            with patch("dashboard.backend.search.index_all_kb") as mock_index:
                mock_index.return_value = {"total_files": 10, "indexed": 10, "skipped": 0, "errors": 0}
                result = auto_index_if_needed()

        mock_index.assert_called_once_with(force=False)

    def test_handles_check_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dashboard.backend.search.KB_DIR", tmp_path / "nonexistent")

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("DB error")
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_conn)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch("dashboard.backend.search.get_db", return_value=mock_context):
            with patch("dashboard.backend.search.index_all_kb") as mock_index:
                mock_index.return_value = {"total_files": 0, "indexed": 0, "skipped": 0, "errors": 0}
                auto_index_if_needed()

        mock_index.assert_called_once_with(force=True)


class TestFallbackSearch:
    """Test _fallback_search function."""

    def test_finds_matching_file(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        section_dir = kb_dir / "topics"
        section_dir.mkdir(parents=True)
        (section_dir / "ai-guide.md").write_text("# AI Guide\n\n人工智能入门指南。", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        results = _fallback_search("人工智能", section=None, limit=20)

        assert len(results) == 1
        assert results[0]["title"] == "AI Guide"
        assert results[0]["section"] == "topics"
        assert results[0]["score"] == 1.0

    def test_section_filter(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        (kb_dir / "topics").mkdir(parents=True)
        (kb_dir / "topics" / "t1.md").write_text("# T1\nAI content", encoding="utf-8")
        (kb_dir / "viral").mkdir(parents=True)
        (kb_dir / "viral" / "v1.md").write_text("# V1\nAI content", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        results = _fallback_search("AI", section="viral", limit=20)

        assert len(results) == 1
        assert results[0]["section"] == "viral"

    def test_limit_respected(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        section_dir = kb_dir / "topics"
        section_dir.mkdir(parents=True)
        for i in range(5):
            (section_dir / f"f{i}.md").write_text(f"# F{i}\nAI content here", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        results = _fallback_search("AI", section=None, limit=2)

        assert len(results) <= 2

    def test_no_match(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        section_dir = kb_dir / "topics"
        section_dir.mkdir(parents=True)
        (section_dir / "test.md").write_text("# Test\nNo match here", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        results = _fallback_search("不存在的关键词", section=None, limit=20)

        assert len(results) == 0

    def test_no_heading_uses_stem(self, tmp_path, monkeypatch):
        kb_dir = tmp_path / "kb"
        section_dir = kb_dir / "topics"
        section_dir.mkdir(parents=True)
        (section_dir / "my-file.md").write_text("Just content with AI keyword", encoding="utf-8")

        monkeypatch.setattr("dashboard.backend.search.KB_DIR", kb_dir)

        results = _fallback_search("AI", section=None, limit=20)

        assert len(results) == 1
        assert results[0]["title"] == "my-file"
