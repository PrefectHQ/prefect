FROM python:3.9-slim

# Install build dependencies and git
RUN apt-get update && apt-get install -y \
    build-essential \
    wget

# Download and compile SQLite 3.24.0
RUN wget https://www.sqlite.org/2018/sqlite-autoconf-3240000.tar.gz \
    && tar xvfz sqlite-autoconf-3240000.tar.gz \
    && cd sqlite-autoconf-3240000 \
    && ./configure \
    && make \
    && make install \
    && ldconfig \
    && cd .. \
    && rm -rf sqlite-autoconf-3240000*

# Install uv for faster pip operations
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_SYSTEM_PYTHON=1

# Set library path to use our compiled SQLite
ENV LD_LIBRARY_PATH=/usr/local/lib

WORKDIR /app

# Copy all requirements files first
COPY README.md ./
COPY requirements*.txt ./
COPY setup.py setup.cfg versioneer.py ./
COPY src/prefect/__init__.py ./src/prefect/
COPY src/prefect/_version.py ./src/prefect/

# Install requirements and Prefect core
RUN uv pip install -r requirements.txt
RUN uv pip install -e .

# Now copy the rest of the source code
COPY src/prefect ./src/prefect

# Verify SQLite version
RUN python -c "import sqlite3; print(f'SQLite Version: {sqlite3.sqlite_version}')"

# Update the command to handle migrations before starting the server
CMD prefect server database downgrade -y -r base && \
    prefect server database upgrade -y
