# CLAUDE.md

Fullstack Databricks application with React/TypeScript frontend and Python/FastAPI backend.

## Quick Reference

- **Frontend**: `src/web/` - React + TypeScript + Vite + TailwindCSS
- **Backend**: `src/api/` - Python + FastAPI + Databricks SDK
- **Config**: `.env` file for local development credentials

## Key Commands

```bash
./scripts/setup.sh    # Install dependencies
pnpm dev              # Start development servers
pnpm build            # Build for production
databricks bundle deploy  # Deploy to Databricks
```

## Modular Rules

Detailed guidelines are in `.claude/rules/`:

- `python-backend.md` - Python typing, imports, FastAPI patterns
- `typescript-frontend.md` - TypeScript, React component patterns
- `databricks.md` - SDK usage, SQL safety, authentication
- `project-structure.md` - Directory layout, commands, environment setup