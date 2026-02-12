"""Lakebase (PostgreSQL) backends for Databricks.

Lightweight implementation for executing queries against Databricks Lakebase
(managed PostgreSQL) with connection pooling, OAuth token refresh, and async support.
"""

from __future__ import annotations

import abc
import asyncio
import contextlib
import logging
import os
import socket
import subprocess
import time
from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING, Any, TypeVar

import psycopg

from clients.sql_core import Row, dataclass_to_columns
from clients.sql_escapes import escape_pg_full_name, escape_pg_name

if TYPE_CHECKING:
    from collections.abc import Iterator

    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.database import DatabaseInstance

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Token refresh interval (50 minutes for 1-hour credential TTL)
TOKEN_REFRESH_INTERVAL = 50 * 60


def resolve_hostname(hostname: str) -> str | None:
    """Resolve hostname to IP. Falls back to dig on macOS DNS failures."""
    try:
        result = socket.getaddrinfo(hostname, 5432)
        if result:
            return result[0][4][0]
    except socket.gaierror:
        pass
    try:
        result = subprocess.run(
            ["dig", "+short", hostname, "A"],
            capture_output=True, text=True, timeout=10,
        )
        ips = [line for line in result.stdout.strip().split("\n") if line and line[0].isdigit()]
        if ips:
            logger.info("Resolved %s -> %s via dig (Python DNS failed)", hostname, ips[0])
            return ips[0]
    except Exception as e:
        logger.warning("dig resolution failed for %s: %s", hostname, e)
    return None


class PostgresConfig:
    """PostgreSQL connection configuration for Lakebase."""

    def __init__(
        self,
        host: str,
        port: str = "5432",
        database: str = "databricks_postgres",
        user: str = "token",
        sslmode: str = "require",
        hostaddr: str | None = None,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.sslmode = sslmode
        self.hostaddr = hostaddr

    @classmethod
    def from_instance(cls, instance: DatabaseInstance) -> PostgresConfig:
        """Create config from a Databricks Lakebase DatabaseInstance."""
        hostaddr = resolve_hostname(instance.read_write_dns)
        return cls(host=instance.read_write_dns, hostaddr=hostaddr)

    def build_connection_string(self, password: str) -> str:
        """Build PostgreSQL connection string.

        Args:
            password: OAuth token for authentication (required).
        """
        conn_str = f"postgresql://{self.user}:{password}@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"
        if self.hostaddr:
            conn_str += f"&hostaddr={self.hostaddr}"
        return conn_str

    def __repr__(self) -> str:
        return f"<PostgresConfig host={self.host} port={self.port} database={self.database}>"


class OAuthTokenManager:
    """Manages OAuth token refresh for Lakebase connections.

    Databricks Apps inject PGPASSWORD as an OAuth token that expires.
    This manager handles automatic token refresh using the WorkspaceClient.

    Args:
        workspace_client: Databricks WorkspaceClient for token refresh
        refresh_interval: Seconds between token refreshes (default: 50 min)
        instance_name: Lakebase instance name for generate_database_credential()
    """

    def __init__(
        self,
        workspace_client: WorkspaceClient | None = None,
        refresh_interval: int = TOKEN_REFRESH_INTERVAL,
        instance_name: str | None = None,
    ):
        self._token: str | None = None
        self._last_refresh: float = 0
        self._refresh_interval = refresh_interval
        self._workspace_client = workspace_client
        self._instance_name = instance_name
        self._use_env_fallback = True
        self._refresh_task: asyncio.Task | None = None

    @classmethod
    def from_workspace_client(
        cls,
        workspace_client: WorkspaceClient,
        instance_name: str | None = None,
    ) -> OAuthTokenManager:
        """Create token manager that exclusively uses WorkspaceClient for tokens.

        Unlike default constructor, does NOT fall back to environment variables.
        """
        manager = cls(workspace_client=workspace_client, instance_name=instance_name)
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
        1. generate_database_credential() — dedicated Lakebase credential API
        2. WorkspaceClient.config.oauth_token()
        3. WorkspaceClient header_factory
        4. PGPASSWORD environment variable (if _use_env_fallback is True)
        5. DATABRICKS_TOKEN environment variable (if _use_env_fallback is True)
        """
        logger.debug("Refreshing Lakebase OAuth token...")

        ws = self._workspace_client
        if ws:
            # Method 1: Dedicated Lakebase credential API (properly scoped, 1-hour TTL)
            if self._instance_name:
                try:
                    import uuid

                    cred = ws.database.generate_database_credential(
                        request_id=str(uuid.uuid4()),
                        instance_names=[self._instance_name],
                    )
                    if cred and cred.access_token:
                        self._token = cred.access_token
                        self._last_refresh = time.time()
                        logger.info("Lakebase token refreshed via generate_database_credential()")
                        return True
                except Exception as e:
                    logger.debug("generate_database_credential() failed: %s", e)

            # Method 2: WorkspaceClient OAuth token
            try:
                oauth_token = ws.config.oauth_token()
                if oauth_token and oauth_token.access_token:
                    self._token = oauth_token.access_token
                    self._last_refresh = time.time()
                    logger.info("Lakebase token refreshed via WorkspaceClient.oauth_token()")
                    return True
            except Exception as e:
                logger.debug("oauth_token() failed: %s", e)

            # Method 3: header_factory as fallback
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
                logger.debug("header_factory failed: %s", e)

        # Environment fallbacks (only if enabled)
        if self._use_env_fallback:
            # Method 4: PGPASSWORD from environment (set by Databricks Apps)
            pg_password = os.environ.get("PGPASSWORD")
            if pg_password and len(pg_password) > 20:
                self._token = pg_password
                self._last_refresh = time.time()
                logger.info("Using PGPASSWORD from environment")
                return True

            # Method 5: DATABRICKS_TOKEN
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

    async def start_background_refresh(self) -> None:
        """Start background token refresh loop."""
        if self._refresh_task is not None:
            return
        # Do initial refresh synchronously
        self._refresh_token()
        self._refresh_task = asyncio.create_task(self._background_refresh_loop())

    async def _background_refresh_loop(self) -> None:
        """Background loop: refresh token every 50 minutes."""
        while True:
            try:
                await asyncio.sleep(50 * 60)
                await asyncio.to_thread(self._refresh_token)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in token refresh loop: %s", e)

    async def stop_background_refresh(self) -> None:
        """Stop the background refresh task."""
        if self._refresh_task:
            self._refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._refresh_task
            self._refresh_task = None


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
