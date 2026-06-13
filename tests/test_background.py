"""Tests for dashboard/backend/background.py — Background tasks."""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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


# ── TopicTimeoutPoller tests ────────────────────────────────────────


def _create_topic(pending_dir, name, score, age_minutes):
    """Helper: create a topic file with a given age (in minutes)."""
    path = pending_dir / f"{name}.json"
    path.write_text(json.dumps({
        "title": f"Topic {name}",
        "score": score,
        "source": "rss",
    }))
    old_time = time.time() - (age_minutes * 60)
    os.utime(path, (old_time, old_time))
    return path


def _create_review_article(review_dir, article_id, age_minutes):
    """Helper: create a review article with a given age (in minutes)."""
    meta_path = review_dir / f"{article_id}.meta.json"
    meta_path.write_text(json.dumps({
        "topic": f"Article {article_id}",
        "platform": "wechat",
        "proofread_score": 85,
    }))
    md_path = review_dir / f"{article_id}.md"
    md_path.write_text(f"# Article {article_id}\n\nContent here.")
    old_time = time.time() - (age_minutes * 60)
    os.utime(meta_path, (old_time, old_time))
    os.utime(md_path, (old_time, old_time))
    return meta_path


class TestTopicTimeoutTarget:
    """Test topic_timeout_target — auto-confirm highest-score expired topic."""

    def test_confirms_highest_score_expired_topic(self, tmp_path):
        """Expired topics: should auto-confirm the one with the highest score."""
        from dashboard.backend.background import topic_timeout_target

        pending = tmp_path / "pending"
        pending.mkdir()
        actions = tmp_path / "actions"
        actions.mkdir()

        _create_topic(pending, "topic_old_low", 60, 45)
        _create_topic(pending, "topic_old_high", 90, 40)
        _create_topic(pending, "topic_old_mid", 75, 35)

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 30}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_topic_timeout"):
            topic_timeout_target()

        mock_write.assert_called_once()
        call_kwargs = mock_write.call_args
        assert call_kwargs[0][0] == "confirm"
        assert call_kwargs[0][1] == "topic_old_high"

    def test_ignores_fresh_topics(self, tmp_path):
        """Topics younger than timeout threshold should be left alone."""
        from dashboard.backend.background import topic_timeout_target

        pending = tmp_path / "pending"
        pending.mkdir()

        _create_topic(pending, "topic_fresh", 85, 10)

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 30}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_topic_timeout"):
            topic_timeout_target()

        mock_write.assert_not_called()

    def test_no_pending_topics(self, tmp_path):
        """Empty pending directory should be a no-op."""
        from dashboard.backend.background import topic_timeout_target

        pending = tmp_path / "pending"
        pending.mkdir()

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 30}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_topic_timeout"):
            topic_timeout_target()

        mock_write.assert_not_called()

    def test_feishu_notification_sent(self, tmp_path):
        """Timeout event should trigger Feishu notification."""
        from dashboard.backend.background import topic_timeout_target

        pending = tmp_path / "pending"
        pending.mkdir()
        _create_topic(pending, "topic_notify", 80, 50)

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 30}), \
             patch("dashboard.backend.background.write_action"), \
             patch("dashboard.backend.background.alert_topic_timeout") as mock_alert:
            topic_timeout_target()

        mock_alert.assert_called_once()

    def test_timeout_threshold_from_config(self, tmp_path):
        """Timeout threshold should be read from quality_gates.json."""
        from dashboard.backend.background import topic_timeout_target

        pending = tmp_path / "pending"
        pending.mkdir()
        _create_topic(pending, "topic_custom", 70, 15)

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 10}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_topic_timeout"):
            topic_timeout_target()

        mock_write.assert_called_once()
        assert mock_write.call_args[0][1] == "topic_custom"

    def test_timeout_records_in_sqlite(self, tmp_path):
        """Timeout event should be recorded in SQLite."""
        from dashboard.backend.background import topic_timeout_target
        from dashboard.backend.database import get_db

        pending = tmp_path / "pending"
        pending.mkdir()
        _create_topic(pending, "topic_db", 80, 50)

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 30}), \
             patch("dashboard.backend.background.write_action"), \
             patch("dashboard.backend.background.alert_topic_timeout"):
            topic_timeout_target()

        # Verify DB records were created via raw SQL
        with get_db() as conn:
            session = conn.execute(
                "SELECT * FROM pipeline_sessions WHERE topic LIKE 'timeout-confirm:topic_db%'"
            ).fetchone()
            assert session is not None
            trace = conn.execute(
                "SELECT * FROM pipeline_traces WHERE session_id = ?", (session['id'],)
            ).fetchone()
            assert trace is not None
            assert trace['status'] == 'completed'


# ── ApprovalTimeoutPoller tests ─────────────────────────────────────


class TestApprovalTimeoutTarget:
    """Test approval_timeout_target — auto-skip expired review articles."""

    def test_skips_expired_articles(self, tmp_path):
        """Articles older than threshold should be marked as skipped."""
        from dashboard.backend.background import approval_timeout_target

        review = tmp_path / "review"
        review.mkdir()
        actions = tmp_path / "actions"
        actions.mkdir()

        _create_review_article(review, "expired-article-001", 150)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        mock_write.assert_called_once()
        call_args = mock_write.call_args
        assert call_args[0][0] == "skip"
        assert call_args[0][1] == "expired-article-001"

    def test_ignores_fresh_articles(self, tmp_path):
        """Articles younger than threshold should not be skipped."""
        from dashboard.backend.background import approval_timeout_target

        review = tmp_path / "review"
        review.mkdir()

        _create_review_article(review, "fresh-article", 60)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        mock_write.assert_not_called()

    def test_no_review_articles(self, tmp_path):
        """Empty review directory should be a no-op."""
        from dashboard.backend.background import approval_timeout_target

        review = tmp_path / "review"
        review.mkdir()

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        mock_write.assert_not_called()

    def test_feishu_notification_sent(self, tmp_path):
        """Approval timeout should trigger Feishu notification."""
        from dashboard.backend.background import approval_timeout_target

        review = tmp_path / "review"
        review.mkdir()
        _create_review_article(review, "notify-article", 150)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action"), \
             patch("dashboard.backend.background.alert_approval_timeout") as mock_alert:
            approval_timeout_target()

        mock_alert.assert_called_once()

    def test_timeout_records_in_sqlite(self, tmp_path):
        """Approval timeout should be recorded in SQLite."""
        from dashboard.backend.background import approval_timeout_target
        from dashboard.backend.database import get_db

        review = tmp_path / "review"
        review.mkdir()
        _create_review_article(review, "db-article", 150)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action"), \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        # Verify DB records were created via raw SQL
        with get_db() as conn:
            session = conn.execute(
                "SELECT * FROM pipeline_sessions WHERE topic LIKE 'timeout-skip:db-article%'"
            ).fetchone()
            assert session is not None
            trace = conn.execute(
                "SELECT * FROM pipeline_traces WHERE session_id = ?", (session['id'],)
            ).fetchone()
            assert trace is not None
            assert trace['status'] == 'completed'

    def test_timeout_threshold_from_config(self, tmp_path):
        """Approval timeout threshold should be read from quality_gates.json."""
        from dashboard.backend.background import approval_timeout_target

        review = tmp_path / "review"
        review.mkdir()
        _create_review_article(review, "custom-threshold-article", 90)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 60}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        mock_write.assert_called_once()
        assert mock_write.call_args[0][1] == "custom-threshold-article"

    def test_multiple_expired_articles_all_skipped(self, tmp_path):
        """All expired articles should be skipped, not just the first."""
        from dashboard.backend.background import approval_timeout_target

        review = tmp_path / "review"
        review.mkdir()

        _create_review_article(review, "expired-1", 150)
        _create_review_article(review, "expired-2", 200)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        assert mock_write.call_count == 2


# ── Named acceptance tests (ITER1-002 / ITER1-004) ─────────────────


class TestTopicTimeoutAcceptance:
    """Acceptance tests for topic timeout auto-confirm behavior."""

    def test_topic_timeout_auto_confirm(self, tmp_path):
        """Expired topic with highest score is auto-confirmed via write_action."""
        from dashboard.backend.background import topic_timeout_target

        pending = tmp_path / "pending"
        pending.mkdir()

        _create_topic(pending, "topic_low", 50, 40)
        _create_topic(pending, "topic_high", 95, 50)
        _create_topic(pending, "topic_mid", 70, 45)

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 30}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_topic_timeout"):
            topic_timeout_target()

        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == "confirm"
        assert mock_write.call_args[0][1] == "topic_high"

    def test_topic_within_timeout_not_affected(self, tmp_path):
        """Topics younger than timeout threshold are not auto-confirmed."""
        from dashboard.backend.background import topic_timeout_target

        pending = tmp_path / "pending"
        pending.mkdir()

        _create_topic(pending, "topic_young", 90, 5)

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 30}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_topic_timeout"):
            topic_timeout_target()

        mock_write.assert_not_called()


class TestApprovalTimeoutAcceptance:
    """Acceptance tests for approval timeout auto-skip behavior."""

    def test_approval_timeout_auto_skip(self, tmp_path):
        """Expired review article is auto-skipped via skip action."""
        from dashboard.backend.background import approval_timeout_target

        review = tmp_path / "review"
        review.mkdir()

        _create_review_article(review, "stale-article-001", 200)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == "skip"
        assert mock_write.call_args[0][1] == "stale-article-001"

    def test_approval_within_timeout_not_affected(self, tmp_path):
        """Articles younger than threshold are not auto-skipped."""
        from dashboard.backend.background import approval_timeout_target

        review = tmp_path / "review"
        review.mkdir()

        _create_review_article(review, "fresh-article-001", 30)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action") as mock_write, \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        mock_write.assert_not_called()


class TestTimeoutRecordsInDB:
    """Acceptance test: timeout events are recorded in SQLite."""

    def test_timeout_records_in_db(self, tmp_path):
        """Both topic and approval timeouts must record in SQLite."""
        from dashboard.backend.background import topic_timeout_target, approval_timeout_target
        from dashboard.backend.database import get_db

        # Test topic timeout recording
        pending = tmp_path / "pending"
        pending.mkdir()
        _create_topic(pending, "topic_db_test", 80, 50)

        with patch("dashboard.backend.background.PENDING_DIR", pending), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"topic_timeout_minutes": 30}), \
             patch("dashboard.backend.background.write_action"), \
             patch("dashboard.backend.background.alert_topic_timeout"):
            topic_timeout_target()

        # Verify topic timeout DB records
        with get_db() as conn:
            session = conn.execute(
                "SELECT * FROM pipeline_sessions WHERE topic LIKE 'timeout-confirm:topic_db_test%'"
            ).fetchone()
            assert session is not None
            trace = conn.execute(
                "SELECT * FROM pipeline_traces WHERE session_id = ?", (session['id'],)
            ).fetchone()
            assert trace is not None
            assert trace['status'] == 'completed'

        # Test approval timeout recording
        review = tmp_path / "review"
        review.mkdir()
        _create_review_article(review, "db-test-article", 200)

        with patch("dashboard.backend.background.REVIEW_DIR", review), \
             patch("dashboard.backend.background.get_quality_gates",
                   return_value={"approval_timeout_minutes": 120}), \
             patch("dashboard.backend.background.write_action"), \
             patch("dashboard.backend.background.alert_approval_timeout"):
            approval_timeout_target()

        # Verify approval timeout DB records
        with get_db() as conn:
            session2 = conn.execute(
                "SELECT * FROM pipeline_sessions WHERE topic LIKE 'timeout-skip:db-test-article%'"
            ).fetchone()
            assert session2 is not None
            trace2 = conn.execute(
                "SELECT * FROM pipeline_traces WHERE session_id = ?", (session2['id'],)
            ).fetchone()
            assert trace2 is not None
            assert trace2['status'] == 'completed'
