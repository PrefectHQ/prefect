# The version of Python in the final image
ARG PYTHON_VERSION=3.11
# The base image to use for the final image; Prefect and its Python requirements will
# be installed in this image. The default is the official Python slim image.
# The following images are also available in this file:
#   prefect-conda: Derivative of continuum/miniconda3 with a 'prefect' environment. Used for the 'conda' flavor.
# Any image tag can be used, but it must have apt and pip.
ARG BASE_IMAGE=python:${PYTHON_VERSION}-alpine3.18
# The version used to build the Python distributable.
ARG BUILD_PYTHON_VERSION=3.11
# THe version used to build the UI distributable.
ARG NODE_VERSION=18
# Any extra Python requirements to install
ARG EXTRA_PIP_PACKAGES=""

# Build the UI distributable.
FROM node:${NODE_VERSION}-alpine3.18 as ui-builder

WORKDIR /opt/ui

RUN apk update && \
    apk --no-cache add \
    # Required for arm64 builds
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Install a newer npm to avoid esbuild errors
RUN npm install -g npm@8

# Install dependencies separately so they cache
COPY ./ui/package*.json ./
RUN npm ci install

# Build static UI files
COPY ./ui .
ENV PREFECT_UI_SERVE_BASE="/"
RUN npm run build


# Build the Python distributable.
# Without this build step, versioneer cannot infer the version without git
# see https://github.com/python-versioneer/python-versioneer/issues/215
FROM python:${BUILD_PYTHON_VERSION}-alpine3.18 AS python-builder

WORKDIR /opt/prefect

RUN apk update && \
    apk add \
    gpg \
    git~=2 \
    && rm -rf /var/lib/apt/lists/*

# Copy the repository in; requires full git history for versions to generate correctly
COPY . ./

# Package the UI into the distributable.
COPY --from=ui-builder /opt/ui/dist ./src/prefect/server/ui

# Create a source distributable archive; ensuring existing dists are removed first
RUN rm -rf dist && python setup.py sdist
RUN mv "dist/$(python setup.py --fullname).tar.gz" "dist/prefect.tar.gz"

# Build the final image with Prefect installed and our entrypoint configured
FROM ${BASE_IMAGE} as final

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

LABEL maintainer="help@prefect.io"
LABEL io.prefect.python-version=${PYTHON_VERSION}
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="prefect"
LABEL org.label-schema.url="https://www.prefect.io/"

WORKDIR /opt/prefect

# Install requirements
# - tini: Used in the entrypoint
# - build-essential: Required for Python dependencies without wheels
# - git: Required for retrieving workflows from git sources
RUN apk update && \
    apk add \
    libffi-dev \
    alpine-sdk \
    tini~=0.19 \
    git~=2 \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Pin the pip version
RUN python -m pip install --no-cache-dir pip==22.3.1

# Install the base requirements separately so they cache
COPY requirements-client.txt requirements.txt ./
RUN pip install --upgrade --upgrade-strategy eager --no-cache-dir -r requirements.txt

# Install prefect from the sdist
COPY --from=python-builder /opt/prefect/dist ./dist

# Extras to include during `pip install`. Must be wrapped in brackets, e.g. "[dev]"
ARG PREFECT_EXTRAS=${PREFECT_EXTRAS:-""}
RUN pip install --no-cache-dir "./dist/prefect.tar.gz${PREFECT_EXTRAS}"

ARG EXTRA_PIP_PACKAGES=${EXTRA_PIP_PACKAGES:-""}
RUN [ -z "${EXTRA_PIP_PACKAGES}" ] || pip install --no-cache-dir "${EXTRA_PIP_PACKAGES}"

# Smoke test
ENV TZ UTC
RUN prefect version

RUN which tini

# Setup entrypoint
COPY scripts/entrypoint.sh ./entrypoint.sh
ENTRYPOINT ["/sbin/tini", "-g", "--", "/opt/prefect/entrypoint.sh"]
