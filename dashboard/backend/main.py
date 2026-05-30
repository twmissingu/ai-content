"""FastAPI Dashboard backend — 稿定 AI 内容生产系统.

Slim entry point: middleware setup, route mounting, lifespan management.
"""

import json
import logging
import os
import threading
from pathlib import Path

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dashboard.backend.auth import AuthMiddleware
from dashboard.backend.background import (
    budget_monitor_loop,
    budget_stop_event,
    scan_loop,
    scanner_stop_event,
)
from dashboard.backend.database import init_db, import_prompts_from_files
from dashboard.backend.search import auto_index_if_needed
from dashboard.backend.ws import ws_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gaoding.dashboard")

# Import route modules
from dashboard.backend.routes.pipeline import router as pipeline_router
from dashboard.backend.routes.approval import router as approval_router
from dashboard.backend.routes.topics import router as topics_router
from dashboard.backend.routes.data import router as data_router
from dashboard.backend.routes.kb import router as kb_router
from dashboard.backend.routes.config import router as config_router
from dashboard.backend.routes.health import router as health_router
from dashboard.backend.routes.traces import router as traces_router
from dashboard.backend.routes.prompts import router as prompts_router
from dashboard.backend.routes.sources import router as sources_router
from dashboard.backend.routes.reader import router as reader_router
from fastapi import WebSocket as WSProtocol, WebSocketDisconnect

# Import rate limiter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
from collections import defaultdict
import time


class RateLimiter:
    """Simple in-memory rate limiter with bounded memory."""

    _MAX_CLIENTS = 10000

    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60
        with self._lock:
            # Evict stale clients when map grows too large
            if len(self.requests) > self._MAX_CLIENTS:
                stale = [ip for ip, ts in self.requests.items()
                         if not ts or ts[-1] < minute_ago]
                for ip in stale:
                    del self.requests[ip]

            self.requests[client_ip] = [
                t for t in self.requests[client_ip] if t > minute_ago
            ]
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                return False
            self.requests[client_ip].append(now)
            return True


rate_limiter = RateLimiter(requests_per_minute=120)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/api/health":
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.is_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."}
            )
        return await call_next(request)


# CORS origins - configurable via environment variable
def _get_cors_origins() -> list[str]:
    """Get and validate CORS origins from environment."""
    env_value = os.getenv("CORS_ORIGINS", "")
    default_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8710",
        "http://127.0.0.1:8710",
    ]
    if not env_value:
        return default_origins
    origins = [o.strip() for o in env_value.split(",") if o.strip()]
    environment = os.getenv("ENV", os.getenv("NODE_ENV", "development"))
    if "*" in origins and environment == "production":
        logger.warning("CORS_ORIGINS='*' is not recommended for production!")
    valid_origins = []
    for origin in origins:
        if origin == "*":
            valid_origins.append(origin)
        elif origin.startswith(("http://", "https://")):
            valid_origins.append(origin)
        else:
            logger.warning(f"Invalid CORS origin ignored: {origin}")
    return valid_origins if valid_origins else default_origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, search index, and start background scanner."""
    init_db()
    logger.info("SQLite database initialized")

    try:
        index_stats = auto_index_if_needed()
        logger.info(f"Knowledge base index: {index_stats}")
    except Exception as e:
        logger.error(f"Error initializing search index: {e}")

    try:
        imported = import_prompts_from_files()
        if imported:
            logger.info(f"Imported {imported} prompt templates from files")
    except Exception as e:
        logger.error(f"Error importing prompts: {e}")

    thread = threading.Thread(target=scan_loop, daemon=True, name="action-scanner")
    thread.start()
    logger.info("Background action scanner started (10s interval)")

    budget_thread = threading.Thread(target=budget_monitor_loop, daemon=True, name="budget-monitor")
    budget_thread.start()
    logger.info("Budget monitor started")

    ws_manager.start_watcher()

    yield

    ws_manager.stop_watcher()
    scanner_stop_event.set()
    budget_stop_event.set()
    logger.info("Background tasks stopped")


app = FastAPI(title="稿定 Dashboard", version="0.7.0", lifespan=lifespan)

# Middleware (order matters: last added = first executed)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    AuthMiddleware,
    api_key=os.getenv("API_KEY"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Mount route modules
app.include_router(pipeline_router)
app.include_router(approval_router)
app.include_router(topics_router)
app.include_router(data_router)
app.include_router(kb_router)
app.include_router(config_router)
app.include_router(health_router)
app.include_router(traces_router)
app.include_router(prompts_router)
app.include_router(sources_router)
app.include_router(reader_router)


@app.websocket("/ws/pipeline")
async def websocket_pipeline(websocket: WSProtocol):
    """WebSocket endpoint for real-time pipeline status updates."""
    await ws_manager.connect(websocket)
    try:
        # Send initial status immediately
        status = ws_manager._build_status()
        await websocket.send_text(json.dumps(status, ensure_ascii=False))
        # Keep connection alive, handle client messages
        while True:
            data = await websocket.receive_text()
            # Client can send ping/pong or request specific data
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8710)
