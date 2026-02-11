# Dev Container for Databricks Fullstack Application
# Supports: VS Code, Cursor, PyCharm, and any devcontainer-compatible IDE

FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Avoid prompts during package installation
ARG DEBIAN_FRONTEND=noninteractive

# Tool versions
ARG NODE_VERSION=22
ARG PYTHON_VERSION=3.10
ARG PNPM_VERSION=10

# Better error handling for piped commands (e.g. curl | bash)
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install system dependencies, Node.js, and Python in a single layer
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential curl wget unzip jq \
        libpq-dev postgresql-client \
        software-properties-common \
    # Node.js via NodeSource
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    # Python via deadsnakes PPA
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
        python${PYTHON_VERSION}-dev \
    && update-alternatives --install /usr/bin/python python /usr/bin/python${PYTHON_VERSION} 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1 \
    # pnpm
    && npm install -g pnpm@${PNPM_VERSION} \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install Databricks CLI (system-wide)
RUN curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh

# Switch to vscode user for remaining setup
USER vscode

# Install uv (fast Python package manager) and configure pnpm store
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && pnpm config set store-dir /home/vscode/.local/share/pnpm
ENV PATH="/home/vscode/.local/bin:$PATH"

# Set up bash history persistence and helpful aliases
RUN mkdir -p /home/vscode/.bash_history_dir \
    && { \
        echo 'export HISTFILE=/home/vscode/.bash_history_dir/.bash_history'; \
        echo 'export HISTSIZE=10000'; \
        echo 'export HISTFILESIZE=20000'; \
        echo 'alias dev="pnpm dev"'; \
        echo 'alias build="pnpm build"'; \
        echo 'alias lint="pnpm lint"'; \
        echo 'alias db="databricks"'; \
    } >> /home/vscode/.bashrc

# Working directory
WORKDIR /workspace
