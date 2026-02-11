"""Lakebase (PostgreSQL) backends for Databricks.

Lightweight implementation for executing queries against Databricks Lakebase
(managed PostgreSQL) with connection pooling, OAuth token refresh, and async support.
"""

from __future__ import annotations

import abc
import contextlib
import logging
import os
import time
from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING, Any, TypeVar

import psycopg

from api.clients.sql_core import Row, dataclass_to_columns
from api.clients.sql_escapes import escape_pg_full_name, escape_pg_name

if TYPE_CHECKING:
    from collections.abc import Iterator

    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.database import DatabaseInstance

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Token refresh interval (15 minutes before expiry)
TOKEN_REFRESH_INTERVAL = 900


class PostgresConfig:
    """PostgreSQL connection configuration for Lakebase."""

    def __init__(
        self,
        host: str,
        port: str = "5432",
        database: str = "databricks_postgres",
        user: str = "token",
        sslmode: str = "require",
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.sslmode = sslmode

    @classmethod
    def from_instance(cls, instance: DatabaseInstance) -> PostgresConfig:
        """Create config from a Databricks Lakebase DatabaseInstance."""
        return cls(host=instance.read_write_dns)

    def build_connection_string(self, password: str) -> str:
        """Build PostgreSQL connection string.

        Args:
            password: OAuth token for authentication (required).
        """
        return f"postgresql://{self.user}:{password}@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"

    def __repr__(self) -> str:
        return f"<PostgresConfig host={self.host} port={self.port} database={self.database}>"


class OAuthTokenManager:
    """Manages OAuth token refresh for Lakebase connections.

    Databricks Apps inject PGPASSWORD as an OAuth token that expires.
    This manager handles automatic token refresh using the WorkspaceClient.

    Args:
        workspace_client: Databricks WorkspaceClient for token refresh
        refresh_interval: Seconds between token refreshes (default: 900)
    """

    def __init__(
        self,
        workspace_client: WorkspaceClient | None = None,
        refresh_interval: int = TOKEN_REFRESH_INTERVAL,
    ):
        self._token: str | None = None
        self._last_refresh: float = 0
        self._refresh_interval = refresh_interval
        self._workspace_client = workspace_client
        self._use_env_fallback = True

    @classmethod
    def from_workspace_client(cls, workspace_client: WorkspaceClient) -> OAuthTokenManager:
        """Create token manager that exclusively uses WorkspaceClient for tokens.

        Unlike default constructor, does NOT fall back to environment variables.
        """
        manager = cls(workspace_client=workspace_client)
        manager._use_env_fallback = False
        return manager

    def set_workspace_client(self, workspace_client: WorkspaceClient) -> None:
        """Set or update the WorkspaceClient."""
        self._workspace_client = workspace_client

    def get_token(self) -> str:
        """Get a valid OAuth token, refreshing if needed."""
        current_time = time.time()

        if self._token is None or (current_time - self._last_refresh) > self._refresh_interval:
            self._refresh_token()

        return self._token or ""

    def _refresh_token(self) -> bool:
        """Refresh the OAuth token.

        Tries multiple methods in order:
        1. WorkspaceClient.config.oauth_token()
        2. WorkspaceClient header_factory
        3. PGPASSWORD environment variable (if _use_env_fallback is True)
        4. DATABRICKS_TOKEN environment variable (if _use_env_fallback is True)
        """
        logger.debug("Refreshing Lakebase OAuth token...")

        # Method 1: Use provided WorkspaceClient
        ws = self._workspace_client
        if ws:
            try:
                oauth_token = ws.config.oauth_token()
                if oauth_token and oauth_token.access_token:
                    self._token = oauth_token.access_token
                    self._last_refresh = time.time()
                    logger.info("Lakebase token refreshed via WorkspaceClient.oauth_token()")
                    return True
            except Exception as e:
                logger.debug(f"oauth_token() failed: {e}")

            # Try header_factory as fallback
            try:
                if hasattr(ws.config, "header_factory") and ws.config.header_factory:
                    headers = ws.config.header_factory()
                    auth_header = headers.get("Authorization", "")
                    if auth_header.startswith("Bearer "):
                        self._token = auth_header[7:]
                        self._last_refresh = time.time()
                        logger.info("Lakebase token refreshed via header_factory")
                        return True
            except Exception as e:
                logger.debug(f"header_factory failed: {e}")

        # Environment fallbacks (only if enabled)
        if self._use_env_fallback:
            # Method 2: PGPASSWORD from environment (set by Databricks Apps)
            pg_password = os.environ.get("PGPASSWORD")
            if pg_password and len(pg_password) > 20:
                self._token = pg_password
                self._last_refresh = time.time()
                logger.info("Using PGPASSWORD from environment")
                return True

            # Method 3: DATABRICKS_TOKEN
            db_token = os.environ.get("DATABRICKS_TOKEN")
            if db_token:
                self._token = db_token
                self._last_refresh = time.time()
                logger.info("Using DATABRICKS_TOKEN")
                return True

        logger.warning("Failed to refresh Lakebase OAuth token")
        return False

    def invalidate(self) -> None:
        """Invalidate current token to force refresh on next get."""
        self._last_refresh = 0


class LakebaseBackend(abc.ABC):
    """Abstract base class for Lakebase (PostgreSQL) backends.

    Provides interface for executing SQL and fetching results
    against Databricks Lakebase instances with automatic OAuth token refresh.
    """

    # Shared token manager and config - set by subclasses
    _token_manager: OAuthTokenManager
    _pg_config: PostgresConfig | None = None
    _connection_string: str | None = None

    def _get_pg_config(self) -> PostgresConfig:
        """Get PostgreSQL configuration (must be set by caller)."""
        if self._pg_config is None:
            raise ValueError("pg_config not set. Pass pg_config when constructing the backend.")
        return self._pg_config

    def _build_connection_string(self) -> str:
        """Build connection string with fresh OAuth token."""
        if self._connection_string:
            return self._connection_string

        config = self._get_pg_config()
        password = self._token_manager.get_token()
        return config.build_connection_string(password)

    @staticmethod
    def _is_auth_error(e: Exception) -> bool:
        """Check if exception is an authentication error."""
        error_str = str(e).lower()
        return "authentication" in error_str or "password" in error_str

    @abc.abstractmethod
    def execute(self, sql: str, params: tuple | None = None) -> int:
        """Execute a SQL statement."""

    @abc.abstractmethod
    def fetch(self, sql: str, params: tuple | None = None) -> Iterator[Row]:
        """Execute a query and fetch results."""

    def fetch_one(self, sql: str, params: tuple | None = None) -> Row | None:
        """Fetch first row from query results."""
        for row in self.fetch(sql, params):
            return row
        return None

    def fetch_value(self, sql: str, params: tuple | None = None) -> Any:
        """Fetch first column of first row."""
        row = self.fetch_one(sql, params)
        return row[0] if row else None

    def fetch_all(self, sql: str, params: tuple | None = None) -> list[Row]:
        """Fetch all rows as a list."""
        return list(self.fetch(sql, params))

    def save_table(
        self,
        full_name: str,
        rows: Iterator[T],
        klass: type[T],
        mode: str = "append",
    ) -> None:
        """Save dataclass instances to a PostgreSQL table."""
        if not is_dataclass(klass):
            raise ValueError(f"{klass} is not a dataclass")

        rows_list = list(rows)
        if not rows_list:
            return

        field_names = [f.name for f in fields(klass)]
        escaped_table = escape_pg_full_name(full_name)
        escaped_cols = ", ".join(escape_pg_name(c) for c in field_names)
        placeholders = ", ".join(["%s"] * len(field_names))

        if mode == "overwrite":
            self.execute(f"TRUNCATE TABLE {escaped_table}")

        sql = f"INSERT INTO {escaped_table} ({escaped_cols}) VALUES ({placeholders})"
        for row in rows_list:
            values = tuple(getattr(row, name) for name in field_names)
            self.execute(sql, values)

    def create_table(self, full_name: str, klass: type[T]) -> None:
        """Create a PostgreSQL table from a dataclass schema."""
        columns = dataclass_to_columns(klass)
        escaped_table = escape_pg_full_name(full_name)

        pg_type_map = {
            "BIGINT": "BIGINT",
            "STRING": "TEXT",
            "DOUBLE": "DOUBLE PRECISION",
            "BOOLEAN": "BOOLEAN",
            "DATE": "DATE",
            "TIMESTAMP": "TIMESTAMP WITH TIME ZONE",
            "DECIMAL(38,18)": "NUMERIC(38,18)",
        }

        col_defs = []
        for name, sql_type in columns:
            pg_type = pg_type_map.get(sql_type, "TEXT")
            col_defs.append(f"{escape_pg_name(name)} {pg_type}")

        sql = f"CREATE TABLE IF NOT EXISTS {escaped_table} ({', '.join(col_defs)})"
        self.execute(sql)


class SyncLakebaseBackend(LakebaseBackend):
    """Synchronous Lakebase backend with OAuth token refresh.

    Executes queries synchronously against a Lakebase PostgreSQL instance.
    Automatically refreshes OAuth tokens before expiration.

    Args:
        workspace_client: Databricks WorkspaceClient for token refresh
        pg_config: PostgreSQL configuration (optional, uses env vars if not provided)
        connection_string: PostgreSQL connection string (optional, overrides pg_config)
        _token_manager: Pre-configured token manager (internal use)
    """

    def __init__(
        self,
        workspace_client: WorkspaceClient | None = None,
        pg_config: PostgresConfig | None = None,
        connection_string: str | None = None,
        *,
        _token_manager: OAuthTokenManager | None = None,
    ):
        self._connection_string = connection_string
        self._token_manager = _token_manager or OAuthTokenManager(workspace_client=workspace_client)
        self._pg_config: PostgresConfig | None = pg_config
        self._conn = None

    def _get_connection(self):
        """Get or create a connection with fresh token."""
        conn_string = self._build_connection_string()

        if self._conn is None:
            self._conn = psycopg.connect(conn_string)

        return self._conn

    def _reconnect(self):
        """Force reconnection with fresh token."""
        if self._conn:
            with contextlib.suppress(Exception):
                self._conn.close()
        self._conn = None
        self._token_manager.invalidate()

    def execute(self, sql: str, params: tuple | None = None) -> int:
        """Execute a SQL statement with auto-retry on auth failure."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conn.commit()
                return cur.rowcount
        except Exception as e:
            if self._is_auth_error(e):
                logger.warning("Auth error, refreshing token and retrying...")
                self._reconnect()
                conn = self._get_connection()
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    conn.commit()
                    return cur.rowcount
            raise

    def fetch(self, sql: str, params: tuple | None = None) -> Iterator[Row]:
        """Execute a query with auto-retry on auth failure."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(sql, params)
                col_names = [desc[0] for desc in cur.description]
                RowClass = Row.factory(col_names)
                for raw_row in cur:
                    yield RowClass(*raw_row)
        except Exception as e:
            if self._is_auth_error(e):
                logger.warning("Auth error, refreshing token and retrying...")
                self._reconnect()
                conn = self._get_connection()
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    col_names = [desc[0] for desc in cur.description]
                    RowClass = Row.factory(col_names)
                    for raw_row in cur:
                        yield RowClass(*raw_row)
            else:
                raise

    def close(self):
        """Close the connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


class AsyncLakebaseBackend(LakebaseBackend):
    """Asynchronous Lakebase backend with OAuth token refresh.

    Executes queries asynchronously with connection pooling support.
    Automatically refreshes OAuth tokens before expiration.

    Args:
        workspace_client: Databricks WorkspaceClient for token refresh
        pg_config: PostgreSQL configuration (optional, uses env vars if not provided)
        pool: AsyncConnectionPool from psycopg_pool (optional)
        _token_manager: Pre-configured token manager (internal use)
    """

    def __init__(
        self,
        workspace_client: WorkspaceClient | None = None,
        pg_config: PostgresConfig | None = None,
        pool: Any | None = None,
        *,
        _token_manager: OAuthTokenManager | None = None,
    ):
        self._pool = pool
        self._token_manager = _token_manager or OAuthTokenManager(workspace_client=workspace_client)
        self._pg_config: PostgresConfig | None = pg_config
        self._connection_string: str | None = None

    # Sync methods not supported
    def execute(self, sql: str, params: tuple | None = None) -> int:
        raise NotImplementedError("Use execute_async() for async backend")

    def fetch(self, sql: str, params: tuple | None = None) -> Iterator[Row]:
        raise NotImplementedError("Use fetch_async() for async backend")

    async def execute_async(self, sql: str, params: tuple | None = None) -> int:
        """Execute a SQL statement asynchronously with auto-retry."""
        try:
            async with self._get_connection() as conn, conn.cursor() as cur:
                await cur.execute(sql, params)
                await conn.commit()
                return cur.rowcount
        except Exception as e:
            if self._is_auth_error(e):
                logger.warning("Auth error, refreshing token and retrying...")
                self._token_manager.invalidate()
                async with self._get_connection() as conn, conn.cursor() as cur:
                    await cur.execute(sql, params)
                    await conn.commit()
                    return cur.rowcount
            raise

    async def fetch_async(self, sql: str, params: tuple | None = None) -> list[Row]:
        """Execute a query and return Row objects."""
        try:
            async with self._get_connection() as conn, conn.cursor() as cur:
                await cur.execute(sql, params)
                col_names = [desc[0] for desc in cur.description]
                RowClass = Row.factory(col_names)
                rows = await cur.fetchall()
                return [RowClass(*raw_row) for raw_row in rows]
        except Exception as e:
            if self._is_auth_error(e):
                logger.warning("Auth error, refreshing token and retrying...")
                self._token_manager.invalidate()
                async with self._get_connection() as conn, conn.cursor() as cur:
                    await cur.execute(sql, params)
                    col_names = [desc[0] for desc in cur.description]
                    RowClass = Row.factory(col_names)
                    rows = await cur.fetchall()
                    return [RowClass(*raw_row) for raw_row in rows]
            raise

    async def fetch_one_async(self, sql: str, params: tuple | None = None) -> Row | None:
        """Fetch first row asynchronously."""
        rows = await self.fetch_async(sql, params)
        return rows[0] if rows else None

    async def fetch_value_async(self, sql: str, params: tuple | None = None) -> Any:
        """Fetch first value asynchronously."""
        row = await self.fetch_one_async(sql, params)
        return row[0] if row else None

    def _get_connection(self):
        """Get connection context manager."""
        if self._pool:
            return self._pool.connection()

        conn_string = self._build_connection_string()
        return psycopg.AsyncConnection.connect(conn_string)

    async def close(self):
        """Close the pool if present."""
        if self._pool:
            await self._pool.close()
