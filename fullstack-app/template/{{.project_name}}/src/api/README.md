# FastAPI Backend

Python backend built with FastAPI, featuring Databricks SDK integration and Lakebase (PostgreSQL) support.

## Structure

```

src/api/
├── main.py              # FastAPI application entry point
├── clients/             # SQL backend implementations
│   ├── sql_backends.py  # Databricks SQL Warehouse backend
│   ├── lakebase_backends.py  # PostgreSQL/Lakebase backend
│   ├── sql_core.py      # Row class and type converters
│   └── sql_escapes.py   # SQL identifier escaping
├── core/
│   ├── config.py        # Settings via pydantic-settings
│   ├── context.py       # Request context (user tokens)
│   └── middleware.py    # Request logging, token extraction
├── routers/
│   └── health.py        # Health check endpoint
├── services/
│   └── databricks_service.py  # Centralized Databricks access
└── models/              # Pydantic models
└── pyproject.toml           # Python dependencies (uv)
```

## Quick Start

```bash
# Install dependencies
cd src/api
uv sync

# Run development server
uv run uvicorn api.main:app --reload --port 8000
```

## Configuration

Environment variables (via `.env` file in project root):

```env
# Databricks (required)
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
#DATABRICKS_PROFILE=cfgprofile
DATABRICKS_WAREHOUSE=abc123

# Lakebase/PostgreSQL (optional)
INSTANCE_NAME=your-lakebase-instance

# app settings
DEBUG=false
```

## Usage

### DatabricksService

Centralized access to all Databricks resources:

```python
from api.services import DatabricksService

service = DatabricksService()

# SQL Warehouse queries
rows = service.sql_backend.fetch("SELECT * FROM catalog.schema.table")

# Lakebase (PostgreSQL) queries
rows = service.lakebase_backend.fetch("SELECT * FROM schema.table")

# Direct SDK access
user = service.workspace_client.current_user.me()
```

### Settings

Access configuration anywhere:

```python
from api.core import settings

# Check environment
if settings.is_deployed:
    # Running in Databricks Apps
    pass

# Get Databricks SDK config (handles per-user OAuth)
config = settings.databricks_config

# Lakebase instance name (resolved via SDK in DatabricksService)
instance_name = settings.instance_name
```

### Adding New Endpoints

1. Create a new router in `routers/`:

```python
# routers/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
async def get_current_user():
    return {"user": "example"}
```

2. Include it in `main.py`:

```python
from .routers import users

api_router.include_router(users.router)
```

## SQL Clients

### StatementExecutionBackend (Databricks SQL)

```python
from api.clients import StatementExecutionBackend

backend = StatementExecutionBackend(ws, warehouse_id)
rows = backend.fetch("SELECT * FROM table")
```

### SyncLakebaseBackend (PostgreSQL)

```python
from api.clients import SyncLakebaseBackend, PostgresConfig

config = PostgresConfig(host="localhost", database="mydb")
backend = SyncLakebaseBackend(workspace_client=ws, pg_config=config)
rows = backend.fetch("SELECT * FROM table")
```

## Testing

```bash
# Run tests
uv run pytest

# With coverage
uv run pytest --cov=api
```

## API Documentation

When running locally, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
