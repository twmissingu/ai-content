"""Unit tests for skills/action.py — action file protocol."""

import json
import os
import time
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def action_dirs(tmp_path, monkeypatch):
    """Create temporary action directories (fresh per test)."""
    dirs = {
        'actions': tmp_path / 'queue' / 'actions',
        'processed': tmp_path / 'queue' / 'actions' / 'processed',
        'failed': tmp_path / 'queue' / 'actions' / 'failed',
        'pending': tmp_path / 'queue' / 'pending',
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    # Patch at the module level where the constants are used
    import skills.action
    monkeypatch.setattr(skills.action, 'ACTIONS_DIR', dirs['actions'])
    monkeypatch.setattr(skills.action, 'PROCESSED_DIR', dirs['processed'])
    monkeypatch.setattr(skills.action, 'FAILED_ACTIONS_DIR', dirs['failed'])
    monkeypatch.setattr(skills.action, 'PENDING_DIR', dirs['pending'])

    return dirs


class TestWriteAction:
    """Test write_action function."""

    def test_write_approve_action(self, action_dirs):
        from skills.action import write_action

        path = write_action("approve", "article_123")

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["action"] == "approve"
        assert data["target_id"] == "article_123"
        assert "timestamp" in data

    def test_write_reject_action_with_reason(self, action_dirs):
        from skills.action import write_action

        path = write_action("reject", "article_456", reason="质量不达标")

        data = json.loads(path.read_text())
        assert data["action"] == "reject"
        assert data["reason"] == "质量不达标"

    def test_write_action_with_platforms(self, action_dirs):
        from skills.action import write_action

        path = write_action("approve", "article_789",
                           platform_versions=["wechat", "xiaohongshu"])

        data = json.loads(path.read_text())
        assert data["platform_versions"] == ["wechat", "xiaohongshu"]

    def test_write_action_with_trigger_agent(self, action_dirs):
        from skills.action import write_action

        path = write_action("confirm", "topic_001", trigger_agent="scout")

        data = json.loads(path.read_text())
        assert data["trigger_agent"] == "scout"

    def test_write_invalid_action_raises(self, action_dirs):
        from skills.action import write_action

        with pytest.raises(ValueError, match="Invalid action"):
            write_action("invalid_action", "test")

    def test_write_invalid_platform_raises(self, action_dirs):
        from skills.action import write_action

        with pytest.raises(ValueError, match="Invalid platform"):
            write_action("approve", "test", platform_versions=["invalid_platform"])

    def test_write_all_valid_actions(self, action_dirs):
        from skills.action import write_action

        for action_type in ["confirm", "approve", "reject", "rewrite", "test_scout"]:
            path = write_action(action_type, f"test_{action_type}")
            assert path.exists()


class TestScanActions:
    """Test scan_actions function."""

    def test_scan_empty_dir(self, action_dirs):
        from skills.action import scan_actions

        result = scan_actions()
        assert result == []

    def test_scan_returns_action_files(self, action_dirs):
        from skills.action import scan_actions
        # Write directly to avoid state leakage
        for target_id in ["article_1", "article_2"]:
            path = action_dirs['actions'] / f"approve_{target_id}.json"
            path.write_text(json.dumps({
                "action": "approve",
                "target_id": target_id,
                "timestamp": "2026-01-01T00:00:00Z",
            }))

        result = scan_actions()
        assert len(result) == 2

    def test_scan_sorted_by_mtime(self, action_dirs):
        from skills.action import scan_actions

        for i in range(3):
            path = action_dirs['actions'] / f"approve_test_{i}.json"
            path.write_text(json.dumps({
                "action": "approve",
                "target_id": f"test_{i}",
                "timestamp": f"2026-01-0{i+1}T00:00:00Z",
            }))
            os.utime(path, (i + 1000, i + 1000))

        result = scan_actions()
        assert len(result) == 3
        assert result[0]["target_id"] == "test_0"
        assert result[2]["target_id"] == "test_2"

    def test_scan_moves_malformed_files(self, action_dirs):
        from skills.action import scan_actions

        bad_file = action_dirs['actions'] / "bad_action.json"
        bad_file.write_text("not valid json{")

        result = scan_actions()
        assert len(result) == 0
        assert (action_dirs['failed'] / "bad_action.json").exists()
        assert not bad_file.exists()

    def test_scan_action_file_attributes(self, action_dirs):
        from skills.action import scan_actions

        path = action_dirs['actions'] / "approve_article_1.json"
        path.write_text(json.dumps({
            "action": "approve",
            "target_id": "article_1",
            "timestamp": "2026-01-01T00:00:00Z",
            "trigger_agent": "scout",
        }))

        result = scan_actions()
        assert len(result) == 1
        # ActionFile stores data in dict, access via dict keys
        assert result[0]["action"] == "approve"
        assert result[0]["target_id"] == "article_1"
        assert result[0]["trigger_agent"] == "scout"


class TestMarkProcessed:
    """Test mark_processed function."""

    def test_mark_processed_moves_file(self, action_dirs):
        from skills.action import mark_processed

        source = action_dirs['actions'] / "approve_test.json"
        source.write_text(json.dumps({"action": "approve", "target_id": "test"}))

        mark_processed(source)

        assert not source.exists()
        processed_path = action_dirs['processed'] / source.name
        assert processed_path.exists()

    def test_mark_processed_handles_collision(self, action_dirs):
        from skills.action import mark_processed

        source = action_dirs['actions'] / "test_action.json"
        source.write_text('{"action": "approve"}')

        dest = action_dirs['processed'] / "test_action.json"
        dest.write_text('{"action": "old"}')

        mark_processed(source)

        assert not source.exists()
        assert dest.exists()
        processed_files = list(action_dirs['processed'].glob("test_action*"))
        assert len(processed_files) == 2


class TestWriteTopicPending:
    """Test write_topic_pending function."""

    def test_write_topic(self, action_dirs):
        from skills.action import write_topic_pending

        topic = {"title": "AI 发展趋势", "score": 85}
        path = write_topic_pending(topic)

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["title"] == "AI 发展趋势"
        assert data["score"] == 85

    def test_write_topic_with_filename(self, action_dirs):
        from skills.action import write_topic_pending

        topic = {"title": "测试选题"}
        path = write_topic_pending(topic, filename="custom_topic.json")

        assert path.name == "custom_topic.json"
        assert path.exists()


class TestCleanupOldActions:
    """Test cleanup_old_actions function."""

    def test_cleanup_removes_old_files(self, action_dirs):
        from skills.action import cleanup_old_actions

        old_file = action_dirs['processed'] / "old_action.json"
        old_file.write_text('{"action": "approve"}')
        old_time = time.time() - (10 * 24 * 60 * 60)
        os.utime(old_file, (old_time, old_time))

        recent_file = action_dirs['processed'] / "recent_action.json"
        recent_file.write_text('{"action": "reject"}')

        cleaned = cleanup_old_actions(days=7)

        assert cleaned == 1
        assert not old_file.exists()
        assert recent_file.exists()

    def test_cleanup_empty_dir(self, action_dirs):
        from skills.action import cleanup_old_actions

        cleaned = cleanup_old_actions(days=7)
        assert cleaned == 0

    def test_cleanup_custom_days(self, action_dirs):
        from skills.action import cleanup_old_actions

        file_3d = action_dirs['processed'] / "3day_action.json"
        file_3d.write_text('{"action": "approve"}')
        old_time = time.time() - (3 * 24 * 60 * 60)
        os.utime(file_3d, (old_time, old_time))

        assert cleanup_old_actions(days=7) == 0
        assert file_3d.exists()

        assert cleanup_old_actions(days=1) == 1
        assert not file_3d.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
