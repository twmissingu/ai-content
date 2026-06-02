"""API authentication middleware.

Simple API Key authentication via X-API-Key header.
When API_KEY env var is not set, authentication is skipped
only in development mode. In production/staging, missing API_KEY
denies all requests.
"""

import hmac
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config.settings import ENVIRONMENT

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
        self._deny_all = False
        if self._api_key:
            logger.info("API authentication enabled")
        elif ENVIRONMENT in ("production", "staging"):
            logger.error(
                "API_KEY is not set in %s mode — denying all requests. "
                "Set the API_KEY environment variable before starting the server.",
                ENVIRONMENT,
            )
            self._deny_all = True
        else:
            logger.warning("API authentication disabled (no API_KEY set). "
                          "Set API_KEY env var to enable authentication.")

    async def dispatch(self, request: Request, call_next):
        # Deny all requests if API_KEY is missing in non-development mode
        if self._deny_all:
            return JSONResponse(
                status_code=503,
                content={"detail": "Server misconfiguration: API_KEY is not set"},
            )

        # Skip auth if no key configured (development only)
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
