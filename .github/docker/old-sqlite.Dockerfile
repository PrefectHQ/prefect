# The version used to build the V1 UI distributable.
ARG NODE_VERSION=20.19.0
# The version used to build the V2 UI distributable (requires Node 22+).
ARG NODE_V2_VERSION=22.12.0

# Build the V1 UI distributable.
FROM node:${NODE_VERSION}-bullseye-slim AS ui-builder

WORKDIR /opt/ui

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./ui/package*.json ./
RUN npm ci --legacy-peer-deps

COPY ./ui .
RUN npm run build

# Build the V2 UI distributable.
FROM node:${NODE_V2_VERSION}-bullseye-slim AS ui-v2-builder

ARG VITE_AMPLITUDE_API_KEY=""
ENV VITE_AMPLITUDE_API_KEY=$VITE_AMPLITUDE_API_KEY

WORKDIR /opt/ui-v2

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./ui-v2/package*.json ./
RUN npm ci --legacy-peer-deps

COPY ./ui-v2 .
RUN npm run build

# Build the Python distributable
FROM python:3.10-slim AS python-builder

WORKDIR /opt/prefect

# Install git for version calculation
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the repository for version calculation
COPY . .

# Package both UI bundles into the Python distributable.
COPY --from=ui-builder /opt/ui/dist ./src/prefect/server/ui
COPY --from=ui-v2-builder /opt/ui-v2/dist ./src/prefect/server/ui-v2

# Copy uv from official image - pin to specific version for build caching
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv


# Create source distribution
RUN uv build --sdist --wheel --out-dir dist && \
    mv "dist/prefect-"*".tar.gz" "dist/prefect.tar.gz"

# Final image
FROM python:3.10-slim
COPY --from=python-builder /bin/uv /bin/uv

# Accept SQLite version as build argument
ARG SQLITE_VERSION="3310100"
ARG SQLITE_YEAR="2020"

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget

# Download and compile SQLite
RUN wget https://www.sqlite.org/${SQLITE_YEAR}/sqlite-autoconf-${SQLITE_VERSION}.tar.gz \
    && tar xvfz sqlite-autoconf-${SQLITE_VERSION}.tar.gz \
    && cd sqlite-autoconf-${SQLITE_VERSION} \
    && ./configure \
    && make \
    && make install \
    && cd .. \
    && rm -rf sqlite-autoconf-${SQLITE_VERSION}*

ENV UV_SYSTEM_PYTHON=1

# Set library path to use our compiled SQLite
ENV LD_LIBRARY_PATH=/usr/local/lib

WORKDIR /app

# Copy UV and built artifacts
COPY --from=python-builder /bin/uv /bin/uv
COPY --from=python-builder /opt/prefect/dist/prefect.tar.gz ./dist/
COPY pyproject.toml ./
COPY README.md ./

# Install requirements and Prefect
RUN uv export | uv pip install -r -
RUN uv pip install ./dist/prefect.tar.gz

