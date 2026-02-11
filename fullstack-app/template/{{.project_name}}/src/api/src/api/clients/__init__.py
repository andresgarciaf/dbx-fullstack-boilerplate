"""SQL clients for Databricks and Lakebase.

Lightweight implementations for SQL execution with:
- StatementExecutionBackend: Databricks SQL Warehouse queries
- SyncLakebaseBackend: Synchronous PostgreSQL/Lakebase queries
- AsyncLakebaseBackend: Async PostgreSQL/Lakebase with pooling
"""

from api.clients.lakebase_backends import (
    AsyncLakebaseBackend,
    LakebaseBackend,
    OAuthTokenManager,
    PostgresConfig,
    SyncLakebaseBackend,
)
from api.clients.sql_backends import SqlBackend, StatementExecutionBackend
from api.clients.sql_core import (
    Row,
    dataclass_to_columns,
    row_to_dataclass,
    rows_to_dataclass,
)
from api.clients.sql_escapes import (
    escape_full_name,
    escape_name,
    escape_pg_full_name,
    escape_pg_name,
    escape_value,
)

__all__ = [
    "AsyncLakebaseBackend",
    # Lakebase backends
    "LakebaseBackend",
    "OAuthTokenManager",
    "PostgresConfig",
    # Core types
    "Row",
    # Databricks SQL backends
    "SqlBackend",
    "StatementExecutionBackend",
    "SyncLakebaseBackend",
    "dataclass_to_columns",
    "escape_full_name",
    # Escaping
    "escape_name",
    "escape_pg_full_name",
    "escape_pg_name",
    "escape_value",
    "row_to_dataclass",
    "rows_to_dataclass",
]
