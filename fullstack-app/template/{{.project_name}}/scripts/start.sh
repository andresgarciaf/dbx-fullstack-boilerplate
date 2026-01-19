#!/bin/bash
# Start script for Databricks Apps deployment
# This script runs the production server

set -e

# Navigate to the project root
cd "$(dirname "$0")/.."

echo "Starting production server..."

# Run the FastAPI server (which serves both API and static frontend)
cd src/api
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
