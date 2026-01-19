#!/bin/bash

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

# Symbols
CHECK="${GREEN}✓${RESET}"
CROSS="${RED}✗${RESET}"
WARN="${YELLOW}⚠${RESET}"

echo ""
echo -e "${CYAN}  ╔════════════════════════════════╗${RESET}"
echo -e "${CYAN}  ║       Environment Setup        ║${RESET}"
echo -e "${CYAN}  ╚════════════════════════════════╝${RESET}"
echo ""

# Track missing dependencies
MISSING=()

# Check Node.js
echo -e "  Checking dependencies..."
echo ""

if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "  ${CHECK} Node.js         ${DIM}${NODE_VERSION}${RESET}"
else
    echo -e "  ${CROSS} Node.js         ${RED}Not installed${RESET}"
    MISSING+=("node")
fi

# Check pnpm
if command -v pnpm &> /dev/null; then
    PNPM_VERSION=$(pnpm --version)
    echo -e "  ${CHECK} pnpm            ${DIM}v${PNPM_VERSION}${RESET}"
else
    echo -e "  ${CROSS} pnpm            ${RED}Not installed${RESET}"
    MISSING+=("pnpm")
fi

# Check uv
if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version | head -1)
    echo -e "  ${CHECK} uv              ${DIM}${UV_VERSION}${RESET}"
else
    echo -e "  ${CROSS} uv              ${RED}Not installed${RESET}"
    MISSING+=("uv")
fi

# Check turbo (local)
if [ -f "node_modules/.bin/turbo" ] || command -v turbo &> /dev/null; then
    if [ -f "node_modules/.bin/turbo" ]; then
        TURBO_VERSION=$(./node_modules/.bin/turbo --version 2>/dev/null || echo "installed")
    else
        TURBO_VERSION=$(turbo --version 2>/dev/null || echo "installed")
    fi
    echo -e "  ${CHECK} turbo           ${DIM}${TURBO_VERSION}${RESET}"
else
    echo -e "  ${WARN} turbo           ${YELLOW}Will install with pnpm${RESET}"
fi

echo ""

# Show installation instructions if missing
if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "  ${RED}Missing dependencies:${RESET}"
    echo ""

    for dep in "${MISSING[@]}"; do
        case $dep in
            node)
                echo -e "  ${YELLOW}Node.js:${RESET}"
                echo -e "    brew install node"
                echo -e "    ${DIM}or visit: https://nodejs.org${RESET}"
                echo ""
                ;;
            pnpm)
                echo -e "  ${YELLOW}pnpm:${RESET}"
                echo -e "    npm install -g pnpm"
                echo -e "    ${DIM}or: brew install pnpm${RESET}"
                echo ""
                ;;
            uv)
                echo -e "  ${YELLOW}uv:${RESET}"
                echo -e "    curl -LsSf https://astral.sh/uv/install.sh | sh"
                echo -e "    ${DIM}or: brew install uv${RESET}"
                echo ""
                ;;
        esac
    done

    echo -e "  ${DIM}Install missing dependencies and run this script again.${RESET}"
    echo ""
    exit 1
fi

# All dependencies found, proceed with setup
echo -e "  ${GREEN}All dependencies found!${RESET}"
echo ""
echo -e "  ${DIM}Installing packages...${RESET}"
echo ""

# Install Node.js dependencies
echo -e "  ${YELLOW}→${RESET} Installing Node.js packages..."
pnpm install --silent
echo -e "  ${CHECK} Node.js packages installed"

# Install Python dependencies
echo -e "  ${YELLOW}→${RESET} Installing Python packages..."
cd src/api && uv sync --quiet && cd ../..
echo -e "  ${CHECK} Python packages installed"

echo ""
echo -e "  ${GREEN}╔═══════════════════════════════╗${RESET}"
echo -e "  ${GREEN}║       Setup Complete!         ║${RESET}"
echo -e "  ${GREEN}╚═══════════════════════════════╝${RESET}"
echo ""
echo -e "  Run ${CYAN}pnpm dev${RESET} to start development"
echo ""
