ARG PREFECT_VERSION=3-latest
ARG PYTHON_VERSION=3.12
FROM prefecthq/prefect:${PREFECT_VERSION}-python${PYTHON_VERSION}

ARG PREFECT_VERSION
ARG PREFECT_AWS_VERSION
ARG PYTHON_VERSION
ENV PREFECT_VERSION=${PREFECT_VERSION} \
    PREFECT_AWS_VERSION=${PREFECT_AWS_VERSION} \
    PYTHON_VERSION=${PYTHON_VERSION}

LABEL maintainer="help@prefect.io" \
    io.prefect.python-version=${PYTHON_VERSION} \
    io.prefect.prefect-version=${PREFECT_VERSION} \
    io.prefect.prefect-aws-version=${PREFECT_AWS_VERSION} \
    org.label-schema.schema-version="1.0" \
    org.label-schema.name="prefect-aws" \
    org.label-schema.url="https://www.prefect.io/"

# Install pinned versions of both prefect and prefect-aws to prevent version conflicts
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install prefect==${PREFECT_VERSION} prefect-aws==${PREFECT_AWS_VERSION}

# Smoke test to verify installation and versions
RUN prefect version && python -c "import prefect_aws; print('prefect-aws installed successfully')"
