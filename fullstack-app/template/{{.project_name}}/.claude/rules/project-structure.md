# Project Structure and Conventions

## Overview

This is a fullstack Databricks application with:
- React/TypeScript frontend (Next.js, Vite, TailwindCSS)
- Python/FastAPI backend
- Databricks SDK integration
- Lakebase (PostgreSQL) support

## Directory Structure

```
├── src/
│   ├── api/                    # Python FastAPI backend
│   │   ├── clients/            # SQL backends (Databricks, Lakebase)
│   │   ├── core/               # Config, middleware, context
│   │   ├── routers/            # API endpoints
│   │   └── services/           # Business logic
│   └── web/                    # React TypeScript frontend
│       └── src/
│           ├── components/     # React components
│           ├── hooks/          # Custom hooks
│           ├── lib/            # Utilities
│           └── types/          # TypeScript types
├── scripts/                    # Build and dev scripts
└── resources/                  # Databricks app configuration
```

## Common Commands

```bash
# Development
pnpm dev              # Start both frontend and backend
pnpm dev:api          # Start backend only
pnpm dev:web          # Start frontend only

# Build
pnpm build            # Build for production

# Linting
pnpm lint             # Run linters
ruff check .          # Python linting (from src/api/)
ruff format .         # Python formatting (from src/api/)

# Databricks
databricks bundle deploy        # Deploy to Databricks
databricks bundle run           # Run jobs
```

## Environment Variables

### Required for Local Development
```
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_WAREHOUSE=abc123def456
```

### Optional (Lakebase)
```
INSTANCE_NAME=your-lakebase-instance
```

## Testing

- Python: pytest with fixtures, mock external services
- TypeScript: Vitest + React Testing Library
- Test behavior, not implementation

## Security Notes

- Never commit `.env` files
- Use parameterized queries for all SQL
- Validate all user input
- Use proper escaping for dynamic identifiers
- Review CORS settings before deployment

## When Generating Code

1. Always include proper type annotations
2. Group imports correctly (stdlib → third-party → local)
3. Follow existing patterns in the codebase
4. Use modern syntax (Python 3.10+, ES2022+)
5. Prefer explicit over implicit
6. Handle errors appropriately
7. Add docstrings for public functions/classes