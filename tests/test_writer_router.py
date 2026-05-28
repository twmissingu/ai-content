"""Tests for skills/writer_router.py — Writer Router."""

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from skills.writer_router import (
    _write_router_status,
    _find_topic,
    _run_worker,
    _aggregate,
    WORKER_CONFIGS,
    PARALLEL,
)


class TestWriteRouterStatus:
    """Tests for _write_router_status function."""

    def test_writes_status_file(self, tmp_path):
        """Should write router status to STATUS_DIR."""
        with patch("skills.writer_router.STATUS_DIR", tmp_path):
            _write_router_status(50, "Test detail", {"worker1": {"status": "running"}})

        status_file = tmp_path / "writer-router.json"
        assert status_file.exists()
        status = json.loads(status_file.read_text())
        assert status["agent"] == "writer"
        assert status["router"] is True
        assert status["progress_pct"] == 50
        assert status["detail"] == "Test detail"
        assert "worker1" in status["workers"]

    def test_writes_empty_workers_by_default(self, tmp_path):
        """Should write empty workers dict when not provided."""
        with patch("skills.writer_router.STATUS_DIR", tmp_path):
            _write_router_status(0, "Starting")

        status = json.loads((tmp_path / "writer-router.json").read_text())
        assert status["workers"] == {}


class TestFindTopic:
    """Tests for _find_topic function."""

    def test_finds_topic_by_id(self, tmp_path):
        """Should find topic file matching topic_id."""
        with patch("skills.writer_router.PENDING_DIR", tmp_path):
            topic = {"title": "Test Topic", "score": 85}
            (tmp_path / "topic_abc123.json").write_text(json.dumps(topic))

            path, data = _find_topic("abc123")

        assert path is not None
        assert data["title"] == "Test Topic"

    def test_returns_none_when_not_found(self, tmp_path):
        """Should return None when no topic matches."""
        with patch("skills.writer_router.PENDING_DIR", tmp_path):
            path, data = _find_topic("nonexistent")

        assert path is None
        assert data is None

    def test_finds_latest_confirmed_topic(self, tmp_path):
        """Should find latest confirmed topic when no topic_id given."""
        pending_dir = tmp_path / "pending"
        topics_dir = tmp_path / "queue" / "topics"
        pending_dir.mkdir(parents=True)
        topics_dir.mkdir(parents=True)

        topic = {"title": "Confirmed Topic", "score": 90}
        (pending_dir / "topic_confirmed.json").write_text(json.dumps(topic))
        (topics_dir / "topic_confirmed.confirmed").write_text("")

        with patch("skills.writer_router.PENDING_DIR", pending_dir):
            with patch("skills.writer_router.QUEUE_DIR", tmp_path / "queue"):
                path, data = _find_topic()

        assert path is not None
        assert data["title"] == "Confirmed Topic"

    def test_returns_none_when_no_confirmed_topics(self, tmp_path):
        """Should return None when no confirmed topics exist."""
        with patch("skills.writer_router.PENDING_DIR", tmp_path):
            with patch("skills.writer_router.QUEUE_DIR", tmp_path / "queue"):
                path, data = _find_topic()

        assert path is None
        assert data is None


@pytest.mark.asyncio
class TestRunWorker:
    """Tests for _run_worker function."""

    async def test_returns_skipped_when_script_not_found(self, tmp_path):
        """Should return skipped status when script doesn't exist."""
        config = {
            "type": "test",
            "script": "nonexistent.py",
            "args": [],
            "enabled": True,
            "timeout": 60,
        }
        topic_path = tmp_path / "topic.json"
        topic_path.write_text(json.dumps({"title": "Test"}))

        with patch("skills.writer_router.PROJECT_ROOT", tmp_path):
            result = await _run_worker(config, topic_path, {"title": "Test"})

        assert result["status"] == "skipped"
        assert "not found" in result["detail"].lower()

    async def test_returns_completed_on_success(self, tmp_path):
        """Should return completed status when worker succeeds."""
        script = tmp_path / "skills" / "writer.py"
        script.parent.mkdir(parents=True)
        script.write_text("# Worker script")

        topic_path = tmp_path / "topic.json"
        topic_path.write_text(json.dumps({"title": "Test"}))

        config = {
            "type": "test",
            "script": "writer.py",
            "args": [],
            "enabled": True,
            "timeout": 60,
        }

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"Success", b"")

        with patch("skills.writer_router.PROJECT_ROOT", tmp_path):
            with patch("skills.writer_router.TMP_DIR", tmp_path / "tmp"):
                with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                    with patch("asyncio.wait_for", return_value=mock_proc):
                        result = await _run_worker(config, topic_path, {"title": "Test"})

        assert result["status"] == "completed"
        assert result["type"] == "test"

    async def test_returns_failed_on_nonzero_exit(self, tmp_path):
        """Should return failed status when worker exits with error."""
        script = tmp_path / "skills" / "writer.py"
        script.parent.mkdir(parents=True)
        script.write_text("# Worker script")

        topic_path = tmp_path / "topic.json"
        topic_path.write_text(json.dumps({"title": "Test"}))

        config = {
            "type": "test",
            "script": "writer.py",
            "args": [],
            "enabled": True,
            "timeout": 60,
        }

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", b"Error occurred")

        with patch("skills.writer_router.PROJECT_ROOT", tmp_path):
            with patch("skills.writer_router.TMP_DIR", tmp_path / "tmp"):
                with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                    with patch("asyncio.wait_for", return_value=mock_proc):
                        result = await _run_worker(config, topic_path, {"title": "Test"})

        assert result["status"] == "failed"
        assert "Error occurred" in result["detail"]

    async def test_returns_timeout_on_timeout(self, tmp_path):
        """Should return timeout status when worker times out."""
        script = tmp_path / "skills" / "writer.py"
        script.parent.mkdir(parents=True)
        script.write_text("# Worker script")

        topic_path = tmp_path / "topic.json"
        topic_path.write_text(json.dumps({"title": "Test"}))

        config = {
            "type": "test",
            "script": "writer.py",
            "args": [],
            "enabled": True,
            "timeout": 60,
        }

        with patch("skills.writer_router.PROJECT_ROOT", tmp_path):
            with patch("skills.writer_router.TMP_DIR", tmp_path / "tmp"):
                with patch("asyncio.create_subprocess_exec", side_effect=asyncio.TimeoutError()):
                    with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                        result = await _run_worker(config, topic_path, {"title": "Test"})

        assert result["status"] == "timeout"
        assert "timeout" in result["detail"].lower()


@pytest.mark.asyncio
class TestAggregate:
    """Tests for _aggregate function."""

    async def test_copies_completed_articles(self, tmp_path):
        """Should copy completed worker articles to REVIEW_DIR."""
        review_dir = tmp_path / "review"
        review_dir.mkdir()

        results = [
            {
                "type": "wechat",
                "status": "completed",
                "article": str(tmp_path / "article.md"),
                "meta": str(tmp_path / "meta.json"),
            }
        ]
        (tmp_path / "article.md").write_text("# Article")
        (tmp_path / "meta.json").write_text(json.dumps({"score": 90}))

        topic = {"title": "Test Topic"}

        with patch("skills.writer_router.REVIEW_DIR", review_dir):
            aggregated = await _aggregate(results, topic)

        assert aggregated["status"] == "completed"
        assert len(aggregated["articles"]) == 1
        assert aggregated["topic"] == "Test Topic"

    async def test_skips_failed_workers(self, tmp_path):
        """Should skip workers that failed."""
        review_dir = tmp_path / "review"
        review_dir.mkdir()

        results = [
            {"type": "wechat", "status": "failed", "detail": "Error"},
            {"type": "xhs", "status": "completed", "article": str(tmp_path / "xhs.md"), "meta": str(tmp_path / "xhs.json")},
        ]
        (tmp_path / "xhs.md").write_text("# XHS Article")
        (tmp_path / "xhs.json").write_text("{}")

        topic = {"title": "Test"}

        with patch("skills.writer_router.REVIEW_DIR", review_dir):
            aggregated = await _aggregate(results, topic)

        assert aggregated["status"] == "completed"
        assert len(aggregated["articles"]) == 1
        assert aggregated["articles"][0]["type"] == "xhs"

    async def test_returns_failed_when_no_articles(self, tmp_path):
        """Should return failed status when no articles produced."""
        review_dir = tmp_path / "review"
        review_dir.mkdir()

        results = [
            {"type": "wechat", "status": "failed", "detail": "Error"},
        ]

        topic = {"title": "Test"}

        with patch("skills.writer_router.REVIEW_DIR", review_dir):
            aggregated = await _aggregate(results, topic)

        assert aggregated["status"] == "failed"
        assert len(aggregated["articles"]) == 0


class TestWorkerConfigs:
    """Tests for WORKER_CONFIGS and PARALLEL flag."""

    def test_wechat_always_enabled(self):
        """WeChat worker should always be enabled."""
        wechat_config = next(w for w in WORKER_CONFIGS if w["type"] == "wechat")
        assert wechat_config["enabled"] is True

    def test_all_configs_have_required_fields(self):
        """All worker configs should have required fields."""
        for config in WORKER_CONFIGS:
            assert "type" in config
            assert "script" in config
            assert "enabled" in config
            assert "timeout" in config
            assert isinstance(config["timeout"], int)
            assert config["timeout"] > 0

    def test_parallel_workers_have_different_types(self):
        """Each worker config should have a unique type."""
        types = [w["type"] for w in WORKER_CONFIGS]
        assert len(types) == len(set(types))
