"""Tests for skills/publisher_toutiao.py — Toutiao publisher."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skills.publisher_toutiao import _get_article, publish


class TestGetArticle:
    """Tests for _get_article function."""

    def test_returns_article_data(self, tmp_path):
        """Should return title, content, and topic when article exists."""
        # Create mock review directory
        with patch("skills.publisher_toutiao.REVIEW_DIR", tmp_path):
            meta = {"topic": "Test Topic", "score": 85}
            (tmp_path / "test123.meta.json").write_text(json.dumps(meta))
            (tmp_path / "test123.md").write_text("# Test Article\n\nContent here.")

            title, content, topic = _get_article("test123")

        assert title == "Test Topic"
        assert "Content here" in content
        assert topic == "Test Topic"

    def test_returns_none_when_not_found(self, tmp_path):
        """Should return None values when article doesn't exist."""
        with patch("skills.publisher_toutiao.REVIEW_DIR", tmp_path):
            title, content, topic = _get_article("nonexistent")

        assert title is None
        assert content is None
        assert topic is None

    def test_falls_back_to_glob_search(self, tmp_path):
        """Should find article via glob when exact match fails."""
        with patch("skills.publisher_toutiao.REVIEW_DIR", tmp_path):
            meta = {"topic": "Fallback Topic"}
            # Create files that match the glob pattern
            (tmp_path / "20250101_test123_v2.meta.json").write_text(json.dumps(meta))
            (tmp_path / "20250101_test123_v2.md").write_text("# Fallback")

            title, content, topic = _get_article("test123")

        assert title == "Fallback Topic"
        assert "Fallback" in content

    def test_handles_missing_article_file(self, tmp_path):
        """Should handle case where meta exists but article doesn't."""
        with patch("skills.publisher_toutiao.REVIEW_DIR", tmp_path):
            meta = {"topic": "No Article"}
            (tmp_path / "test456.meta.json").write_text(json.dumps(meta))

            title, content, topic = _get_article("test456")

        assert title == "No Article"
        assert content == ""

    def test_uses_target_id_as_fallback_title(self, tmp_path):
        """Should use target_id as title when topic is not in meta."""
        with patch("skills.publisher_toutiao.REVIEW_DIR", tmp_path):
            meta = {"score": 90}
            (tmp_path / "test789.meta.json").write_text(json.dumps(meta))
            (tmp_path / "test789.md").write_text("# Content")

            title, content, topic = _get_article("test789")

        assert title == "test789"


class TestPublish:
    """Tests for publish function."""

    def test_returns_false_when_playwright_not_installed(self):
        """Should return False when playwright is not available."""
        # Save original modules
        original_modules = sys.modules.copy()

        # Remove playwright from sys.modules
        sys.modules.pop("playwright", None)
        sys.modules.pop("playwright.sync_api", None)

        # Make import raise ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "playwright" or name.startswith("playwright."):
                raise ImportError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = publish("test123")
            assert result is False

        # Restore modules
        sys.modules.update(original_modules)

    def test_returns_false_when_article_not_found(self, tmp_path):
        """Should return False when article doesn't exist."""
        with patch("skills.publisher_toutiao.REVIEW_DIR", tmp_path):
            # Create a mock playwright module
            mock_playwright_module = MagicMock()
            mock_sync_api = MagicMock()
            mock_playwright_module.sync_api = mock_sync_api

            # Add mock module to sys.modules
            sys.modules["playwright"] = mock_playwright_module
            sys.modules["playwright.sync_api"] = mock_sync_api

            try:
                result = publish("nonexistent")
                assert result is False
            finally:
                # Clean up
                sys.modules.pop("playwright", None)
                sys.modules.pop("playwright.sync_api", None)

    def test_returns_true_on_success(self, tmp_path):
        """Should return True when publishing succeeds."""
        with patch("skills.publisher_toutiao.REVIEW_DIR", tmp_path):
            meta = {"topic": "Test Topic"}
            (tmp_path / "test123.meta.json").write_text(json.dumps(meta))
            (tmp_path / "test123.md").write_text("# Test Article")

            # Create a mock playwright module
            mock_playwright_module = MagicMock()
            mock_sync_api = MagicMock()
            mock_playwright = MagicMock()
            mock_browser = MagicMock()
            mock_context = MagicMock()
            mock_page = MagicMock()

            mock_playwright_module.sync_api = mock_sync_api
            mock_sync_api.sync_playwright.return_value = mock_playwright
            mock_playwright.__enter__ = MagicMock(return_value=mock_playwright)
            mock_playwright.__exit__ = MagicMock(return_value=False)
            mock_playwright.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page
            mock_page.locator.return_value.count.return_value = 0
            mock_page.locator.return_value.is_visible.return_value = False

            # Add mock module to sys.modules
            sys.modules["playwright"] = mock_playwright_module
            sys.modules["playwright.sync_api"] = mock_sync_api

            try:
                with patch("skills.publisher_toutiao.STATE_FILE", tmp_path / "state.json"):
                    result = publish("test123")
                    assert result is True
                    mock_browser.close.assert_called()
            finally:
                # Clean up
                sys.modules.pop("playwright", None)
                sys.modules.pop("playwright.sync_api", None)

    def test_records_failure_on_exception(self, tmp_path):
        """Should record failure to FAILED_DIR on exception."""
        with patch("skills.publisher_toutiao.REVIEW_DIR", tmp_path):
            with patch("skills.publisher_toutiao.FAILED_DIR", tmp_path / "failed"):
                (tmp_path / "failed").mkdir(exist_ok=True)
                meta = {"topic": "Test Topic"}
                (tmp_path / "test123.meta.json").write_text(json.dumps(meta))
                (tmp_path / "test123.md").write_text("# Test Article")

                # Create a mock playwright module that raises exception
                mock_playwright_module = MagicMock()
                mock_sync_api = MagicMock()
                mock_playwright_module.sync_api = mock_sync_api
                mock_sync_api.sync_playwright.side_effect = Exception("Browser error")

                # Add mock module to sys.modules
                sys.modules["playwright"] = mock_playwright_module
                sys.modules["playwright.sync_api"] = mock_sync_api

                try:
                    with patch("skills.publisher_toutiao.STATE_FILE", tmp_path / "state.json"):
                        result = publish("test123")
                        assert result is False
                        failed_file = tmp_path / "failed" / "toutiao_test123.json"
                        assert failed_file.exists()
                        failed_data = json.loads(failed_file.read_text())
                        assert failed_data["platform"] == "toutiao"
                        assert "Browser error" in failed_data["error"]
                finally:
                    # Clean up
                    sys.modules.pop("playwright", None)
                    sys.modules.pop("playwright.sync_api", None)
