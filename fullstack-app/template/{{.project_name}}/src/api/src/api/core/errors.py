"""Structured error classes for consistent API error responses.

Error hierarchy following Databricks appkit patterns with standard HTTP status codes.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with structured response support."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize error for JSON response."""
        result: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class ValidationError(AppError):
    """Invalid input data (400)."""

    status_code = 400
    code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    """Missing or invalid authentication (401)."""

    status_code = 401
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppError):
    """Permission denied (403)."""

    status_code = 403
    code = "AUTHORIZATION_ERROR"


class NotFoundError(AppError):
    """Resource not found (404)."""

    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    """State conflict, e.g., duplicate resource (409)."""

    status_code = 409
    code = "CONFLICT"


class RateLimitError(AppError):
    """Too many requests (429)."""

    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"


class ConfigurationError(AppError):
    """Application misconfiguration (500)."""

    status_code = 500
    code = "CONFIGURATION_ERROR"


class DatabaseError(AppError):
    """Database operation failed (500)."""

    status_code = 500
    code = "DATABASE_ERROR"


class ExternalServiceError(AppError):
    """External API or service failed (502)."""

    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"


class ServiceUnavailableError(AppError):
    """Service temporarily unavailable (503)."""

    status_code = 503
    code = "SERVICE_UNAVAILABLE"
