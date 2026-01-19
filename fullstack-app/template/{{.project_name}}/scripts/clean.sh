#!/bin/bash

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

CHECK="${GREEN}✓${RESET}"

echo ""
echo -e "${CYAN}  ╔════════════════════════════════╗${RESET}"
echo -e "${CYAN}  ║         Cleaning Project       ║${RESET}"
echo -e "${CYAN}  ╚════════════════════════════════╝${RESET}"
echo ""

# Kill running processes
echo -e "  ${YELLOW}→${RESET} Stopping running processes..."
pkill -f "uvicorn" 2>/dev/null
pkill -f "next" 2>/dev/null
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null
echo -e "  ${CHECK} Processes stopped"

# Clean Node.js
echo -e "  ${YELLOW}→${RESET} Cleaning Node.js cache..."
rm -rf node_modules 2>/dev/null
rm -rf src/web/node_modules 2>/dev/null
rm -rf src/web/.next 2>/dev/null
rm -rf src/web/out 2>/dev/null
rm -rf .turbo 2>/dev/null
rm -rf src/web/.turbo 2>/dev/null
echo -e "  ${CHECK} Node.js cache cleaned"

# Clean Python
echo -e "  ${YELLOW}→${RESET} Cleaning Python cache..."
rm -rf src/api/.venv 2>/dev/null
rm -rf src/static 2>/dev/null
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
echo -e "  ${CHECK} Python cache cleaned"

# Clean temp files
echo -e "  ${YELLOW}→${RESET} Cleaning temp files..."
rm -f /tmp/dbx_* 2>/dev/null
rm -rf .flowbite-react 2>/dev/null
rm -rf src/web/.flowbite-react 2>/dev/null
echo -e "  ${CHECK} Temp files cleaned"

echo ""
echo -e "  ${GREEN}╔═══════════════════════════════╗${RESET}"
echo -e "  ${GREEN}║       Clean Complete!         ║${RESET}"
echo -e "  ${GREEN}╚═══════════════════════════════╝${RESET}"
echo ""
echo -e "  Run ${CYAN}pnpm setup${RESET} to reinstall dependencies"
echo ""
