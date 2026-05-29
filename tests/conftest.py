"""Pytest configuration for ai-content tests."""

import sys
from pathlib import Path

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
