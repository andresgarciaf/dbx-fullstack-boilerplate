"""Core module for configuration, context, middleware, and errors."""

from core.config import settings
from core.context import (
    clear_request_id,
    clear_user_token,
    get_request_id,
    get_user_token,
    set_request_id,
    set_user_token,
)
from core.errors import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConflictError,
    DatabaseError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
)
from core.logging_config import configure_logging
from core.middleware import RequestContextMiddleware

__all__ = [
    # Errors
    "AppError",
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "ConflictError",
    "DatabaseError",
    "ExternalServiceError",
    "NotFoundError",
    "RateLimitError",
    # Middleware
    "RequestContextMiddleware",
    "ServiceUnavailableError",
    "ValidationError",
    "clear_request_id",
    "clear_user_token",
    # Logging
    "configure_logging",
    "get_request_id",
    # Context
    "get_user_token",
    "set_request_id",
    "set_user_token",
    # Config
    "settings",
]
