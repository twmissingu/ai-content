"""Tests for skills/publisher.py — Publisher Agent."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skills.publisher import PublisherAgent


class TestPublisherAgent:
    """Tests for PublisherAgent class."""

    def test_initialization(self):
        """Should initialize with correct name and version."""
        agent = PublisherAgent()
        assert agent.name == "publisher"
        assert agent.version == "1.0.0"

    def test_find_article_returns_article_and_meta(self, tmp_path):
        """Should find article files matching target_id."""
        agent = PublisherAgent()

        with patch("skills.publisher.REVIEW_DIR", tmp_path):
            meta = {"topic": "Test Topic", "score": 85}
            (tmp_path / "test123.meta.json").write_text(json.dumps(meta))
            (tmp_path / "test123.md").write_text("# Test Article\n\nContent.")

            article, found_meta = agent.find_article("test123")

        assert article is not None
        assert found_meta["topic"] == "Test Topic"

    def test_find_article_returns_none_when_not_found(self, tmp_path):
        """Should return None when article doesn't exist."""
        agent = PublisherAgent()

        with patch("skills.publisher.REVIEW_DIR", tmp_path):
            article, meta = agent.find_article("nonexistent")

        assert article is None
        assert meta is None

    def test_find_article_falls_back_to_glob(self, tmp_path):
        """Should find article via glob when exact match fails."""
        agent = PublisherAgent()

        with patch("skills.publisher.REVIEW_DIR", tmp_path):
            meta = {"topic": "Fallback Topic"}
            # Create files that match the glob pattern
            (tmp_path / "20250101_test123_v2.meta.json").write_text(json.dumps(meta))
            (tmp_path / "20250101_test123_v2.md").write_text("# Fallback")

            article, found_meta = agent.find_article("test123")

        assert article is not None
        assert found_meta["topic"] == "Fallback Topic"

    def test_run_returns_early_when_no_target_id(self):
        """Should return early when no target_id provided."""
        agent = PublisherAgent()
        # Mock sys.argv to have just the script name
        with patch("skills.publisher.sys", MagicMock(argv=["publisher.py"])):
            with patch.object(agent, "write_status") as mock_status:
                with patch.object(agent, "write_error") as mock_error:
                    agent.run(target_id=None)
                    # Should not write any status since it returns early
                    mock_status.assert_not_called()
                    mock_error.assert_not_called()

    def test_run_handles_article_not_found(self, tmp_path):
        """Should write error when article not found."""
        agent = PublisherAgent()

        with patch("skills.publisher.REVIEW_DIR", tmp_path):
            with patch.object(agent, "write_error") as mock_error:
                agent.run(target_id="nonexistent")
                mock_error.assert_called_once()
                assert "not found" in mock_error.call_args[0][0].lower()

    def test_publish_wechat_success(self, tmp_path):
        """Should return True when WeChat publish succeeds."""
        agent = PublisherAgent()
        article = tmp_path / "test.md"
        article.write_text("# Test Article\nContent here.")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = agent._publish_wechat(article, {"topic": "Test"})

        assert result is True

    def test_publish_wechat_failure(self, tmp_path):
        """Should return False when WeChat publish fails."""
        agent = PublisherAgent()
        article = tmp_path / "test.md"
        article.write_text("# Test Article\nContent here.")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            result = agent._publish_wechat(article, {"topic": "Test"})

        assert result is False

    def test_publish_wechat_handles_exception(self, tmp_path):
        """Should return False when subprocess raises exception."""
        agent = PublisherAgent()
        article = tmp_path / "test.md"
        article.write_text("# Test Article\nContent here.")

        with patch("subprocess.run", side_effect=Exception("Subprocess error")):
            result = agent._publish_wechat(article, {"topic": "Test"})

        assert result is False

    def test_publish_aitoearn_success(self, tmp_path):
        """Should return True when AiToEarn publish succeeds."""
        agent = PublisherAgent()
        article = tmp_path / "test.md"
        article.write_text("# Test Article\nContent here.")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = agent._publish_aitoearn("xiaohongshu", article, {"topic": "Test"})

        assert result is True

    def test_publish_aitoearn_unsupported_platform(self, tmp_path):
        """Should return False for unsupported platform."""
        agent = PublisherAgent()
        article = tmp_path / "test.md"
        article.write_text("# Test Article\nContent here.")

        result = agent._publish_aitoearn("unsupported", article, {"topic": "Test"})
        assert result is False

    def test_publish_aitoearn_failure(self, tmp_path):
        """Should return False when AiToEarn publish fails."""
        agent = PublisherAgent()
        article = tmp_path / "test.md"
        article.write_text("# Test Article\nContent here.")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            result = agent._publish_aitoearn("douyin", article, {"topic": "Test"})

        assert result is False

    def test_run_distributes_to_multiple_platforms(self, tmp_path):
        """Should distribute to all specified platforms."""
        agent = PublisherAgent()

        with patch("skills.publisher.REVIEW_DIR", tmp_path):
            meta = {"topic": "Test Topic"}
            (tmp_path / "test123.meta.json").write_text(json.dumps(meta))
            (tmp_path / "test123.md").write_text("# Test Article")

            with patch.object(agent, "_publish_wechat", return_value=True) as mock_wechat:
                with patch.object(agent, "_publish_aitoearn", return_value=True) as mock_aitoearn:
                    with patch.object(agent, "write_status"):
                        with patch.object(agent, "write_completed"):
                            agent.run(target_id="test123", platforms=["wechat", "xiaohongshu"])

        mock_wechat.assert_called_once()
        mock_aitoearn.assert_called_once()

    def test_run_records_failures(self, tmp_path):
        """Should record failures when platform publish fails."""
        agent = PublisherAgent()

        with patch("skills.publisher.REVIEW_DIR", tmp_path):
            meta = {"topic": "Test Topic"}
            (tmp_path / "test123.meta.json").write_text(json.dumps(meta))
            (tmp_path / "test123.md").write_text("# Test Article")

            with patch.object(agent, "_publish_wechat", return_value=False):
                with patch.object(agent, "write_status"):
                    with patch.object(agent, "write_failed_action") as mock_failed:
                        with patch.object(agent, "write_completed"):
                            agent.run(target_id="test123", platforms=["wechat"])

        mock_failed.assert_called_once()
