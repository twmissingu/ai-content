"""Pytest configuration for ai-content tests."""

# TODO: Add performance/load/concurrency tests for:
#   - API endpoint response times under concurrent requests
#   - WebSocket broadcast latency with many connected clients
#   - Rate limiter accuracy under high throughput
#   - Database connection pool behavior under load
#   - File watcher scalability with many status files

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Configure pytest."""
    # Add custom markers
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset rate limiter between tests to prevent cross-test 429 errors."""
    yield
    try:
        from dashboard.backend.main import rate_limiter
        rate_limiter.requests.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _close_db_connections():
    """Close thread-local DB connections after each test to prevent ResourceWarning."""
    yield
    try:
        import dashboard.backend.database.core as db_core
        local = db_core._thread_local
        if hasattr(local, 'conn') and local.conn is not None:
            local.conn.close()
            local.conn = None
    except Exception:
        pass


@pytest.fixture
def mock_db_context():
    """Reusable mock for get_db() context manager.

    Returns (mock_conn, mock_context) where mock_context is a context manager
    that yields mock_conn. Use with patch("module.get_db", return_value=mock_context).
    """
    mock_conn = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=mock_conn)
    mock_context.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_context


@pytest.fixture
def mock_llm_client():
    """Reusable mock for LLM chat function."""
    with MagicMock() as mock:
        mock.return_value = "Mocked LLM response"
        yield mock


@pytest.fixture
def sample_topic_data():
    """Sample topic data for tests."""
    return {
        "title": "AI Agent 框架对比：LangChain vs CrewAI vs AutoGen",
        "score": 85,
        "source": "rss",
        "keywords": ["AI", "Agent", "LangChain"],
        "url": "https://example.com/ai-agents",
    }


@pytest.fixture
def temp_settings(tmp_path):
    """Temporary settings override for tests that need isolated config."""
    return {
        "queue_dir": tmp_path / "queue",
        "config_dir": tmp_path / "config",
        "data_dir": tmp_path / "data",
    }
