"""SQL escaping utilities.

Lightweight implementation inspired by databricks-labs-lsql.
"""

from __future__ import annotations

from typing import Any


def escape_name(name: str) -> str:
    """Escape a SQL identifier name with backticks.

    Args:
        name: The identifier to escape

    Returns:
        Escaped identifier safe for SQL

    Example:
        escape_name("my_table")  # "`my_table`"
        escape_name("table`name")  # "`table``name`"
    """
    # Strip existing backticks and escape internal ones
    name = name.strip("`")
    name = name.replace("`", "``")
    return f"`{name}`"


def escape_full_name(full_name: str) -> str:
    """Escape a fully qualified table name (catalog.schema.table).

    Args:
        full_name: Dot-separated identifier path

    Returns:
        Escaped full name safe for SQL

    Example:
        escape_full_name("catalog.schema.table")  # "`catalog`.`schema`.`table`"
    """
    parts = full_name.split(".", maxsplit=2)
    return ".".join(escape_name(part) for part in parts)


def escape_value(value: Any) -> str:
    """Escape a value for SQL interpolation.

    Args:
        value: Python value to escape

    Returns:
        SQL-safe string representation

    Example:
        escape_value("test")  # "'test'"
        escape_value(123)  # "123"
        escape_value(None)  # "NULL"
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        # Escape single quotes by doubling them
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    if isinstance(value, (list, tuple)):
        return f"({', '.join(escape_value(v) for v in value)})"
    # Default: convert to string and escape
    return escape_value(str(value))


def escape_pg_name(name: str) -> str:
    """Escape a PostgreSQL identifier name with double quotes.

    Args:
        name: The identifier to escape

    Returns:
        Escaped identifier safe for PostgreSQL

    Example:
        escape_pg_name("my_table")  # '"my_table"'
        escape_pg_name('table"name')  # '"table""name"'
    """
    # Strip existing quotes and escape internal ones
    name = name.strip('"')
    name = name.replace('"', '""')
    return f'"{name}"'


def escape_pg_full_name(full_name: str) -> str:
    """Escape a fully qualified PostgreSQL table name (schema.table).

    Args:
        full_name: Dot-separated identifier path

    Returns:
        Escaped full name safe for PostgreSQL

    Example:
        escape_pg_full_name("schema.table")  # '"schema"."table"'
    """
    parts = full_name.split(".", maxsplit=1)
    return ".".join(escape_pg_name(part) for part in parts)


def build_insert_sql(
    table: str,
    columns: list[str],
    values: list[Any],
    dialect: str = "databricks",
) -> str:
    """Build an INSERT SQL statement.

    Args:
        table: Table name (can be fully qualified)
        columns: List of column names
        values: List of values to insert
        dialect: SQL dialect ("databricks" or "postgres")

    Returns:
        INSERT SQL statement
    """
    escape_fn = escape_name if dialect == "databricks" else escape_pg_name
    full_escape_fn = escape_full_name if dialect == "databricks" else escape_pg_full_name

    escaped_table = full_escape_fn(table)
    escaped_cols = ", ".join(escape_fn(c) for c in columns)
    escaped_vals = ", ".join(escape_value(v) for v in values)

    return f"INSERT INTO {escaped_table} ({escaped_cols}) VALUES ({escaped_vals})"
