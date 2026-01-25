"""Databricks service for workspace and SQL operations.

Provides centralized access to Databricks clients with cached properties
for efficient resource usage across the application.
"""

from __future__ import annotations

import abc
from functools import cached_property

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition

from api.clients import (
    AsyncLakebaseBackend,
    LakebaseBackend,
    SqlBackend,
    StatementExecutionBackend,
    StatementExecutionPgBackend,
    SyncLakebaseBackend,
)
from api.core import settings


class GlobalContext(abc.ABC):
    """Abstract base for service contexts with lazy-loaded clients."""

    @cached_property
    def workspace_client(self) -> WorkspaceClient:
        raise ValueError("Workspace client not set")

    @cached_property
    def sql_backend(self) -> SqlBackend:
        raise ValueError("SQL backend not set")

    @cached_property
    def lakebase_backend(self) -> LakebaseBackend:
        raise ValueError("Lakebase backend not set")


class DatabricksService(GlobalContext):
    """Service providing access to Databricks resources.

    Uses cached properties to lazily initialize clients on first access.
    Clients are configured from application settings.

    Usage:
        service = DatabricksService()

        # SQL Warehouse queries
        rows = service.sql_backend.fetch("SELECT * FROM catalog.schema.table")

        # Lakebase (PostgreSQL) queries
        rows = service.lakebase_backend.fetch("SELECT * FROM schema.table")

        # Direct SDK access
        user = service.workspace_client.current_user.me()
    """

    def __init__(self, async_lakebase: bool = False):
        """Initialize service.

        Args:
            async_lakebase: If True, use AsyncLakebaseBackend instead of sync
        """
        super().__init__()
        self._settings = settings
        self._async_lakebase = async_lakebase
        self._async_lakebase_backend: AsyncLakebaseBackend | None = None

    @cached_property
    def workspace_client(self) -> WorkspaceClient:
        """Get Databricks WorkspaceClient.

        Uses per-user authentication when deployed, or local credentials
        from .env file during development.
        """
        return WorkspaceClient(config=self._settings.databricks_config)

    @cached_property
    def sql_backend(self) -> SqlBackend:
        """Get SQL backend for Databricks SQL Warehouse queries.

        Executes queries via Statement Execution API with automatic
        result pagination and type conversion.
        """
        return StatementExecutionBackend(
            self.workspace_client,
            self._settings.databricks_warehouse,
            disposition=Disposition.INLINE,
        )

    @cached_property
    def lakebase_backend(self) -> SyncLakebaseBackend:
        """Get synchronous Lakebase (PostgreSQL) backend.

        Uses StatementExecutionPgBackend factory which configures OAuth token
        management via WorkspaceClient. PostgreSQL config comes from settings.
        """
        return StatementExecutionPgBackend.sync(self.workspace_client)

    @property
    def async_lakebase_backend(self) -> AsyncLakebaseBackend:
        """Get async Lakebase backend for high-performance queries.

        Uses StatementExecutionPgBackend factory which configures OAuth token
        management via WorkspaceClient. PostgreSQL config comes from settings.
        Note: This is a property, not cached_property, because async
        backends may need fresh connections per request context.
        """
        if self._async_lakebase_backend is None:
            self._async_lakebase_backend = StatementExecutionPgBackend.async_(
                self.workspace_client
            )
        return self._async_lakebase_backend
