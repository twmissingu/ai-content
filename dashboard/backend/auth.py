"""API authentication middleware.

Simple API Key authentication via X-API-Key header.
When API_KEY env var is not set, authentication is skipped.
"""

import hmac
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("gaoding.dashboard")

# Paths that don't require authentication
_PUBLIC_PATHS = {
    "/api/health",
    "/api/token/log",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key authentication middleware."""

    def __init__(self, app, api_key: str | None = None):
        super().__init__(app)
        self._api_key = api_key or os.getenv("API_KEY", "")
        if self._api_key:
            logger.info("API authentication enabled")
        else:
            logger.info("API authentication disabled (no API_KEY set)")

    async def dispatch(self, request: Request, call_next):
        # Skip auth if no key configured
        if not self._api_key:
            return await call_next(request)

        # Skip auth for public paths
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check API key
        provided_key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(provided_key, self._api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
