ARG PYTHON_VERSION=3.9

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

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_SYSTEM_PYTHON=1

LABEL maintainer="help@prefect.io" \
    io.prefect.python-version=${PYTHON_VERSION} \
    org.label-schema.schema-version="1.0" \
    org.label-schema.name="prefect" \
    org.label-schema.url="https://www.prefect.io/"

WORKDIR /opt/prefect

# Install system requirements
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

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
