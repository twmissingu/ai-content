"""Tests for WebSocket manager (dashboard/backend/ws.py)."""

import asyncio
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def manager():
    from dashboard.backend.ws import ConnectionManager
    return ConnectionManager()


class TestConnect:
    @pytest.mark.asyncio
    async def test_adds_client(self, manager):
        ws = AsyncMock()
        await manager.connect(ws)
        assert ws in manager._connections

    @pytest.mark.asyncio
    async def test_accepts_websocket(self, manager):
        ws = AsyncMock()
        await manager.connect(ws)
        ws.accept.assert_called_once()


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_removes_client(self, manager):
        ws = AsyncMock()
        await manager.connect(ws)
        await manager.disconnect(ws)
        assert ws not in manager._connections

    @pytest.mark.asyncio
    async def test_nonexistent_is_noop(self, manager):
        ws = AsyncMock()
        await manager.disconnect(ws)  # should not raise

    @pytest.mark.asyncio
    async def test_only_removes_target(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.disconnect(ws1)
        assert ws1 not in manager._connections
        assert ws2 in manager._connections


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_sends_to_all(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.broadcast({"type": "test"})
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_json(self, manager):
        ws = AsyncMock()
        await manager.connect(ws)
        data = {"type": "pipeline_status", "agents": {}}
        await manager.broadcast(data)
        sent = json.loads(ws.send_text.call_args[0][0])
        assert sent["type"] == "pipeline_status"

    @pytest.mark.asyncio
    async def test_removes_dead_connections(self, manager):
        ws_good = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.send_text.side_effect = Exception("connection closed")
        await manager.connect(ws_good)
        await manager.connect(ws_bad)
        await manager.broadcast({"type": "test"})
        assert ws_good in manager._connections
        assert ws_bad not in manager._connections

    @pytest.mark.asyncio
    async def test_empty_connections(self, manager):
        await manager.broadcast({"type": "test"})  # should not raise


class TestStatusHash:
    def test_deterministic(self, manager):
        status = {"type": "test", "value": 42}
        h1 = manager._status_hash(status)
        h2 = manager._status_hash(status)
        assert h1 == h2

    def test_different_for_different_data(self, manager):
        h1 = manager._status_hash({"a": 1})
        h2 = manager._status_hash({"a": 2})
        assert h1 != h2


class TestBuildStatus:
    def test_reads_status_files(self, manager, tmp_path, monkeypatch):
        import json as json_mod

        monkeypatch.setattr("dashboard.backend.ws.STATUS_DIR", tmp_path)

        status_file = tmp_path / "scout.json"
        status_file.write_text(json_mod.dumps({
            "agent": "scout",
            "status": "running",
            "progress_pct": 50,
            "started_at": "20260528_120000",
        }))

        monkeypatch.setattr(
            "dashboard.backend.ws.read_json",
            lambda f: json_mod.loads(f.read_text()),
        )
        monkeypatch.setattr(
            "dashboard.backend.ws.detect_timeout",
            lambda data: False,
        )
        monkeypatch.setattr(
            "dashboard.backend.ws.check_budget_limit",
            lambda: {"current_cost": 5.0, "budget": 15.0},
        )

        result = manager._build_status()

        assert result["type"] == "pipeline_status"
        assert "scout" in result["agents"]
        assert "budget" in result
        assert "timestamp" in result

    def test_empty_status_dir(self, manager, tmp_path, monkeypatch):
        monkeypatch.setattr("dashboard.backend.ws.STATUS_DIR", tmp_path)
        monkeypatch.setattr(
            "dashboard.backend.ws.check_budget_limit",
            lambda: {"current_cost": 0, "budget": 15.0},
        )

        result = manager._build_status()
        assert result["agents"] == {}

    def test_marks_timeout(self, manager, tmp_path, monkeypatch):
        import json as json_mod

        monkeypatch.setattr("dashboard.backend.ws.STATUS_DIR", tmp_path)

        status_file = tmp_path / "writer.json"
        status_file.write_text(json_mod.dumps({
            "agent": "writer",
            "status": "running",
            "progress_pct": 30,
            "started_at": "20260528_120000",
        }))

        monkeypatch.setattr(
            "dashboard.backend.ws.read_json",
            lambda f: json_mod.loads(f.read_text()),
        )
        monkeypatch.setattr(
            "dashboard.backend.ws.detect_timeout",
            lambda data: True,
        )
        monkeypatch.setattr(
            "dashboard.backend.ws.check_budget_limit",
            lambda: {"current_cost": 0, "budget": 15.0},
        )

        result = manager._build_status()
        assert result["agents"]["writer"]["timeout"] is True


class TestWatcher:
    def test_start_watcher_creates_task(self, manager):
        async def run():
            manager.start_watcher()
            assert manager._watcher_task is not None
            manager.stop_watcher()

        asyncio.run(run())

    def test_start_watcher_no_loop(self, manager):
        # When no event loop is running, should log warning and not crash
        manager.start_watcher()
        assert manager._watcher_task is None

    def test_stop_watcher_no_task(self, manager):
        manager.stop_watcher()  # should not raise

    @pytest.mark.asyncio
    async def test_watcher_broadcasts_on_change(self, manager):
        call_count = 0

        def mock_build():
            nonlocal call_count
            call_count += 1
            return {"type": "test", "count": call_count}

        ws = AsyncMock()
        await manager.connect(ws)

        with patch.object(manager, '_build_status', side_effect=mock_build):
            # Start watcher, let it run one iteration, then stop
            task = asyncio.create_task(manager._watch_status_files())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Should have broadcast at least once
        assert ws.send_text.call_count >= 1
