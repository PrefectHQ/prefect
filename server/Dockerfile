# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license

# syntax=docker/dockerfile:1.0.0-experimental

FROM python:3.7
ARG VERSION
ENV SERVER_VERSION=${VERSION}

RUN apt-get -qq -y update && apt-get -qq -y install --no-install-recommends --no-install-suggests --allow-unauthenticated \
    curl \
    git \
    sudo && \
    rm -rf /var/lib/apt/lists/*

ARG PREFECT_VERSION=master
ENV PREFECT_VERSION=$PREFECT_VERSION

RUN pip install git+https://github.com/PrefectHQ/prefect.git@${PREFECT_VERSION}#egg=prefect

COPY . /prefect-server

RUN \
    cd /prefect-server \
    && pip install -e .

WORKDIR /prefect-server
CMD python
