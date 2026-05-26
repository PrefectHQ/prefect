"""Runs inside the pre-built container to verify detection logic."""

import json
import os
from pathlib import Path

from prefect.runner._workspace_resolver import PreparedWorkspace
from prefect.runner._workspace_starter import _project_is_installed, _uv_run_command

workdir = Path("/opt/prefect/flow")
pyproject = workdir / "pyproject.toml"

installed = _project_is_installed(pyproject)

workspace = PreparedWorkspace(
    workspace_root=workdir,
    working_directory=workdir,
    project_root=workdir,
    runtime_entrypoint="flows.py:hello",
    environment=dict(os.environ),
    sys_path=[],
)

command = _uv_run_command(workspace)

print(json.dumps({"project_is_installed": installed, "uv_run_command": command}))
