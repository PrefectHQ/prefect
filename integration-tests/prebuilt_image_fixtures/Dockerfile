FROM prefecthq/prefect:3-latest
WORKDIR /opt/prefect/flow

# Simulate the pre-built image pattern: install the project at build time
COPY pyproject.toml flows.py ./
RUN uv pip install --system -e .

# Patch the runner with the version under test
COPY _workspace_starter.py /tmp/_workspace_starter.py
RUN SITE=$(python -c "import prefect.runner; from pathlib import Path; print(Path(prefect.runner.__file__).parent)") && \
    cp /tmp/_workspace_starter.py "$SITE/_workspace_starter.py"

COPY check_uv_skip.py /tmp/check_uv_skip.py
