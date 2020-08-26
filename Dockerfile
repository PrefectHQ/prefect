ARG PYTHON_VERSION=${PYTHON_VERSION}
FROM python:${PYTHON_VERSION}-slim

# Build Arguments
ARG PREFECT_VERSION
ARG EXTRAS=kubernetes
ARG GIT_SHA
ARG BUILD_DATE

# Set system locale
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

# Image Labels
LABEL maintainer="help@prefect.io"
LABEL io.prefect.python-version=${PYTHON_VERSION}
LABEL org.label-schema.schema-version = "1.0"
LABEL org.label-schema.name="prefect"
LABEL org.label-schema.url="https://www.prefect.io/"
LABEL org.label-schema.version=${PREFECT_VERSION}
LABEL org.label-schema.vcs-ref=${GIT_SHA}
LABEL org.label-schema.build-date=${BUILD_DATE}

RUN apt update && \
    apt install -y gcc git && \
    mkdir /root/.prefect/ && \
    pip install --no-cache-dir git+https://github.com/PrefectHQ/prefect.git@${PREFECT_VERSION}#egg=prefect[${EXTRAS}] && \
    apt remove -y git && \
    apt clean && apt autoremove -y && \
    rm -rf /var/lib/apt/lists/*
