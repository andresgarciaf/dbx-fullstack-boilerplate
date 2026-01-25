#!/bin/bash
# Post-start script - runs every time the container starts
set -e

# Ensure dependencies are up to date (in case package files changed)
if [ -f /workspace/pnpm-lock.yaml ]; then
    pnpm install --frozen-lockfile 2>/dev/null || pnpm install
fi

if [ -f /workspace/src/api/uv.lock ]; then
    cd /workspace/src/api && uv sync --quiet && cd /workspace
fi

echo "Container started. Run 'pnpm dev' to start development servers."
