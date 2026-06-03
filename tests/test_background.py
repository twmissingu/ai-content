"""Tests for dashboard/backend/background.py — Background tasks."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dashboard.backend.background import _dispatch_action_async


class TestDispatchAction:
    """Test _dispatch_action_async function."""

    def test_confirm_action(self, tmp_path, monkeypatch):
        """Test confirm action dispatches to writer_router and writes action file."""
        import re as _re
        # Need to mock write_action's target_id validation
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )
        # write_action validates target_id format
        monkeypatch.setattr(
            "skills.action.ACTIONS_DIR",
            tmp_path / "queue" / "actions"
        )

        actions_dir = tmp_path / "queue" / "actions"

        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with patch("subprocess.Popen", return_value=mock_proc):
            action = {"action": "confirm", "target_id": "topic-123"}
            result = _dispatch_action_async(action)

        assert result == 12345
        # Confirm action writes to queue/actions/ via write_action
        action_files = list(actions_dir.glob("confirm_topic-123_*.json"))
        assert len(action_files) == 1
        data = json.loads(action_files[0].read_text())
        assert data["action"] == "confirm"

    def test_unknown_action(self):
        """Test unknown action returns -1."""
        action = {"action": "unknown_type", "target_id": "test"}
        result = _dispatch_action_async(action)
        assert result == -1

    def test_approve_action_success(self, tmp_path, monkeypatch):
        """Test approve action dispatches to publisher."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        publisher = tmp_path / "skills" / "publisher.py"
        publisher.parent.mkdir(parents=True)
        publisher.write_text("print('published')")

        mock_proc = MagicMock()
        mock_proc.pid = 99999

        with patch("subprocess.Popen", return_value=mock_proc):
            action = {"action": "approve", "target_id": "article-456"}
            result = _dispatch_action_async(action)

        assert result == 99999

    def test_approve_action_failure(self, tmp_path, monkeypatch):
        """Test approve action handles subprocess failure."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        publisher = tmp_path / "skills" / "publisher.py"
        publisher.parent.mkdir(parents=True)
        publisher.write_text("print('published')")

        with patch("subprocess.Popen", side_effect=OSError("spawn failed")):
            action = {"action": "approve", "target_id": "article-456"}
            result = _dispatch_action_async(action)

        assert result == -1

    def test_reject_action_dispatches_to_writer(self, tmp_path, monkeypatch):
        """Test reject action dispatches to writer with --rewrite."""
        monkeypatch.setattr(
            "dashboard.backend.background.PROJECT_ROOT",
            tmp_path
        )

        writer = tmp_path / "skills" / "writer.py"
        writer.parent.mkdir(parents=True)
        writer.write_text("print('writer')")

        mock_proc = MagicMock()
        mock_proc.pid = 77777

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            action = {"action": "reject", "target_id": "article-789", "reason": "AI腔太重"}
            result = _dispatch_action_async(action)

        assert result == 77777
        # Verify --rewrite flag was passed
        call_args = mock_popen.call_args[0][0]
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

        mock_proc = MagicMock()
        mock_proc.pid = 88888

        with patch("subprocess.Popen", return_value=mock_proc):
            action = {"action": "rewrite", "target_id": "article-101"}
            result = _dispatch_action_async(action)

        assert result == 88888
