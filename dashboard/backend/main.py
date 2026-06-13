"""FastAPI Dashboard backend — 稿定 AI 内容生产系统.

Slim entry point: middleware setup, route mounting, lifespan management.
"""

import asyncio
import hmac
import json
import logging
import os
import threading
from pathlib import Path

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from dashboard.backend.auth import AuthMiddleware
from dashboard.backend.background import start_all_pollers, stop_all_pollers
from dashboard.backend.database import init_db, import_prompts_from_files, shutdown_db_connections
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
from dashboard.backend.routes.reviews import router as reviews_router
from fastapi import WebSocket as WSProtocol, WebSocketDisconnect

# Import rate limiter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
from collections import defaultdict
import time


class RateLimiter:
    """Simple in-memory rate limiter with bounded memory.

    NOTE: In-memory storage means per-process isolation — each worker gets its
    own counter. Multi-worker deployments (e.g. gunicorn --workers=N) require a
    shared store (Redis, memcached) for accurate rate limiting.
    """

    _MAX_CLIENTS = 10000

    def __init__(self, requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60
        with self._lock:
            # Evict stale clients when map grows too large.
            # NOTE: O(n) scan over all entries; could be optimized with an LRU
            # cache or time-bucketed counters if the client map grows very large.
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
    def __init__(self, app, trusted_proxies: set[str] | None = None):
        super().__init__(app)
        self._trusted_proxies = trusted_proxies or set()

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/api/health":
            return await call_next(request)
        # Support X-Forwarded-For only from trusted proxies
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded and client_ip in self._trusted_proxies:
            client_ip = forwarded.split(",")[0].strip()
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
    if "*" in origins:
        if environment == "production":
            logger.warning("CORS_ORIGINS='*' blocked in production — using default origins")
            return default_origins
        else:
            logger.warning("CORS_ORIGINS='*' detected — credentials will be disabled for wildcard")
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

    # Register prompt loader to break circular dependency (skills/ <-> dashboard/)
    from skills.common import register_prompt_loader
    from dashboard.backend.database.prompts import get_prompt as _get_prompt

    def _db_prompt_loader(name: str) -> str | None:
        row = _get_prompt(name)
        return row["template"] if row else None

    register_prompt_loader(_db_prompt_loader)
    logger.info("Prompt loader registered")

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

    if os.getenv("GAODING_DISABLE_POLLERS", "").lower() in ("1", "true", "yes"):
        logger.info("Background pollers disabled by GAODING_DISABLE_POLLERS")
    else:
        start_all_pollers()

    ws_manager.start_watcher()

    yield

    ws_manager.stop_watcher()
    stop_all_pollers()
    shutdown_db_connections()
    from skills.llm import close_cache_connections
    close_cache_connections()
    logger.info("Background tasks stopped")


_env = os.getenv("ENV", os.getenv("NODE_ENV", "development"))
app = FastAPI(
    title="稿定 Dashboard",
    description="稿定 AI 内容生产系统 — 自动化从选题发现到多平台分发的完整流程",
    version="0.9.9",
    docs_url="/api/docs" if _env != "production" else None,
    redoc_url="/api/redoc" if _env != "production" else None,
    openapi_url="/api/openapi.json" if _env != "production" else None,
    lifespan=lifespan,
)

# Middleware (order matters: last added = first executed)
_trusted_proxies = set(
    p.strip() for p in os.getenv("TRUSTED_PROXIES", "").split(",") if p.strip()
)
app.add_middleware(RateLimitMiddleware, trusted_proxies=_trusted_proxies)
app.add_middleware(
    AuthMiddleware,
    api_key=os.getenv("API_KEY"),
)
_cors_origins = _get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=("*" not in _cors_origins),  # credentials + wildcard is unsafe
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
app.include_router(reviews_router)
app.include_router(sources_router)
app.include_router(reader_router)

# Static file serving for generated images.
# SECURITY NOTE: FastAPI's StaticFiles does not validate filenames — paths like
# ../..  are blocked by the library, but callers should still ensure that only
# safe filenames are written to IMAGES_DIR upstream.
from config.settings import IMAGES_DIR
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    "/api/images",
    StaticFiles(directory=str(IMAGES_DIR), check_dir=True),
    name="images",
)


@app.middleware("http")
async def add_image_cache_headers(request: Request, call_next):
    """Add Cache-Control headers for static image responses."""
    response = await call_next(request)
    if request.url.path.startswith("/api/images/"):
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.websocket("/ws/pipeline")
async def websocket_pipeline(websocket: WSProtocol):
    """WebSocket endpoint for real-time pipeline status updates.

    Auth: When API_KEY is set, the client must send {"api_key": "..."} as the
    first message within 10 seconds.  Invalid or missing key closes with 4001.
    """
    api_key = os.getenv("API_KEY", "")
    if api_key:
        # Accept connection first, then authenticate via first message
        await websocket.accept()
        try:
            first_msg = await asyncio.wait_for(
                websocket.receive_text(), timeout=10
            )
            data = json.loads(first_msg)
            ws_key = data.get("api_key", "")
            if not isinstance(ws_key, str) or not hmac.compare_digest(ws_key, api_key):
                await websocket.close(code=4001, reason="Invalid API key")
                return
        except Exception:
            await websocket.close(code=4001, reason="Invalid API key")
            return
    else:
        await websocket.accept()

    # Register after successful auth
    await ws_manager.register(websocket)
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
