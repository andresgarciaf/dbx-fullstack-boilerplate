#!/bin/bash
# =============================================================================
# Dev Container Runtime Initializer
# =============================================================================
# This script runs on the HOST machine before the dev container starts.
# It ensures Docker or Podman is installed, running, and properly configured.
#
# Supports: macOS, Linux (including WSL2)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)  echo "macos" ;;
        Linux*)
            if grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
                echo "wsl"
            else
                echo "linux"
            fi
            ;;
        MINGW*|CYGWIN*|MSYS*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

OS=$(detect_os)

# Logging functions
log_info() { echo -e "${BLUE}ℹ${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_step() { echo -e "${CYAN}▶${NC} ${BOLD}$1${NC}"; }

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# =============================================================================
# Docker Functions
# =============================================================================

check_docker_installed() {
    command_exists docker
}

check_docker_running() {
    docker info >/dev/null 2>&1
}

start_docker_macos() {
    log_step "Starting Docker Desktop..."

    # Check if Docker Desktop is installed
    if [ -d "/Applications/Docker.app" ]; then
        open -a Docker

        # Wait for Docker to start (max 60 seconds)
        local max_attempts=30
        local attempt=0

        echo -n "  Waiting for Docker to start"
        while [ $attempt -lt $max_attempts ]; do
            if docker info >/dev/null 2>&1; then
                echo ""
                log_success "Docker Desktop is running"
                return 0
            fi
            echo -n "."
            sleep 2
            attempt=$((attempt + 1))
        done

        echo ""
        log_error "Docker Desktop failed to start within 60 seconds"
        log_info "Please start Docker Desktop manually and try again"
        return 1
    else
        log_error "Docker Desktop is not installed"
        return 1
    fi
}

start_docker_linux() {
    log_step "Starting Docker service..."

    # Try systemctl first (most modern Linux distros)
    if command_exists systemctl; then
        if sudo systemctl start docker 2>/dev/null; then
            sleep 2
            if check_docker_running; then
                log_success "Docker service started"
                return 0
            fi
        fi
    fi

    # Try service command
    if command_exists service; then
        if sudo service docker start 2>/dev/null; then
            sleep 2
            if check_docker_running; then
                log_success "Docker service started"
                return 0
            fi
        fi
    fi

    log_error "Failed to start Docker service"
    log_info "Try: sudo systemctl start docker"
    return 1
}

start_docker_wsl() {
    log_step "Starting Docker in WSL..."

    # Check if using Docker Desktop integration
    if [ -S "/var/run/docker.sock" ]; then
        # Docker Desktop WSL integration
        if ! check_docker_running; then
            log_warn "Docker Desktop may not be running on Windows host"
            log_info "Please start Docker Desktop on Windows"

            # Try to start via PowerShell
            if command_exists powershell.exe; then
                powershell.exe -Command "Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'" 2>/dev/null || true

                local max_attempts=30
                local attempt=0
                echo -n "  Waiting for Docker Desktop"
                while [ $attempt -lt $max_attempts ]; do
                    if check_docker_running; then
                        echo ""
                        log_success "Docker Desktop is running"
                        return 0
                    fi
                    echo -n "."
                    sleep 2
                    attempt=$((attempt + 1))
                done
                echo ""
            fi
        else
            log_success "Docker Desktop WSL integration is active"
            return 0
        fi
    fi

    # Fallback to native Docker in WSL
    start_docker_linux
}

install_docker_instructions() {
    log_error "Docker is not installed"
    echo ""
    case $OS in
        macos)
            log_info "Install Docker Desktop:"
            echo "  brew install --cask docker"
            echo "  # Or download from: https://www.docker.com/products/docker-desktop"
            ;;
        linux)
            log_info "Install Docker:"
            echo "  # Ubuntu/Debian:"
            echo "  curl -fsSL https://get.docker.com | sh"
            echo "  sudo usermod -aG docker \$USER"
            echo ""
            echo "  # Fedora:"
            echo "  sudo dnf install docker-ce docker-ce-cli containerd.io"
            ;;
        wsl)
            log_info "Install Docker Desktop for Windows with WSL2 backend:"
            echo "  https://www.docker.com/products/docker-desktop"
            echo "  Enable WSL2 integration in Docker Desktop settings"
            ;;
    esac
}

# =============================================================================
# Podman Functions
# =============================================================================

check_podman_installed() {
    command_exists podman
}

check_podman_running() {
    # On macOS, Podman needs a machine running
    if [ "$OS" = "macos" ]; then
        podman machine info >/dev/null 2>&1
    else
        # On Linux, Podman is daemonless but we check socket
        podman info >/dev/null 2>&1
    fi
}

start_podman_macos() {
    log_step "Starting Podman machine..."

    # Check if a machine exists
    if ! podman machine list 2>/dev/null | grep -q "podman-machine-default"; then
        log_info "Creating Podman machine..."
        podman machine init --cpus 4 --memory 4096 --disk-size 60
    fi

    # Check if machine is running
    if podman machine list 2>/dev/null | grep -q "Currently running"; then
        log_success "Podman machine is already running"
        return 0
    fi

    # Start the machine
    podman machine start

    # Wait for it to be ready
    local max_attempts=15
    local attempt=0
    echo -n "  Waiting for Podman machine"
    while [ $attempt -lt $max_attempts ]; do
        if check_podman_running; then
            echo ""
            log_success "Podman machine is running"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    log_error "Podman machine failed to start"
    return 1
}

start_podman_linux() {
    # Podman on Linux is daemonless, but we need to ensure socket is available
    log_step "Configuring Podman..."

    # Enable and start podman socket for rootless
    if command_exists systemctl; then
        systemctl --user enable --now podman.socket 2>/dev/null || true
    fi

    if check_podman_running; then
        log_success "Podman is ready"
        return 0
    else
        log_error "Podman is not responding"
        return 1
    fi
}

install_podman_instructions() {
    log_warn "Podman is not installed"
    echo ""
    case $OS in
        macos)
            log_info "Install Podman:"
            echo "  brew install podman"
            echo "  podman machine init"
            echo "  podman machine start"
            ;;
        linux)
            log_info "Install Podman:"
            echo "  # Ubuntu/Debian:"
            echo "  sudo apt install podman"
            echo ""
            echo "  # Fedora:"
            echo "  sudo dnf install podman"
            ;;
    esac
}

# =============================================================================
# VS Code / Cursor Configuration
# =============================================================================

configure_vscode_for_podman() {
    log_step "Configuring VS Code/Cursor for Podman..."

    local settings_updated=false

    # Find VS Code settings locations
    local vscode_dirs=(
        "$HOME/.config/Code/User"
        "$HOME/Library/Application Support/Code/User"
        "$HOME/.config/Cursor/User"
        "$HOME/Library/Application Support/Cursor/User"
    )

    for dir in "${vscode_dirs[@]}"; do
        if [ -d "$dir" ]; then
            local settings_file="$dir/settings.json"

            # Create settings.json if it doesn't exist
            if [ ! -f "$settings_file" ]; then
                echo '{}' > "$settings_file"
            fi

            # Check if podman is already configured
            if grep -q '"dev.containers.dockerPath"' "$settings_file" 2>/dev/null; then
                if grep -q '"dev.containers.dockerPath".*"podman"' "$settings_file"; then
                    continue  # Already configured
                fi
            fi

            # Use Python to update JSON (more reliable than sed for JSON)
            if command_exists python3; then
                python3 << EOF
import json
import os

settings_file = "$settings_file"
try:
    with open(settings_file, 'r') as f:
        settings = json.load(f)
except:
    settings = {}

settings['dev.containers.dockerPath'] = 'podman'
settings['dev.containers.dockerComposePath'] = 'podman-compose'

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)
EOF
                settings_updated=true
                log_info "Updated: $settings_file"
            fi
        fi
    done

    if [ "$settings_updated" = true ]; then
        log_success "VS Code/Cursor configured to use Podman"
    else
        log_info "No VS Code/Cursor settings found or already configured"
    fi
}

configure_podman_docker_socket() {
    log_step "Setting up Docker socket compatibility..."

    case $OS in
        macos)
            # On macOS with Podman, create a symlink for Docker socket compatibility
            local podman_socket="$HOME/.local/share/containers/podman/machine/podman.sock"
            if [ -S "$podman_socket" ]; then
                log_success "Podman socket available at: $podman_socket"
                export DOCKER_HOST="unix://$podman_socket"
                log_info "Set DOCKER_HOST=$DOCKER_HOST"
            fi
            ;;
        linux)
            # Enable podman socket
            if command_exists systemctl; then
                systemctl --user enable --now podman.socket 2>/dev/null || true
                local socket_path="/run/user/$(id -u)/podman/podman.sock"
                if [ -S "$socket_path" ]; then
                    export DOCKER_HOST="unix://$socket_path"
                    log_success "Podman socket: $socket_path"
                fi
            fi
            ;;
    esac
}

# =============================================================================
# Prerequisite Checks
# =============================================================================

ensure_config_files_exist() {
    log_step "Ensuring configuration files exist..."

    # Create .databrickscfg if it doesn't exist (for bind mount)
    if [ ! -f "$HOME/.databrickscfg" ]; then
        touch "$HOME/.databrickscfg"
        log_info "Created empty ~/.databrickscfg"
    fi

    # Create .gitconfig if it doesn't exist
    if [ ! -f "$HOME/.gitconfig" ]; then
        touch "$HOME/.gitconfig"
        log_info "Created empty ~/.gitconfig"
    fi

    log_success "Configuration files ready"
}

# =============================================================================
# Main Logic
# =============================================================================

main() {
    echo ""
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  Dev Container Runtime Initializer${NC}"
    echo -e "${BOLD}${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo ""
    log_info "Detected OS: $OS"
    echo ""

    local runtime=""
    local runtime_ready=false

    # Step 1: Detect available container runtime
    log_step "Detecting container runtime..."

    if check_docker_installed; then
        log_info "Docker is installed"
        runtime="docker"
    fi

    if check_podman_installed; then
        log_info "Podman is installed"
        # Prefer Podman if both are installed (it's lighter weight)
        if [ -z "$runtime" ]; then
            runtime="podman"
        else
            # If both installed, check which one is running
            if check_podman_running && ! check_docker_running; then
                runtime="podman"
            fi
        fi
    fi

    if [ -z "$runtime" ]; then
        echo ""
        log_error "No container runtime found!"
        echo ""
        install_docker_instructions
        echo ""
        echo "  ${BOLD}OR${NC}"
        echo ""
        install_podman_instructions
        echo ""
        exit 1
    fi

    echo ""
    log_info "Using container runtime: ${BOLD}$runtime${NC}"
    echo ""

    # Step 2: Ensure runtime is running
    if [ "$runtime" = "docker" ]; then
        if check_docker_running; then
            log_success "Docker is already running"
            runtime_ready=true
        else
            case $OS in
                macos) start_docker_macos && runtime_ready=true ;;
                linux) start_docker_linux && runtime_ready=true ;;
                wsl)   start_docker_wsl && runtime_ready=true ;;
            esac
        fi
    elif [ "$runtime" = "podman" ]; then
        if check_podman_running; then
            log_success "Podman is already running"
            runtime_ready=true
        else
            case $OS in
                macos) start_podman_macos && runtime_ready=true ;;
                linux) start_podman_linux && runtime_ready=true ;;
            esac
        fi

        # Configure Podman for VS Code/Cursor
        if [ "$runtime_ready" = true ]; then
            echo ""
            configure_vscode_for_podman
            configure_podman_docker_socket
        fi
    fi

    if [ "$runtime_ready" != true ]; then
        echo ""
        log_error "Failed to start container runtime"
        exit 1
    fi

    # Step 3: Ensure config files exist for bind mounts
    echo ""
    ensure_config_files_exist

    # Final status
    echo ""
    echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Container runtime is ready!${NC}"
    echo -e "${GREEN}  Runtime: $runtime${NC}"
    echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Run main
main "$@"
