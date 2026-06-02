"""WebSocket manager for real-time pipeline status push.

Broadcasts status changes to all connected clients when status files change,
eliminating the need for polling.
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from config.settings import STATUS_DIR
from dashboard.backend.helpers import detect_timeout, read_json
from dashboard.backend.database import check_budget_limit

logger = logging.getLogger("gaoding.dashboard")


MAX_CONNECTIONS = 100


class ConnectionManager:
    """Manages WebSocket connections and broadcasts status updates."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = threading.Lock()
        self._last_status_hash: str = ""
        self._watcher_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        await self.register(websocket)

    async def register(self, websocket: WebSocket):
        """Register an already-accepted WebSocket connection."""
        with self._lock:
            if len(self._connections) >= MAX_CONNECTIONS:
                logger.warning(
                    f"Connection limit reached ({MAX_CONNECTIONS}), rejecting"
                )
                await websocket.close(code=4002, reason="Connection limit reached")
                return
            self._connections.append(websocket)
        logger.info(f"WebSocket connected ({len(self._connections)} total)")

    async def disconnect(self, websocket: WebSocket):
        with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(f"WebSocket disconnected ({len(self._connections)} total)")

    async def broadcast(self, data: dict):
        """Send data to all connected clients."""
        with self._lock:
            if not self._connections:
                return
            # Snapshot the list under lock, then send outside lock
            clients = list(self._connections)
        message = json.dumps(data, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)

    def _build_status(self) -> dict:
        """Read current pipeline status from disk."""
        agents = {}
        for f in STATUS_DIR.glob("*.json"):
            data = read_json(f)
            name = f.stem
            agents[name] = data
            timeout = detect_timeout(data)
            if timeout and data.get("progress_pct", 100) < 100:
                agents[name]["timeout"] = True

        budget = check_budget_limit()
        return {
            "type": "pipeline_status",
            "agents": agents,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": budget,
        }

    def _status_hash(self) -> str:
        """Compute deterministic change key from status file mtimes + sizes."""
        # This is deterministic across processes, unlike Python's hash()
        parts = []
        for f in sorted(STATUS_DIR.glob("*.json"), key=lambda x: x.name):
            try:
                stat = f.stat()
                parts.append(f"{f.name}:{stat.st_mtime_ns}:{stat.st_size}")
            except OSError:
                parts.append(f"{f.name}:0:0")
        return "|".join(parts)

    async def _watch_status_files(self):
        """Poll status files every 3s and broadcast on change."""
        while True:
            try:
                h = self._status_hash()
                if h != self._last_status_hash:
                    self._last_status_hash = h
                    status = await asyncio.to_thread(self._build_status)
                    await self.broadcast(status)
            except Exception as e:
                logger.error(f"Status watcher error: {e}")
            await asyncio.sleep(3)

    def start_watcher(self):
        """Start the background status file watcher."""
        try:
            loop = asyncio.get_running_loop()
            self._watcher_task = loop.create_task(self._watch_status_files())
            logger.info("WebSocket status watcher started (3s interval)")
        except RuntimeError:
            logger.warning("No event loop running, watcher not started")

    def stop_watcher(self):
        if self._watcher_task:
            self._watcher_task.cancel()


# Singleton instance
ws_manager = ConnectionManager()
