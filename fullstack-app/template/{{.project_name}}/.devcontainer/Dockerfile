# Dev Container for Databricks Fullstack Application
# Supports: VS Code, Cursor, PyCharm, and any devcontainer-compatible IDE

FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Avoid prompts during package installation
ARG DEBIAN_FRONTEND=noninteractive

# Tool versions
ARG NODE_VERSION=22
ARG PYTHON_VERSION=3.10
ARG PNPM_VERSION=10

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    unzip \
    jq \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm globally
RUN npm install -g pnpm@${PNPM_VERSION}

# Install Python via deadsnakes PPA
RUN apt-get update \
    && apt-get install -y software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
        python${PYTHON_VERSION}-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python${PYTHON_VERSION} 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

# Install uv (fast Python package manager from Astral)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/home/vscode/.local/bin:$PATH"

# Install Databricks CLI
RUN curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh

# Switch to vscode user for remaining setup
USER vscode

# Install uv for vscode user
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Configure pnpm
RUN pnpm config set store-dir /home/vscode/.local/share/pnpm

# Set up bash history persistence
RUN mkdir -p /home/vscode/.bash_history_dir \
    && echo 'export HISTFILE=/home/vscode/.bash_history_dir/.bash_history' >> /home/vscode/.bashrc \
    && echo 'export HISTSIZE=10000' >> /home/vscode/.bashrc \
    && echo 'export HISTFILESIZE=20000' >> /home/vscode/.bashrc

# Add helpful aliases
RUN echo 'alias dev="pnpm dev"' >> /home/vscode/.bashrc \
    && echo 'alias build="pnpm build"' >> /home/vscode/.bashrc \
    && echo 'alias lint="pnpm lint"' >> /home/vscode/.bashrc \
    && echo 'alias db="databricks"' >> /home/vscode/.bashrc

# Working directory
WORKDIR /workspace
