#!/bin/bash
# Post-create script — runs once when the container is first created
set -e

echo "Setting up development environment..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_step() { echo -e "${BLUE}==>${NC} $1"; }
print_done() { echo -e "${GREEN}✓${NC} $1"; }
print_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Install Node.js dependencies
if [ -f /workspace/package.json ]; then
    print_step "Installing Node.js dependencies..."
    cd /workspace
    if pnpm install; then
        print_done "Node.js dependencies installed"
    else
        print_error "Failed to install Node.js dependencies — run 'pnpm install' manually"
    fi
else
    print_warn "No package.json found — skipping Node.js dependencies"
fi

# Install Python dependencies
if [ -d /workspace/src/api ]; then
    print_step "Installing Python dependencies..."
    cd /workspace/src/api
    if uv sync; then
        print_done "Python dependencies installed"
    else
        print_error "Failed to install Python dependencies — run 'cd src/api && uv sync' manually"
    fi
    cd /workspace
else
    print_warn "No src/api directory found — skipping Python dependencies"
fi

# Create .env file if it doesn't exist
if [ ! -f /workspace/.env ]; then
    print_step "Creating .env file from template..."
    if [ -f /workspace/.env.example ]; then
        cp /workspace/.env.example /workspace/.env
    else
        cat > /workspace/.env << 'EOF'
# Databricks Configuration
# Option 1: Direct credentials
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_WAREHOUSE=abc123def456

# Option 2: Use a profile from ~/.databrickscfg (mounted from host)
# DATABRICKS_PROFILE=your-profile-name

# Application settings
DEBUG=true

# Optional: Lakebase instance name
# INSTANCE_NAME=your-lakebase-instance
EOF
    fi
    print_done ".env file created — please update with your credentials"
fi

# Check Databricks CLI authentication (non-fatal)
print_step "Checking Databricks CLI..."
if databricks auth describe 2>/dev/null; then
    print_done "Databricks CLI is authenticated"
else
    print_warn "Databricks CLI is not authenticated"
    echo "   Run: databricks configure"
    echo "   Or mount your ~/.databrickscfg file from the host"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}Development environment is ready!${NC}"
echo ""
echo "Quick commands:"
echo "  pnpm dev       - Start frontend and backend"
echo "  pnpm build     - Build for production"
echo "  pnpm lint      - Run linters"
echo ""
echo "Ports:"
echo "  http://localhost:3000  - Frontend (Next.js)"
echo "  http://localhost:8000  - Backend (FastAPI)"
echo "  http://localhost:8000/api/docs  - API Documentation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
