FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install prefect from a pre-built wheel (current branch)
COPY prefect_wheel /tmp/prefect_wheel
RUN uv pip install --system /tmp/prefect_wheel/*.whl && rm -rf /tmp/prefect_wheel

# Simulate the pre-built image pattern: install the project at build time
WORKDIR /opt/prefect/flow
COPY pyproject.toml flows.py ./
RUN uv pip install --system -e .
