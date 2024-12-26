FROM debian:12-slim

# Set working directory
WORKDIR /opt/prefect

# Define default Python version
ENV PYTHON_VERSION=3.12

# Define default Prefect version
ENV PREFECT_VERSION=latest

# Install system requirements
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    tini=0.19.* \
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5.12 /uv /uvx /bin/

# Set uv link mode to copy since cache and sync target are on separate filesystems
# https://docs.astral.sh/uv/guides/integration/docker/#caching
ENV UV_LINK_MODE=copy

# Set default uv cache directory
ENV UV_CACHE_DIR=/opt/uv-cache/

# Set default Python installation directory
ENV UV_PYTHON_INSTALL_DIR=/opt/python-installs

# Setup entrypoint
COPY entrypoint.sh ./entrypoint.sh
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/prefect/entrypoint.sh"]