# Quickstart

Get your development environment running in minutes.

## Prerequisites

Ensure you have the following installed:

- **Node.js** (v18+): `brew install node`
- **pnpm**: `npm install -g pnpm`
- **uv** (Python): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Databricks CLI**: `brew tap databricks/tap && brew install databricks`

## Setup

```bash
# Install all dependencies (Node.js + Python)
./scripts/setup.sh
```

## Development

```bash
# Start both frontend and backend
pnpm dev
```

This starts:
- **Frontend**: http://localhost:3000 (Next.js with hot reload)
- **Backend**: http://localhost:8000 (FastAPI with auto-reload)
- **API Docs**: http://localhost:8000/api/docs (Swagger UI)

## Environment Variables

Create a `.env` file in the project root (copy from `.env.tmpl`):

```bash
cp .env.tmpl .env
```

Required variables:
```env
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_WAREHOUSE=abc123def456
```

Optional (for Lakebase):
```env
PGHOST=your-lakebase-host
PGPORT=5432
PGDATABASE=databricks_postgres
```

## Build for Production

```bash
# Build frontend and prepare for deployment
pnpm build

# Test production server locally
pnpm start
```

## Deploy to Databricks

```bash
# Validate configuration
databricks bundle validate

# Deploy to dev environment
databricks bundle deploy

# Deploy to production
databricks bundle deploy --target prod
```

## Other Commands

| Command | Description |
|---------|-------------|
| `pnpm lint` | Run linter |
| `pnpm typecheck` | TypeScript type checking |
| `pnpm format` | Format code with Prettier |
| `./scripts/clean.sh` | Remove all dependencies and caches |

## Project Structure

```
├── src/
│   ├── web/           # Next.js frontend
│   │   └── app/       # App Router pages
│   └── api/           # FastAPI backend
│       └── src/api/
│           ├── clients/   # SQL backends
│           ├── core/      # Config, middleware
│           ├── routers/   # API endpoints
│           └── services/  # Business logic
├── scripts/           # Setup and dev scripts
└── resources/         # Databricks resources (app, lakebase)
```

## Need Help?

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Next.js Docs](https://nextjs.org/docs)
- [Databricks Apps](https://docs.databricks.com/en/dev-tools/databricks-apps/index.html)
- [Databricks Asset Bundles](https://docs.databricks.com/en/dev-tools/bundles/index.html)
