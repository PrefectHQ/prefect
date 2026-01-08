# The version of Python in the final image
ARG PYTHON_VERSION=3.10
# The base image to use for the final image; Prefect and its Python requirements will
# be installed in this image. The default is the official Python slim image.
# The following images are also available in this file:
#   prefect-conda: Derivative of continuum/miniconda3 with a 'prefect' environment. Used for the 'conda' flavor.
# Any image tag can be used, but it must have apt and pip.
ARG BASE_IMAGE=python:${PYTHON_VERSION}-slim
# The version used to build the Python distributable.
ARG BUILD_PYTHON_VERSION=3.10
# The version used to build the V1 UI distributable.
ARG NODE_VERSION=20.19.0
# The version used to build the V2 UI distributable (requires Node 22+).
ARG NODE_V2_VERSION=22.12.0
# SQLite version to install (format: X.YY.Z becomes XYYZZOO in filename)
ARG SQLITE_VERSION=3.50.4
ARG SQLITE_YEAR=2025
ARG SQLITE_FILE_VERSION=3500400
# Any extra Python requirements to install
ARG EXTRA_PIP_PACKAGES=""

# Build SQLite from source to address CVE-2025-6965
# This stage is cached separately to avoid recompiling on every build
FROM python:${PYTHON_VERSION}-slim AS sqlite-builder

ARG SQLITE_VERSION
ARG SQLITE_YEAR
ARG SQLITE_FILE_VERSION

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    build-essential \
    wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN wget -q https://sqlite.org/${SQLITE_YEAR}/sqlite-autoconf-${SQLITE_FILE_VERSION}.tar.gz && \
    tar xzf sqlite-autoconf-${SQLITE_FILE_VERSION}.tar.gz && \
    cd sqlite-autoconf-${SQLITE_FILE_VERSION} && \
    ./configure --prefix=/usr/local && \
    make -j$(nproc) && \
    make install && \
    cd .. && \
    rm -rf sqlite-autoconf-${SQLITE_FILE_VERSION} sqlite-autoconf-${SQLITE_FILE_VERSION}.tar.gz

# Build the V1 UI distributable.
FROM --platform=$BUILDPLATFORM node:${NODE_VERSION}-bullseye-slim AS ui-builder

WORKDIR /opt/ui

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    # Required for arm64 builds
    chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install dependencies separately so they cache
COPY ./ui/package*.json ./
RUN npm ci

# Build static UI files
COPY ./ui .
RUN npm run build

# Build the V2 UI distributable.
FROM --platform=$BUILDPLATFORM node:${NODE_V2_VERSION}-bullseye-slim AS ui-v2-builder

WORKDIR /opt/ui-v2

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    # Required for arm64 builds
    chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install dependencies separately so they cache
COPY ./ui-v2/package*.json ./
RUN npm ci

# Build static UI files
COPY ./ui-v2 .
RUN npm run build


# Build the Python distributable.
# Without this build step, versioningit cannot infer the version without git
FROM python:${BUILD_PYTHON_VERSION}-slim AS python-builder

WORKDIR /opt/prefect

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    gpg \
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' git)" ge '1:2.47.3' || \
    (echo "ERROR: git version must be >= 1:2.47.3" && exit 1)

# Install UV from official image - pin to specific version for build caching
COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /bin/uv

# Copy the repository in; requires full git history for versions to generate correctly
COPY . ./

# Package the V1 UI into the distributable.
COPY --from=ui-builder /opt/ui/dist ./src/prefect/server/ui

# Package the V2 UI into the distributable.
COPY --from=ui-v2-builder /opt/ui-v2/dist ./src/prefect/server/ui-v2

# Create a source distributable archive; ensuring existing dists are removed first
RUN rm -rf dist && uv build --sdist --out-dir dist
RUN mv "dist/prefect-"*".tar.gz" "dist/prefect.tar.gz"


# Setup a base final image from miniconda
FROM continuumio/miniconda3 AS prefect-conda

# Create a new conda environment with our required Python version
ARG PYTHON_VERSION
RUN conda create \
    python=${PYTHON_VERSION} \
    --name prefect

# Use the prefect environment by default
RUN echo "conda activate prefect" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]



# Build the final image with Prefect installed and our entrypoint configured
FROM ${BASE_IMAGE} AS final

# Redeclare ARGs needed in this stage
ARG PYTHON_VERSION
ARG SQLITE_VERSION
ARG SQLITE_YEAR
ARG SQLITE_FILE_VERSION

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_SYSTEM_PYTHON=1

# Ensure Python uses the upgraded SQLite library
ENV LD_LIBRARY_PATH=/usr/local/lib

LABEL maintainer="help@prefect.io" \
    io.prefect.python-version=${PYTHON_VERSION} \
    io.prefect.sqlite-version=${SQLITE_VERSION} \
    org.label-schema.schema-version="1.0" \
    org.label-schema.name="prefect" \
    org.label-schema.url="https://www.prefect.io/"

WORKDIR /opt/prefect

# Install system requirements
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    tini=0.19.* \
    build-essential \
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' git)" ge '1:2.47.3' || \
    (echo "ERROR: git version must be >= 1:2.47.3" && exit 1)

# Copy pre-compiled SQLite ${SQLITE_VERSION} from sqlite-builder stage
COPY --from=sqlite-builder /usr/local/lib/libsqlite3* /usr/local/lib/
COPY --from=sqlite-builder /usr/local/include/sqlite3*.h /usr/local/include/
COPY --from=sqlite-builder /usr/local/bin/sqlite3 /usr/local/bin/
COPY --from=sqlite-builder /usr/local/lib/pkgconfig/sqlite3.pc /usr/local/lib/pkgconfig/
RUN ldconfig

# Install UV from official image - pin to specific version for build caching
COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /bin/uv

# Install prefect from the sdist
COPY --from=python-builder /opt/prefect/dist ./dist

# Extras to include during installation
ARG PREFECT_EXTRAS=[redis,client,otel]
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
