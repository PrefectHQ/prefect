# The version of Python in the final image
ARG PYTHON_VERSION=3.9
# The base image to use for the final image
ARG BASE_IMAGE=python:${PYTHON_VERSION}-slim
# The version used to build the Python distributable.
ARG BUILD_PYTHON_VERSION=3.9
# The version used to build the UI distributable.
ARG NODE_VERSION=18.18.0
# Any extra Python requirements to install
ARG EXTRA_PIP_PACKAGES=""

# ============= STAGE 1: UI Dependencies (rarely changes) =============
FROM --platform=$BUILDPLATFORM node:${NODE_VERSION}-bullseye-slim AS ui-deps
WORKDIR /opt/ui
# Only copy package files first
COPY ./ui/package*.json ./
RUN npm ci

# ============= STAGE 2: UI Builder (only rebuilds when UI code changes) =============
FROM ui-deps AS ui-builder
WORKDIR /opt/ui
# Install chromium only when we need to build
RUN apt-get update && \
    apt-get install --no-install-recommends -y chromium && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
# Now copy the actual UI code
COPY ./ui .
RUN npm run build

# ============= STAGE 3: Python Builder Base (rarely changes) =============
FROM python:${BUILD_PYTHON_VERSION}-slim AS python-builder-base
WORKDIR /opt/prefect
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    gpg \
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Install UV early and cache it
COPY --from=ghcr.io/astral-sh/uv:0.5.30 /uv /bin/uv

# ============= STAGE 4: Python Source Builder =============
FROM python-builder-base AS python-builder
WORKDIR /opt/prefect
# Copy the repository in; requires full git history for versions to generate correctly
COPY . ./
# Package the UI into the distributable.
COPY --from=ui-builder /opt/ui/dist ./src/prefect/server/ui
# Debug: Check git status to see what's dirty
RUN git config --global --add safe.directory /opt/prefect && \
    echo "=== Git status ===" && \
    git status --porcelain | head -20 && \
    echo "=== Git diff ===" && \
    git diff --stat | head -20 && \
    echo "=== Checking if UI is tracked ===" && \
    git ls-files src/prefect/server/ui | head -5 || echo "UI files not tracked"
# Create a source distributable archive; ensuring existing dists are removed first
RUN rm -rf dist && uv build --sdist --out-dir dist
RUN mv "dist/prefect-"*".tar.gz" "dist/prefect.tar.gz"

# ============= STAGE 5: Conda Base (for conda flavor) =============
FROM continuumio/miniconda3 AS prefect-conda
ARG PYTHON_VERSION
RUN conda create python=${PYTHON_VERSION} --name prefect
RUN echo "conda activate prefect" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]

# ============= STAGE 6: Final Base (system packages) =============
FROM ${BASE_IMAGE} AS final-base
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
WORKDIR /opt/prefect
# Install system requirements
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    tini=0.19.* \
    build-essential \
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Install UV
COPY --from=ghcr.io/astral-sh/uv:0.5.30 /uv /bin/uv

# ============= STAGE 7: Final Image =============
FROM final-base AS final
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_SYSTEM_PYTHON=1
LABEL maintainer="help@prefect.io" \
    io.prefect.python-version=${PYTHON_VERSION} \
    org.label-schema.schema-version="1.0" \
    org.label-schema.name="prefect" \
    org.label-schema.url="https://www.prefect.io/"

# Install prefect from the sdist
COPY --from=python-builder /opt/prefect/dist ./dist
ARG PREFECT_EXTRAS=[redis,otel]
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install "./dist/prefect.tar.gz${PREFECT_EXTRAS:-""}" && \
    rm -rf dist/

# Remove setuptools
RUN uv pip uninstall setuptools

# Install any extra packages
ARG EXTRA_PIP_PACKAGES
RUN --mount=type=cache,target=/root/.cache/uv \
    [ -z "${EXTRA_PIP_PACKAGES:-""}" ] || uv pip install "${EXTRA_PIP_PACKAGES}"

# Smoke test
RUN prefect version

# Setup entrypoint
COPY scripts/entrypoint.sh ./entrypoint.sh
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/prefect/entrypoint.sh"]