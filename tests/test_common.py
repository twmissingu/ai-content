"""Unit tests for skills/common.py utilities."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path

import pytest

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestAtomicWriteJson:
    """Test atomic JSON file writing."""
    
    def test_write_creates_file(self, tmp_path):
        """Test that atomic_write_json creates the file."""
        from skills.common import atomic_write_json
        
        path = tmp_path / "test.json"
        data = {"key": "value", "number": 42}
        
        atomic_write_json(path, data)
        
        assert path.exists()
        content = json.loads(path.read_text())
        assert content == data
    
    def test_write_creates_parent_dirs(self, tmp_path):
        """Test that parent directories are created."""
        from skills.common import atomic_write_json
        
        path = tmp_path / "subdir" / "deep" / "test.json"
        data = {"nested": True}
        
        atomic_write_json(path, data)
        
        assert path.exists()
        content = json.loads(path.read_text())
        assert content == data
    
    def test_write_overwrites_existing(self, tmp_path):
        """Test that existing file is overwritten."""
        from skills.common import atomic_write_json
        
        path = tmp_path / "test.json"
        
        atomic_write_json(path, {"version": 1})
        atomic_write_json(path, {"version": 2})
        
        content = json.loads(path.read_text())
        assert content["version"] == 2
    
    def test_write_preserves_unicode(self, tmp_path):
        """Test that Unicode characters are preserved."""
        from skills.common import atomic_write_json
        
        path = tmp_path / "test.json"
        data = {"中文": "测试", "emoji": "🎉"}
        
        atomic_write_json(path, data)
        
        content = json.loads(path.read_text())
        assert content == data


class TestAtomicWriteText:
    """Test atomic text file writing."""
    
    def test_write_creates_file(self, tmp_path):
        """Test that atomic_write_text creates the file."""
        from skills.common import atomic_write_text
        
        path = tmp_path / "test.txt"
        content = "Hello, World!"
        
        atomic_write_text(path, content)
        
        assert path.exists()
        assert path.read_text() == content
    
    def test_write_with_encoding(self, tmp_path):
        """Test writing with specific encoding."""
        from skills.common import atomic_write_text
        
        path = tmp_path / "test.txt"
        content = "中文内容"
        
        atomic_write_text(path, content, encoding='utf-8')
        
        assert path.read_text(encoding='utf-8') == content


class TestFileLock:
    """Test file locking mechanism."""
    
    def test_lock_basic(self, tmp_path):
        """Test basic lock acquisition and release."""
        from skills.common import file_lock
        
        lock_path = tmp_path / "test.lock"
        
        with file_lock(lock_path):
            assert lock_path.exists()
        
        # Lock should be released
        assert not lock_path.exists()
    
    def test_lock_timeout(self, tmp_path):
        """Test lock timeout behavior."""
        from skills.common import file_lock
        
        lock_path = tmp_path / "test.lock"
        
        # Create lock manually
        os.mkdir(lock_path)
        
        with pytest.raises(TimeoutError):
            with file_lock(lock_path, timeout=0.1):
                pass
        
        # Clean up
        os.rmdir(lock_path)


class TestInputValidation:
    """Test input validation functions."""
    
    def test_validate_source_valid(self):
        """Test valid source validation."""
        from skills.common import validate_source
        
        assert validate_source("weibo") == "weibo"
        assert validate_source("github") == "github"
    
    def test_validate_source_invalid(self):
        """Test invalid source validation."""
        from skills.common import validate_source
        
        with pytest.raises(ValueError):
            validate_source("invalid_source")
    
    def test_validate_platform_valid(self):
        """Test valid platform validation."""
        from skills.common import validate_platform
        
        assert validate_platform("wechat") == "wechat"
        assert validate_platform("xiaohongshu") == "xiaohongshu"
    
    def test_validate_platform_invalid(self):
        """Test invalid platform validation."""
        from skills.common import validate_platform
        
        with pytest.raises(ValueError):
            validate_platform("invalid_platform")
    
    def test_validate_action_valid(self):
        """Test valid action validation."""
        from skills.common import validate_action
        
        assert validate_action("approve") == "approve"
        assert validate_action("reject") == "reject"
    
    def test_validate_action_invalid(self):
        """Test invalid action validation."""
        from skills.common import validate_action
        
        with pytest.raises(ValueError):
            validate_action("invalid_action")


class TestSanitizeFilename:
    """Test filename sanitization."""
    
    def test_normal_filename(self):
        """Test normal filename passes through."""
        from skills.common import sanitize_filename
        
        assert sanitize_filename("test.json") == "test.json"
    
    def test_path_traversal(self):
        """Test path traversal prevention."""
        from skills.common import sanitize_filename
        
        assert "/" not in sanitize_filename("../test.json")
        assert "\\" not in sanitize_filename("..\\test.json")
    
    def test_hidden_file(self):
        """Test hidden file prevention."""
        from skills.common import sanitize_filename
        
        assert not sanitize_filename(".hidden").startswith(".")
    
    def test_empty_filename(self):
        """Test empty filename handling."""
        from skills.common import sanitize_filename
        
        result = sanitize_filename("")
        assert result == "unnamed"
    
    def test_long_filename(self):
        """Test long filename truncation."""
        from skills.common import sanitize_filename
        
        long_name = "a" * 300
        result = sanitize_filename(long_name, max_length=255)
        assert len(result) <= 255


class TestMaskApiKey:
    """Test API key masking."""
    
    def test_normal_key(self):
        """Test normal key masking."""
        from skills.common import mask_api_key
        
        result = mask_api_key("sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert result.endswith("cdef")
        assert "****" in result
    
    def test_short_key(self):
        """Test short key masking."""
        from skills.common import mask_api_key
        
        result = mask_api_key("short")
        assert result == "****"
    
    def test_none_key(self):
        """Test None key masking."""
        from skills.common import mask_api_key
        
        result = mask_api_key(None)
        assert result == "****"
    
    def test_empty_key(self):
        """Test empty key masking."""
        from skills.common import mask_api_key
        
        result = mask_api_key("")
        assert result == "****"


class TestSafeSubprocessArgs:
    """Test subprocess argument validation."""
    
    def test_valid_args(self):
        """Test valid command arguments."""
        from skills.common import safe_subprocess_args
        
        args = ["hermes", "mcp", "call", "tool_name"]
        result = safe_subprocess_args(args)
        assert result == args
    
    def test_invalid_binary(self):
        """Test invalid binary rejection."""
        from skills.common import safe_subprocess_args
        
        with pytest.raises(ValueError):
            safe_subprocess_args(["rm", "-rf", "/"])
    
    def test_dangerous_chars(self):
        """Test dangerous character rejection."""
        from skills.common import safe_subprocess_args
        
        with pytest.raises(ValueError):
            safe_subprocess_args(["hermes", "arg;malicious"])
    
    def test_json_params_allowed(self):
        """Test JSON in --params is allowed."""
        from skills.common import safe_subprocess_args
        
        args = ["hermes", "mcp", "call", "tool", "--params", '{"key": "value"}']
        result = safe_subprocess_args(args)
        assert result == args


class TestAgentBase:
    """Test AgentBase class."""
    
    def test_agent_initialization(self, tmp_path, monkeypatch):
        """Test agent initialization."""
        monkeypatch.chdir(tmp_path)
        
        from skills.common import AgentBase
        
        class TestAgent(AgentBase):
            name = "test"
        
        agent = TestAgent()
        assert agent.name == "test"
        assert agent.logger is not None
    
    def test_write_status(self, tmp_path, monkeypatch):
        """Test status writing."""
        # Create status directory
        status_dir = tmp_path / "queue" / "status"
        status_dir.mkdir(parents=True)
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("skills.common.STATUS_DIR", status_dir)
        
        from skills.common import AgentBase
        
        class TestAgent(AgentBase):
            name = "test"
        
        agent = TestAgent()
        agent.write_status("running", 50, "Test detail")
        
        status_file = status_dir / "test.json"
        assert status_file.exists()
        
        status = json.loads(status_file.read_text())
        assert status["agent"] == "test"
        assert status["stage"] == "running"
        assert status["progress_pct"] == 50
        assert status["detail"] == "Test detail"


class TestWriteStatusFunction:
    """Test standalone write_status function."""
    
    def test_write_status(self, tmp_path, monkeypatch):
        """Test standalone status writing."""
        status_dir = tmp_path / "queue" / "status"
        status_dir.mkdir(parents=True)
        
        monkeypatch.setattr("skills.common.STATUS_DIR", status_dir)
        
        from skills.common import write_status
        
        write_status("scout", "collecting", 25, "Collecting topics")
        
        status_file = status_dir / "scout.json"
        assert status_file.exists()
        
        status = json.loads(status_file.read_text())
        assert status["agent"] == "scout"
        assert status["stage"] == "collecting"
        assert status["progress_pct"] == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
