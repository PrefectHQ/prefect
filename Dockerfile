ARG PYTHON_VERSION=${PYTHON_VERSION:-3.8}

# Build the distributable which requires `git` and generates a static version file.
# Without this build step, versioneer cannot infer the version without `git`
# see https://github.com/python-versioneer/python-versioneer/issues/215
FROM python:3.8-slim AS builder
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        git=1:2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/prefect

# Copy the repository in; requires deep history for versions to generate correctly
COPY . ./

# Create a source distributable archive; ensuring existing dists are removed first
RUN rm -rf dist && python setup.py sdist


# Install into the requested Python version image
FROM python:${PYTHON_VERSION}-slim

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

LABEL maintainer="help@prefect.io"
LABEL io.prefect.python-version=${PYTHON_VERSION}
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="prefect"
LABEL org.label-schema.url="https://www.prefect.io/"

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        tini=0.19.* \
        # The following are required for building the asyncpg wheel
        gcc=4:10.* \
        linux-libc-dev=5.10.* \
        libc6-dev=2.* \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Pin the pip version
RUN python -m pip install --no-cache-dir pip==21.3.1

# Copy the sdist and entrypoint
WORKDIR /opt/prefect
COPY --from=builder /opt/prefect/dist ./
COPY scripts/entrypoint.sh ./entrypoint.sh

# Install prefect
RUN pip install --no-cache-dir ./*.tar.gz

ENTRYPOINT ["tini", "-g", "--", "/opt/prefect/entrypoint.sh"]
