# DBX Fullstack Boilerplate Template

A Databricks Asset Bundles (DAB) template for creating modern fullstack applications with Next.js frontend and FastAPI backend, deployable on Databricks Apps.

## Stack

- **Frontend**: Next.js 16, React 19, Tailwind CSS 4, Flowbite React
- **Backend**: Python 3.10+, FastAPI, uvicorn, Databricks SDK
- **Database**: Databricks SQL Warehouse, Lakebase (PostgreSQL)
- **Tooling**: pnpm, uv
- **Deployment**: Databricks Apps

## Features

- **SQL Clients**: Lightweight implementations for Databricks SQL Warehouse and Lakebase (PostgreSQL)
- **OAuth Token Refresh**: Automatic token refresh for Lakebase connections
- **Per-User Authentication**: Support for user-scoped OAuth tokens in Databricks Apps
- **Modern Python**: Type hints using Python 3.10+ syntax (`str | None`, `list[str]`)
- **AI Assistant Rules**: Pre-configured rules for Cursor (`.cursor/rules/`) and Claude Code (`.claude/rules/`)

## Using This Template

### Initialize a New Project

```bash
# Initialize from GitHub
databricks bundle init https://github.com/andresgarciaf/dbx-fullstack-boilerplate --template-dir fullstack-app

# Or from a local copy
databricks bundle init /path/to/dbx-fullstack-boilerplate --template-dir fullstack-app
```

### After Initialization

```bash
cd your-project-name

# Install dependencies
./scripts/setup.sh

# Start development servers
pnpm dev
```

Development servers:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000 (API docs at /api/docs)

### Deploy to Databricks

```bash
# Validate bundle configuration
databricks bundle validate

# Deploy to dev target
databricks bundle deploy

# Deploy to production
databricks bundle deploy --target prod
```

## Template Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `project_name` | Unique name for the project (lowercase, numbers, hyphens) | `fullstack-app` |

## Generated Project Structure

```
your-project-name/
├── databricks.yml              # DAB configuration
├── resources/
│   ├── app.yml                 # Databricks App definition
│   └── lakebase.yml            # Lakebase database resource
├── src/
│   ├── web/                    # Next.js frontend
│   │   ├── app/                # App Router pages
│   │   └── public/             # Static assets
│   └── api/                    # FastAPI backend
│       └── src/api/
│           ├── clients/        # SQL backends (Databricks, Lakebase)
│           ├── core/           # Config, middleware, context
│           ├── routers/        # API endpoints
│           ├── services/       # Business logic (DatabricksService)
│           └── models/         # Pydantic models
├── scripts/
│   ├── setup.sh                # Install dependencies
│   ├── dev.sh                  # Start dev servers
│   ├── build.sh                # Build for production
│   ├── clean.sh                # Clean dependencies
│   └── start.sh                # Production start script
├── .cursor/rules/              # Cursor IDE rules
├── .claude/                    # Claude Code configuration
│   ├── CLAUDE.md               # Project overview
│   └── rules/                  # Modular AI rules
├── package.json
└── pnpm-workspace.yaml
```

## API Architecture

### SQL Clients

The template includes lightweight SQL client implementations:

```python
from api.services import DatabricksService

service = DatabricksService()

# Databricks SQL Warehouse queries
rows = service.sql_backend.fetch("SELECT * FROM catalog.schema.table")

# Lakebase (PostgreSQL) queries
rows = service.lakebase_backend.fetch("SELECT * FROM schema.table")

# Direct SDK access
user = service.workspace_client.current_user.me()
```

### Configuration

All configuration via `pydantic-settings` with `.env` file support:

```python
from api.core import settings

# Databricks SDK config (handles per-user OAuth in deployed mode)
ws = WorkspaceClient(config=settings.databricks_config)

# PostgreSQL config for Lakebase
pg_config = settings.postgres_config
```

## Scripts

| Command | Description |
|---------|-------------|
| `./scripts/setup.sh` | Check prerequisites and install dependencies |
| `pnpm dev` | Start development servers |
| `pnpm build` | Build for production |
| `./scripts/clean.sh` | Remove all dependencies and caches |
| `./scripts/start.sh` | Start production server (used by Databricks Apps) |

## Prerequisites

```bash
# Node.js
brew install node

# pnpm
npm install -g pnpm

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Databricks CLI
brew tap databricks/tap
brew install databricks
```

## Environment Variables

### Required for Local Development

```env
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_WAREHOUSE=abc123def456
```

### Optional (Lakebase)

```env
PGHOST=your-lakebase-host
PGPORT=5432
PGDATABASE=databricks_postgres
PGUSER=token
PGPASSWORD=your_oauth_token
```

## Production Deployment

The template is configured for Databricks Apps deployment. The FastAPI backend serves both the API endpoints and the static Next.js frontend from a single port.

```bash
# Build frontend
pnpm build

# Deploy to Databricks
databricks bundle deploy --target prod
```

## Template Structure

```
fullstack-app/
├── databricks_template_schema.json   # Template configuration
└── template/
    └── {{.project_name}}/            # Generated project structure
        ├── databricks.yml.tmpl       # DAB configuration
        ├── resources/
        │   ├── app.yml.tmpl          # App resource definition
        │   └── lakebase.yml.tmpl     # Lakebase resource definition
        ├── src/
        │   ├── web/                  # Next.js frontend
        │   └── api/                  # FastAPI backend
        └── scripts/                  # Setup, dev, build scripts
```