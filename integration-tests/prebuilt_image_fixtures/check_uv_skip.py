"""Runs inside the pre-built container to verify detection logic.

Checks three things:
1. The project is discoverable via importlib.metadata (our detection signal).
2. Prefect is already importable at the expected version without uv run.
3. Running uv run would create a redundant .venv (proving skipping matters).
"""

import importlib.metadata
import json
import subprocess
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

from pathlib import Path

workdir = Path("/opt/prefect/flow")
pyproject = workdir / "pyproject.toml"
data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
project_name = data["project"]["name"]

# 1. Check if the project is detectable via importlib.metadata
try:
    importlib.metadata.distribution(project_name)
    project_installed = True
except importlib.metadata.PackageNotFoundError:
    project_installed = False

# 2. Record the pre-installed prefect version (available without uv run)
prefect_version = importlib.metadata.distribution("prefect").version

# 3. Check whether uv run would create a .venv (proving it reinstalls)
venv_before = (workdir / ".venv").exists()
subprocess.run(
    ["uv", "run", "--project", str(workdir), "python", "-c", "pass"],
    capture_output=True,
)
venv_after = (workdir / ".venv").exists()

print(
    json.dumps(
        {
            "project_name": project_name,
            "project_installed": project_installed,
            "prefect_version": prefect_version,
            "venv_existed_before": venv_before,
            "venv_created_by_uv_run": not venv_before and venv_after,
        }
    )
)
