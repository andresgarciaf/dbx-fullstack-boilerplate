"""Request middleware for logging and context management."""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from core.context import (
    clear_request_id,
    clear_user_token,
    set_request_id,
    set_user_token,
)

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and set request context from headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate request ID for tracing
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)

        # Extract user token from Databricks Apps header (X-Forwarded-Access-Token)
        user_token = request.headers.get("X-Forwarded-Access-Token")
        set_user_token(user_token)

        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception:
            clear_user_token()
            clear_request_id()
            raise

        # Add request ID to response headers for client tracing
        response.headers["X-Request-ID"] = request_id

        # Log non-health requests
        if request.url.path not in ["/health", "/api/health"]:
            duration_ms = round((time.time() - start_time) * 1000)
            logger.info(
                "%s %s -> %s (%dms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        # Clear request context
        clear_user_token()
        clear_request_id()

        return response
