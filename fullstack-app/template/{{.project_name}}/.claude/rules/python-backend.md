# Python Backend Guidelines

## Modern Type Hints (Python 3.10+)

- Use lowercase built-in types: `list`, `dict`, `tuple`, `set`
- Use `|` for unions: `str | None` NOT `Optional[str]`
- Use `X | Y` NOT `Union[X, Y]`
- NEVER import: `Dict`, `List`, `Optional`, `Union`, `Tuple`, `Set` from typing

```python
# Good
def fetch(self, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    ...

# Bad
from typing import Dict, List, Optional, Tuple
def fetch(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
    ...
```

## Import Structure

```python
from __future__ import annotations

# Standard library
import os
import logging
from typing import TYPE_CHECKING, Any, TypeVar
from collections.abc import Iterator, Callable

# Third-party
import psycopg
from fastapi import FastAPI, APIRouter
from pydantic import BaseModel

# Local
from api.core import settings
from api.clients import SqlBackend

# Type checking only (avoid circular imports)
if TYPE_CHECKING:
    from databricks.sdk import WorkspaceClient
```

## Code Patterns

- Add `from __future__ import annotations` to all Python files
- Use `@cached_property` for lazy-loaded expensive objects
- Use dataclasses or Pydantic models for data structures
- Use descriptors for configuration attributes
- Prefer explicit error handling over bare except
- Use logging module, never print()

## FastAPI Patterns

- Use dependency injection for services
- Define response models with Pydantic
- Use proper HTTP status codes
- Handle errors with HTTPException

## File Location

These rules apply to files in `src/api/**/*.py`