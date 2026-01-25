# Dev Container Setup

This project includes a fully configured development container that works with **VS Code**, **Cursor**, and **PyCharm**. The container includes all required tools pre-installed:

- Node.js 22 with pnpm 10
- Python 3.10 with uv
- Databricks CLI
- PostgreSQL client (for Lakebase)
- Git and GitHub CLI

## Quick Start

### VS Code / Cursor

1. Install the **Dev Containers** extension
2. Open the project folder
3. Click "Reopen in Container" when prompted (or use Command Palette: `Dev Containers: Reopen in Container`)
4. Wait for the container to build and dependencies to install
5. Run `pnpm dev` to start development

### PyCharm

**Option 1: Dev Containers Plugin (Recommended)**
1. Install the **Dev Containers** plugin from JetBrains Marketplace
2. File → Remote Development → Dev Containers
3. Select this project folder
4. PyCharm will use the `devcontainer.json` configuration

**Option 2: Docker Compose**
1. Open the project normally
2. Go to Settings → Build, Execution, Deployment → Docker
3. Add a new Docker configuration pointing to `.devcontainer/docker-compose.yml`
4. Configure Python interpreter to use the container

**Option 3: JetBrains Gateway**
1. Install JetBrains Gateway
2. Connect to the running dev container
3. Open the project through Gateway

## Configuration

### Databricks Authentication

The container mounts your host's `~/.databrickscfg` file automatically. Make sure you have configured the Databricks CLI on your host machine:

```bash
# On your host machine (not in the container)
databricks configure
```

Alternatively, set environment variables in the `.env` file:

```env
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_WAREHOUSE=abc123def456
```

### Git Configuration

The container mounts your host's `~/.gitconfig` for seamless git operations.

## Ports

| Port | Service | URL |
|------|---------|-----|
| 3000 | Frontend (Next.js) | http://localhost:3000 |
| 8000 | Backend (FastAPI) | http://localhost:8000 |
| 8000 | API Documentation | http://localhost:8000/api/docs |

## Helpful Aliases

The container includes these aliases:

| Alias | Command |
|-------|---------|
| `dev` | `pnpm dev` |
| `build` | `pnpm build` |
| `lint` | `pnpm lint` |
| `db` | `databricks` |

## Persistent Storage

The following are persisted between container rebuilds:

- VS Code extensions and settings
- pnpm package cache
- uv (Python) package cache
- Bash history

## Troubleshooting

### Container won't start

1. Ensure Docker is running
2. Try rebuilding: Command Palette → `Dev Containers: Rebuild Container`

### Databricks CLI not authenticated

```bash
# Check current auth status
databricks auth describe

# Configure if needed
databricks configure
```

### Dependencies out of sync

```bash
# Reinstall all dependencies
pnpm install
cd src/api && uv sync && cd ..
```

### Port already in use

```bash
# Find and kill process using port
lsof -ti:3000 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```
