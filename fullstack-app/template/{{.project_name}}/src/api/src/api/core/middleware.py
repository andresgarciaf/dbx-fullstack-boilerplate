"""Request middleware for logging and context management."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.core.context import clear_user_token, set_user_token

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and set user token from Databricks Apps header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract user token from Databricks Apps header (X-Forwarded-Access-Token)
        user_token = request.headers.get("X-Forwarded-Access-Token")
        set_user_token(user_token)

        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception:
            clear_user_token()
            raise

        # Log non-health requests
        if request.url.path not in ["/health", "/api/health"]:
            duration_ms = round((time.time() - start_time) * 1000)
            logger.info("%s %s -> %s (%dms)", request.method, request.url.path, response.status_code, duration_ms)

        # Clear request context
        clear_user_token()

        return response
