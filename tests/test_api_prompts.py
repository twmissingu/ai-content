"""Tests for /api/prompts routes."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create test client with mocked prompt DB functions."""
    mock_prompts = [
        {
            "name": "writer_draft",
            "version": 2,
            "template": "Write about {topic}",
            "variables": ["topic"],
            "is_active": True,
            "created_at": "2026-05-28T10:00:00Z",
        }
    ]

    monkeypatch.setattr(
        "dashboard.backend.routes.prompts.list_prompts",
        lambda: mock_prompts,
    )
    monkeypatch.setattr(
        "dashboard.backend.routes.prompts.get_prompt",
        lambda name, version=None: mock_prompts[0] if name == "writer_draft" else None,
    )
    monkeypatch.setattr(
        "dashboard.backend.routes.prompts.list_prompt_versions",
        lambda name: mock_prompts if name == "writer_draft" else [],
    )
    monkeypatch.setattr(
        "dashboard.backend.routes.prompts.save_prompt",
        lambda name, template, variables=None: 1,
    )
    monkeypatch.setattr(
        "dashboard.backend.routes.prompts.activate_prompt",
        lambda name, version: True if name == "writer_draft" else False,
    )
    monkeypatch.setattr(
        "dashboard.backend.routes.prompts.delete_prompt_version",
        lambda name, version: True,
    )
    monkeypatch.setattr(
        "dashboard.backend.routes.prompts.import_prompts_from_files",
        lambda: 3,
    )

    from dashboard.backend.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


class TestGetAllPrompts:
    def test_returns_prompts_list(self, client):
        resp = client.get("/api/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "prompts" in data
        assert "count" in data
        assert data["count"] == 1
        assert data["prompts"][0]["name"] == "writer_draft"


class TestGetPromptDetail:
    def test_get_existing_prompt(self, client):
        resp = client.get("/api/prompts/writer_draft")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "writer_draft"

    def test_get_prompt_with_version(self, client):
        resp = client.get("/api/prompts/writer_draft", params={"version": 2})
        assert resp.status_code == 200

    def test_get_nonexistent_prompt_returns_404(self, client):
        resp = client.get("/api/prompts/nonexistent")
        assert resp.status_code == 404


class TestGetPromptVersions:
    def test_returns_versions(self, client):
        resp = client.get("/api/prompts/writer_draft/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "writer_draft"
        assert "versions" in data
        assert data["count"] == 1

    def test_nonexistent_name_returns_404(self, client):
        resp = client.get("/api/prompts/nonexistent/versions")
        assert resp.status_code == 404


class TestCreatePrompt:
    def test_creates_new_version(self, client):
        resp = client.post(
            "/api/prompts",
            json={"name": "test_prompt", "template": "Hello {name}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["name"] == "test_prompt"
        assert data["version"] == 1

    def test_missing_name_returns_400(self, client):
        resp = client.post(
            "/api/prompts",
            json={"name": "", "template": "Hello"},
        )
        assert resp.status_code == 400

    def test_missing_template_returns_400(self, client):
        resp = client.post(
            "/api/prompts",
            json={"name": "test", "template": ""},
        )
        assert resp.status_code == 400

    def test_with_variables(self, client):
        resp = client.post(
            "/api/prompts",
            json={
                "name": "test_prompt",
                "template": "Write about {topic} for {platform}",
                "variables": ["topic", "platform"],
            },
        )
        assert resp.status_code == 200


class TestActivatePrompt:
    def test_activates_version(self, client):
        resp = client.post("/api/prompts/writer_draft/activate", params={"version": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_version"] == 1

    def test_nonexistent_version_returns_404(self, client):
        resp = client.post("/api/prompts/nonexistent/activate", params={"version": 99})
        assert resp.status_code == 404


class TestDeletePromptVersion:
    def test_deletes_version(self, client):
        resp = client.delete("/api/prompts/writer_draft/1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestImportPrompts:
    def test_imports_from_files(self, client):
        resp = client.post("/api/prompts/import")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["imported"] == 3
