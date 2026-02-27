ARG PYTHON_VERSION=3.10
# SQLite version — must match the tag published to prefecthq/prefect-sqlite on DockerHub
# See Dockerfile.sqlite-builder and .github/workflows/sqlite-builder.yaml
ARG SQLITE_VERSION=3.50.4
# SQLite source selector: 'prebuilt' (default) pulls from DockerHub; 'from-source' builds
# inline. Pass --build-arg SQLITE_SOURCE=from-source for fork PRs where the pre-built tag
# for a new SQLITE_VERSION doesn't exist yet.
ARG SQLITE_SOURCE=prebuilt
# Companion args used only when SQLITE_SOURCE=from-source
ARG SQLITE_YEAR=2025
ARG SQLITE_FILE_VERSION=3500400

# Pre-compiled SQLite from DockerHub — used when SQLITE_SOURCE=prebuilt (default).
FROM prefecthq/prefect-sqlite:${SQLITE_VERSION} AS sqlite-prebuilt

# Build SQLite from source — used when SQLITE_SOURCE=from-source (e.g. fork PRs).
FROM debian:bookworm-slim AS sqlite-from-source
ARG SQLITE_YEAR
ARG SQLITE_FILE_VERSION
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    build-essential \
    ca-certificates \
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

# Select the SQLite stage based on SQLITE_SOURCE.
FROM sqlite-${SQLITE_SOURCE} AS sqlite-builder

# Build the Python distributable.
# Without this build step, versioningit cannot infer the version without git
FROM python:${PYTHON_VERSION}-slim AS python-builder

WORKDIR /opt/prefect

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    gpg \
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install UV from official image - pin to specific version for build caching
COPY --from=ghcr.io/astral-sh/uv:0.5.30 /uv /bin/uv

# Copy the repository in; requires full git history for versions to generate correctly
COPY . ./

# Create a source distributable archive; ensuring existing dists are removed first
ENV TMPDIR=/tmp/prefect-client-build
RUN mkdir -p $TMPDIR && \
    sh client/build_client.sh && \
    cd $TMPDIR && \
    uv build --sdist --out-dir /opt/prefect/dist
RUN mv "dist/prefect_client-"*".tar.gz" "dist/prefect_client.tar.gz"


FROM python:${PYTHON_VERSION}-slim

# Redeclare ARGs needed in this stage
ARG PYTHON_VERSION
ARG SQLITE_VERSION

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
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy pre-compiled SQLite ${SQLITE_VERSION} from sqlite-builder stage
COPY --from=sqlite-builder /usr/local/lib/libsqlite3* /usr/local/lib/
COPY --from=sqlite-builder /usr/local/include/sqlite3*.h /usr/local/include/
COPY --from=sqlite-builder /usr/local/bin/sqlite3 /usr/local/bin/
COPY --from=sqlite-builder /usr/local/lib/pkgconfig/sqlite3.pc /usr/local/lib/pkgconfig/
RUN ldconfig

# Install UV from official image - pin to specific version for build caching
COPY --from=ghcr.io/astral-sh/uv:0.5.30 /uv /bin/uv

# Install prefect from the sdist
COPY --from=python-builder /opt/prefect/dist ./dist
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install "./dist/prefect_client.tar.gz" && \
    rm -rf dist/

# Remove setuptools
RUN uv pip uninstall setuptools

# Smoke test
RUN python -c "import prefect; print(prefect.__version__)"

# Setup entrypoint
COPY ./client/prefect-cli-stub /usr/local/bin/prefect
COPY ./scripts/entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
