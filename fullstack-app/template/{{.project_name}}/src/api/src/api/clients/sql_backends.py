"""SQL backends for Databricks.

Lightweight implementation inspired by databricks-labs-lsql.
Provides StatementExecutionBackend for Databricks SQL Warehouse queries.
"""

from __future__ import annotations

import abc
import logging
import re
import time
from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from databricks.sdk.service.sql import (
    Disposition,
    ExecuteStatementRequestOnWaitTimeout,
    Format,
    StatementState,
)

from api.clients.sql_core import Row, dataclass_to_columns, get_type_converter
from api.clients.sql_escapes import escape_full_name, escape_name

if TYPE_CHECKING:
    from collections.abc import Iterator

    from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SqlBackend(abc.ABC):
    """Abstract base class for SQL execution backends.

    Provides interface for executing SQL and fetching results,
    with support for dataclass-based table operations.
    """

    _whitespace = re.compile(r"\s+")

    @abc.abstractmethod
    def execute(self, sql: str, *, catalog: str | None = None, schema: str | None = None) -> None:
        """Execute a SQL statement.

        Args:
            sql: SQL statement to execute
            catalog: Optional catalog context
            schema: Optional schema context
        """

    @abc.abstractmethod
    def fetch(self, sql: str, *, catalog: str | None = None, schema: str | None = None) -> Iterator[Row]:
        """Execute a SQL query and fetch results.

        Args:
            sql: SQL query to execute
            catalog: Optional catalog context
            schema: Optional schema context

        Returns:
            Iterator of Row objects
        """

    def fetch_one(self, sql: str, *, catalog: str | None = None, schema: str | None = None) -> Row | None:
        """Fetch first row from query results.

        Args:
            sql: SQL query to execute
            catalog: Optional catalog context
            schema: Optional schema context

        Returns:
            First Row or None if no results
        """
        for row in self.fetch(sql, catalog=catalog, schema=schema):
            return row
        return None

    def fetch_value(self, sql: str, *, catalog: str | None = None, schema: str | None = None) -> Any:
        """Fetch first column of first row.

        Args:
            sql: SQL query to execute
            catalog: Optional catalog context
            schema: Optional schema context

        Returns:
            First value or None
        """
        row = self.fetch_one(sql, catalog=catalog, schema=schema)
        return row[0] if row else None

    def fetch_all(self, sql: str, *, catalog: str | None = None, schema: str | None = None) -> list[Row]:
        """Fetch all rows as a list.

        Args:
            sql: SQL query to execute
            catalog: Optional catalog context
            schema: Optional schema context

        Returns:
            List of Row objects
        """
        return list(self.fetch(sql, catalog=catalog, schema=schema))

    def save_table(
        self,
        full_name: str,
        rows: Iterator[T],
        klass: type[T],
        mode: str = "append",
    ) -> None:
        """Save dataclass instances to a Delta table.

        Args:
            full_name: Fully qualified table name (catalog.schema.table)
            rows: Iterator of dataclass instances
            klass: Dataclass type
            mode: "append" or "overwrite"
        """
        if not is_dataclass(klass):
            raise ValueError(f"{klass} is not a dataclass")

        rows_list = list(rows)
        if not rows_list:
            return

        # Get column info from dataclass
        field_names = [f.name for f in fields(klass)]
        escaped_table = escape_full_name(full_name)
        escaped_cols = ", ".join(escape_name(c) for c in field_names)

        if mode == "overwrite":
            self.execute(f"TRUNCATE TABLE {escaped_table}")

        # Build batch INSERT
        for batch_start in range(0, len(rows_list), 1000):
            batch = rows_list[batch_start : batch_start + 1000]
            values_sql = []

            for row in batch:
                row_values = []
                for field_name in field_names:
                    value = getattr(row, field_name)
                    row_values.append(self._escape_value(value))
                values_sql.append(f"({', '.join(row_values)})")

            sql = f"INSERT INTO {escaped_table} ({escaped_cols}) VALUES {', '.join(values_sql)}"
            self.execute(sql)

    def create_table(self, full_name: str, klass: type[T]) -> None:
        """Create a Delta table from a dataclass schema.

        Args:
            full_name: Fully qualified table name
            klass: Dataclass type defining the schema
        """
        columns = dataclass_to_columns(klass)
        escaped_table = escape_full_name(full_name)

        col_defs = ", ".join(f"{escape_name(name)} {sql_type}" for name, sql_type in columns)
        sql = f"CREATE TABLE IF NOT EXISTS {escaped_table} ({col_defs}) USING DELTA"
        self.execute(sql)

    @staticmethod
    def _escape_value(value: Any) -> str:
        """Escape a value for SQL."""
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        return f"'{value!s}'"

    def _normalize_sql(self, sql: str) -> str:
        """Normalize whitespace in SQL for logging."""
        return self._whitespace.sub(" ", sql).strip()


class StatementExecutionBackend(SqlBackend):
    """SQL backend using Databricks SQL Warehouse statement execution.

    Executes queries via the Statement Execution API, which provides
    serverless execution with automatic retry handling.

    Args:
        ws: Databricks WorkspaceClient
        warehouse_id: SQL Warehouse ID
        max_records_per_batch: Maximum records per result batch
        disposition: Result disposition (INLINE or EXTERNAL_LINKS)
        timeout: Query timeout in seconds
    """

    def __init__(
        self,
        ws: WorkspaceClient,
        warehouse_id: str,
        *,
        max_records_per_batch: int = 10000,
        disposition: Disposition = Disposition.INLINE,
        timeout: int = 600,
    ):
        self._ws = ws
        self._warehouse_id = warehouse_id
        self._max_records = max_records_per_batch
        self._disposition = disposition
        self._timeout = timeout

    def execute(self, sql: str, *, catalog: str | None = None, schema: str | None = None) -> None:
        """Execute a SQL statement."""
        self._execute_statement(sql, catalog=catalog, schema=schema)

    def fetch(self, sql: str, *, catalog: str | None = None, schema: str | None = None) -> Iterator[Row]:
        """Execute a query and yield Row objects."""
        response = self._execute_statement(sql, catalog=catalog, schema=schema)

        if not response.manifest or not response.manifest.schema or not response.manifest.schema.columns:
            return

        # Build column names and type converters
        columns = response.manifest.schema.columns
        col_names = [c.name for c in columns]
        converters = [get_type_converter(c.type_name.value) if c.type_name else None for c in columns]

        RowClass = Row.factory(col_names)

        # Process result chunks
        if response.result and response.result.data_array:
            for raw_row in response.result.data_array:
                converted = self._convert_row(raw_row, converters)
                yield RowClass(*converted)

        # Handle pagination for large results
        while response.result and response.result.next_chunk_index is not None:
            chunk_response = self._ws.statement_execution.get_statement_result_chunk_n(
                response.statement_id, response.result.next_chunk_index
            )
            if chunk_response.data_array:
                for raw_row in chunk_response.data_array:
                    converted = self._convert_row(raw_row, converters)
                    yield RowClass(*converted)

            # Check for more chunks
            if chunk_response.next_chunk_index is None:
                break
            response.result.next_chunk_index = chunk_response.next_chunk_index

    def _execute_statement(self, sql: str, *, catalog: str | None = None, schema: str | None = None):
        """Execute statement and wait for completion."""
        normalized = self._normalize_sql(sql)
        logger.debug(f"Executing: {normalized[:200]}...")

        start = time.time()
        response = self._ws.statement_execution.execute_statement(
            warehouse_id=self._warehouse_id,
            statement=sql,
            catalog=catalog,
            schema=schema,
            disposition=self._disposition,
            format=Format.JSON_ARRAY,
            byte_limit=10_000_000,
            wait_timeout=f"{self._timeout}s",
            on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
        )

        # Poll for completion if needed
        while response.status and response.status.state in (
            StatementState.PENDING,
            StatementState.RUNNING,
        ):
            if time.time() - start > self._timeout:
                if response.statement_id:
                    self._ws.statement_execution.cancel_execution(response.statement_id)
                raise TimeoutError(f"Query timed out after {self._timeout}s")

            time.sleep(0.5)
            response = self._ws.statement_execution.get_statement(response.statement_id)

        # Check for errors
        if response.status and response.status.state == StatementState.FAILED:
            error_msg = response.status.error.message if response.status.error else "Unknown error"
            raise RuntimeError(f"Query failed: {error_msg}")

        duration = time.time() - start
        logger.debug(f"Query completed in {duration:.2f}s")

        return response

    @staticmethod
    def _convert_row(raw_row: list[str], converters: list) -> list[Any]:
        """Convert raw string values using type converters."""
        result = []
        for i, value in enumerate(raw_row):
            if value is None:
                result.append(None)
            elif converters[i]:
                try:
                    result.append(converters[i](value))
                except (ValueError, TypeError):
                    result.append(value)
            else:
                result.append(value)
        return result
