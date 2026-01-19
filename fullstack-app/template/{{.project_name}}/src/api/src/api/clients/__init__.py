"""SQL clients for Databricks and Lakebase.

Lightweight implementations for SQL execution with:
- StatementExecutionBackend: Databricks SQL Warehouse queries
- SyncLakebaseBackend: Synchronous PostgreSQL/Lakebase queries
- AsyncLakebaseBackend: Async PostgreSQL/Lakebase with pooling
"""

from api.clients.sql_core import Row, dataclass_to_columns, row_to_dataclass, rows_to_dataclass
from api.clients.sql_escapes import (
    escape_name,
    escape_full_name,
    escape_pg_name,
    escape_pg_full_name,
    escape_value,
)
from api.clients.sql_backends import SqlBackend, StatementExecutionBackend
from api.clients.lakebase_backends import (
    LakebaseBackend,
    SyncLakebaseBackend,
    AsyncLakebaseBackend,
    OAuthTokenManager,
    PostgresConfig,
)

__all__ = [
    # Core types
    "Row",
    "dataclass_to_columns",
    "row_to_dataclass",
    "rows_to_dataclass",
    # Escaping
    "escape_name",
    "escape_full_name",
    "escape_pg_name",
    "escape_pg_full_name",
    "escape_value",
    # Databricks SQL backends
    "SqlBackend",
    "StatementExecutionBackend",
    # Lakebase backends
    "LakebaseBackend",
    "SyncLakebaseBackend",
    "AsyncLakebaseBackend",
    "OAuthTokenManager",
    "PostgresConfig",
]
