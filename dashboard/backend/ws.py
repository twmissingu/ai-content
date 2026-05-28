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


class ConnectionManager:
    """Manages WebSocket connections and broadcasts status updates."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self._last_status_hash: str = ""
        self._watcher_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info(f"WebSocket connected ({len(self._connections)} total)")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(f"WebSocket disconnected ({len(self._connections)} total)")

    async def broadcast(self, data: dict):
        """Send data to all connected clients."""
        if not self._connections:
            return
        message = json.dumps(data, ensure_ascii=False)
        dead: list[WebSocket] = []
        async with self._lock:
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
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

    def _status_hash(self, status: dict) -> str:
        """Compute a hash of the status to detect changes."""
        return hash(json.dumps(status, sort_keys=True, default=str))

    async def _watch_status_files(self):
        """Poll status files every 3s and broadcast on change."""
        while True:
            try:
                status = await asyncio.to_thread(self._build_status)
                h = self._status_hash(status)
                if h != self._last_status_hash:
                    self._last_status_hash = h
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
