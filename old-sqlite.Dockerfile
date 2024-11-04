FROM python:3.9-slim

# Accept SQLite version as build argument
ARG SQLITE_VERSION="3310100"
ARG SQLITE_YEAR="2020"

# Install build dependencies and git
RUN apt-get update && apt-get install -y \
    build-essential \
    wget

# Download and compile SQLite
RUN wget https://www.sqlite.org/${SQLITE_YEAR}/sqlite-autoconf-${SQLITE_VERSION}.tar.gz \
    && tar xvfz sqlite-autoconf-${SQLITE_VERSION}.tar.gz \
    && cd sqlite-autoconf-${SQLITE_VERSION} \
    && ./configure \
    && make \
    && make install \
    && ldconfig \
    && cd .. \
    && rm -rf sqlite-autoconf-${SQLITE_VERSION}*

# Install uv for faster pip operations
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_SYSTEM_PYTHON=1

# Set library path to use our compiled SQLite
ENV LD_LIBRARY_PATH=/usr/local/lib

WORKDIR /app

# Copy the entire source directory first
COPY src ./src
COPY README.md ./
COPY requirements*.txt ./
COPY setup.py setup.cfg versioneer.py ./

# Install requirements and Prefect core
RUN uv pip install -r requirements.txt
RUN uv pip install .

# Verify SQLite version
RUN python -c "import sqlite3; print(f'SQLite Version: {sqlite3.sqlite_version}')"

# Start Prefect server
ENTRYPOINT ["prefect", "server", "start", "--host", "0.0.0.0"]
