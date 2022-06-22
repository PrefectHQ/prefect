# The version of Python in the final image
ARG PYTHON_VERSION=3.8
# The base image to use for the final image; Prefect and its Python requirements will
# be installed in this image. The default is the official Python slim image.
# The following images are also available in this file:
#   prefect-conda: Derivative of continuum/miniconda3 with a 'prefect' environment. Used for the 'conda' flavor.
# Any image tag can be used, but it must have apt and pip.
ARG BASE_IMAGE=python:${PYTHON_VERSION}-slim
# The version used to build the Python distributable.
ARG BUILD_PYTHON_VERSION=3.8
# THe version used to build the UI distributable.
ARG NODE_VERSION=16.15


# Build the UI distributable.
FROM node:${NODE_VERSION}-bullseye-slim as ui-builder

WORKDIR /opt/orion-ui

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        # Required for arm64 builds
        chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install a newer npm to avoid esbuild errors
RUN npm install -g npm@8

# Install dependencies separately so they cache
COPY ./orion-ui/package*.json .
RUN npm ci install

# Build static UI files
COPY ./orion-ui .
ENV ORION_UI_SERVE_BASE="/"
RUN npm run build


# Build the Python distributable.
# Without this build step, versioneer cannot infer the version without git
# see https://github.com/python-versioneer/python-versioneer/issues/215
FROM python:${BUILD_PYTHON_VERSION}-slim AS python-builder

WORKDIR /opt/prefect

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        gpg \
        git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy the repository in; requires full git history for versions to generate correctly
COPY . ./

# Package the UI into the distributable.
COPY --from=ui-builder /opt/orion-ui/dist ./src/prefect/orion/ui

# Create a source distributable archive; ensuring existing dists are removed first
RUN rm -rf dist && python setup.py sdist
RUN mv "dist/$(python setup.py --fullname).tar.gz" "dist/prefect.tar.gz"


# Setup a base final image from miniconda
FROM continuumio/miniconda3 as prefect-conda

# Create a new conda environment with our required Python version
ARG PYTHON_VERSION
RUN conda create \
    python=${PYTHON_VERSION} \
    --name prefect

# Use the prefect environment by default
RUN echo "conda activate prefect" >> ~/.bashrc
SHELL ["/bin/bash", "--login", "-c"]



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

# Install tini for the entrypoint
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        tini=0.19.* \
        build-essential \ 
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Pin the pip version
RUN python -m pip install --no-cache-dir pip==21.3.1

# Install the base requirements separately so they cache
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install prefect from the sdist
COPY --from=python-builder /opt/prefect/dist ./dist

# Extras to include during `pip install`. Must be wrapped in brackets, e.g. "[dev]"
ARG PREFECT_EXTRAS=${PREFECT_EXTRAS:-""}
RUN pip install --no-cache-dir "./dist/prefect.tar.gz${PREFECT_EXTRAS}"

# Setup entrypoint
COPY scripts/entrypoint.sh ./entrypoint.sh
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/prefect/entrypoint.sh"]
