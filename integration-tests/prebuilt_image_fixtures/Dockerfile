FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install released prefect, then overlay the module under test
RUN uv pip install --system prefect
COPY _workspace_starter.py _workspace_starter.py
RUN SITE=$(python -c "import prefect.runner; from pathlib import Path; print(Path(prefect.runner.__file__).parent)") && \
    cp _workspace_starter.py "$SITE/_workspace_starter.py" && \
    rm _workspace_starter.py

# Simulate the pre-built image pattern: install the project at build time
WORKDIR /opt/prefect/flow
COPY pyproject.toml flows.py ./
RUN uv pip install --system -e .

COPY check_uv_skip.py /tmp/check_uv_skip.py
