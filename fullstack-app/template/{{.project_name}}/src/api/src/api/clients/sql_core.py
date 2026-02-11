"""Core types for SQL backends.

Lightweight implementation inspired by databricks-labs-lsql.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

T = TypeVar("T")


class Row(tuple):
    """A row of data with named column access.

    Similar to PySpark's Row class - supports both index and attribute access.

    Usage:
        row = Row(id=1, name="test")
        row.id  # 1
        row["name"]  # "test"
        row[0]  # 1
    """

    _fields: tuple[str, ...] = ()

    def __new__(cls, *args, **kwargs):
        if args and kwargs:
            raise ValueError("Cannot use both positional and keyword arguments")

        if kwargs:
            row = tuple.__new__(cls, kwargs.values())
            row._fields = tuple(kwargs.keys())
            return row

        if args and len(args) == 1 and isinstance(args[0], dict):
            row = tuple.__new__(cls, args[0].values())
            row._fields = tuple(args[0].keys())
            return row

        return tuple.__new__(cls, args)

    @classmethod
    def factory(cls, col_names: list[str]) -> type[Row]:
        """Create a Row subclass with predefined column names."""

        class NamedRow(Row):
            _fields = tuple(col_names)

            def __new__(cls, *values):
                row = tuple.__new__(cls, values)
                row._fields = tuple(col_names)
                return row

        return NamedRow

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        try:
            idx = self._fields.index(name)
            return self[idx]
        except (ValueError, AttributeError) as err:
            raise AttributeError(f"Row has no field '{name}'") from err

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                idx = self._fields.index(key)
                return tuple.__getitem__(self, idx)
            except ValueError as err:
                raise KeyError(f"Row has no field '{key}'") from err
        return tuple.__getitem__(self, key)

    def as_dict(self) -> dict[str, Any]:
        """Convert row to dictionary."""
        return dict(zip(self._fields, self, strict=False))

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in zip(self._fields, self, strict=False))
        return f"Row({items})"


# Type converters for SQL result parsing
def _parse_date(value: str) -> date:
    """Parse ISO date string."""
    return datetime.fromisoformat(value).date()


def _parse_timestamp(value: str) -> datetime:
    """Parse ISO timestamp string."""
    # Handle various timestamp formats
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def _parse_decimal(value: str) -> Decimal:
    """Parse decimal string."""
    return Decimal(value)


# Map SQL types to Python converters
TYPE_CONVERTERS: dict[str, Callable[[str], Any]] = {
    "DATE": _parse_date,
    "TIMESTAMP": _parse_timestamp,
    "TIMESTAMP_NTZ": _parse_timestamp,
    "DECIMAL": _parse_decimal,
    "DOUBLE": float,
    "FLOAT": float,
    "INT": int,
    "BIGINT": int,
    "SMALLINT": int,
    "TINYINT": int,
    "BOOLEAN": lambda x: x.lower() == "true",
}


def get_type_converter(sql_type: str) -> Callable[[str], Any] | None:
    """Get converter function for SQL type."""
    # Extract base type (e.g., "DECIMAL(10,2)" -> "DECIMAL")
    base_type = sql_type.split("(")[0].upper()
    return TYPE_CONVERTERS.get(base_type)


def dataclass_to_columns(klass: type[T]) -> list[tuple[str, str]]:
    """Extract column names and SQL types from a dataclass.

    Returns:
        List of (column_name, sql_type) tuples
    """
    if not is_dataclass(klass):
        raise ValueError(f"{klass} is not a dataclass")

    type_mapping = {
        int: "BIGINT",
        str: "STRING",
        float: "DOUBLE",
        bool: "BOOLEAN",
        date: "DATE",
        datetime: "TIMESTAMP",
        Decimal: "DECIMAL(38,18)",
    }

    columns = []
    for field in fields(klass):
        # Handle Optional types
        field_type = field.type
        if hasattr(field_type, "__origin__"):
            # Optional[X] is Union[X, None]
            args = getattr(field_type, "__args__", ())
            if type(None) in args:
                field_type = next(a for a in args if a is not type(None))

        sql_type = type_mapping.get(field_type, "STRING")
        columns.append((field.name, sql_type))

    return columns


def row_to_dataclass(row: Row, klass: type[T]) -> T:
    """Convert a Row to a dataclass instance."""
    return klass(**row.as_dict())


def rows_to_dataclass(rows: Iterator[Row], klass: type[T]) -> Iterator[T]:
    """Convert rows to dataclass instances."""
    for row in rows:
        yield row_to_dataclass(row, klass)
