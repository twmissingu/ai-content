"""Tests for trace API routes."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(monkeypatch):
    """Create a test client with mocked database functions."""
    sample_traces = [
        {"id": 1, "session_id": 10, "agent": "scout", "stage": "collect",
         "stage_name": "收集选题", "status": "completed", "duration_ms": 1200,
         "tokens_used": 300, "output_summary": "5 topics", "error_message": None},
        {"id": 2, "session_id": 10, "agent": "writer", "stage": "draft",
         "stage_name": "初稿", "status": "completed", "duration_ms": 5000,
         "tokens_used": 1500, "output_summary": "2000 chars", "error_message": None},
        {"id": 3, "session_id": 10, "agent": "writer", "stage": "proofread",
         "stage_name": "审校", "status": "failed", "duration_ms": 800,
         "tokens_used": 0, "output_summary": None, "error_message": "Timeout"},
    ]

    monkeypatch.setattr(
        "dashboard.backend.routes.traces.get_traces",
        lambda session_id=None, agent=None, limit=100: [
            t for t in sample_traces
            if (session_id is None or t["session_id"] == session_id)
            and (agent is None or t["agent"] == agent)
        ][:limit],
    )

    def _mock_summary(sid):
        return {
            "stages": [t for t in sample_traces if t["session_id"] == sid],
            "total_tokens": 1800,
            "total_duration_ms": 7000,
            "failed_stages": ["proofread"] if sid == 10 else [],
            "stage_count": 3 if sid == 10 else 0,
        }

    monkeypatch.setattr(
        "dashboard.backend.routes.traces.get_trace_summary",
        _mock_summary,
    )

    def _mock_summaries_batch(session_ids):
        return {sid: _mock_summary(sid) for sid in session_ids}

    monkeypatch.setattr(
        "dashboard.backend.routes.traces.get_trace_summaries_batch",
        _mock_summaries_batch,
    )

    _sessions = [
        {"id": 10, "date": "2026-05-28", "period": "am", "topic": "Test Topic", "status": "completed"},
        {"id": 9, "date": "2026-05-27", "period": "pm", "topic": "Old Topic", "status": "completed"},
    ]

    def _mock_get_sessions(limit=20):
        return {"items": _sessions[:limit], "total": len(_sessions)}

    monkeypatch.setattr(
        "dashboard.backend.routes.traces.get_pipeline_sessions",
        _mock_get_sessions,
    )

    import os
    os.environ.pop("API_KEY", None)
    from dashboard.backend.main import app
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


class TestTraceList:
    """Test GET /api/pipeline/traces."""

    def test_list_all(self, client):
        resp = client.get("/api/pipeline/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "traces" in data
        assert data["total"] == 3

    def test_filter_by_session(self, client):
        resp = client.get("/api/pipeline/traces?session_id=10")
        assert resp.status_code == 200
        traces = resp.json()["traces"]
        assert all(t["session_id"] == 10 for t in traces)

    def test_filter_by_agent(self, client):
        resp = client.get("/api/pipeline/traces?agent=writer")
        assert resp.status_code == 200
        traces = resp.json()["traces"]
        assert all(t["agent"] == "writer" for t in traces)
        assert len(traces) == 2

    def test_limit(self, client):
        resp = client.get("/api/pipeline/traces?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["traces"]) == 1


class TestTraceSummary:
    """Test GET /api/pipeline/traces/summary/{session_id}."""

    def test_summary(self, client):
        resp = client.get("/api/pipeline/traces/summary/10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage_count"] == 3
        assert data["total_tokens"] == 1800
        assert len(data["failed_stages"]) == 1

    def test_summary_empty(self, client):
        resp = client.get("/api/pipeline/traces/summary/99999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage_count"] == 0


class TestTraceSessions:
    """Test GET /api/pipeline/traces/sessions."""

    def test_sessions_with_traces(self, client):
        resp = client.get("/api/pipeline/traces/sessions")
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert len(sessions) == 2
        found = [s for s in sessions if s["id"] == 10]
        assert len(found) == 1
        assert found[0]["stage_count"] == 3
        assert found[0]["total_tokens"] == 1800
        assert found[0]["failed_stages"] == ["proofread"]

    def test_sessions_limit(self, client):
        resp = client.get("/api/pipeline/traces/sessions?limit=1")
        assert resp.status_code == 200
        assert len(resp.json()["sessions"]) <= 1


class TestTraceDBError:
    """Test error handling when database fails."""

    def test_list_traces_db_error(self, client, monkeypatch):
        monkeypatch.setattr(
            "dashboard.backend.routes.traces.get_traces",
            MagicMock(side_effect=Exception("db down")),
        )
        resp = client.get("/api/pipeline/traces")
        assert resp.status_code == 500

    def test_summary_db_error(self, client, monkeypatch):
        monkeypatch.setattr(
            "dashboard.backend.routes.traces.get_trace_summary",
            MagicMock(side_effect=Exception("db down")),
        )
        resp = client.get("/api/pipeline/traces/summary/1")
        assert resp.status_code == 500

    def test_sessions_db_error(self, client, monkeypatch):
        monkeypatch.setattr(
            "dashboard.backend.routes.traces.get_pipeline_sessions",
            MagicMock(side_effect=Exception("db down")),
        )
        resp = client.get("/api/pipeline/traces/sessions")
        assert resp.status_code == 500
