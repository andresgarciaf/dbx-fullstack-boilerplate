#!/bin/bash
# Post-start script — runs every time the container starts
# Syncs dependencies if lockfiles changed since last container run

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Sync Node.js dependencies (if lockfile exists)
if [ -f /workspace/pnpm-lock.yaml ]; then
    cd /workspace
    if ! pnpm install --frozen-lockfile 2>/dev/null; then
        echo -e "${YELLOW}⚠${NC} Lockfile changed — running full pnpm install..."
        pnpm install || echo -e "${YELLOW}⚠${NC} pnpm install failed — run manually if needed"
    fi
fi

# Sync Python dependencies (if lockfile exists)
if [ -f /workspace/src/api/uv.lock ]; then
    cd /workspace/src/api
    uv sync --quiet || echo -e "${YELLOW}⚠${NC} uv sync failed — run 'cd src/api && uv sync' manually"
    cd /workspace
fi

echo ""
echo -e "${GREEN}Container ready.${NC} Run ${GREEN}pnpm dev${NC} to start development servers."
echo ""
