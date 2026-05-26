FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install prefect so it's available as a dependency
RUN uv pip install --system prefect

# Simulate the pre-built image pattern: install the project at build time
WORKDIR /opt/prefect/flow
COPY pyproject.toml flows.py ./
RUN uv pip install --system -e .

COPY check_uv_skip.py /tmp/check_uv_skip.py
