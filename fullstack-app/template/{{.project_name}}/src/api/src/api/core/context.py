"""Request Context Variables.

Uses Python's contextvars for request-scoped state that works with async/await.
Each request gets its own isolated context automatically.
"""

from __future__ import annotations

from contextvars import ContextVar

# Per-request user token from Databricks Apps (X-Forwarded-Access-Token header)
_user_token_var: ContextVar[str | None] = ContextVar("user_token", default=None)

# Per-request unique identifier for tracing
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_user_token() -> str | None:
    """Get the current request's user token."""
    return _user_token_var.get()


def set_user_token(token: str | None) -> None:
    """Set the user token for the current request context."""
    _user_token_var.set(token)


def clear_user_token() -> None:
    """Clear the user token (reset to default)."""
    _user_token_var.set(None)


def get_request_id() -> str | None:
    """Get the current request's unique identifier."""
    return _request_id_var.get()


def set_request_id(request_id: str | None) -> None:
    """Set the request ID for the current request context."""
    _request_id_var.set(request_id)


def clear_request_id() -> None:
    """Clear the request ID (reset to default)."""
    _request_id_var.set(None)
