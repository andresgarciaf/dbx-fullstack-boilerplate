"""Lakebase (PostgreSQL) backends for Databricks.

Lightweight implementation for executing queries against Databricks Lakebase
(managed PostgreSQL) with connection pooling, OAuth token refresh, and async support.
"""

from __future__ import annotations

import abc
import logging
import os
import time
from collections.abc import Iterable, Iterator
from dataclasses import fields, is_dataclass
from typing import Any, TypeVar

import psycopg

from api.clients.sql_core import Row, dataclass_to_columns
from api.clients.sql_escapes import escape_pg_full_name, escape_pg_name

from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Token refresh interval (15 minutes before expiry)
TOKEN_REFRESH_INTERVAL = 900


class PostgresConfigAttribute:
    """Configuration attribute metadata and descriptor for PostgresConfig."""

    name: str = None
    transform: type = str

    def __init__(self, env: str = None, default: Any = None, sensitive: bool = False):
        self.env = env
        self.default = default
        self.sensitive = sensitive

    def __get__(self, cfg: "PostgresConfig", owner):
        if cfg is None:
            return None
        return cfg._inner.get(self.name, self.default)

    def __set__(self, cfg: "PostgresConfig", value: Any):
        if value is not None:
            cfg._inner[self.name] = self.transform(value)

    def __repr__(self) -> str:
        return f"<PostgresConfigAttribute '{self.name}' {self.transform.__name__}>"


class PostgresConfig:
    """PostgreSQL connection configuration.

    Inspired by Databricks SDK Config pattern. Automatically loads from
    environment variables when not explicitly provided.

    Environment variables (set by Databricks Apps resource binding):
        PGHOST: PostgreSQL host
        PGPORT: Port (default: 5432)
        PGDATABASE: Database name (default: databricks_postgres)
        PGUSER: Username (default: token)
        PGSSLMODE: SSL mode (default: require)

    Note: Password/OAuth token is handled by OAuthTokenManager, not stored here.

    Usage:
        # Load from environment
        config = PostgresConfig()

        # Explicit configuration
        config = PostgresConfig(host="localhost", database="mydb")

        # Mix of explicit and environment
        config = PostgresConfig(host="localhost")  # other values from env
    """

    host: str = PostgresConfigAttribute(env="PGHOST")
    port: str = PostgresConfigAttribute(env="PGPORT", default="5432")
    database: str = PostgresConfigAttribute(
        env="PGDATABASE", default="databricks_postgres"
    )
    user: str = PostgresConfigAttribute(env="PGUSER", default="token")
    sslmode: str = PostgresConfigAttribute(env="PGSSLMODE", default="require")

    def __init__(self, **kwargs):
        self._inner: dict[str, Any] = {}

        # Set explicit values first
        self._set_inner_config(kwargs)

        # Load from environment for unset values
        self._load_from_env()

        # Validate required fields
        self._validate()

    def _set_inner_config(self, keyword_args: dict[str, Any]):
        """Set configuration from keyword arguments."""
        for attr in self.attributes():
            if attr.name not in keyword_args:
                continue
            value = keyword_args.get(attr.name)
            if value is not None:
                setattr(self, attr.name, value)

    def _load_from_env(self):
        """Load configuration from environment variables."""
        for attr in self.attributes():
            if not attr.env:
                continue
            if attr.name in self._inner:
                continue
            value = os.environ.get(attr.env)
            if value:
                setattr(self, attr.name, value)
                logger.debug(f"Loaded {attr.name} from {attr.env}")

    def _validate(self):
        """Validate required configuration."""
        if not self.host:
            raise ValueError(
                "PostgreSQL host not configured. Set PGHOST environment variable "
                "or pass host parameter explicitly."
            )

    @classmethod
    def attributes(cls) -> Iterable[PostgresConfigAttribute]:
        """Returns list of configuration attributes."""
        if hasattr(cls, "_attributes"):
            return cls._attributes
        attrs = []
        for name, v in cls.__dict__.items():
            if not isinstance(v, PostgresConfigAttribute):
                continue
            v.name = name
            attrs.append(v)
        cls._attributes = attrs
        return cls._attributes

    def build_connection_string(self, password: str) -> str:
        """Build PostgreSQL connection string.

        Args:
            password: OAuth token for authentication (required).
        """
        return (
            f"postgresql://{self.user}:{password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?sslmode={self.sslmode}"
        )

    def as_dict(self) -> dict[str, Any]:
        """Return configuration as dictionary."""
        return {attr.name: getattr(self, attr.name) for attr in self.attributes()}

    def debug_string(self) -> str:
        """Returns log-friendly representation of configured attributes."""
        parts = []
        for attr in self.attributes():
            value = getattr(self, attr.name)
            if value is None:
                continue
            safe = "***" if attr.sensitive else str(value)
            parts.append(f"{attr.name}={safe}")
        return f"PostgresConfig: {', '.join(parts)}"

    def __repr__(self) -> str:
        return f"<{self.debug_string()}>"


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
    def from_workspace_client(
        cls, workspace_client: WorkspaceClient
    ) -> "OAuthTokenManager":
        """Create token manager that exclusively uses WorkspaceClient for tokens.

        Unlike default constructor, does NOT fall back to environment variables.
        """
        manager = cls(workspace_client=workspace_client)
        manager._use_env_fallback = False
        return manager

    def set_workspace_client(self, workspace_client: "WorkspaceClient") -> None:
        """Set or update the WorkspaceClient."""
        self._workspace_client = workspace_client

    def get_token(self) -> str:
        """Get a valid OAuth token, refreshing if needed."""
        current_time = time.time()

        if (
            self._token is None
            or (current_time - self._last_refresh) > self._refresh_interval
        ):
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
                    logger.info(
                        "Lakebase token refreshed via WorkspaceClient.oauth_token()"
                    )
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
        """Get PostgreSQL configuration (cached)."""
        if self._pg_config is None:
            self._pg_config = PostgresConfig()
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
        self._token_manager = _token_manager or OAuthTokenManager(
            workspace_client=workspace_client
        )
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
            try:
                self._conn.close()
            except Exception:
                pass
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
        self._token_manager = _token_manager or OAuthTokenManager(
            workspace_client=workspace_client
        )
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
            async with self._get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
                    await conn.commit()
                    return cur.rowcount
        except Exception as e:
            if self._is_auth_error(e):
                logger.warning("Auth error, refreshing token and retrying...")
                self._token_manager.invalidate()
                async with self._get_connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(sql, params)
                        await conn.commit()
                        return cur.rowcount
            raise

    async def fetch_async(self, sql: str, params: tuple | None = None) -> list[Row]:
        """Execute a query and return Row objects."""
        try:
            async with self._get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params)
                    col_names = [desc[0] for desc in cur.description]
                    RowClass = Row.factory(col_names)
                    rows = await cur.fetchall()
                    return [RowClass(*raw_row) for raw_row in rows]
        except Exception as e:
            if self._is_auth_error(e):
                logger.warning("Auth error, refreshing token and retrying...")
                self._token_manager.invalidate()
                async with self._get_connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(sql, params)
                        col_names = [desc[0] for desc in cur.description]
                        RowClass = Row.factory(col_names)
                        rows = await cur.fetchall()
                        return [RowClass(*raw_row) for raw_row in rows]
            raise

    async def fetch_one_async(
        self, sql: str, params: tuple | None = None
    ) -> Row | None:
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


class StatementExecutionPgBackend:
    """Factory for creating Lakebase backends with workspace authentication.

    Creates sync or async PostgreSQL backends using WorkspaceClient for
    OAuth token management. Configuration is retrieved internally from settings.

    Usage:
        from api.clients import StatementExecutionPgBackend

        # Create sync backend
        backend = StatementExecutionPgBackend.sync(workspace_client)

        # Create async backend
        async_backend = StatementExecutionPgBackend.async_(workspace_client)
    """

    def __new__(cls, *args, **kwargs):
        """Prevent direct instantiation."""
        raise TypeError(
            "StatementExecutionPgBackend cannot be instantiated directly. "
            "Use .sync() or .async_() instead."
        )

    @classmethod
    def sync(cls, workspace_client: WorkspaceClient) -> SyncLakebaseBackend:
        """Create synchronous Lakebase backend.

        Args:
            workspace_client: Databricks WorkspaceClient for token refresh

        Returns:
            Configured SyncLakebaseBackend instance
        """
        from api.core import settings

        pg_config = settings.postgres_config
        token_manager = OAuthTokenManager.from_workspace_client(workspace_client)

        return SyncLakebaseBackend(
            workspace_client=workspace_client,
            pg_config=pg_config,
            _token_manager=token_manager,
        )

    @classmethod
    def async_(cls, workspace_client: WorkspaceClient) -> AsyncLakebaseBackend:
        """Create asynchronous Lakebase backend.

        Args:
            workspace_client: Databricks WorkspaceClient for token refresh

        Returns:
            Configured AsyncLakebaseBackend instance
        """
        from api.core import settings

        pg_config = settings.postgres_config
        token_manager = OAuthTokenManager.from_workspace_client(workspace_client)

        return AsyncLakebaseBackend(
            workspace_client=workspace_client,
            pg_config=pg_config,
            _token_manager=token_manager,
        )
