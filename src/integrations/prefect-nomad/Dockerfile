ARG PREFECT_VERSION=3-latest
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder
WORKDIR /build
RUN pip install build
COPY src/integrations/prefect-nomad .
RUN python -m build --wheel

FROM prefecthq/prefect:${PREFECT_VERSION}-python${PYTHON_VERSION}

ARG PREFECT_VERSION
ARG PREFECT_NOMAD_VERSION
ARG PYTHON_VERSION
ENV PREFECT_VERSION=${PREFECT_VERSION} \
    PREFECT_NOMAD_VERSION=${PREFECT_NOMAD_VERSION} \
    PYTHON_VERSION=${PYTHON_VERSION}

LABEL maintainer="help@prefect.io" \
    io.prefect.python-version=${PYTHON_VERSION} \
    io.prefect.prefect-version=${PREFECT_VERSION} \
    io.prefect.prefect-nomad-version=${PREFECT_NOMAD_VERSION} \
    org.label-schema.schema-version="1.0" \
    org.label-schema.name="prefect-nomad" \
    org.label-schema.url="https://www.prefect.io/"

COPY --from=builder /build/dist/ /tmp/wheels/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install prefect==${PREFECT_VERSION} /tmp/wheels/*.whl

RUN prefect version && python -c "import prefect_nomad; print('prefect-nomad installed successfully')"
