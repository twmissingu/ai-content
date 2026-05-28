"""Tests for dashboard/backend/background.py — Background tasks."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dashboard.backend.background import _dispatch_action


class TestDispatchAction:
    """Test _dispatch_action function."""

    def test_confirm_action(self, tmp_path, monkeypatch):
        """Test confirm action writes flag file."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        topics_dir = tmp_path / "queue" / "topics"
        topics_dir.mkdir(parents=True)

        action = {"action": "confirm", "target_id": "topic-123"}
        result = _dispatch_action(action)

        assert result is True
        flag_file = topics_dir / "topic-123.confirmed"
        assert flag_file.exists()
        data = json.loads(flag_file.read_text())
        assert data["action"] == "confirm"

    def test_unknown_action(self):
        """Test unknown action returns False."""
        action = {"action": "unknown_type", "target_id": "test"}
        result = _dispatch_action(action)
        assert result is False

    def test_approve_action_success(self, tmp_path, monkeypatch):
        """Test approve action dispatches to publisher."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        # Create mock publisher script
        publisher = tmp_path / "skills" / "publisher.py"
        publisher.parent.mkdir(parents=True)
        publisher.write_text("print('published')")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK")
            action = {"action": "approve", "target_id": "article-456"}
            result = _dispatch_action(action)

        assert result is True

    def test_approve_action_failure(self, tmp_path, monkeypatch):
        """Test approve action handles subprocess failure."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        publisher = tmp_path / "skills" / "publisher.py"
        publisher.parent.mkdir(parents=True)
        publisher.write_text("print('published')")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Error")
            action = {"action": "approve", "target_id": "article-456"}
            result = _dispatch_action(action)

        assert result is False

    def test_approve_action_timeout(self, tmp_path, monkeypatch):
        """Test approve action handles timeout."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        publisher = tmp_path / "skills" / "publisher.py"
        publisher.parent.mkdir(parents=True)
        publisher.write_text("print('published')")

        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=300)):
            action = {"action": "approve", "target_id": "article-456"}
            result = _dispatch_action(action)

        assert result is False

    def test_reject_action_dispatches_to_writer(self, tmp_path, monkeypatch):
        """Test reject action dispatches to writer with --rewrite."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        writer = tmp_path / "skills" / "writer.py"
        writer.parent.mkdir(parents=True)
        writer.write_text("print('writer')")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK")
            action = {"action": "reject", "target_id": "article-789", "reason": "AI腔太重"}
            result = _dispatch_action(action)

        assert result is True
        # Verify --rewrite flag was passed
        call_args = mock_run.call_args[0][0]
        assert "--rewrite" in call_args

    def test_rewrite_action_dispatches_to_writer(self, tmp_path, monkeypatch):
        """Test rewrite action dispatches to writer."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        writer = tmp_path / "skills" / "writer.py"
        writer.parent.mkdir(parents=True)
        writer.write_text("print('writer')")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="OK")
            action = {"action": "rewrite", "target_id": "article-101"}
            result = _dispatch_action(action)

        assert result is True
