"""Databricks service for workspace and SQL operations.

Provides centralized access to Databricks clients with cached properties
for efficient resource usage across the application.
"""

from __future__ import annotations

import abc
import logging
from functools import cached_property

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition

from clients import (
    AsyncLakebaseBackend,
    LakebaseBackend,
    OAuthTokenManager,
    PostgresConfig,
    SqlBackend,
    StatementExecutionBackend,
    SyncLakebaseBackend,
)
from core import settings

logger = logging.getLogger(__name__)


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
        from .env file during development. Tags all SDK calls with product
        identifier for audit trail visibility.
        """
        return WorkspaceClient(
            config=self._settings.databricks_config,
            product="{{.project_name}}",
            product_version=self._settings.api_version,
        )

    @cached_property
    def sql_backend(self) -> SqlBackend:
        """Get SQL backend for Databricks SQL Warehouse queries.

        Executes queries via Statement Execution API with automatic
        result pagination and type conversion. Falls back to auto-selecting
        the best available warehouse when DATABRICKS_WAREHOUSE is not set.
        """
        warehouse_id = self._settings.databricks_warehouse or self._find_best_warehouse()
        if not warehouse_id:
            raise ValueError("No SQL warehouse available. Set DATABRICKS_WAREHOUSE or ensure a warehouse exists.")
        return StatementExecutionBackend(
            self.workspace_client,
            warehouse_id,
            disposition=Disposition.INLINE,
        )

    def _find_best_warehouse(self) -> str | None:
        """Auto-select best SQL warehouse.

        Priority: running shared > running any > stopped shared > stopped any.
        """
        from databricks.sdk.service.sql import State

        try:
            warehouses = list(self.workspace_client.warehouses.list())
        except Exception:
            logger.warning("Failed to list warehouses for auto-selection")
            return None
        if not warehouses:
            return None

        buckets: dict[int, list] = {0: [], 1: [], 2: [], 3: []}
        for w in warehouses:
            is_running = w.state == State.RUNNING
            name_lower = (w.name or "").lower()
            is_shared = "shared" in name_lower
            if is_running and is_shared:
                buckets[0].append(w)
            elif is_running:
                buckets[1].append(w)
            elif is_shared:
                buckets[2].append(w)
            else:
                buckets[3].append(w)
        for bucket in buckets.values():
            if bucket:
                logger.info("Auto-selected warehouse: %s (%s)", bucket[0].name, bucket[0].id)
                return bucket[0].id
        return None

    @cached_property
    def _pg_config(self) -> PostgresConfig:
        """Resolve PostgreSQL config from Lakebase instance via SDK."""
        instance = self.workspace_client.database.get_database_instance(
            self._settings.instance_name
        )
        return PostgresConfig.from_instance(instance)

    @cached_property
    def _token_manager(self) -> OAuthTokenManager:
        """Get OAuth token manager for Lakebase connections."""
        return OAuthTokenManager.from_workspace_client(
            self.workspace_client,
            instance_name=self._settings.instance_name or None,
        )

    @property
    def token_manager(self) -> OAuthTokenManager:
        """Public accessor for the OAuth token manager."""
        return self._token_manager

    @cached_property
    def lakebase_backend(self) -> SyncLakebaseBackend:
        """Get synchronous Lakebase (PostgreSQL) backend.

        Resolves connection details from the Lakebase instance via SDK
        and configures OAuth token management via WorkspaceClient.
        """
        return SyncLakebaseBackend(
            workspace_client=self.workspace_client,
            pg_config=self._pg_config,
            _token_manager=self._token_manager,
        )

    @property
    def async_lakebase_backend(self) -> AsyncLakebaseBackend:
        """Get async Lakebase backend for high-performance queries.

        Resolves connection details from the Lakebase instance via SDK
        and configures OAuth token management via WorkspaceClient.
        Note: This is a property, not cached_property, because async
        backends may need fresh connections per request context.
        """
        if self._async_lakebase_backend is None:
            self._async_lakebase_backend = AsyncLakebaseBackend(
                workspace_client=self.workspace_client,
                pg_config=self._pg_config,
                _token_manager=self._token_manager,
            )
        return self._async_lakebase_backend
