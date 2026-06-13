"""API authentication middleware.

Simple API Key authentication via X-API-Key header.
When API_KEY env var is not set, authentication is skipped
only in development mode. In production/staging, missing API_KEY
denies all requests.
"""

import hmac
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

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

# Auth failure tracking for security event alerting
_auth_failure_counts: dict[str, list[float]] = defaultdict(list)
_AUTH_FAILURE_WINDOW = 300  # 5 minutes
_AUTH_FAILURE_THRESHOLD = 10  # Alert after 10 failures in window
_last_alert_time: float = 0
_ALERT_COOLDOWN = 60  # Min 60 seconds between alerts


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
            self._log_auth_failure(request)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)

    def _log_auth_failure(self, request: Request):
        """Track auth failures per IP and alert if threshold exceeded."""
        global _last_alert_time
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        cutoff = now - _AUTH_FAILURE_WINDOW

        _auth_failure_counts[client_ip] = [
            t for t in _auth_failure_counts[client_ip] if t > cutoff
        ]
        _auth_failure_counts[client_ip].append(now)

        if len(_auth_failure_counts[client_ip]) >= _AUTH_FAILURE_THRESHOLD:
            if now - _last_alert_time > _ALERT_COOLDOWN:
                _last_alert_time = now
                logger.warning(
                    f"Auth failure threshold exceeded for {client_ip}: "
                    f"{len(_auth_failure_counts[client_ip])} failures in {_AUTH_FAILURE_WINDOW}s"
                )
                try:
                    from dashboard.backend.feishu import alert_agent_error
                    alert_agent_error(
                        "auth",
                        f"认证失败阈值告警: {client_ip} 在 {_AUTH_FAILURE_WINDOW}s 内失败 "
                        f"{len(_auth_failure_counts[client_ip])} 次",
                    )
                except Exception as e:
                    logger.debug(f"Failed to send auth failure alert: {e}")
