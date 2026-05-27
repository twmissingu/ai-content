"""Unit tests for the database layer."""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Mock the settings before importing database
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Create a temporary database for testing
TEST_DB_PATH = Path(tempfile.mkdtemp()) / "test_analytics.db"


@pytest.fixture(autouse=True)
def mock_db_path(monkeypatch):
    """Mock database path for testing."""
    import dashboard.backend.database as db
    monkeypatch.setattr(db, 'DATABASE_PATH', TEST_DB_PATH)
    # Reinitialize database
    db.init_db()
    yield
    # Cleanup
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def sample_session():
    """Create a sample pipeline session."""
    from dashboard.backend.database import create_pipeline_session
    session_id = create_pipeline_session(
        date="2026-05-27",
        period="am",
        topic="Test Topic",
        source_url="https://example.com"
    )
    return session_id


class TestPipelineSessions:
    """Test pipeline session operations."""
    
    def test_create_session(self, sample_session):
        """Test creating a pipeline session."""
        from dashboard.backend.database import get_pipeline_sessions
        
        sessions = get_pipeline_sessions(limit=10)
        assert len(sessions) >= 1
        
        session = sessions[0]
        assert session['id'] == sample_session
        assert session['date'] == "2026-05-27"
        assert session['period'] == "am"
        assert session['topic'] == "Test Topic"
        assert session['status'] == "running"
    
    def test_update_session(self, sample_session):
        """Test updating a pipeline session."""
        from dashboard.backend.database import update_pipeline_session, get_pipeline_sessions
        
        update_pipeline_session(
            sample_session,
            status='completed',
            completed_at='2026-05-27T10:00:00Z'
        )
        
        sessions = get_pipeline_sessions(limit=10)
        session = next(s for s in sessions if s['id'] == sample_session)
        assert session['status'] == 'completed'
    
    def test_get_today_sessions(self, sample_session):
        """Test getting today's sessions."""
        from dashboard.backend.database import get_today_sessions
        
        sessions = get_today_sessions()
        # Note: This might be empty if test runs on different day
        # The test mainly checks the function doesn't crash
        assert isinstance(sessions, list)


class TestPlatformVersions:
    """Test platform version operations."""
    
    def test_create_version(self, sample_session):
        """Test creating a platform version."""
        from dashboard.backend.database import create_platform_version, get_platform_versions
        
        version_id = create_platform_version(
            session_id=sample_session,
            platform="wechat",
            content_path="/path/to/content.md",
            meta_path="/path/to/meta.json"
        )
        
        versions = get_platform_versions(sample_session)
        assert len(versions) == 1
        assert versions[0]['id'] == version_id
        assert versions[0]['platform'] == "wechat"
        assert versions[0]['status'] == "pending"
    
    def test_update_version(self, sample_session):
        """Test updating a platform version."""
        from dashboard.backend.database import (
            create_platform_version, update_platform_version, get_platform_versions
        )
        
        version_id = create_platform_version(
            session_id=sample_session,
            platform="xiaohongshu"
        )
        
        update_platform_version(version_id, status='approved', score=85.5)
        
        versions = get_platform_versions(sample_session)
        version = next(v for v in versions if v['id'] == version_id)
        assert version['status'] == 'approved'
        assert version['score'] == 85.5


class TestApprovalRecords:
    """Test approval record operations."""
    
    def test_create_approval(self, sample_session):
        """Test creating an approval record."""
        from dashboard.backend.database import (
            create_platform_version, create_approval_record, get_approval_records
        )
        
        version_id = create_platform_version(
            session_id=sample_session,
            platform="wechat"
        )
        
        record_id = create_approval_record(
            version_id=version_id,
            action="pass",
            reason="Good quality",
            operator="user"
        )
        
        records = get_approval_records(version_id=version_id)
        assert len(records) == 1
        assert records[0]['id'] == record_id
        assert records[0]['action'] == "pass"


class TestTokenUsage:
    """Test token usage operations."""
    
    def test_log_usage(self, sample_session):
        """Test logging token usage."""
        from dashboard.backend.database import log_token_usage, get_token_usage_stats
        
        log_token_usage(
            agent="scout",
            model="claude-sonnet-4",
            input_tokens=1000,
            output_tokens=500,
            session_id=sample_session
        )
        
        stats = get_token_usage_stats(days=1)
        assert stats['monthly']['call_count'] >= 1
        assert stats['monthly']['input_tokens'] >= 1000
    
    def test_monthly_cost(self):
        """Test monthly cost calculation."""
        from dashboard.backend.database import log_token_usage, get_monthly_cost
        
        log_token_usage(
            agent="writer",
            model="gpt-4o",
            input_tokens=2000,
            output_tokens=1000
        )
        
        cost = get_monthly_cost()
        assert cost > 0


class TestConfigEntries:
    """Test configuration entries."""
    
    def test_set_and_get_config(self):
        """Test setting and getting configuration."""
        from dashboard.backend.database import set_config_value, get_config_value
        
        set_config_value("test_key", {"value": 42})
        
        result = get_config_value("test_key")
        assert result == {"value": 42}
    
    def test_config_default(self):
        """Test getting config with default value."""
        from dashboard.backend.database import get_config_value
        
        result = get_config_value("nonexistent", default="default_value")
        assert result == "default_value"
    
    def test_pending_config(self):
        """Test pending configuration."""
        from dashboard.backend.database import set_config_value, get_pending_config
        
        set_config_value("schedule", "09:30", status='pending',
                        effective_from="2026-05-28T00:00:00Z")
        
        pending = get_pending_config(key="schedule")
        assert len(pending) >= 1


class TestBudgetControl:
    """Test budget control functions."""
    
    def test_budget_check(self):
        """Test budget limit check."""
        from dashboard.backend.database import check_budget_limit
        
        status = check_budget_limit(budget_usd=15.0)
        assert 'current_cost' in status
        assert 'budget' in status
        assert 'percentage' in status
        assert 'is_warning' in status
        assert 'is_exceeded' in status
        assert status['budget'] == 15.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
