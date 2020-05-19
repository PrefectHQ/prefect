# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

# syntax=docker/dockerfile:1.0.0-experimental

FROM python:3.7
ARG VERSION
ARG PREFECT_VERSION=master
ENV PREFECT_VERSION=$PREFECT_VERSION
ENV SERVER_VERSION=${VERSION}

COPY . /prefect-server

RUN apt-get -qq -y update && \
    apt-get -qq -y install \
        --no-install-recommends \
        --no-install-suggests \
        --allow-unauthenticated \
            curl \
            git \
            sudo && \
    pip install \
        git+https://github.com/PrefectHQ/prefect.git@${PREFECT_VERSION}#egg=prefect && \
    cd /prefect-server && \
    pip install -e . && \
    sudo apt-get remove -y --auto-remove --purge git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /prefect-server
CMD python
