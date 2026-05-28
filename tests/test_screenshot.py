"""Tests for skills/screenshot.py — HTML to PNG screenshot pipeline."""

import json
import tempfile
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from skills.screenshot import html_to_png, batch_convert


class TestHtmlToPng:
    """Tests for html_to_png function."""

    def test_returns_none_when_playwright_not_installed(self, tmp_path):
        """Should return None when playwright is not available."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>Test</body></html>")

        # Save original modules
        original_modules = sys.modules.copy()

        # Remove playwright from sys.modules to simulate it not being installed
        sys.modules.pop("playwright", None)
        sys.modules.pop("playwright.sync_api", None)

        # Make import raise ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "playwright" or name.startswith("playwright."):
                raise ImportError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = html_to_png(html_file)
            assert result is None

        # Restore modules
        sys.modules.update(original_modules)

    def test_returns_output_path_on_success(self, tmp_path):
        """Should return the output path when screenshot succeeds."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>Test</body></html>")
        output_file = tmp_path / "test.png"

        # Create a mock playwright module
        mock_playwright_module = MagicMock()
        mock_sync_api = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright_module.sync_api = mock_sync_api
        mock_sync_api.sync_playwright.return_value = mock_playwright
        mock_playwright.__enter__ = MagicMock(return_value=mock_playwright)
        mock_playwright.__exit__ = MagicMock(return_value=False)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Add mock module to sys.modules
        sys.modules["playwright"] = mock_playwright_module
        sys.modules["playwright.sync_api"] = mock_sync_api

        try:
            result = html_to_png(html_file, output_file)
            assert result == output_file
            mock_page.goto.assert_called_once()
            mock_page.screenshot.assert_called_once()
        finally:
            # Clean up
            sys.modules.pop("playwright", None)
            sys.modules.pop("playwright.sync_api", None)

    def test_default_output_path(self, tmp_path):
        """Should use .png extension when no output path specified."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>Test</body></html>")

        # Create a mock playwright module
        mock_playwright_module = MagicMock()
        mock_sync_api = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright_module.sync_api = mock_sync_api
        mock_sync_api.sync_playwright.return_value = mock_playwright
        mock_playwright.__enter__ = MagicMock(return_value=mock_playwright)
        mock_playwright.__exit__ = MagicMock(return_value=False)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Add mock module to sys.modules
        sys.modules["playwright"] = mock_playwright_module
        sys.modules["playwright.sync_api"] = mock_sync_api

        try:
            result = html_to_png(html_file)
            assert result == tmp_path / "test.png"
        finally:
            # Clean up
            sys.modules.pop("playwright", None)
            sys.modules.pop("playwright.sync_api", None)

    def test_returns_none_on_exception(self, tmp_path):
        """Should return None when an exception occurs."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>Test</body></html>")

        # Create a mock playwright module that raises exception
        mock_playwright_module = MagicMock()
        mock_sync_api = MagicMock()
        mock_playwright_module.sync_api = mock_sync_api
        mock_sync_api.sync_playwright.side_effect = Exception("Browser error")

        # Add mock module to sys.modules
        sys.modules["playwright"] = mock_playwright_module
        sys.modules["playwright.sync_api"] = mock_sync_api

        try:
            result = html_to_png(html_file)
            assert result is None
        finally:
            # Clean up
            sys.modules.pop("playwright", None)
            sys.modules.pop("playwright.sync_api", None)

    def test_custom_dimensions(self, tmp_path):
        """Should use custom width and height for viewport."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>Test</body></html>")
        output_file = tmp_path / "test.png"

        # Create a mock playwright module
        mock_playwright_module = MagicMock()
        mock_sync_api = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright_module.sync_api = mock_sync_api
        mock_sync_api.sync_playwright.return_value = mock_playwright
        mock_playwright.__enter__ = MagicMock(return_value=mock_playwright)
        mock_playwright.__exit__ = MagicMock(return_value=False)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Add mock module to sys.modules
        sys.modules["playwright"] = mock_playwright_module
        sys.modules["playwright.sync_api"] = mock_sync_api

        try:
            html_to_png(html_file, output_file, width=800, height=600)
            mock_browser.new_page.assert_called_once_with(
                viewport={"width": 800, "height": 600},
                device_scale_factor=2,
            )
        finally:
            # Clean up
            sys.modules.pop("playwright", None)
            sys.modules.pop("playwright.sync_api", None)


class TestBatchConvert:
    """Tests for batch_convert function."""

    def test_converts_all_html_files(self, tmp_path):
        """Should convert all .html files in directory."""
        # Create test HTML files
        for i in range(3):
            (tmp_path / f"test{i}.html").write_text(f"<html><body>Test {i}</body></html>")

        # Create a mock playwright module
        mock_playwright_module = MagicMock()
        mock_sync_api = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright_module.sync_api = mock_sync_api
        mock_sync_api.sync_playwright.return_value = mock_playwright
        mock_playwright.__enter__ = MagicMock(return_value=mock_playwright)
        mock_playwright.__exit__ = MagicMock(return_value=False)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Add mock module to sys.modules
        sys.modules["playwright"] = mock_playwright_module
        sys.modules["playwright.sync_api"] = mock_sync_api

        try:
            results = batch_convert(tmp_path)
            assert len(results) == 3
            for r in results:
                assert r.endswith(".png")
        finally:
            # Clean up
            sys.modules.pop("playwright", None)
            sys.modules.pop("playwright.sync_api", None)

    def test_skips_non_html_files(self, tmp_path):
        """Should skip non-HTML files."""
        (tmp_path / "test.html").write_text("<html><body>Test</body></html>")
        (tmp_path / "test.txt").write_text("Not HTML")
        (tmp_path / "test.css").write_text("body {}")

        # Create a mock playwright module
        mock_playwright_module = MagicMock()
        mock_sync_api = MagicMock()
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright_module.sync_api = mock_sync_api
        mock_sync_api.sync_playwright.return_value = mock_playwright
        mock_playwright.__enter__ = MagicMock(return_value=mock_playwright)
        mock_playwright.__exit__ = MagicMock(return_value=False)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Add mock module to sys.modules
        sys.modules["playwright"] = mock_playwright_module
        sys.modules["playwright.sync_api"] = mock_sync_api

        try:
            results = batch_convert(tmp_path)
            assert len(results) == 1
        finally:
            # Clean up
            sys.modules.pop("playwright", None)
            sys.modules.pop("playwright.sync_api", None)

    def test_returns_empty_for_empty_directory(self, tmp_path):
        """Should return empty list for empty directory."""
        results = batch_convert(tmp_path)
        assert results == []

    def test_handles_failed_conversions(self, tmp_path):
        """Should skip files that fail to convert."""
        (tmp_path / "good.html").write_text("<html><body>Good</body></html>")
        (tmp_path / "bad.html").write_text("<html><body>Bad</body></html>")

        call_count = 0

        def mock_html_to_png(html_path, output_path=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if "bad" in html_path.name:
                return None
            return output_path or html_path.with_suffix(".png")

        with patch("skills.screenshot.html_to_png", side_effect=mock_html_to_png):
            results = batch_convert(tmp_path)

        assert len(results) == 1
        assert "good" in results[0]
