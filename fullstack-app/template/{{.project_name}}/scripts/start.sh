#!/bin/bash
# Start script for Databricks Apps deployment
# This script runs the production server with graceful shutdown support

set -e

# Navigate to the project root
cd "$(dirname "$0")/.."

# Use DATABRICKS_APP_PORT if set, otherwise default to 8000
PORT="${DATABRICKS_APP_PORT:-8000}"
echo "Starting production server on port ${PORT}..."

# Trap SIGTERM and SIGINT for graceful shutdown (Databricks Apps sends SIGTERM with 15s limit)
trap 'echo "Received shutdown signal..."; kill -TERM "$PID" 2>/dev/null; wait "$PID"' SIGTERM SIGINT

# Run the FastAPI server in the background to enable signal forwarding
cd src/api
uv run uvicorn main:app --host 0.0.0.0 --port "${PORT}" &
PID=$!

# Wait for the server process
wait "$PID"
